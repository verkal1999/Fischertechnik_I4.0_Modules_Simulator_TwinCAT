"""Zentrale Konfiguration für die Streamlit-Oberfläche."""

from Simulation import HrlAuslagernRequest, OpcUaConnectionConfig, VsgCompressorControlRequest

# Sensoren, die im UI angezeigt werden
SENSOR_POLL_SYMBOLS = [
    "sim",
    "notaus_a",
    "notaus_b",
    "ts_ausleger_vorne",
    "ts_ausleger_hinten",
    "ts_horizontal",
    "ts_vertical",
    "ls_inner",
    "ls_outer",
    "GVL_HRL.HRL_LS_innen",
    "GVL_HRL.HRL_LS_aussen",
    "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected",
    "diag_finished",
    "VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished",
]

ACTUATOR_POLL_SYMBOLS = [
    "GVL_HRL_Sim.HRL_MOT_horizontal_zum_Regal",
    "GVL_HRL_Sim.HRL_MOT_horizontal_zum_Foerderband",
    "GVL_HRL_Sim.HRL_MOT_vertikal_runter",
    "GVL_HRL_Sim.HRL_MOT_vertikal_hoch",
    "GVL_HRL_Sim.HRL_MOT_Ausleger_vorwaerts",
    "GVL_HRL_Sim.HRL_MOT_Ausleger_rueckwaerts",
    "GVL_HRL_Sim.HRL_MOT_Foerderband_vorwaerts",
    "GVL_HRL_Sim.HRL_MOT_Foerderband_rueckwaerts",
    "HRL_SkillSet.HRL_NMethod_Auslagern.Busy",
    "HRL_SkillSet.HRL_NMethod_Auslagern.Done",
    "HRL_SkillSet.HRL_NMethod_Auslagern.Error",
    "GVL_VSG_Sim.VSG_MOT_vertikal_runter",
    "GVL_VSG_Sim.VSG_MOT_vertikal_hoch",
    "GVL_VSG_Sim.VSG_MOT_horizontal_vorwaerts",
    "GVL_VSG_Sim.VSG_MOT_horizontal_rueckwaerts",
    "GVL_VSG_Sim.VSG_MOT_drehen_CW",
    "GVL_VSG_Sim.VSG_MOT_drehen_CCW",
    "GVL_VSG_Sim.VSG_Kompressor",
    "GVL_VSG_Sim.VSG_MV_Vakuum",
]

BOOL_POLL_SYMBOLS = list(dict.fromkeys(SENSOR_POLL_SYMBOLS + ACTUATOR_POLL_SYMBOLS))

UDINT_POLL_SYMBOLS = [
    "horizontal_1",
    "horizontal_2",
    "vertical_1",
    "vertical_2",
    "HRL_SkillSet.HRL_NMethod_Auslagern.CurrentStep",
    "HRL_SkillSet.HRL_NMethod_Auslagern.ErrorId",
    "vsg_rotation_1",
    "vsg_rotation_2",
    "vsg_horizontal_1",
    "vsg_horizontal_2",
    "vsg_vertical_1",
    "vsg_vertical_2",
    "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorCode",
]

SENSOR_LABELS = {
    "sim": "Simulationsmodus",
    "notaus_a": "Not-Aus Kanal A",
    "notaus_b": "Not-Aus Kanal B",
    "ts_ausleger_vorne": "TS Ausleger vorne",
    "ts_ausleger_hinten": "TS Ausleger hinten",
    "ts_horizontal": "Ref. horizontal",
    "ts_vertical": "Ref. vertikal",
    "ls_inner": "ls_inner",
    "ls_outer": "ls_outer",
    "GVL_HRL.HRL_LS_innen": "LS innen (Bandanfang)",
    "GVL_HRL.HRL_LS_aussen": "LS außen (Bandende)",
    "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorDetected": "VSG Fehler",
    "diag_finished": "OPC UA Diag_finished",
    "VSG_SkillSet.VSG_DiagnosisHandler.Diag_finished": "VSG Diagnosehandler Diag_finished",
}

ACTUATOR_LABELS = {
    "GVL_HRL_Sim.HRL_MOT_horizontal_zum_Regal": "HRL Motor horizontal zum Regal",
    "GVL_HRL_Sim.HRL_MOT_horizontal_zum_Foerderband": "HRL Motor horizontal zum Förderband",
    "GVL_HRL_Sim.HRL_MOT_vertikal_runter": "HRL Motor vertikal runter",
    "GVL_HRL_Sim.HRL_MOT_vertikal_hoch": "HRL Motor vertikal hoch",
    "GVL_HRL_Sim.HRL_MOT_Ausleger_vorwaerts": "HRL Ausleger vorwärts",
    "GVL_HRL_Sim.HRL_MOT_Ausleger_rueckwaerts": "HRL Ausleger rückwärts",
    "GVL_HRL_Sim.HRL_MOT_Foerderband_vorwaerts": "HRL Förderband vorwärts",
    "GVL_HRL_Sim.HRL_MOT_Foerderband_rueckwaerts": "HRL Förderband rückwärts",
    "HRL_SkillSet.HRL_NMethod_Auslagern.Busy": "HRL Auslagern Busy",
    "HRL_SkillSet.HRL_NMethod_Auslagern.Done": "HRL Auslagern Done",
    "HRL_SkillSet.HRL_NMethod_Auslagern.Error": "HRL Auslagern Error",
    "GVL_VSG_Sim.VSG_MOT_vertikal_runter": "VSG Motor vertikal runter",
    "GVL_VSG_Sim.VSG_MOT_vertikal_hoch": "VSG Motor vertikal hoch",
    "GVL_VSG_Sim.VSG_MOT_horizontal_vorwaerts": "VSG Motor horizontal vorwärts",
    "GVL_VSG_Sim.VSG_MOT_horizontal_rueckwaerts": "VSG Motor horizontal rückwärts",
    "GVL_VSG_Sim.VSG_MOT_drehen_CW": "VSG drehen CW",
    "GVL_VSG_Sim.VSG_MOT_drehen_CCW": "VSG drehen CCW",
    "GVL_VSG_Sim.VSG_Kompressor": "VSG Kompressor",
    "GVL_VSG_Sim.VSG_MV_Vakuum": "VSG Ventil Vakuum",
}

UDINT_LABELS = {
    "horizontal_1": "HRL Encoder horizontal I1",
    "horizontal_2": "HRL Encoder horizontal I2",
    "vertical_1": "HRL Encoder vertikal I1",
    "vertical_2": "HRL Encoder vertikal I2",
    "HRL_SkillSet.HRL_NMethod_Auslagern.CurrentStep": "HRL Auslagern CurrentStep",
    "HRL_SkillSet.HRL_NMethod_Auslagern.ErrorId": "HRL Auslagern ErrorId",
    "vsg_rotation_1": "VSG Encoder drehen I1",
    "vsg_rotation_2": "VSG Encoder drehen I2",
    "vsg_horizontal_1": "VSG Encoder horizontal I1",
    "vsg_horizontal_2": "VSG Encoder horizontal I2",
    "vsg_vertical_1": "VSG Encoder vertikal I1",
    "vsg_vertical_2": "VSG Encoder vertikal I2",
    "VSG_SkillSet.VSG_Skill_SuctionProcess.VSG_ErrorCode": "VSG ErrorCode",
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
VSG_WAIT_FOR_LS_AUSSEN_TIMEOUT_SECONDS = 20.0
VSG_LS_AUSSEN_DWELL_SECONDS = 5.0
VSG_MISSING_WORKPIECE_PREVIEW_SECONDS = 1.0
VSG_MISSING_WORKPIECE_MARKER = "missing_workpiece_at_ls_aussen"
SET_VSG_ERROR_FALSE_BEFORE_VSG = True
SET_DIAG_FINISHED_TRUE_BEFORE_VSG = False
