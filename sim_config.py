"""Zentrale Konfiguration fuer die Streamlit-Oberflaeche."""

from Simulation import HrlAuslagernRequest, OpcUaConnectionConfig, VsgCompressorControlRequest

# Sensoren, die im UI angezeigt und gepollt werden
SENSOR_POLL_SYMBOLS = [
    "ts_ausleger_vorne",
    "ts_ausleger_hinten",
    "ls_inner",
    "ls_outer",
    "GVL_HRL.HRL_LS_innen",
    "GVL_HRL.HRL_LS_aussen",
    "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected",
    "diag_finished",
    "VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished",
]

SENSOR_LABELS = {
    "ts_ausleger_vorne": "TS Ausleger vorne",
    "ts_ausleger_hinten": "TS Ausleger hinten",
    "ls_inner": "ls_innen (Band-Anfang)",
    "ls_outer": "ls_aussen (Band-Ende)",
    "GVL_HRL.HRL_LS_innen": "RGB LS innen (Runtime)",
    "GVL_HRL.HRL_LS_aussen": "RGB LS aussen (Runtime)",
    "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected": "VSG Fehler",
    "diag_finished": "OPC UA Diag_finished",
    "VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished": "VSG Diagnosehandler Diag_finished",
}
OPC_CONFIG = OpcUaConnectionConfig(
    username="AdminVD",
    password="123456",
)

HRL_REQUEST = HrlAuslagernRequest(
    method_call=True,
    horizontal_shelf_i1=1000,
    horizontal_shelf_i2=1000,
    vertical_shelf_i1=500,
    vertical_shelf_i2=500,
    horizontal_transfer_i1=0,
    horizontal_transfer_i2=0,
    vertical_transfer_i1=0,
    vertical_transfer_i2=0,
    timeout_ms=12000,
)

VSG_REQUEST = VsgCompressorControlRequest(
    method_call=True,
    destination_reached=True,
    encoder_target_position_01=100,
    encoder_target_position_02=100,
    encoder_target_position_03=200,
    encoder_target_position_04=200,
    encoder_target_position_05=300,
    encoder_target_position_06=300,
)

START_VSG_AFTER_HRL_SUCCESS = True
VSG_WORKPIECE_AT_PICKUP = False
SET_VSG_ERROR_FALSE_BEFORE_VSG = True
SET_DIAG_FINISHED_TRUE_BEFORE_VSG = False
