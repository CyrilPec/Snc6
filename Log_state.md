SCN6 PROJECT — DEVELOPMENT STATE

Last updated: 2026-08-29

1. Current Version

v22 — Textual TUI and configuration integration

v22 is under active development.

The project currently has:

SCN6/TMBSCOM DLL driver
command-line engineering/test interface
thin public SCN6Driver facade
modular Textual TUI
INI configuration loader
multi-axis driver foundation
TMBSCOM memory API discovery

v22 is not yet hardware-ready.

2. Hardware
Controller: SCN6
Current test axis: 0
Target axes: 0..F
Communication: RS485 / Termi-BUS
Current Windows COM port: COM6
DLL: Tmbscom.DLL
Required Python: 3.12 32-bit
Python command:
py -3.12-32

3. Architecture
Scn6.ini
    ↓
scn6_config.py
    ↓
SCN6Config
    ↓
SCN6Driver
    ↓
scn6_dll.py
    ↓
Tmbscom.DLL
    ↓
Termi-BUS / RS485
    ↓
SCN6 controller


CLI and TUI are interfaces over the same driver.

CLI ──┐
      ├──> SCN6Driver ──> Tmbscom.DLL
TUI ──┘

Architecture rules
CLI is the engineering/reference interface.
TUI is the operator interface.
Hardware communication remains in scn6_dll.py.
scn6_driver.py remains the public driver facade.
TUI modules must not construct raw Termi-BUS frames.
Do not replace tested DLL operations with manually constructed serial frames.
New hardware functionality should first be proven through the driver/CLI and then exposed through the TUI.
4. Current Python Files
scn6_dll.py

This is the main TMBSCOM DLL binding and hardware-control layer.

Currently provides:

DLL loading
TMBSCOM function binding
communication state
axis discovery
axis status
position readback
servo ON/OFF
incremental movement
absolute movement
homing
alarm reset
SVMEM access
parameter access
point access
prepared motion
multi-axis fallback execution
motion completion monitoring

import time is present.

Initialization status

Current implementation contains an initialization loop, but it is not yet compliant with the required polling behavior.

Current code:

loops up to 200 times
uses 0.05 seconds while state is TMBS_OPENING
uses 0.01 seconds otherwise
requires both result == SIO_DONE and state 4

The required behavior is:

init_tmbs_config()
       ↓
read communication state
       ↓
if state == 4:
    initialization successful
       ↓
otherwise wait approximately 5 ms
       ↓
poll again


An initial:

result = 0
state  = 3


must not automatically be treated as a fatal initialization error.

Required initialization change

Use approximately:

POLL_DELAY = 0.005
MAX_POLLS  = 200


Initialization success must be based on:

communication state == 4


Do not introduce undefined constants such as:

TMBS_RUNNING
TMBS_ERROR
TMBS_CLOSED


because those named constants are not currently defined.

The existing state table is:

-1  SIO_COMUSED
-2  SIO_TIMEOUT
-5  SIO_INVALID_PARAM
-6  SIO_NOTSUPORT_TO
-8  SIO_NOTSUPORT_BAUD
-9  SIO_NOTSUPORT_PARA
-10 SIO_NO_CONFIGFILE
-12 TMBS_INIT_ERROR / COM OPEN FAILURE
 2  TMBS_INIT_ERROR
 3  TMBS_OPENING
 4  TMBS_RUNNING

5. Initialization Hardware Note

A previous TMBS_OPENING (3) observation was determined to be caused by a loose USB cable.

Therefore:

physical communication problems must not automatically be classified as software initialization failures
USB/COM connection must be checked before diagnosing the polling implementation
successful Python execution does not prove hardware initialization

The polling implementation still needs to be corrected and tested according to the TMBSCOM behavior.

6. scn6_driver.py

scn6_driver.py is intentionally thin.

Current public facade:

SCN6Driver
    axis_status()
    axis_position()
    connected_axes()
    prepare_absolute()
    prepare_incremental()
    execute_prepared()


It inherits the hardware implementation from TmbsController.

The facade should remain the stable interface for:

CLI
TUI
future Mach3 interface
future LinuxCNC interface
7. Configuration
scn6_config.py

Provides:

SCN6Config
load_config()


Configuration fields:

communication.port
communication.baud
communication.nrt
communication.reset
communication.automatic

driver.axis_min
driver.axis_max


Axis range is interpreted as hexadecimal and must remain within:

0..F

Current problem

The configuration loader exists, but configuration is not yet correctly propagated into the driver initialization path.

scn6_cli.py currently calls:

SCN6Driver(config=load_config())


but the current SCN6Driver / TmbsController constructor does not accept a config argument.

Therefore configuration integration is not complete.

Required next change

The driver must accept SCN6Config and use:

port
baud
nrt
reset
automatic


when calling the existing TMBSCOM initialization function.

Do not create a second hardware interface.

8. Scn6.ini

Scn6.ini is the intended project configuration file.

It must control:

COM port
baud
NRT
RESET
AUTOMATIC
axis_min
axis_max


The configuration must be applied by the common driver used by both CLI and TUI.

9. CLI

scn6_cli.py is the engineering and hardware-test interface.

Current command groups include:

Connection / diagnostics
init
axes
diag
exports

Status / position
status <axis>
status_all
position <axis>
pos <axis>
read_status_memory <axis>

Direct motion
move_inc <axis> <distance> CONFIRM
move_abs <axis> <position> CONFIRM

Servo / safety
servo_on <axis> CONFIRM
servo_off <axis> CONFIRM
alarm_reset <axis> CONFIRM
home <axis> <mode> CONFIRM

Prepared motion
prepare_abs <axis> <position>
prepare_inc <axis> <distance>
show_buffer
clear_buffer
start_all CONFIRM

Memory
read_svmem
write_svmem
read_param
write_param
read_point
write_point
load_param
save_param
save_point
reset_memory
select_svparm
write_trqlim

Current CLI problem

The CLI currently attempts:

SCN6Driver(config=load_config())


while the driver constructor currently accepts no configuration argument.

This must be fixed before configuration integration can be considered complete.

10. CLI Priority

CLI remains the engineering/reference interface.

Required order:

Fix initialization polling.
Fix configuration propagation.
Test initialization on COM6.
Confirm axis 0 discovery.
Confirm axis 0 status.
Confirm position readback.
Confirm servo ON.
Confirm servo OFF.
Confirm incremental movement.
Confirm absolute movement.
Confirm homing.
Confirm alarm reset.
Verify memory APIs.
Only then continue with multi-axis synchronization.

Do not add unnecessary new motion functionality before these tests are complete.

11. Baseline Hardware Test

The established baseline is:

init
axes
status 0
servo_on 0 CONFIRM
move_inc 0 -1000 CONFIRM
status 0
servo_off 0 CONFIRM


For absolute movement:

move_abs 0 <position> CONFIRM


All physical operations require explicit confirmation.

12. Known Working Functionality

Previously established functionality:

servo ON
servo OFF
incremental movement
status
position
axis discovery
all-axis status
TMBSCOM DLL initialization path
memory API discovery
direct DLL motion functions

These are considered software-level working functionality.

They are not automatically considered hardware-verified after code changes.

13. Verification Rule

A feature is:

Implemented

when the software interface exists.

A feature is:

Verified

only after it has been tested against the real SCN6 controller.

Do not mark the following verified from Python execution alone:

initialization
physical movement
homing
servo operation
alarm reset
multi-axis synchronization
14. TUI

The current TUI is a modular Textual application under:

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


The TUI is intended to provide:

connection
configuration
live axis status
position
servo control
incremental movement
absolute movement
homing
alarm reset
confirmation dialogs
operator log
diagnostics

The TUI must use the same SCN6Driver operations as the CLI.

15. TUI Launcher Problem

Current Tui/run_tui.py contains:

from scn6_tui_v2.app import SCN6TUI


but the repository currently contains:

Tui/app.py


rather than:

Tui/scn6_tui_v2/app.py


Therefore the launcher is currently inconsistent with the actual repository structure.

Required fix

The launcher should import the actual TUI package/module structure.

Do not create a second TUI implementation just to satisfy the launcher.

16. TUI Connection

Tui/connection.py correctly uses:

SCN6Driver


for hardware ownership.

The connection flow is:

CONNECT
   ↓
SCN6Driver()
   ↓
driver.initialize()
   ↓
refresh_connected_axes()
   ↓
display TMBSCOM state
   ↓
display connected axes


However, because configuration is not yet correctly passed into the driver, the TUI configuration path is not yet complete.

17. TUI Safety

Physical operations require confirmation.

The TUI must show:

selected axis
operation
movement distance/position
servo state where relevant
explicit confirmation

The TUI must not bypass driver safety checks.

18. Memory API

Previously discovered TMBSCOM APIs:

reset_memory
read_svmem
write_svmem
read_param
write_param
read_point
write_point
load_param
save_param
save_point
select_svparm
write_trqlim


These APIs should be verified against the real controller before being considered hardware-verified.

19. Q1 / Q2 / Q3

Q1/Q2/Q3 are documented memory/execution mechanisms.

Current rule:

use actual TMBSCOM APIs where available
do not invent raw Termi-BUS frames
verify behavior against EE06426I-EN and the TMBSCOM documentation

True synchronized multi-axis execution is not yet verified.

The current prepared-motion implementation dispatches DLL movement commands rapidly in sequence.

It is explicitly not hardware-synchronized.

20. Multi-Axis Goal

Target:

0..F


Every axis should eventually support:

status
position
servo control
parameter read
parameter write where supported
motion preparation
physical movement
alarm handling

Then implement documented synchronized/all-axis execution.

Two SCN6 controllers may share the RS485 bus, but their axis addresses must remain unique.

21. Current Tasks
Immediate
Correct scn6_dll.py initialization polling.
Use approximately 5 ms polling delay.
Treat TMBS_RUNNING (4) as initialization completion.
Do not require the intermediate result to be SIO_DONE.
Test initialization on COM6.
Confirm axis 0.
Next
Fix SCN6Config propagation into SCN6Driver.
Verify Scn6.ini values are actually used.
Verify CLI initialization output.
Verify axis 0 status.
Verify position.
Verify servo ON/OFF.
Verify incremental movement.
Verify absolute movement.
Verify homing.
Verify alarm reset.
Fix Tui/run_tui.py package import.
Test TUI connection using the same driver as CLI.
Test TUI status.
Test TUI motion controls.
Later
Verify memory APIs.
Build multi-axis abstraction.
Verify Q1/Q2/Q3 documentation/API.
Implement real synchronized execution.
Add multi-axis TUI controls.
Develop Mach3 interface.
Develop LinuxCNC interface.
22. Do Not Change

Do not change without hardware or documentation justification:

working DLL bindings
tested motion functions
axis numbering
Termi-BUS protocol assumptions
TMBSCOM API semantics
established safety checks

Do not replace tested DLL calls with raw serial protocol code.

Do not turn the TUI into a replacement hardware-control layer.

23. Development Principle
CLI = engineering / test interface

TUI = operator interface

Both
  ↓
SCN6Driver
  ↓
Tmbscom.DLL
  ↓
SCN6


Any new SCN6 hardware operation should first be proven through the common driver/CLI and then exposed safely through the TUI.

24. Next Milestones
v22 — TUI and configuration

Required before declaring v22 hardware-ready:

correct initialization polling
successful COM6 initialization
correct Scn6.ini loading
configuration applied to the driver
axis 0 discovery
axis 0 status
position
servo ON/OFF
incremental movement
absolute movement
safe disconnect
working TUI launcher
no CLI/driver regression
v23 — Multi-axis

Focus:

axes 0..F
prepared motion
documented synchronized execution
Q1/Q2/Q3 verification
operator controls
Future
SVMEM editor
parameter editor
point editor
multi-axis motion editor
Mach3 interface
LinuxCNC interface
25. Current Status Summary
Area	Status
DLL binding	Working
import time	Present
Driver facade	Working
CLI command framework	Working
Direct motion API	Existing/working
Axis 0 target	Defined
Initialization polling	Needs correction
5 ms polling	Not yet applied on current main
INI loader	Implemented
INI → driver	Not complete
CLI config construction	Currently incompatible with driver constructor
TUI modules	Present
TUI driver architecture	Correct direction
TUI launcher	Import path currently wrong
Memory API discovery	Done
Multi-axis preparation	Implemented
Hardware synchronization	Not verified / not implemented
Q1/Q2/Q3	Documentation/API verification pending
v22 hardware-ready	No
26. Immediate Action

Do not start Q1/Q2/Q3 or multi-axis synchronization yet.

The next code changes should be limited to:

1. scn6_dll.py
   → correct initialization polling

2. scn6_driver.py / scn6_dll.py
   → accept and apply SCN6Config

3. scn6_cli.py
   → use the corrected configuration/driver path

4. Tui/run_tui.py
   → correct launcher import

5. Hardware test on COM6


After those are stable, continue with the TUI hardware verification.Termi-BUS / RS485
    ↓
SCN6


The TUI must remain a presentation/control layer.

The existing SCN6 driver and DLL binding remain the hardware-control layer.

No raw Termi-BUS frames are generated by the TUI.

CONFIGURATION

Scn6.ini is required for correct driver initialization.

Configuration currently contains:

communication.port
communication.baud
communication.nrt
communication.reset
communication.automatic
driver.axis_min
driver.axis_max

scn6_config.py provides the SCN6Config dataclass and load_config() parser.

The TUI uses the INI configuration as the source of connection settings.

The Connection tab should provide:

COM port
baud rate
NRT
reset
automatic
minimum axis
maximum axis
reload configuration
save configuration
connect
disconnect

The TUI applies the loaded configuration to the existing TMBSCOM initialization path rather than creating a second hardware interface.

INITIALIZATION

Known TMBSCOM behavior:

init_tmbs_config() may initially return:

result = 0
state = TMBS_OPENING (3)


This is not necessarily an initialization error.

The TMBSCOM manual specifies polling with a short delay until initialization reaches:

TMBS_RUNNING = 4

REQUIRED

Initialization polling must be completed and tested before declaring v22 hardware-ready.

The TUI must not interpret an initial TMBS_OPENING state as a successful connection.

CURRENT TUI DESIGN

The Textual TUI is intended to provide:

Connection
load Scn6.ini
edit communication parameters
save configuration
reload configuration
connect/disconnect
display TMBSCOM communication state
Axis status

For each configured axis:

servo
run
alarm
origin
PFIN
controller position
connected state

Axis visibility is controlled by:

axis_min .. axis_max

Manual motion

Planned/implemented interface:

axis selection
absolute position
incremental positive move
incremental negative move
home
Servo / safety
servo ON
servo OFF
alarm reset
refresh
confirmation before physical actions
Logging

The TUI provides an operator log containing:

connection events
initialization results
configuration values
motion requests
motion results
errors
status information
SAFETY

The TUI must not bypass the existing driver safety checks.

Direct movement continues to use the existing SCN6 driver methods.

Before physical operations, the TUI displays an explicit confirmation dialog.

Do not invent new Termi-BUS frames or replace tested DLL calls with manually constructed protocol messages.

KNOWN-GOOD TEST

Previously established test:

servo_on 0 CONFIRM
move_inc 0 -1000 CONFIRM
status 0
servo_off 0 CONFIRM


This remains the baseline hardware regression test.

WORKING FUNCTIONALITY

Previously verified:

servo_on
servo_off
move_inc
status
position
axes
status_all
TMBSCOM DLL initialization path
memory API discovery

The following TUI functionality is being integrated around these existing driver capabilities:

connection
live axis status
servo control
incremental motion
absolute motion
homing
alarm reset
configuration management

These TUI functions must still be hardware-tested before being marked as independently verified.

DRIVER API

scn6_driver.py remains intentionally thin.

Current facade:

axis_status()
axis_position()
connected_axes()
prepare_absolute()
prepare_incremental()
execute_prepared()


The TUI should use this public driver interface where possible.

Hardware/DLL implementation should remain below the SCN6Driver API.

MEMORY API

Available DLL APIs previously found:

reset_memory
read_svmem
write_svmem
read_param
write_param
read_point
write_point
load_param
save_param
save_point
select_svparm
write_trqlim

Q1/Q2/Q3:

documented as memory-control mechanisms
must use the actual TMBSCOM API
do not invent raw wire frames
Q3 is believed to provide multi-axis execution/start functionality
verify against EE06426I-EN and TMBSCOM documentation
MULTI-AXIS GOAL

Target support:

0..F


Each axis should eventually support:

parameter read
parameter write where supported
status
position
servo control
motion preparation

Then provide synchronized/all-axis execution using the actual TMBSCOM functionality.

Two SCN6 controllers may share one RS485 bus, but their axis addresses must remain unique.

CURRENT TASKS
Complete/fix initialization polling.
Test initialization on COM6.
Confirm axis 0.
Confirm status.
Confirm servo ON/OFF.
Confirm incremental movement.
Confirm absolute movement.
Confirm homing.
Confirm alarm reset.
Verify Scn6.ini configuration is correctly applied during initialization.
Verify TUI configuration reload/save.
Verify all TUI physical controls against the real controller.
Verify memory APIs.
Build multi-axis abstraction.
Implement Q1/Q2/Q3 execution after documentation verification.
Add multi-axis controls to the TUI.
Build Mach3/LinuxCNC interface.
DO NOT CHANGE

Do not change without hardware/documentation justification:

working DLL bindings
working motion functions
axis numbering
Termi-BUS protocol assumptions
proven v20/v21 functionality
TMBSCOM API semantics

The TUI must not become a replacement for the tested driver layer.

IMPORTANT DEVELOPMENT RULE

A feature is implemented when the software interface exists.

A feature is verified only after it has been tested against the SCN6 controller.

Do not mark physical motion, initialization, or multi-axis synchronization as verified based solely on successful Python execution.

NEXT MILESTONE
v22

Complete the Textual TUI and configuration integration.

Required before v22 is considered hardware-ready:

successful initialization polling
correct Scn6.ini loading
correct COM/baud/NRT/reset/automatic application
axis 0 status
servo ON/OFF
incremental move
absolute move
safe disconnect
no regression of the existing CLI/driver functionality
v23

Multi-axis preparation and execution.

Focus:

axes 0..F
prepared motion
synchronized execution
Q1/Q2/Q3 verification
operator controls in the Textual TUI
FUTURE
memory/parameter editor
point editor
multi-axis motion editor
Mach3 interface
LinuxCNC interface
init_tmbs_config() may initially return:

result = 0
state = TMBS_OPENING (3)

This is NOT necessarily an error.

The TMBSCOM manual specifies polling with a short delay
until initialization completes.

Expected final state:

TMBS_RUNNING = 4

## KNOWN-GOOD TEST

servo_on 0 CONFIRM

move_inc 0 -1000 CONFIRM

status 0

servo_off 0 CONFIRM

## STATUS

Working:
- servo_on
- servo_off
- move_inc
- status
- position
- axes
- status_all
- TMBSCOM DLL initialization
- memory API discovery

## MEMORY API

Available DLL APIs found in v14:

- reset_memory
- read_svmem
- write_svmem
- read_param
- write_param
- read_point
- write_point
- load_param
- save_param
- save_point
- select_svparm
- write_trqlim

Q1/Q2/Q3:
- documented as memory-control mechanisms
- must use the actual TMBSCOM API
- do not invent raw wire frames
- Q3 is believed to provide multi-axis execution/start functionality
- verify against EE06426I-EN and TMBSCOM documentation

## MULTI-AXIS GOAL

Support axes:

0..F

Each axis must be individually addressable for:
- reading parameters
- writing parameters where supported
- reading status
- position
- servo control
- motion preparation

Then provide a synchronized/all-axis execution command.

Two SCN6 controllers may share one RS485 bus, but their
axis addresses must be unique.

## CURRENT TASK
## Initialization Polling

Status: FIXED in d224083.

The initialization routine now:
- polls TMBSCOM every 5 ms
- allows up to 200 polls (1 second)
- reads communication state after each initialization call
- considers initialization successful when state reaches 4 (TMBS_RUNNING)
- does not require the intermediate init result to be SIO_DONE
- treats states -12 and 2 as initialization errors

Fix v21 initialization.

Current observed behavior:

final init result : 0
communication state: 3 (TMBS_OPENING)
initialized: False

Repeated manual `init` commands do not reliably advance the
communication state.

Expected solution:
poll init_tmbs_config() with approximately 5 ms delay,
following the TMBSCOM manual.

## DO NOT CHANGE

Do not change:
- working DLL bindings
- working motion functions
- axis numbering
- Termi-BUS protocol assumptions
- proven v20.1 functionality

TUI Improvement Priority
Confirmed baseline
SCN6 initialization is working.
Previous TMBS_OPENING (3) observation was caused by a loose USB cable.
Do not treat that observation as an initialization software fault.
CLI is the engineering/reference interface.
TUI should use the same proven SCN6 driver operations as CLI.
Priority order

Verify TUI uses the same proven driver operations as CLI

Initialization
Axis discovery
Servo ON/OFF
Status
Position
Motion
Memory/parameter/point operations

Connection and initialization indication

COM/USB connection state
TMBSCOM state
SCN6 online/offline state
Clear indication of communication failure
Do not misinterpret physical communication problems as software initialization faults

Motion safety

Explicit confirmation before movement
Clear selected axis
Servo state visible before movement
Increment/distance clearly displayed
Safe handling of communication loss

Real-time axis/status display

Position
Servo state
Controller status
Alarm/error state
Selected axis
Motion state

Diagnostics screen

COM port
TMBSCOM state
DLL state
Initialization state
Axis availability
Last operation/result

Operation/event log

Timestamped operations
Initialization events
Servo operations
Motion commands
Errors/results
Communication state changes

Advanced TUI functions

SVMEM
Parameters
Points
Execution/Q1/Q2/Q3

TUI code refactoring

Reduce duplication
Separate screens/widgets/state
Keep SCN6 communication logic in the common driver
Refactor incrementally without breaking working functionality

Q1/Q2/Q3 operator interface

Add after the underlying TUI and driver functionality is stable.
Development principle

CLI = engineering/test interface.

TUI = operator interface.

Both must use the same proven SCN6 driver functionality. Any new SCN6 operation should first be proven through the driver/CLI and then exposed safely through the TUI.


