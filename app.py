"""
Streamlit-Oberfläche für den Fischertechnik-Simulator.

Aufruf:
    streamlit run app.py
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict

import streamlit as st
import streamlit.components.v1 as components

import sim_config as cfg
from sim_actions import (
    action_init,
    action_reset,
    action_start,
    read_scene_snapshot,
    read_string_values,
)


st.set_page_config(
    page_title="Fischertechnik Simulator",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #09111c 0%, #0c1726 100%);
        color: #dce7f5;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0.8rem;
    }
    .stButton > button {
        font-size: 0.98rem;
        font-weight: 600;
        border-radius: 8px;
        padding: 0.58rem 1.15rem;
        border: 1px solid rgba(140, 170, 210, 0.22);
        background: linear-gradient(180deg, #15253a 0%, #101b2b 100%);
        color: #e6eef8;
    }
    .stButton > button:hover {
        border-color: rgba(120, 199, 168, 0.45);
        box-shadow: 0 0 0 1px rgba(120, 199, 168, 0.15);
    }
    .stButton > button:disabled {
        opacity: 0.45;
    }
    textarea {
        font-family: Consolas, "Courier New", monospace !important;
        font-size: 0.78rem !important;
    }
    div[data-testid="stDataFrame"] {
        font-size: 0.82rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults: Dict[str, Any] = {
        "running": False,
        "current_action": None,
        "log_lines": [],
        "result_queue": queue.Queue(),
        "log_queue": queue.Queue(),
        "last_result": None,
        "last_error": None,
        "sensors": {},
        "udints": {},
        "strings": {},
        "missing_workpiece_at_pickup": False,
        "workpiece_stage": "initial",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()
ss = st.session_state


def _drain_queues() -> None:
    while True:
        try:
            ss.log_lines.append(ss.log_queue.get_nowait())
        except queue.Empty:
            break

    try:
        outcome: Dict[str, Any] = ss.result_queue.get_nowait()
        ss.running = False
        ss.current_action = None
        if outcome["success"]:
            ss.last_result = outcome["result"]
            ss.last_error = None
        else:
            ss.last_error = outcome["error"]
            ss.last_result = None
    except queue.Empty:
        pass


def _start_action(name: str, fn) -> None:
    if ss.running:
        return

    if name in {"init", "start", "reset"}:
        ss.missing_workpiece_at_pickup = False
        ss.workpiece_stage = "initial"

    ss.running = True
    ss.current_action = name
    ss.last_error = None
    ss.log_lines.append(f"\n{'=' * 52}")
    ss.log_lines.append(f"[{name.upper()}] gestartet")
    ss.log_lines.append(f"{'=' * 52}")

    log_q: queue.Queue = ss.log_queue
    res_q: queue.Queue = ss.result_queue

    def _worker() -> None:
        try:
            result = fn(log=lambda msg: log_q.put(str(msg)))
            res_q.put({"success": True, "result": result})
        except Exception:
            res_q.put({"success": False, "error": __import__("traceback").format_exc()})

    threading.Thread(target=_worker, daemon=True).start()


def _refresh_sensors() -> None:
    try:
        snapshot = read_scene_snapshot()
        ss.sensors = snapshot["bools"]
        ss.udints = snapshot["udints"]
    except Exception as exc:
        ss.sensors = {"_error": str(exc)}
        ss.udints = {}

    try:
        ss.strings = read_string_values()
    except Exception:
        ss.strings = {}


_WORKPIECE_STAGE_ORDER = {
    "initial": 0,
    "rbg": 1,
    "ls_inner": 2,
    "ls_outer": 3,
    "missing": 4,
}


def _advance_workpiece_stage(stage: str) -> None:
    current = str(ss.get("workpiece_stage", "initial"))
    if _WORKPIECE_STAGE_ORDER[stage] >= _WORKPIECE_STAGE_ORDER.get(current, 0):
        ss.workpiece_stage = stage


def _update_workpiece_state() -> None:
    process_marker = str(ss.strings.get("last_executed_process", "")).strip("\x00")
    if process_marker == cfg.VSG_MISSING_WORKPIECE_MARKER:
        ss.missing_workpiece_at_pickup = True
        ss.workpiece_stage = "missing"
        return

    if ss.current_action != "start" or "_error" in ss.sensors:
        return

    if ss.get("missing_workpiece_at_pickup", False):
        ss.workpiece_stage = "missing"
        return

    ls_outer = _b(ss.sensors, "ls_outer")
    ls_inner = _b(ss.sensors, "ls_inner")
    current_step = _u(ss.udints, "HRL_SkillSet.HRL_NMethod_Auslagern.CurrentStep")
    ts_front = _b(ss.sensors, "ts_ausleger_vorne")
    vsg_error = _b(ss.sensors, "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected")

    if ls_outer:
        _advance_workpiece_stage("ls_outer")
    elif ls_inner:
        _advance_workpiece_stage("ls_inner")
    elif (
        ts_front
        or current_step in {30, 40, 50, 60, 65, 70}
        or _b(ss.sensors, "GVL_HRL_Sim.HRL_MOT_Ausleger_vorwaerts")
        or _b(ss.sensors, "GVL_HRL_Sim.HRL_MOT_Ausleger_rueckwaerts")
    ):
        _advance_workpiece_stage("rbg")
    elif vsg_error and _WORKPIECE_STAGE_ORDER.get(ss.workpiece_stage, 0) >= _WORKPIECE_STAGE_ORDER["ls_outer"]:
        ss.missing_workpiece_at_pickup = True
        ss.workpiece_stage = "missing"


def _b(values: dict, key: str) -> bool:
    return bool(values.get(key, False))


def _u(values: dict, key: str, default: int = 0) -> int:
    try:
        return int(values.get(key, default))
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _scale(value: float, source_min: float, source_max: float, target_min: float, target_max: float) -> float:
    if source_min == source_max:
        return (target_min + target_max) / 2
    ratio = (value - source_min) / (source_max - source_min)
    ratio = _clamp(ratio, 0, 1)
    return target_min + ratio * (target_max - target_min)


def _lamp_color(active: bool, *, error: bool = False) -> str:
    if error and active:
        return "#ff5a4f"
    return "#2fce83" if active else "#53647a"


def _svg_lamp_row(x: int, y: int, label: str, active: bool, *, error: bool = False) -> str:
    fill = _lamp_color(active, error=error)
    return (
        f'<circle cx="{x}" cy="{y}" r="6.5" fill="{fill}" stroke="#071019" stroke-width="1.2"/>'
        f'<circle cx="{x}" cy="{y}" r="10" fill="none" stroke="{fill}" stroke-opacity="0.25" stroke-width="2"/>'
        f'<text x="{x + 15}" y="{y + 4}" font-size="10" fill="#dbe6f4">{label}</text>'
    )


def _svg_value_row(x: int, y: int, label: str, value: str, *, warn: bool = False) -> str:
    fill = "#ffb25f" if warn else "#dbe6f4"
    return (
        f'<text x="{x}" y="{y}" font-size="10" fill="#8fa6bf">{label}</text>'
        f'<text x="{x + 170}" y="{y}" font-size="10" font-weight="700" fill="{fill}">{value}</text>'
    )


def _workpiece_svg(x: float, y: float, *, active: bool, missing: bool = False) -> str:
    anim = (
        '<animate attributeName="opacity" values="1;0.55;1" dur="0.8s" repeatCount="indefinite"/>'
        if active
        else ""
    )
    if missing:
        return (
            f'<g>'
            f'<rect x="{x - 13:.1f}" y="{y - 13:.1f}" width="26" height="26" rx="5" '
            f'fill="#c93636" stroke="#ffb0a8" stroke-width="2">{anim}</rect>'
            f'<text x="{x:.1f}" y="{y + 7:.1f}" text-anchor="middle" font-size="23" '
            f'font-weight="900" fill="#fff4f2">?</text>'
            f'</g>'
        )
    return (
        f'<g>'
        f'<rect x="{x - 13:.1f}" y="{y - 13:.1f}" width="26" height="26" rx="5" '
        f'fill="#f2a12b" stroke="#ffd06f" stroke-width="2">{anim}</rect>'
        f'<line x1="{x - 5:.1f}" y1="{y:.1f}" x2="{x + 5:.1f}" y2="{y:.1f}" '
        f'stroke="#7d4b00" stroke-width="1.3"/>'
        f'<line x1="{x:.1f}" y1="{y - 5:.1f}" x2="{x:.1f}" y2="{y + 5:.1f}" '
        f'stroke="#7d4b00" stroke-width="1.3"/>'
        f'</g>'
    )


def _step_text(
    step: int,
    hrl_error: bool,
    vsg_error: bool,
    ls_outer: bool,
    ls_inner: bool,
    ts_back: bool,
    missing_at_pickup: bool = False,
) -> str:
    if vsg_error and not ls_outer:
        return "VSG-Fehler: Werkstück fehlt an der äußeren HRL-Lichtschranke."
    if missing_at_pickup:
        return "Werkstück wurde an ls_aussen entfernt. VSG wird mit fehlendem Werkstück gestartet."
    if hrl_error:
        return "HRL-Auslagern meldet eine Störung. ErrorId steht in der Wertetabelle."

    labels = {
        10: "RBG fährt horizontal zur Regalposition.",
        20: "RBG fährt vertikal zur Regalebene.",
        30: "Ausleger fährt in das Regal und nimmt das Werkstück.",
        40: "Ausleger fährt mit Werkstück zurück.",
        50: "RBG fährt horizontal zur Übergabeposition am Förderband.",
        60: "RBG fährt vertikal zur Übergabehöhe.",
        65: "Übergabe an den Bandanfang, Warten auf ls_innen.",
        70: "Förderband transportiert das Werkstück zur VSG-Aufnahmeposition.",
        100: "HRL-Auslagern abgeschlossen.",
        900: "HRL-Auslagern im Fehlerzustand.",
    }
    if step in labels:
        return labels[step]
    if ls_outer:
        return "Werkstück steht an ls_aussen für die VSG-Aufnahme bereit."
    if ls_inner:
        return "Werkstück steht am Bandanfang direkt neben dem Regal."
    if ts_back:
        return "Werkstück liegt im Hochregallager/RBG-Rückzugsbereich."
    return "Kein Werkstücksignal aktiv. Anzeige folgt den SPS-Simulationswerten."


def build_process_svg(
    sensors: dict,
    udints: dict,
    *,
    missing_workpiece_at_pickup: bool = False,
    workpiece_stage: str = "initial",
) -> str:
    ts_front = _b(sensors, "ts_ausleger_vorne")
    ts_back = _b(sensors, "ts_ausleger_hinten")
    ls_inner = _b(sensors, "ls_inner")
    ls_outer = _b(sensors, "ls_outer")
    sim_mode = _b(sensors, "sim")

    hrl_busy = _b(sensors, "HRL_SkillSet.HRL_NMethod_Auslagern.Busy")
    hrl_error = _b(sensors, "HRL_SkillSet.HRL_NMethod_Auslagern.Error")
    vsg_error = _b(sensors, "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected")
    diag_finished = _b(sensors, "diag_finished")
    vsg_diag_finished = _b(sensors, "VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished")

    mot_h_to_rack = _b(sensors, "GVL_HRL_Sim.HRL_MOT_horizontal_zum_Regal")
    mot_h_to_belt = _b(sensors, "GVL_HRL_Sim.HRL_MOT_horizontal_zum_Foerderband")
    mot_v_down = _b(sensors, "GVL_HRL_Sim.HRL_MOT_vertikal_runter")
    mot_v_up = _b(sensors, "GVL_HRL_Sim.HRL_MOT_vertikal_hoch")
    mot_fork_out = _b(sensors, "GVL_HRL_Sim.HRL_MOT_Ausleger_vorwaerts")
    mot_fork_in = _b(sensors, "GVL_HRL_Sim.HRL_MOT_Ausleger_rueckwaerts")
    mot_belt_forward = _b(sensors, "GVL_HRL_Sim.HRL_MOT_Foerderband_vorwaerts")
    mot_belt_backward = _b(sensors, "GVL_HRL_Sim.HRL_MOT_Foerderband_rueckwaerts")

    vsg_compressor = _b(sensors, "GVL_VSG_Sim.VSG_Kompressor")
    vsg_valve = _b(sensors, "GVL_VSG_Sim.VSG_MV_Vakuum")
    vsg_move = any(
        _b(sensors, key)
        for key in (
            "GVL_VSG_Sim.VSG_MOT_vertikal_runter",
            "GVL_VSG_Sim.VSG_MOT_vertikal_hoch",
            "GVL_VSG_Sim.VSG_MOT_horizontal_vorwaerts",
            "GVL_VSG_Sim.VSG_MOT_horizontal_rueckwaerts",
            "GVL_VSG_Sim.VSG_MOT_drehen_CW",
            "GVL_VSG_Sim.VSG_MOT_drehen_CCW",
        )
    )

    horizontal = _u(udints, "horizontal_1")
    vertical = _u(udints, "vertical_1")
    current_step = _u(udints, "HRL_SkillSet.HRL_NMethod_Auslagern.CurrentStep")
    error_id = _u(udints, "HRL_SkillSet.HRL_NMethod_Auslagern.ErrorId")
    vsg_error_code = _u(udints, "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorCode")
    vsg_error_code_display = vsg_error_code if vsg_error else 0

    h_transfer = cfg.HRL_REQUEST.horizontal_transfer_i1
    h_shelf = cfg.HRL_REQUEST.horizontal_shelf_i1
    v_min = min(cfg.HRL_REQUEST.vertical_transfer_i1, cfg.HRL_REQUEST.vertical_shelf_i1)
    v_max = max(cfg.HRL_REQUEST.vertical_transfer_i1, cfg.HRL_REQUEST.vertical_shelf_i1)

    rack_x, rack_y, rack_w, rack_h = 150, 190, 230, 250
    rail_x, rail_y, rail_w, rail_h = 404, 190, 70, 250
    belt_x, belt_y, belt_w, belt_h = 150, 106, 366, 58
    band_center_y = belt_y + belt_h / 2
    outer_x = belt_x + 48
    inner_x = belt_x + belt_w - 50
    transfer_x = rail_x + 21

    carriage_y = _scale(horizontal, h_transfer, h_shelf, rail_y + 30, rail_y + rail_h - 42)
    lift_y = _scale(vertical, v_min, v_max, rail_y + rail_h - 28, rail_y + 34)
    shelf_row = int(round(_scale(vertical, v_min, v_max, 3, 0)))
    shelf_row = int(_clamp(shelf_row, 0, 3))

    rack_cells = []
    for row in range(4):
        for col in range(2):
            x = rack_x + 24 + col * 88
            y = rack_y + 28 + row * 50
            active_cell = row == shelf_row and not (ls_inner or ls_outer)
            fill = "#24364a" if active_cell else "#172434"
            stroke = "#80c6ff" if active_cell else "#334960"
            rack_cells.append(
                f'<rect x="{x}" y="{y}" width="70" height="34" rx="4" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="1.3"/>'
            )
    rack_cells_svg = "".join(rack_cells)

    fork_extension = 58 if (ts_front or mot_fork_out) else 24 if ts_back else 40
    fork_color = "#f6b73c" if (mot_fork_out or mot_fork_in or ts_front) else "#8a9ab0"
    carriage_stroke = "#7fd4ff" if (mot_h_to_rack or mot_h_to_belt or mot_v_down or mot_v_up or hrl_busy) else "#5c7895"
    belt_color = "#2fce83" if (mot_belt_forward or mot_belt_backward) else "#617181"

    missing_at_pickup = bool(missing_workpiece_at_pickup) or workpiece_stage == "missing"
    workpiece_visible = True
    workpiece_active = any((mot_belt_forward, mot_fork_out, mot_fork_in, mot_h_to_rack, mot_h_to_belt))
    workpiece_missing = False
    if missing_at_pickup:
        workpiece_x, workpiece_y = outer_x, band_center_y
        workpiece_active = True
        workpiece_missing = True
    elif workpiece_stage == "ls_outer":
        workpiece_x, workpiece_y = outer_x, band_center_y
    elif workpiece_stage == "ls_inner":
        workpiece_x, workpiece_y = inner_x, band_center_y
    elif workpiece_stage == "rbg":
        workpiece_x, workpiece_y = transfer_x - 28, carriage_y + 21
    else:
        workpiece_x = rack_x + 72
        workpiece_y = rack_y + 45 + shelf_row * 50

    workpiece = (
        _workpiece_svg(workpiece_x, workpiece_y, active=workpiece_active, missing=workpiece_missing)
        if workpiece_visible
        else ""
    )
    step_label = _step_text(current_step, hrl_error, vsg_error, ls_outer, ls_inner, ts_back, missing_at_pickup)

    belt_arrows = "".join(
        f'<polygon points="{x},127 {x + 15},119 {x + 15},135" fill="{belt_color}" opacity="0.88"/>'
        for x in range(236, 454, 56)
    )
    if mot_belt_backward:
        belt_arrows = "".join(
            f'<polygon points="{x + 15},127 {x},119 {x},135" fill="{belt_color}" opacity="0.88"/>'
            for x in range(236, 454, 56)
        )
    elif not mot_belt_forward:
        belt_arrows = belt_arrows.replace('opacity="0.88"', 'opacity="0.25"')

    hrl_motion_arrow = ""
    if mot_h_to_rack:
        hrl_motion_arrow = (
            f'<line x1="{rail_x + rail_w + 18}" y1="{carriage_y + 10:.1f}" '
            f'x2="{rail_x + rail_w + 18}" y2="{carriage_y + 66:.1f}" '
            f'stroke="#2fce83" stroke-width="3" marker-end="url(#arr)"/>'
        )
    elif mot_h_to_belt:
        hrl_motion_arrow = (
            f'<line x1="{rail_x + rail_w + 18}" y1="{carriage_y + 26:.1f}" '
            f'x2="{rail_x + rail_w + 18}" y2="{carriage_y - 30:.1f}" '
            f'stroke="#2fce83" stroke-width="3" marker-end="url(#arr)"/>'
        )

    status_rows = "".join(
        [
            _svg_value_row(622, 129, "HRL CurrentStep", str(current_step)),
            _svg_value_row(622, 149, "HRL horizontal I1", str(horizontal)),
            _svg_value_row(622, 169, "HRL vertikal I1", str(vertical)),
            _svg_value_row(622, 189, "HRL ErrorId", str(error_id), warn=hrl_error),
            _svg_value_row(622, 209, "VSG ErrorCode", str(vsg_error_code_display), warn=vsg_error),
        ]
    )

    system_lamps = "".join(
        [
            _svg_lamp_row(624, 253, "SimMode", sim_mode),
            _svg_lamp_row(624, 276, "HRL Busy", hrl_busy),
            _svg_lamp_row(624, 299, "HRL Error", hrl_error, error=True),
            _svg_lamp_row(624, 322, "OPC Diag_finished", diag_finished),
            _svg_lamp_row(624, 345, "VSG Diag_finished", vsg_diag_finished),
        ]
    )
    sensor_lamps = "".join(
        [
            _svg_lamp_row(822, 253, "ls_innen", ls_inner),
            _svg_lamp_row(822, 276, "ls_aussen", ls_outer),
            _svg_lamp_row(822, 299, "Ausleger vorne", ts_front),
            _svg_lamp_row(822, 322, "Ausleger hinten", ts_back),
            _svg_lamp_row(822, 345, "VSG Fehler", vsg_error, error=True),
        ]
    )
    actuator_lamps = "".join(
        [
            _svg_lamp_row(624, 395, "HRL Band vorwärts", mot_belt_forward),
            _svg_lamp_row(624, 418, "HRL Ausleger vorwärts", mot_fork_out),
            _svg_lamp_row(624, 441, "HRL horizontal aktiv", mot_h_to_rack or mot_h_to_belt),
            _svg_lamp_row(822, 395, "VSG Bewegung", vsg_move),
            _svg_lamp_row(822, 418, "VSG Kompressor", vsg_compressor),
            _svg_lamp_row(822, 441, "VSG Ventil", vsg_valve),
        ]
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 520"
    style="width:100%;background:#0b1420;border-radius:8px;font-family:Segoe UI,Arial,sans-serif;">
  <defs>
    <marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,0 L0,9 L9,4.5 z" fill="#2fce83"/>
    </marker>
    <filter id="softGlow">
      <feGaussianBlur stdDeviation="2.3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="0" y="0" width="1040" height="48" rx="8" fill="#111b2c"/>
  <text x="26" y="30" font-size="15" font-weight="700" fill="#dbe7f7">Draufsicht HRL/RBG/Förderband/VSG</text>
  <text x="320" y="30" font-size="13" fill="#aabbd0">{step_label}</text>

  <rect x="34" y="58" width="550" height="416" rx="8" fill="#0f1926" stroke="#273b51" stroke-width="1.3"/>
  <text x="58" y="452" font-size="10" fill="#8fa6bf">
    <tspan x="58" dy="0">Realer Bezug: Regal links, RBG-Schiene rechts daneben,</tspan>
    <tspan x="58" dy="14">Förderband oberhalb direkt am Regal, VSG links dahinter.</tspan>
  </text>

  <rect x="48" y="74" width="86" height="140" rx="8" fill="#21172a" stroke="#8757a0" stroke-width="1.4"/>
  <text x="70" y="98" font-size="18" font-weight="800" fill="#e4b4ff">VSG</text>
  <rect x="84" y="112" width="14" height="74" rx="6" fill="#4a2d58" stroke="#c89dde" stroke-width="1.2"/>
  <ellipse cx="91" cy="196" rx="25" ry="9" fill="{'#5b2e6e' if vsg_compressor else '#2a1932'}" stroke="#d8b2ed" stroke-width="1.2"/>
  <line x1="91" y1="196" x2="{outer_x}" y2="{band_center_y}" stroke="{'#2fce83' if vsg_valve else '#6f597b'}" stroke-width="3" stroke-dasharray="6,5"/>

  <rect x="{belt_x}" y="{belt_y}" width="{belt_w}" height="{belt_h}" rx="8" fill="#18232b" stroke="#4d626d" stroke-width="1.3"/>
  <text x="{belt_x + 70}" y="{belt_y - 12}" font-size="15" font-weight="800" fill="#8ce0a6">FÖRDERBAND</text>
  <line x1="{belt_x + 16}" y1="{band_center_y}" x2="{belt_x + belt_w - 16}" y2="{band_center_y}" stroke="#26333d" stroke-width="28" stroke-linecap="round"/>
  {belt_arrows}
  <text x="{outer_x}" y="{belt_y - 32}" text-anchor="middle" font-size="10" fill="#cbd8e6">ls_aussen</text>
  <line x1="{outer_x}" y1="{belt_y - 24}" x2="{outer_x}" y2="{band_center_y - 14}" stroke="#7d93ac" stroke-width="1.1" stroke-dasharray="4,3"/>
  <circle cx="{outer_x}" cy="{band_center_y}" r="12" fill="{_lamp_color(ls_outer)}" stroke="#071019" stroke-width="1.5"/>
  <text x="{inner_x}" y="{belt_y - 32}" text-anchor="middle" font-size="10" fill="#cbd8e6">ls_innen</text>
  <line x1="{inner_x}" y1="{belt_y - 24}" x2="{inner_x}" y2="{band_center_y - 14}" stroke="#7d93ac" stroke-width="1.1" stroke-dasharray="4,3"/>
  <circle cx="{inner_x}" cy="{band_center_y}" r="12" fill="{_lamp_color(ls_inner)}" stroke="#071019" stroke-width="1.5"/>

  <rect x="{rack_x}" y="{rack_y}" width="{rack_w}" height="{rack_h}" rx="8" fill="#121f30" stroke="#356086" stroke-width="1.5"/>
  <text x="{rack_x + 22}" y="{rack_y + 23}" font-size="17" font-weight="800" fill="#8fcfff">HOCHREGALLAGER</text>
  {rack_cells_svg}

  <rect x="{rail_x}" y="{rail_y}" width="{rail_w}" height="{rail_h}" rx="8" fill="#142235" stroke="#587da0" stroke-width="1.5"/>
  <text x="{rail_x + rail_w / 2}" y="{rail_y - 12}" text-anchor="middle" font-size="13" font-weight="800" fill="#9bcfff">RBG-SCHIENE</text>
  <line x1="{rail_x + rail_w / 2}" y1="{rail_y + 20}" x2="{rail_x + rail_w / 2}" y2="{rail_y + rail_h - 20}" stroke="#6f849b" stroke-width="6" stroke-linecap="round"/>
  <rect x="{rail_x + 8}" y="{carriage_y:.1f}" width="{rail_w - 16}" height="42" rx="7" fill="#192f4a" stroke="{carriage_stroke}" stroke-width="2" filter="url(#softGlow)"/>
  <text x="{rail_x + rail_w / 2}" y="{carriage_y + 26:.1f}" text-anchor="middle" font-size="10" fill="#dce7f5">RBG</text>
  <rect x="{rail_x + 8 - fork_extension}" y="{carriage_y + 17:.1f}" width="{fork_extension}" height="8" rx="4" fill="{fork_color}" stroke="#f7d890" stroke-width="1"/>
  <rect x="{rail_x + 8 - fork_extension}" y="{carriage_y + 12:.1f}" width="9" height="18" rx="3" fill="{fork_color}" stroke="#f7d890" stroke-width="1"/>
  {hrl_motion_arrow}

  <line x1="{rail_x + rail_w + 40}" y1="{rail_y + 26}" x2="{rail_x + rail_w + 40}" y2="{rail_y + rail_h - 26}" stroke="#243244" stroke-width="8" stroke-linecap="round"/>
  <circle cx="{rail_x + rail_w + 40}" cy="{lift_y:.1f}" r="10" fill="{'#2fce83' if (mot_v_down or mot_v_up) else '#64758a'}" stroke="#111b2c" stroke-width="1.5"/>
  <text x="{rail_x + rail_w + 56}" y="{lift_y + 4:.1f}" font-size="10" fill="#b9cadc">Höhe</text>

  {workpiece}

  <rect x="590" y="82" width="444" height="392" rx="8" fill="#101b29" stroke="#2a3e55" stroke-width="1.3"/>
  <text x="622" y="107" font-size="16" font-weight="800" fill="#dbe7f7">SPS-gebundener Zustand</text>
  {status_rows}
  <line x1="622" y1="229" x2="1002" y2="229" stroke="#263a50" stroke-width="1"/>
  {system_lamps}
  {sensor_lamps}
  <line x1="622" y1="370" x2="1002" y2="370" stroke="#263a50" stroke-width="1"/>
  {actuator_lamps}

  <rect x="0" y="500" width="1040" height="20" rx="8" fill="#111b2c"/>
  <circle cx="26" cy="510" r="5" fill="#2fce83"/>
  <text x="38" y="513" font-size="9.5" fill="#cad7e6">aktiv</text>
  <circle cx="90" cy="510" r="5" fill="#53647a"/>
  <text x="102" y="513" font-size="9.5" fill="#cad7e6">inaktiv</text>
  <circle cx="168" cy="510" r="5" fill="#ff5a4f"/>
  <text x="180" y="513" font-size="9.5" fill="#cad7e6">Fehler</text>
</svg>"""


_drain_queues()
_refresh_sensors()
_update_workpiece_state()

st.title("Fischertechnik Simulator - Steuerungsoberfläche")
st.caption("Draufsicht mit SPS-gebundenen HRL-, RBG-, Förderband- und VSG-Werten.")

if ss.running:
    st.info(f"{ss.current_action.upper()} wird ausgeführt. Bitte warten.")
elif ss.last_error:
    with st.expander("Fehlerdetails", expanded=True):
        st.code(ss.last_error, language="python")
elif ss.last_result is not None:
    st.success("Letzte Aktion erfolgreich abgeschlossen.")

col_init, col_start, col_reset, col_pad = st.columns(
    [1.3, 1.3, 1.3, 5.1]
)

with col_init:
    if st.button(
        "Init",
        disabled=ss.running,
        use_container_width=True,
        type="primary",
    ):
        _start_action("init", action_init)
        st.rerun()

with col_start:
    if st.button(
        "Start",
        disabled=ss.running,
        use_container_width=True,
        type="primary",
    ):
        _start_action("start", action_start)
        st.rerun()

with col_reset:
    if st.button(
        "Reset",
        disabled=ss.running,
        use_container_width=True,
    ):
        _start_action("reset", action_reset)
        st.rerun()

sensor_rows = []
actuator_rows = []
udint_rows = []

if "_error" not in ss.sensors:
    for key in cfg.SENSOR_POLL_SYMBOLS:
        value = ss.sensors.get(key)
        if value is None:
            continue

        sensor_rows.append(
            {
                "Signal": cfg.SENSOR_LABELS.get(key, key),
                "Wert": "Ein" if value else "Aus",
            }
        )

    for key in cfg.ACTUATOR_POLL_SYMBOLS:
        value = ss.sensors.get(key)
        if value is None:
            continue

        actuator_rows.append(
            {
                "Aktor/Zustand": cfg.ACTUATOR_LABELS.get(key, key),
                "Wert": "Ein" if value else "Aus",
            }
        )

    for key in cfg.UDINT_POLL_SYMBOLS:
        value = ss.udints.get(key)
        if value is None:
            continue
        if (
            key == "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorCode"
            and not ss.sensors.get("VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected", False)
        ):
            value = 0

        udint_rows.append(
            {
                "Wert": cfg.UDINT_LABELS.get(key, key),
                "UDINT": value,
            }
        )

st.markdown("---")
components.html(
    f"""
    <div style="margin:4px 0 12px 0">
        {build_process_svg(
            ss.sensors,
            ss.udints,
            missing_workpiece_at_pickup=ss.missing_workpiece_at_pickup,
            workpiece_stage=ss.workpiece_stage,
        )}
    </div>
    """,
    height=1120,
    scrolling=False,
)

sensor_col, actuator_col, udint_col = st.columns([1, 1, 1], gap="medium")

with sensor_col:
    st.subheader("Sensorwerte")
    if "_error" in ss.sensors:
        st.error(f"ADS-Verbindungsfehler: {ss.sensors['_error']}")
    elif sensor_rows:
        st.dataframe(
            sensor_rows,
            hide_index=True,
            use_container_width=True,
            height=320,
            column_config={
                "Signal": st.column_config.TextColumn("Signal", width="medium"),
                "Wert": st.column_config.TextColumn("Wert", width="small"),
            },
        )
    else:
        st.caption("Keine Sensorwerte verfügbar.")

with actuator_col:
    if actuator_rows:
        st.subheader("Aktoren und Skillstatus")
        st.dataframe(
            actuator_rows,
            hide_index=True,
            use_container_width=True,
            height=320,
            column_config={
                "Aktor/Zustand": st.column_config.TextColumn("Aktor/Zustand", width="medium"),
                "Wert": st.column_config.TextColumn("Wert", width="small"),
            },
        )

with udint_col:
    if udint_rows:
        st.subheader("Encoder und Schrittwerte")
        st.dataframe(
            udint_rows,
            hide_index=True,
            use_container_width=True,
            height=320,
            column_config={
                "Wert": st.column_config.TextColumn("Wert", width="medium"),
                "UDINT": st.column_config.NumberColumn("UDINT", width="small"),
            },
        )

if ss.strings:
    st.markdown("**OPC-UA Tracking**")
    for key, value in ss.strings.items():
        display_value = value.strip("\x00") if value else ""
        st.markdown(f"- `{key}`: `{display_value or '(leer)'}`")

if ss.running:
    time.sleep(0.25)
    st.rerun()
