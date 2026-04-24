"""
Streamlit-Oberflaeche fuer den Fischertechnik-Simulator.

Aufruf:
    streamlit run app.py
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict

import streamlit as st

import sim_config as cfg
from sim_actions import (
    action_init,
    action_manual_remove_workpiece,
    action_reset,
    action_start,
    read_bool_sensors,
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
        background:
            radial-gradient(circle at top left, rgba(74, 182, 143, 0.10), transparent 28%),
            radial-gradient(circle at top right, rgba(104, 141, 255, 0.08), transparent 24%),
            linear-gradient(180deg, #09111c 0%, #0c1726 100%);
        color: #dce7f5;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0.8rem;
    }
    .stButton > button {
        font-size: 0.98rem;
        font-weight: 600;
        border-radius: 10px;
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
        "strings": {},
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
        ss.sensors = read_bool_sensors()
    except Exception as exc:
        ss.sensors = {"_error": str(exc)}

    try:
        ss.strings = read_string_values()
    except Exception:
        ss.strings = {}


def _c(sensors: dict, key: str) -> str:
    return "#2fce83" if sensors.get(key, False) else "#4e5f77"


def _err_c(sensors: dict, key: str) -> str:
    return "#ff5a4f" if sensors.get(key, False) else "#2fce83"


def _svg_lamp_row(x: int, y: int, label: str, fill: str) -> str:
    return (
        f'<circle cx="{x}" cy="{y}" r="7" fill="{fill}" stroke="#09111a" stroke-width="1.4"/>'
        f'<circle cx="{x}" cy="{y}" r="11" fill="none" stroke="{fill}" stroke-opacity="0.28" stroke-width="2"/>'
        f'<text x="{x + 16}" y="{y + 4}" font-size="9.5" fill="#dbe6f4">{label}</text>'
    )


def build_process_svg(sensors: dict) -> str:
    ts_front = bool(sensors.get("ts_ausleger_vorne", False))
    ts_back = bool(sensors.get("ts_ausleger_hinten", False))
    ls_inner = bool(sensors.get("ls_inner", False))
    ls_outer = bool(sensors.get("ls_outer", False))

    rgb_runtime_inner = bool(sensors.get("GVL_HRL.HRL_LS_innen", False))
    rgb_runtime_outer = bool(sensors.get("GVL_HRL.HRL_LS_aussen", False))
    vsg_error = bool(
        sensors.get("VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected", False)
    )
    opc_diag_finished = bool(sensors.get("diag_finished", False))
    vsg_diag_finished = bool(
        sensors.get("VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished", False)
    )
    c_ts_front = _c(sensors, "ts_ausleger_vorne")
    c_ts_back = _c(sensors, "ts_ausleger_hinten")
    c_ls_inner = _c(sensors, "ls_inner")
    c_ls_outer = _c(sensors, "ls_outer")
    c_rgb_inner = _c(sensors, "GVL_HRL.HRL_LS_innen")
    c_rgb_outer = _c(sensors, "GVL_HRL.HRL_LS_aussen")
    c_vsg_error = _err_c(sensors, "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected")
    c_opc_diag = _c(sensors, "diag_finished")
    c_vsg_diag = _c(sensors, "VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished")

    if ls_outer:
        workpiece_x, workpiece_y = 616, 167
        step_label = "Schritt 3: Werkstueck steht am Bandende fuer die VSG-Aufnahme bereit."
    elif ls_inner:
        workpiece_x, workpiece_y = 350, 167
        step_label = "Schritt 2: Werkstueck hat den Bandanfang erreicht."
    elif ts_front:
        workpiece_x, workpiece_y = 246, 166
        step_label = "RGB faehrt aus: Werkstueck wird aus dem Regal auf das Band uebergeben."
    elif ts_back:
        workpiece_x, workpiece_y = 104, 160
        step_label = "Schritt 1: Werkstueck liegt im Regalbediengeraet im Rueckzugsbereich."
    else:
        workpiece_x, workpiece_y = -100, -100
        step_label = "Kein Werkstueck eindeutig detektiert."

    fork_extension = 60 if ts_front else 30 if ts_back else 42
    fork_fill = "#f6b73c" if ts_front else "#8090a7"
    carriage_glow = "#89d7ff" if ts_front else "#5e7692"
    active_shelf_fill = "#274257" if ts_back and not ls_inner and not ls_outer else "#162334"
    active_shelf_stroke = "#78c4ff" if ts_back and not ls_inner and not ls_outer else "#2a4158"

    if workpiece_x > 0:
        workpiece_anim = (
            '<animate attributeName="opacity" values="1;0.45;1" dur="0.65s" repeatCount="indefinite"/>'
            if ts_front
            else ""
        )
        workpiece = (
            f'<g>'
            f'<rect x="{workpiece_x - 12}" y="{workpiece_y - 12}" width="24" height="24" rx="5" '
            f'fill="#f1a329" stroke="#ffcf6b" stroke-width="2">{workpiece_anim}</rect>'
            f'<line x1="{workpiece_x - 5}" y1="{workpiece_y}" x2="{workpiece_x + 5}" y2="{workpiece_y}" '
            f'stroke="#7f4d00" stroke-width="1.4"/>'
            f'<line x1="{workpiece_x}" y1="{workpiece_y - 5}" x2="{workpiece_x}" y2="{workpiece_y + 5}" '
            f'stroke="#7f4d00" stroke-width="1.4"/>'
            f'</g>'
        )
    else:
        workpiece = ""

    belt_stripes = "".join(
        f'<line x1="{x}" y1="148" x2="{x}" y2="186" stroke="#1b252c" stroke-width="2"/>'
        for x in range(332, 652, 28)
    )

    rgb_lamps = "".join(
        [
            _svg_lamp_row(40, 242, "TS Ausleger vorne", c_ts_front),
            _svg_lamp_row(40, 265, "TS Ausleger hinten", c_ts_back),
            _svg_lamp_row(40, 288, "RGB LS innen (Runtime)", c_rgb_inner),
            _svg_lamp_row(40, 311, "RGB LS aussen (Runtime)", c_rgb_outer),
        ]
    )

    conveyor_lamps = "".join(
        [
            _svg_lamp_row(302, 290, "ls_innen Band-Anfang", c_ls_inner),
            _svg_lamp_row(500, 290, "ls_aussen Band-Ende", c_ls_outer),
        ]
    )

    vsg_lamps = "".join(
        [
            _svg_lamp_row(730, 242, "VSG Fehler", c_vsg_error),
            _svg_lamp_row(730, 265, "OPC UA Diag_finished", c_opc_diag),
            _svg_lamp_row(730, 288, "VSG Diagnosis Diag_finished", c_vsg_diag),
        ]
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 350"
    style="width:100%;background:#0b1420;border-radius:18px;font-family:Segoe UI,Arial,sans-serif;">
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="#7c90a8"/>
    </marker>
    <filter id="softGlow">
      <feGaussianBlur stdDeviation="2.6" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <rect x="0" y="0" width="920" height="42" rx="18" fill="#111b2c"/>
  <text x="460" y="26" text-anchor="middle" font-size="13" font-weight="700" fill="#dbe7f7">{step_label}</text>

  <rect x="16" y="58" width="248" height="272" rx="18" fill="#122233" stroke="#335d86" stroke-width="1.8"/>
  <text x="38" y="84" font-size="20" font-weight="800" fill="#8cd0ff">RGB</text>
  <text x="38" y="101" font-size="10" fill="#7ea2c5">Regalbediengeraet</text>

  <rect x="32" y="114" width="116" height="98" rx="10" fill="#101928" stroke="#2d4058" stroke-width="1.2"/>
  <rect x="48" y="126" width="88" height="14" rx="3" fill="#172435" stroke="#25384d" stroke-width="1"/>
  <rect x="48" y="146" width="88" height="14" rx="3" fill="#172435" stroke="#25384d" stroke-width="1"/>
  <rect x="48" y="166" width="88" height="14" rx="3" fill="{active_shelf_fill}" stroke="{active_shelf_stroke}" stroke-width="1.4"/>
  <rect x="48" y="186" width="88" height="14" rx="3" fill="#172435" stroke="#25384d" stroke-width="1"/>
  <line x1="48" y1="124" x2="48" y2="202" stroke="#31465e" stroke-width="3"/>
  <line x1="136" y1="124" x2="136" y2="202" stroke="#31465e" stroke-width="3"/>

  <rect x="174" y="108" width="12" height="116" rx="5" fill="#20364f" stroke="#4f7396" stroke-width="1.2"/>
  <rect x="160" y="151" width="38" height="30" rx="7" fill="#19314c" stroke="{carriage_glow}" stroke-width="1.8"
        filter="{'url(#softGlow)' if ts_front else 'none'}"/>
  <rect x="198" y="163" width="{fork_extension}" height="6" rx="3" fill="{fork_fill}" stroke="#f7d890" stroke-width="1.1"/>
  <rect x="{198 + fork_extension - 8}" y="159" width="8" height="14" rx="2" fill="{fork_fill}" stroke="#f7d890" stroke-width="1.1"/>
  <circle cx="180" cy="142" r="5" fill="#89a8c7"/>
  <circle cx="180" cy="192" r="5" fill="#89a8c7"/>
  <text x="34" y="226" font-size="9.5" fill="#96aec7">I/O direkt am RGB</text>
  {rgb_lamps}

  <line x1="262" y1="166" x2="286" y2="166" stroke="#6a7f96" stroke-width="2" marker-end="url(#arr)"/>

  <rect x="278" y="58" width="406" height="272" rx="18" fill="#122016" stroke="#2c6f46" stroke-width="1.8"/>
  <text x="302" y="84" font-size="20" font-weight="800" fill="#8ce0a6">FOERDERBAND</text>
  <text x="302" y="101" font-size="10" fill="#87b798">Werkstueck-Transport und Lichtschranken</text>
  <rect x="324" y="148" width="338" height="38" rx="8" fill="#1a2329" stroke="#4d626d" stroke-width="1.1"/>
  {belt_stripes}
  <circle cx="324" cy="167" r="18" fill="#20292f" stroke="#6d838f" stroke-width="2"/>
  <circle cx="324" cy="167" r="6" fill="#12181c" stroke="#8ba0ad" stroke-width="1"/>
  <circle cx="662" cy="167" r="18" fill="#20292f" stroke="#6d838f" stroke-width="2"/>
  <circle cx="662" cy="167" r="6" fill="#12181c" stroke="#8ba0ad" stroke-width="1"/>
  <polygon points="442,160 456,165 442,170" fill="#5cb67d" opacity="0.85"/>
  <polygon points="482,160 496,165 482,170" fill="#5cb67d" opacity="0.85"/>
  <polygon points="522,160 536,165 522,170" fill="#5cb67d" opacity="0.85"/>

  <line x1="350" y1="148" x2="350" y2="124" stroke="#7d93ac" stroke-width="1.1" stroke-dasharray="4,3"/>
  <circle cx="350" cy="114" r="10" fill="{c_ls_inner}" stroke="#101820" stroke-width="1.6"
          filter="{'url(#softGlow)' if ls_inner else 'none'}"/>
  <text x="350" y="96" text-anchor="middle" font-size="9" fill="#d9e7f4">ls_innen</text>
  <text x="350" y="84" text-anchor="middle" font-size="8" fill="#92a6bc">Band-Anfang</text>

  <line x1="616" y1="148" x2="616" y2="124" stroke="#7d93ac" stroke-width="1.1" stroke-dasharray="4,3"/>
  <circle cx="616" cy="114" r="10" fill="{c_ls_outer}" stroke="#101820" stroke-width="1.6"
          filter="{'url(#softGlow)' if ls_outer else 'none'}"/>
  <text x="616" y="96" text-anchor="middle" font-size="9" fill="#d9e7f4">ls_aussen</text>
  <text x="616" y="84" text-anchor="middle" font-size="8" fill="#92a6bc">Band-Ende</text>
  <text x="302" y="226" font-size="9.5" fill="#96c4a3">I/O direkt am Foerderband</text>
  {conveyor_lamps}

  <line x1="684" y1="166" x2="710" y2="166" stroke="#6a7f96" stroke-width="2" marker-end="url(#arr)"/>

  <rect x="698" y="58" width="206" height="272" rx="18" fill="#201327" stroke="#7d4d93" stroke-width="1.8"/>
  <text x="730" y="84" font-size="20" font-weight="800" fill="#e0a7ff">VSG</text>
  <text x="730" y="101" font-size="10" fill="#c895df">Vakuumsauggreifer</text>
  <rect x="722" y="118" width="158" height="12" rx="6" fill="#3a2445" stroke="#9468a8" stroke-width="1"/>
  <rect x="790" y="130" width="22" height="62" rx="8" fill="#452753" stroke="#b283c9" stroke-width="1.4"/>
  <ellipse cx="801" cy="200" rx="24" ry="10" fill="#2a1533" stroke="#c294db" stroke-width="1.4"/>
  <ellipse cx="801" cy="199" rx="13" ry="5" fill="#5b2e6e" stroke="#e1b6f8" stroke-width="1"/>
  <rect x="760" y="146" width="82" height="10" rx="5" fill="#533061" stroke="#cb9ce2" stroke-width="1"/>
  <text x="722" y="226" font-size="9.5" fill="#d8c2e6">I/O direkt am VSG</text>
  {vsg_lamps}

  {workpiece}

  <rect x="0" y="334" width="920" height="16" rx="8" fill="#111b2c"/>
  <text x="24" y="346" font-size="9" fill="#cad7e6">Legende:</text>
  <circle cx="84" cy="343" r="5" fill="#2fce83"/>
  <text x="94" y="346" font-size="9" fill="#cad7e6">aktiv</text>
  <circle cx="146" cy="343" r="5" fill="#4e5f77"/>
  <text x="156" y="346" font-size="9" fill="#cad7e6">inaktiv</text>
  <circle cx="220" cy="343" r="5" fill="#ff5a4f"/>
  <text x="230" y="346" font-size="9" fill="#cad7e6">Fehler</text>
  <text x="546" y="346" font-size="9" fill="#cad7e6">RGB Runtime innen={str(rgb_runtime_inner)} | aussen={str(rgb_runtime_outer)} | VSG Fehler={str(vsg_error)} | OPC={str(opc_diag_finished)} | VSG Diag={str(vsg_diag_finished)}</text>
</svg>"""


_drain_queues()
_refresh_sensors()

st.title("Fischertechnik Simulator - Steuerungsoberflaeche")
st.caption("RGB-Darstellung, Sensorstatus und manuelle Werkstueck-Entnahme in einer Ansicht.")

if ss.running:
    st.info(f"{ss.current_action.upper()} wird ausgefuehrt. Bitte warten.")
elif ss.last_error:
    with st.expander("Fehlerdetails", expanded=True):
        st.code(ss.last_error, language="python")
elif ss.last_result is not None:
    st.success("Letzte Aktion erfolgreich abgeschlossen.")

col_init, col_start, col_reset, col_remove, col_clear, col_pad = st.columns(
    [1.3, 1.3, 1.3, 1.9, 1.2, 2.0]
)

with col_init:
    if st.button(
        "Init (Zelle 1)",
        disabled=ss.running,
        use_container_width=True,
        type="primary",
    ):
        _start_action("init", action_init)
        st.rerun()

with col_start:
    if st.button(
        "Start (Zelle 2)",
        disabled=ss.running,
        use_container_width=True,
        type="primary",
    ):
        _start_action("start", action_start)
        st.rerun()

with col_reset:
    if st.button(
        "Reset (Zelle 3)",
        disabled=ss.running,
        use_container_width=True,
    ):
        _start_action("reset", action_reset)
        st.rerun()

with col_remove:
    if st.button(
        "Werkstueck manuell entnehmen",
        disabled=ss.running,
        use_container_width=True,
    ):
        _start_action("manuelle_entnahme", action_manual_remove_workpiece)
        st.rerun()

with col_clear:
    if st.button("Log leeren", use_container_width=True):
        ss.log_lines = []
        st.rerun()

st.markdown("---")
st.markdown(
    f'<div style="margin:4px 0 12px 0">{build_process_svg(ss.sensors)}</div>',
    unsafe_allow_html=True,
)

sensor_col, log_col = st.columns([1, 1.15], gap="medium")

with sensor_col:
    st.subheader("Sensorwerte")

    if "_error" in ss.sensors:
        st.error(f"ADS-Verbindungsfehler: {ss.sensors['_error']}")
    else:
        rows = []
        for key in cfg.SENSOR_POLL_SYMBOLS:
            value = ss.sensors.get(key)
            if value is None:
                continue

            rows.append(
                {
                    "Sensor": cfg.SENSOR_LABELS.get(key, key),
                    "Wert": "True" if value else "False",
                }
            )

        if rows:
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            st.caption("Keine Sensorwerte verfuegbar.")

    if ss.strings:
        st.markdown("**OPC-UA Tracking**")
        for key, value in ss.strings.items():
            display_value = value.strip("\x00") if value else ""
            st.markdown(f"- `{key}`: `{display_value or '(leer)'}`")

with log_col:
    st.subheader("Protokoll")
    log_text = "\n".join(ss.log_lines[-80:])
    st.text_area(
        label="log",
        value=log_text,
        height=340,
        disabled=True,
        label_visibility="collapsed",
        key="log_area",
    )

if ss.running:
    time.sleep(1)
    st.rerun()
