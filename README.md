# SCN6 TUI Period 2
Modular TUI split from the SCN6 Textual interface.

Files:
- app.py       main application/event routing
- ui.py        widgets/layout
- connection.py connection lifecycle
- status.py    status polling/display
- motion.py    motion/servo/alarm/home operations
- confirm.py   physical-action confirmation
- run_tui.py   launcher

Keep scn6_driver.py and scn6_dll.py from the existing SCN6 project beside
this package. This TUI does not construct raw Termi-BUS frames.
