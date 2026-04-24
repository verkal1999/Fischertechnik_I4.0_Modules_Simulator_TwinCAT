# Auto-generated intermediate representation from PLCopen XML

POU = {
    'pou_name': 'MBS_MR01_AS_SecuringProcess',
    'pou_type': 'functionBlock',
    'input_vars': ['ESS:BOOL', 'TouchSensor_01:BOOL', 'AutomaticMode:BOOL', 'hdl:UDINT', 'hdl:UDINT', 'MethodCall:BOOL', 'Securing_Time:TIME', 'SecuringProcessing_Time:TIME'],
    'output_vars': ['DO_SecuringProcessCompressorMR01_01:BOOL', 'DO_SecuringProcessValveMR01_02:BOOL', 'bBusy:BOOL', 'State:BOOL', 'MethodCall:BOOL', 'hdl:UDINT'],
    'local_vars': ['AlwaysTrue:BOOL', 'MethodCall_SecuringProcess:BOOL', 'ResetMethodCall:BOOL', 'SecuringTime:TIME', 'SecuringProcessingTime:TIME', 'callCounterStart:ULINT', 'callCounterCheckState:ULINT', 'callCounterAbort:ULINT', 'jobRunning:BOOL', 'jobFinished:BOOL', 'state:UDINT', 'MBS_MR01_SecuringProcess:derived'],
    'input_ids': [{'Expression': 'AlwaysTrue', 'InVariable': '10000000001'}, {'Expression': 'MethodCall_SecuringProcess', 'InVariable': '20000000000'}, {'Expression': 'ESS', 'InVariable': '20000000001'}, {'Expression': None, 'InVariable': '20000000002'}, {'Expression': 'TouchSensor_01', 'InVariable': '20000000003'}, {'Expression': 'SecuringTime', 'InVariable': '20000000004'}, {'Expression': 'SecuringProcessingTime', 'InVariable': '20000000005'}, {'Expression': 'AutomaticMode', 'InVariable': '20000000006'}],
    'output_ids': [{'Expression': 'DO_SecuringProcessCompressorMR01_01', 'OutVariable': '20000000008', 'SourceLocalId': '20000000007'}],
}

B1 = {'name': 'B1', 'block_localId': '10000000002', 'typeName': 'EXECUTE', 'pou_name': 'MBS_MR01_AS_SecuringProcess', 'block_position': {'x': '0', 'y': '0'}, 'inputVariables': ['10000000001'], 'variable': ['EN', 'ENO'], 'connectionpointIn': ['connectionPointIn'], 'connection_refLocalId': ['10000000001'], 'stcode': 'CASE state OF\n\t0:\n\t\tIF jobRunning THEN\n\t\t\tstate := state + 1;\n\t\tEND_IF\n\t\t\n\t1:\n\t\tIF ResetMethodCall THEN\n\t\t\tjobRunning := FALSE;\n\t\t\tjobFinished := TRUE;\n\t\t\tstate := 0;\n\t\t\tMethodCall_SecuringProcess := FALSE;\n\t\tEND_IF\n\t\t\nEND_CASE'}
B2 = {'name': 'B2', 'block_localId': '20000000007', 'typeName': 'SecuringWorkpiece', 'pou_name': 'MBS_MR01_AS_SecuringProcess', 'block_position': {'x': '0', 'y': '0'}, 'inputVariables': ['20000000000', '20000000001', '20000000002', '20000000003', '20000000004', '20000000005', '20000000006'], 'variable': ['MethodCall', 'EmergencyStopSignal', 'InitStateDrive_Input', 'DI01', 'TON_Time_Securing', 'TON_Time_SecuringProcess', 'OperatingMode', 'DigitalOutputControl_01', 'DigitalOutputControl_02', 'ResetMethodCall'], 'connectionpointIn': ['connectionPointIn', 'connectionPointIn', 'connectionPointIn', 'connectionPointIn', 'connectionPointIn', 'connectionPointIn', 'connectionPointIn'], 'connection_refLocalId': ['20000000000', '20000000001', '20000000002', '20000000003', '20000000004', '20000000005', '20000000006'], 'stcode': None}

