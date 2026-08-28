# SCN6 PROJECT — DEVELOPMENT STATE

Last updated: 2026-08-28

## CURRENT VERSION

v21 — initialization polling fix in progress.

## HARDWARE

Controller:
- SCN6
- currently testing axis 0
- future range: axes 0..F
- RS485 / Termi-BUS
- current Windows COM port: COM6

## SOFTWARE

Python:
- Python 3.12.0rc3 32-bit
- command: py -3.12-32

DLL:
- Tmbscom.DLL
- accessed directly through Python binding

## ARCHITECTURE

CLI
  ↓
SCN6 Driver
  ↓
TmbsSCOM DLL
  ↓
Termi-BUS / RS485
  ↓
SCN6

No raw Termi-BUS frames are currently generated.

## KNOWN-GOOD INITIALIZATION

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

## NEXT STEPS

1. Fix initialization polling.
2. Test v21 on COM6.
3. Confirm axis 0.
4. Confirm status.
5. Confirm servo_on/off.
6. Confirm move_inc.
7. Confirm memory APIs.
8. Build multi-axis abstraction.
9. Implement Q1/Q2/Q3 execution.
10. Build TUI.
11. Build Mach3/LinuxCNC interface.
