SCN6 G-code / SimulIDE Project Log

Date: 2026-08-30
Repository: CyrilPec/Snc6
Working branch: Dll-changed-and-update

Goal

Build a system where an Arduino Mega running inside SimulIDE sends G-code through a serial/virtual COM port to scn6_server.py.

Target chain:

SimulIDE 2
  └── Arduino Mega
        │
        │ G-code / Serial
        ▼
  scn6_server.py
        │
        ├── Serial receiver
        ├── Lark G-code parser
        ├── G-code interpreter / machine state
        │
        ▼
  scn6_driver.py
        │
        ▼
  scn6_dll.py / TmbsController
        │
        ▼
  TMBSCOM / TERMI-BUS
        │
        ▼
  SCN6 actuator

Important architecture decision

Use the existing scn6_driver.py.

Do NOT reimplement TERMI-BUS in the new G-code server.

scn6_server.py should operate above the existing SCN6 stack:

G-code
 → Lark
 → G-code command
 → SCN6Driver
 → existing DLL implementation
 → SCN6


Lark handles G-code syntax/state. It does not handle TERMI-BUS.

Important correction

Earlier we created/proposed machine.py, but after checking the current Dll-changed-and-update branch we decided:

Remove machine.py.

Reason: the current SCN6Driver/TmbsController already provides the hardware abstraction. A second machine wrapper would duplicate functionality.

If multiple backends are introduced later (real SCN6 vs pure simulator), a machine/backend abstraction can be added then.

Current desired project layout
Snc6/
├── scn6_server.py
├── scn6_driver.py
├── scn6_dll.py
│
└── gcode/
    ├── __init__.py
    ├── grammar.lark
    ├── commands.py
    ├── parser.py
    └── interpreter.py

Existing SCN6 API

The current branch has a much smaller/cleaner SCN6Driver facade than previously assumed.

Use the actual API from:

scn6_driver.py
scn6_dll.py


Important movement methods include:

driver.direct_move_absolute(axis, position)
driver.direct_move_incremental(axis, distance)

driver.prepare_absolute_move(...)
driver.prepare_incremental_move(...)
driver.start_prepared_moves(...)


The prepared multi-axis implementation currently dispatches axes sequentially and is not true hardware-synchronized interpolation. Do not claim G1 X100 Y100 is coordinated interpolation yet.

The driver/DLL also has initialization, axis discovery, status/position, servo and alarm-related functionality.

G-code first milestone

Initially support:

G90
G91

G0 X100
G1 X200 F500

M3
M5

M114
M999


G28 should be added only after checking the exact homing API in the current branch.

G-code state

The interpreter should maintain:

absolute / incremental mode
current logical X/Y/Z position
current feed rate


Example:

G90
G0 X100
G91
G0 X20


means:

G90 → absolute mode
G0 X100 → absolute X=100
G91 → incremental mode
G0 X20 → X=120

Feed rate

F should initially be parsed and stored, but do not guess the conversion to SCN6 velocity units.

The existing DLL exposes velocity-related functionality, but the exact mapping between G-code feed rate and SCN6 velocity must be established from the SCN6/TERMI-BUS documentation before sending values to hardware.

Serial protocol

Initial SimulIDE → server protocol should be deliberately simple:

G90\n
G0 X100\n
G1 X200 F500\n
M3\n


Server replies:

ok\n
ok\n
ok\n
ok\n


Errors:

error: ...


One complete G-code command per serial line.

The Arduino Mega in SimulIDE is primarily the G-code sender. It does not need to implement SCN6/TERMI-BUS.

SimulIDE role

SimulIDE 2 should provide:

Arduino Mega
   ↓
Serial
   ↓
virtual COM port
   ↓
scn6_server.py


The exact SimulIDE 2 serial/COM configuration still needs to be tested.

TERMI-BUS documentation

Relevant document:

DocumentationTERMIBUS-EE06426I-EN.pdf


We want to use this as the protocol specification, but the existing scn6_driver.py / scn6_dll.py remains the implementation layer unless functionality is missing.

Do not duplicate the TERMI-BUS implementation unnecessarily.

Next task

Continue by inspecting the current Dll-changed-and-update branch APIs carefully, then implement:

gcode/grammar.lark
gcode/commands.py
gcode/parser.py
gcode/interpreter.py
scn6_server.py

First end-to-end target:

SimulIDE Mega
   ↓
Serial
   ↓
scn6_server.py
   ↓
Lark
   ↓
G-code interpreter
   ↓
SCN6Driver.direct_move_absolute()
       or
SCN6Driver.direct_move_incremental()
   ↓
existing SCN6 DLL stack


Do not modify scn6_driver.py unless inspection shows a specific missing wrapper/function needed by the G-code layer.

Key principle

Keep the layers separate:

G-code language
      ↓
Lark/parser/interpreter
      ↓
SCN6Driver API
      ↓
TERMI-BUS/DLL
      ↓
SCN6 hardware


The first goal is a working, testable G-code-to-SCN6 path, not a complete CNC controller.

Continuation phrase:
“Continue SCN6 project from the 2026-08-30 log.”