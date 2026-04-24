import time

def MBS_MR01_AS_SecuringProcess(AlwaysTrue: bool, MethodCall_SecuringProcess: bool, ESS: bool, V_20000000002, TouchSensor_01: UDint, SecuringTime: bool, SecuringProcessingTime: int, AutomaticMode: int):
    """Auto-generated from PLCopen XML (vereinfachte Semantik)."""

    def EXECUTE(V_10000000001):
        """EXECUTE block – original ST-Code:
CASE state OF
	0:
		IF jobRunning THEN
			state := state + 1;
		END_IF
		
	1:
		IF ResetMethodCall THEN
			jobRunning := FALSE;
			jobFinished := TRUE;
			state := 0;
			MethodCall_SecuringProcess := FALSE;
		END_IF
		
END_CASE"""
        result = AlwaysTrue
        return result

    def SecuringWorkpiece(V_20000000000, V_20000000001, V_20000000002, V_20000000003, V_20000000004, V_20000000005, V_20000000006):
        result = AutomaticMode
        return result
    V_20000000007 = SecuringWorkpiece(MethodCall_SecuringProcess, ESS, V_20000000002, TouchSensor_01, SecuringTime, SecuringProcessingTime, AutomaticMode)
    DO_SecuringProcessCompressorMR01_01 = V_20000000007
    print('Value of DO_SecuringProcessCompressorMR01_01:', DO_SecuringProcessCompressorMR01_01)
    return {'DO_SecuringProcessCompressorMR01_01': DO_SecuringProcessCompressorMR01_01}