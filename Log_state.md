SCN6 — Development State

Last updated: 2026-08-29

Current State

SCN6 TMBSCOM driver and Textual TUI are working with the test controller.

Current hardware:

Controller: SCN6
Test axis: 0
COM port: COM6
Baud: 115200
Python: 3.12 32-bit
DLL: Tmbscom.DLL
Supported axis range: 0..F

Recent TUI hardware test:

TMBSCOM reached TMBS_RUNNING (4)
Axis 0 detected
Homing command issued
Incremental -1000 movement accepted twice
Incremental +1000 movement accepted
Physical movement requires operator confirmation
Architecture
Scn6.ini
   ↓
scn6_config.py
   ↓
SCN6Driver
   ↓
scn6_dll.py
   ↓
Tmbscom.DLL
   ↓
SCN6 / Termi-BUS / RS485


Interfaces:

CLI ──┐
      ├──> SCN6Driver ──> Tmbscom.DLL
TUI ──┘


Rules:

scn6_dll.py owns hardware communication.
scn6_driver.py remains the public driver facade.
CLI is the engineering/test interface.
TUI is the operator interface.
TUI must not construct raw Termi-BUS frames.
New hardware functions should be tested through the driver/CLI before TUI integration.
Driver

scn6_dll.py provides:

TMBSCOM DLL loading and calls
initialization
communication state
axis discovery
axis status
position readback
servo control
incremental movement
absolute movement
homing
alarm reset
prepared motion
memory/parameter/point APIs

scn6_driver.py provides the stable SCN6Driver interface.

Initialization

TMBSCOM may initially report:

result = 0
state  = 3 (TMBS_OPENING)


This is an intermediate state, not automatically a fatal error.

Successful initialization requires:

TMBS_RUNNING = 4


The TUI should trust the driver's initialize() result/state handling and must not require the initial return value to be SIO_DONE.

If initialization fails repeatedly, check the physical COM/USB connection before diagnosing software.

Configuration

Scn6.ini controls:

COM port
baud rate
NRT
RESET
AUTOMATIC
minimum axis
maximum axis

The same configuration/driver path must be used by CLI and TUI.

TUI

Location:

Tui/
├── __init__.py
├── README.md
├── app.py
├── confirm.py
├── connection.py
├── motion.py
├── run_tui.py
├── status.py
└── ui.py


The TUI provides:

connection/disconnection
axis discovery
live status
position
servo control
incremental movement
absolute movement
homing
alarm reset
configuration
operator log
confirmation dialogs

Physical operations require explicit operator confirmation.

Safety

Before any physical operation the TUI must show:

selected axis
operation
distance or target position
relevant servo state
explicit confirmation

Do not bypass driver safety checks.

Do not replace tested DLL operations with manually constructed serial frames.

Verified / Tested
Hardware-tested
TMBSCOM connection
COM6 communication
Axis 0 discovery
Axis 0 status
Incremental movement -1000
Incremental movement +1000
Implemented but still requiring dedicated verification
Absolute movement
Homing completion
Servo ON/OFF through TUI
Alarm reset
Configuration reload/save
Safe disconnect/reconnect
Memory APIs
Multi-axis operation

A feature is implemented when the software interface exists.

A feature is verified only after testing against the real SCN6 controller.

Known TUI Issue

Connection has sometimes required more than one attempt.

Observed behavior:

CONNECT
→ initialization result 0

later CONNECT
→ TMBS_RUNNING (4)
→ axis 0 detected


This needs to be made reliable so the operator does not need to reconnect manually.

Ctrl+Q must also close the driver and exit the Textual application cleanly.

Current Priority
Make CONNECT reliable on the first attempt.
Verify clean DISCONNECT.
Verify Ctrl+Q shutdown.
Verify axis status and position updates after movement.
Verify homing completion.
Verify servo ON/OFF.
Verify absolute movement.
Verify configuration is actually applied.
Verify alarm reset.
Only then continue with multi-axis functionality.
Multi-Axis

Target axis range:

0..F


Prepared movement currently does not constitute hardware-synchronized multi-axis motion.

True synchronized execution must use documented TMBSCOM functionality and be verified against the controller/documentation.

Do not start Q1/Q2/Q3 or synchronized multi-axis development until the single-axis functions are stable.

Development Rule
CLI / TUI
    ↓
SCN6Driver
    ↓
scn6_dll.py
    ↓
Tmbscom.DLL
    ↓
SCN6


Keep the hardware-control layer separate from the operator interface.

Do not modify working DLL bindings or motion functions without hardware or documentation justification.