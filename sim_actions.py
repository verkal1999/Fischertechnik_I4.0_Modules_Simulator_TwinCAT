"""Aktionen entsprechend den Notebook-Zellen (Init, Start, Reset) und Sensor-Lesen."""

from __future__ import annotations

import time
import traceback
from typing import Any, Callable, Dict

from Simulation import SPS_Simulator, SkillOA_Simulator

import sim_config as cfg

LogCallback = Callable[[str], None]


def _noop(msg: str) -> None:
    pass

def _make_sps() -> SPS_Simulator:
    return SPS_Simulator()


def _make_skilloa(sps: SPS_Simulator) -> SkillOA_Simulator:
    return SkillOA_Simulator(cfg.OPC_CONFIG, sps=sps)


def _reset_vsg_error_code(sps: SPS_Simulator, log: LogCallback) -> None:
    try:
        sps.write_udint("VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorCode", 0)
        log("VSG_ErrorCode auf 0 gesetzt.")
    except Exception as exc:
        log(f"VSG_ErrorCode konnte nicht zurückgesetzt werden: {exc}")


def _wait_for_bool_signal(
    sps: SPS_Simulator,
    symbol_or_key: str,
    expected: bool,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = 0.1,
) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        if bool(sps.read_bool(symbol_or_key).value) == expected:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_interval_seconds)


# ---------------------------------------------------------------------------
# Zelle 1 — Init
# ---------------------------------------------------------------------------

def action_init(log: LogCallback = _noop) -> Dict[str, Any]:
    """
    Entspricht Notebook-Zelle 1:
    SPS vorbereiten, Pläne bauen, Initialwerte schreiben.
    """
    sps = _make_sps()
    skilloa = _make_skilloa(sps)

    log("Bereite SPS für Skill-Tests vor...")
    prepared = sps.prepare_plc_for_skill_tests()
    log(f"SPS vorbereitet: {list(prepared.keys())}")

    hrl_plan = skilloa.build_hrl_auslagern_start_plan(cfg.HRL_REQUEST)
    vsg_plan = skilloa.build_vsg_compressor_control_start_plan(cfg.VSG_REQUEST)
    log(f"HRL-Plan erstellt: {hrl_plan.name}")
    log(f"VSG-Plan erstellt: {vsg_plan.name}")

    sps.write_bool("OPCUA.Diag_finished", False)
    sps.write_string("OPCUA.lastFinishedSkill", "")
    sps.write_string("OPCUA.lastExecutedProcess", "")
    _reset_vsg_error_code(sps, log)
    log("Initialwerte geschrieben (Diag_finished=False, lastFinishedSkill='').")

    return {
        "prepared": prepared,
        "hrl_plan": {
            "name": hrl_plan.name,
            "method_nodeid": hrl_plan.method.method_nodeid,
            "payload": hrl_plan.payload,
        },
        "vsg_plan": {
            "name": vsg_plan.name,
            "method_nodeid": vsg_plan.method.method_nodeid,
            "payload": vsg_plan.payload,
        },
    }


# ---------------------------------------------------------------------------
# Zelle 2 — Start
# ---------------------------------------------------------------------------

def action_start(log: LogCallback = _noop) -> Dict[str, Any]:
    """
    Entspricht Notebook-Zelle 2:
    HRL_Auslagern ausführen, bei Erfolg VSG_CompressorControl starten.
    """
    sps = _make_sps()
    skilloa = _make_skilloa(sps)

    hrl_plan = skilloa.build_hrl_auslagern_start_plan(cfg.HRL_REQUEST)
    vsg_plan = skilloa.build_vsg_compressor_control_start_plan(cfg.VSG_REQUEST)

    result: Dict[str, Any] = {
        "hrl": None,
        "hrl_last_finished_write": None,
        "vsg_prepare": None,
        "vsg_manual_writes": [],
        "vsg_pickup_wait": None,
        "vsg_skipped_reason": None,
        "vsg": None,
    }

    log("Starte HRL_Auslagern...")
    hrl_execution = skilloa.start_skill_plan(hrl_plan)
    result["hrl"] = hrl_execution.as_dict()
    log(
        f"HRL abgeschlossen — erfolgreich={hrl_execution.is_successful()}, "
        f"outputs={hrl_execution.call.outputs}"
    )

    if hrl_execution.is_successful():
        receipt = sps.write_string("OPCUA.lastFinishedSkill", "HRL_NMethod_Auslagern")
        result["hrl_last_finished_write"] = receipt.as_dict()
        log("lastFinishedSkill='HRL_NMethod_Auslagern' geschrieben.")

    if cfg.START_VSG_AFTER_HRL_SUCCESS and hrl_execution.is_successful():
        log("Warte auf Werkstück an ls_aussen...")
        ls_outer_seen = _wait_for_bool_signal(
            sps,
            "ls_outer",
            True,
            timeout_seconds=cfg.VSG_WAIT_FOR_LS_AUSSEN_TIMEOUT_SECONDS,
        )
        result["vsg_pickup_wait"] = {
            "ls_outer_seen": ls_outer_seen,
            "timeout_seconds": cfg.VSG_WAIT_FOR_LS_AUSSEN_TIMEOUT_SECONDS,
            "dwell_seconds": cfg.VSG_LS_AUSSEN_DWELL_SECONDS if ls_outer_seen else 0.0,
            "missing_preview_seconds": 0.0,
            "ls_outer_removed": None,
            "missing_marker_write": None,
            "missing_marker_clear": None,
        }

        if not ls_outer_seen:
            result["vsg_skipped_reason"] = "ls_outer wurde vor Timeout nicht aktiv."
            log("VSG übersprungen - ls_outer wurde vor Timeout nicht aktiv.")
            return result

        if cfg.VSG_LS_AUSSEN_DWELL_SECONDS > 0:
            log(
                "Werkstück steht an ls_aussen. "
                f"Warte {cfg.VSG_LS_AUSSEN_DWELL_SECONDS:.1f} s vor VSG."
            )
            time.sleep(cfg.VSG_LS_AUSSEN_DWELL_SECONDS)

        log("Entferne Werkstück an ls_aussen vor VSG-Start.")
        removal = sps.write_bool("ls_outer", False)
        result["vsg_pickup_wait"]["ls_outer_removed"] = removal.as_dict()
        marker = sps.write_string("OPCUA.lastExecutedProcess", cfg.VSG_MISSING_WORKPIECE_MARKER)
        result["vsg_pickup_wait"]["missing_marker_write"] = marker.as_dict()

        if cfg.VSG_MISSING_WORKPIECE_PREVIEW_SECONDS > 0:
            result["vsg_pickup_wait"]["missing_preview_seconds"] = (
                cfg.VSG_MISSING_WORKPIECE_PREVIEW_SECONDS
            )
            log(
                "Werkstück fehlt an ls_aussen. "
                f"Zeige Fehler-Vorschau {cfg.VSG_MISSING_WORKPIECE_PREVIEW_SECONDS:.1f} s."
            )
            time.sleep(cfg.VSG_MISSING_WORKPIECE_PREVIEW_SECONDS)

        marker_clear = sps.write_string("OPCUA.lastExecutedProcess", "")
        result["vsg_pickup_wait"]["missing_marker_clear"] = marker_clear.as_dict()

        log("Bereite VSG vor...")
        vsg_prepare = sps.prepare_vsg_for_compressor_test(
            workpiece_at_pickup=cfg.VSG_WORKPIECE_AT_PICKUP
        )
        result["vsg_prepare"] = vsg_prepare
        log(f"VSG vorbereitet: {list(vsg_prepare.keys())}")

        manual_writes = []
        if cfg.SET_VSG_ERROR_FALSE_BEFORE_VSG:
            w = sps.write_bool(
                "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected", False
            )
            manual_writes.append(w.as_dict())
            log("VSG_ErrorDetected auf False gesetzt.")
            _reset_vsg_error_code(sps, log)

        if cfg.SET_DIAG_FINISHED_TRUE_BEFORE_VSG:
            w = sps.write_bool("OPCUA.Diag_finished", True)
            manual_writes.append(w.as_dict())
            log("Diag_finished auf True gesetzt.")

        result["vsg_manual_writes"] = manual_writes

        log("Starte VSG_CompressorControl...")
        vsg_execution = skilloa.start_skill_plan(vsg_plan)
        result["vsg"] = vsg_execution.as_dict()
        log(
            f"VSG abgeschlossen — erfolgreich={vsg_execution.is_successful()}, "
            f"outputs={vsg_execution.call.outputs}"
        )

    elif cfg.START_VSG_AFTER_HRL_SUCCESS:
        log("VSG übersprungen - HRL nicht erfolgreich.")

    return result


# ---------------------------------------------------------------------------
# Zelle 3 — Reset
# ---------------------------------------------------------------------------

def action_reset(log: LogCallback = _noop) -> Dict[str, Any]:
    """
    Entspricht Notebook-Zelle 3:
    VSG-Fehlerzustand zurücksetzen.
    """
    sps = _make_sps()

    log("VSG_SkillSet.ResetButton = True")
    sps.write_bool("VSG_SkillSet.ResetButton", True)

    log("VSG_ErrorDetected = False")
    sps.write_bool("VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected", False)
    _reset_vsg_error_code(sps, log)
    sps.write_string("OPCUA.lastExecutedProcess", "")

    log("VSG DiagnosisHandler.Diag_finished = True")
    sps.write_bool("VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished", True)

    vsg_error = sps.read_bool("VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected")
    diag_finished = sps.read_bool("VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished")
    log(
        f"Reset abgeschlossen — VSG_Fehler={vsg_error.value}, "
        f"Diag_finished={diag_finished.value}"
    )

    return {
        "vsg_error": vsg_error.as_dict(),
        "diag_finished": diag_finished.as_dict(),
    }


# ---------------------------------------------------------------------------
# Sensor-Lesen für das UI
# ---------------------------------------------------------------------------

def read_bool_sensors() -> Dict[str, bool]:
    """Liest alle Bool-Sensoren in einem ADS-Verbindungsaufruf."""
    sps = _make_sps()
    snapshot = sps.read_bool_snapshot(cfg.SENSOR_POLL_SYMBOLS)
    return {key: bool(result.value) for key, result in snapshot.items()}


def read_udint_values() -> Dict[str, int]:
    """Liest Encoder- und Schrittwerte in einem ADS-Verbindungsaufruf."""
    sps = _make_sps()
    snapshot = sps.read_udint_snapshot(cfg.UDINT_POLL_SYMBOLS)
    return {key: int(result.value) for key, result in snapshot.items()}


def read_scene_snapshot() -> Dict[str, Dict[str, Any]]:
    """Liest alle Werte, aus denen die Draufsicht abgeleitet wird."""
    sps = _make_sps()
    bool_snapshot = sps.read_bool_snapshot(cfg.BOOL_POLL_SYMBOLS)
    udint_snapshot = sps.read_udint_snapshot(cfg.UDINT_POLL_SYMBOLS)
    return {
        "bools": {key: bool(result.value) for key, result in bool_snapshot.items()},
        "udints": {key: int(result.value) for key, result in udint_snapshot.items()},
    }


def read_string_values() -> Dict[str, str]:
    """Liest OPC-UA-Tracking-Strings."""
    sps = _make_sps()
    tracking = sps.read_skill_tracking()
    return {key: str(result.value) for key, result in tracking.items()}
