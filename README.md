# Fischertechnik I4.0 HRL Simulation for TwinCAT

This repository contains a Python-based simulator and operator interface for a
Fischertechnik I4.0 demonstrator scenario. It was created as part of a master's
thesis and was used together with the Manufacturing ExcH Agents project:

https://github.com/verkal1999/Manufacturing-ExcH-Agents

The simulator supports an application example in which an agent-based error
handling workflow is evaluated on a high-bay warehouse module (Hochregallager). The original
setup is based on the Fischertechnik 24 V factory simulation and a Beckhoff
TwinCAT PLC program. Because a laboratory test on the physical PLC setup was
affected by a PLC-related issue, this repository provides a simulation layer for
the PLC-side signals and skill execution flow.

![High-bay warehouse module](assets/HRL.svg)

## Purpose

The project reproduces a representative material handling process of the
high-bay warehouse module. The simulated process focuses on the retrieval of a
workpiece from storage and its transfer to the conveyor end position. A
manually caused fault is then reproduced by removing the workpiece from the
expected sensor position. This allows the surrounding monitoring and agent
system to classify and process the resulting deviation.

The scenario demonstrates how the following parts interact:

- TwinCAT PLC logic for the high-bay warehouse module
- OPC UA method calls for PLC skills
- ADS communication with the TwinCAT PLC runtime on port 851
- Simulated PLC variables with the `_Sim` suffix
- GEMMA-based operating states and error state transitions
- SkillOA-based skill execution and process tracking
- MSRGuard and ExcH agent-based error handling

## System Context

The high-bay warehouse module contains a rack-serving unit with horizontal and
vertical axes, a telescopic pusher, and a conveyor on the transfer side. The PLC
program uses encoder values, reference switches, limit switches, light barriers,
and motor outputs to control and monitor the process.

In the real setup, the OPC UA server exposes PLC methods for skills such as
`HRL_NMethod_Auslagern`. The OPC UA call is forwarded through TwinCAT ADS to the
PLC runtime on port 851. The PLC then controls physical inputs and outputs
through the I/O process image, which is commonly associated with ADS port 300.

In the simulation setup, the skill call chain remains the same, but the hardware
I/O layer is replaced by symbolic simulation variables. When
`GVL_Sim.bSimMode` is enabled, the PLC logic reads and writes simulated signal
values instead of physical input and output signals. This keeps the original
program structure largely unchanged while making the process reproducible
without the physical demonstrator.

## Simulated Scenario

The main process starts with the skill `HRL_NMethod_Auslagern`. This composite
skill represents the retrieval of a workpiece from the high-bay warehouse and
its transfer to the conveyor. It combines lower-level movement skills for the
horizontal axis, vertical axis, pusher, and conveyor.

The regular process contains three main workpiece states:

1. The workpiece is stored in the rack.
2. The workpiece is transferred to the beginning of the conveyor.
3. The workpiece reaches the end of the conveyor.

The fault scenario is triggered by simulating the manual removal of the
workpiece at the conveyor end. The relevant outer light barrier signal is set to
`FALSE`, which represents the missing workpiece at the expected pickup
position. The subsequent VSG suction process checks this signal and can trigger
`VSG_ErrorDetected`, causing the PLC operating mode to transition into the
fault state `D2`.

The PLC-side tracking variables such as `OPCUA.lastExecutedSkill`,
`OPCUA.lastFinishedSkill`, and related process state values provide the context
needed by the agent system to reconstruct the executed skill sequence and
classify the fault.

## Repository Contents

- `Simulation.py` contains the core Python classes for ADS access, OPC UA method
  calls, skill execution planning, and helper data structures.
- `sim_config.py` contains the scenario configuration, OPC UA connection
  settings, request payloads, and UI sensor mappings.
- `sim_actions.py` maps the notebook-style workflow to executable actions such
  as initialization, process start, automated fault injection, reset, and sensor
  polling.
- `app.py` provides a Streamlit-based user interface for executing and
  monitoring the simulated scenario.
- `Sim.ipynb` and `Test_Notebook.ipynb` contain exploratory and test workflows
  used during development.
- `Szenario.plantuml` and `Szenario_Sim.plantuml` describe the communication and
  process sequence diagrams.
- `TwinCAT Simulator ST2/` contains exported TwinCAT-related simulation and
  mapping data.

## Python Environment

The simulator was restored and verified with Python 3.12.1 on Windows. Create a
local virtual environment in the repository root and install the runtime
packages with:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install streamlit pyads opcua cryptography ipykernel
```

The directly used Python packages are:

- `streamlit` for the operator interface
- `pyads` for TwinCAT ADS access
- `opcua` for OPC UA client communication
- `cryptography` for OPC UA client certificates
- `ipykernel` for the included notebooks

The following package set was exported from the current `.venv` with
`pip freeze`:

<details>
<summary>Exact Python dependencies</summary>

```text
altair==6.1.0
anyio==4.13.0
asttokens==3.0.1
attrs==26.1.0
blinker==1.9.0
cachetools==7.0.6
certifi==2026.4.22
cffi==2.0.0
charset-normalizer==3.4.7
click==8.3.3
colorama==0.4.6
comm==0.2.3
cryptography==47.0.0
debugpy==1.8.20
decorator==5.2.1
executing==2.2.1
gitdb==4.0.12
GitPython==3.1.49
h11==0.16.0
httptools==0.7.1
idna==3.13
ipykernel==7.2.0
ipython==9.13.0
ipython_pygments_lexers==1.1.1
itsdangerous==2.2.0
jedi==0.19.2
Jinja2==3.1.6
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
jupyter_client==8.8.0
jupyter_core==5.9.1
lxml==6.1.0
MarkupSafe==3.0.3
matplotlib-inline==0.2.1
narwhals==2.20.0
nest-asyncio==1.6.0
numpy==2.4.4
opcua==0.98.13
packaging==26.2
pandas==3.0.2
parso==0.8.6
pillow==12.2.0
platformdirs==4.9.6
prompt_toolkit==3.0.52
protobuf==7.34.1
psutil==7.2.2
pure_eval==0.2.3
pyads==3.5.2
pyarrow==24.0.0
pycparser==3.0
pydeck==0.9.2
Pygments==2.20.0
python-dateutil==2.9.0.post0
python-multipart==0.0.27
pytz==2026.1.post1
pyzmq==27.1.0
referencing==0.37.0
requests==2.33.1
rpds-py==0.30.0
six==1.17.0
smmap==5.0.3
stack-data==0.6.3
starlette==1.0.0
streamlit==1.57.0
tenacity==9.1.4
toml==0.10.2
tornado==6.5.5
traitlets==5.14.3
typing_extensions==4.15.0
tzdata==2026.2
urllib3==2.6.3
uvicorn==0.46.0
watchdog==6.0.0
wcwidth==0.6.0
websockets==16.0
```

</details>

## Running the UI

Install the required Python packages in your environment, then start the
Streamlit interface from the repository root:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

The default configuration expects a reachable TwinCAT runtime and OPC UA server
matching the symbols and endpoint configured in `sim_config.py` and
`Simulation.py`. Certificates for secure OPC UA communication are expected in
the `certs/` directory.

The Streamlit frontend provides a top-view visualization of the simulated
high-bay warehouse scenario. It shows the rack, rack-serving unit, conveyor,
VSG pickup area, current SPS-bound state values, sensor states, actuator states,
and encoder/step values. During the fault scenario, the workpiece is shown at
the outer conveyor light barrier before it is removed and the VSG skill detects
the missing workpiece.

![Streamlit frontend showing the simulated HRL, conveyor, VSG state, and SPS values](assets/Screenshot_UI.png)

## Typical Workflow

1. Prepare the TwinCAT PLC runtime and enable simulation mode.
2. Start the Streamlit UI.
3. Run the initialization action to prepare PLC variables and skill plans.
4. Start `HRL_NMethod_Auslagern`.
5. Observe the automated workpiece removal at the conveyor end and the resulting
   VSG fault detection.
6. Use the reset action to clear the VSG fault state for another run.

## Relation to Manufacturing ExcH Agents

This repository provides the simulated PLC and skill execution side of the
application example. The agent-based error handling, knowledge access, and
classification workflow were used together with the separate Manufacturing ExcH
Agents repository:

https://github.com/verkal1999/Manufacturing-ExcH-Agents

Together, both repositories demonstrate how PLC skill execution, process
monitoring, knowledge-based context reconstruction, and agent-supported error
handling can be combined for a Fischertechnik I4.0 demonstrator scenario.

## Academic Context

This implementation was developed as part of a master's thesis. Its purpose is
to support the evaluation of an agent-based error handling approach for modular
manufacturing systems using a reproducible simulation of a Fischertechnik
high-bay warehouse scenario.

## License

Unless otherwise noted, the author's own source code, documentation, simulation
logic, and TwinCAT project files in this repository are licensed under the MIT
License.

Third-party software, tools, libraries, trademarks, and generated artifacts
remain subject to their respective license terms. Beckhoff TwinCAT itself,
Beckhoff-provided libraries, and other Beckhoff software components are not
licensed under this repository's MIT License and must be used under the
applicable Beckhoff license terms.
