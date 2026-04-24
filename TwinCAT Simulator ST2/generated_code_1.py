import time

def MBS_MR01_AS_SecuringProcess(V_10000000001:bool, V_20000000000:bool, V_20000000001:bool, V_20000000002, V_20000000003:UDint, V_20000000004:bool, V_20000000005:int, V_20000000006:int):
    """Auto-generated from PLCopen XML (vereinfachte Semantik)."""

    def EXECUTE(V_10000000001):
        'EXECUTE block – original ST-Code:\nCASE state OF\n\t0:\n\t\tIF jobRunning THEN\n\t\t\tstate := state + 1;\n\t\tEND_IF\n\t\t\n\t1:\n\t\tIF ResetMethodCall THEN\n\t\t\tjobRunning := FALSE;\n\t\t\tjobFinished := TRUE;\n\t\t\tstate := 0;\n\t\t\tMethodCall_SecuringProcess := FALSE;\n\t\tEND_IF\n\t\t\nEND_CASE'
        result = V_10000000001
        return result

    def SecuringWorkpiece(V_20000000000, V_20000000001, V_20000000002, V_20000000003, V_20000000004, V_20000000005, V_20000000006):
        result = V_20000000006
        return result

    V_20000000007 = SecuringWorkpiece(V_20000000000, V_20000000001, V_20000000002, V_20000000003, V_20000000004, V_20000000005, V_20000000006)
    V_20000000008 = V_20000000007
    print('Value of DO_SecuringProcessCompressorMR01_01:', V_20000000008)
    return {'DO_SecuringProcessCompressorMR01_01': V_20000000008}