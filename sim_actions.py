"""Aktionen entsprechend den Notebook-Zellen (Init, Start, Reset) und Sensor-Lesen."""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Zelle 1 — Init
# ---------------------------------------------------------------------------

def action_init(log: LogCallback = _noop) -> Dict[str, Any]:
    """
    Entspricht Notebook-Zelle 1:
    SPS vorbereiten, Plaene bauen, Initialwerte schreiben.
    """
    sps = _make_sps()
    skilloa = _make_skilloa(sps)

    log("Bereite SPS fuer Skill-Tests vor...")
    prepared = sps.prepare_plc_for_skill_tests()
    log(f"SPS vorbereitet: {list(prepared.keys())}")

    hrl_plan = skilloa.build_hrl_auslagern_start_plan(cfg.HRL_REQUEST)
    vsg_plan = skilloa.build_vsg_compressor_control_start_plan(cfg.VSG_REQUEST)
    log(f"HRL-Plan erstellt: {hrl_plan.name}")
    log(f"VSG-Plan erstellt: {vsg_plan.name}")

    sps.write_bool("OPCUA.Diag_finished", False)
    sps.write_string("OPCUA.lastFinishedSkill", "")
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
    HRL_Auslagern ausfuehren, bei Erfolg VSG_CompressorControl starten.
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
        log("VSG uebersprungen — HRL nicht erfolgreich.")

    return result


# ---------------------------------------------------------------------------
# Zelle 3 — Reset
# ---------------------------------------------------------------------------

def action_reset(log: LogCallback = _noop) -> Dict[str, Any]:
    """
    Entspricht Notebook-Zelle 3:
    VSG-Fehlerzustand zuruecksetzen.
    """
    sps = _make_sps()

    log("VSG_SkillSet.ResetButton = True")
    sps.write_bool("VSG_SkillSet.ResetButton", True)

    log("VSG_ErrorDetected = False")
    sps.write_bool("VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected", False)

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


def action_manual_remove_workpiece(log: LogCallback = _noop) -> Dict[str, Any]:
    """
    Simuliert eine manuelle Werkstueck-Entnahme am Bandende.

    Entsprechend der Anforderung wird ls_aussen / ls_outer auf False gesetzt.
    """
    sps = _make_sps()

    log("Setze ls_outer = False (manuelle Werkstueck-Entnahme).")
    write_receipt = sps.write_bool("ls_outer", False)

    outer_sim = sps.read_bool("ls_outer")
    outer_runtime = sps.read_bool("GVL_HRL.HRL_LS_aussen")
    log(
        "Manuelle Entnahme abgeschlossen - "
        f"ls_outer_sim={outer_sim.value}, ls_outer_runtime={outer_runtime.value}"
    )

    return {
        "write": write_receipt.as_dict(),
        "ls_outer_sim": outer_sim.as_dict(),
        "ls_outer_runtime": outer_runtime.as_dict(),
    }


# ---------------------------------------------------------------------------
# Sensor-Lesen fuer das UI
# ---------------------------------------------------------------------------

def read_bool_sensors() -> Dict[str, bool]:
    """Liest alle Bool-Sensoren in einem ADS-Verbindungsaufruf."""
    sps = _make_sps()
    snapshot = sps.read_bool_snapshot(cfg.SENSOR_POLL_SYMBOLS)
    return {key: bool(result.value) for key, result in snapshot.items()}


def read_string_values() -> Dict[str, str]:
    """Liest OPC-UA-Tracking-Strings."""
    sps = _make_sps()
    tracking = sps.read_skill_tracking()
    return {key: str(result.value) for key, result in tracking.items()}
