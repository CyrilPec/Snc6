                 SimulIDE 2
                     │
                     ▼
                Arduino Mega
                     │
                  Serial
                     │
                     ▼
             ┌───────────────┐
             │ scn6_server.py│
             └───────┬───────┘
                     │
                   Lark
                     │
                     ▼
              GCodeCommand
                     │
                     ▼
             GCodeInterpreter
                     │
                     ▼
                SCN6Driver
                     │
                     ▼
              TmbsController
                     │
                     ▼
               scn6_dll.py
                     │
                     ▼
                 TMBSCOM
                     │
                     ▼
                    SCN6

init_tmbs_config()
        ↓
TMBS_OPENING
        ↓
poll
        ↓
TMBS_RUNNING
        ↓
discover axes

For the current Dll-changed-and-update branch, let's keep the architecture simpler:

SimulIDE Arduino Mega
        │
        │ Serial / COM
        ▼
 scn6_server.py
        │
        ├── Lark G-code parser
        ├── G-code interpreter/state
        │
        ▼
   SCN6Driver
        │
        ▼
 TmbsController
        │
        ▼
  scn6_dll.py
        │
        ▼
     TMBSCOM
        │
        ▼
      SCN6

So no machine.py for now.

Project structure
I'd use:

Snc6/
├── scn6_server.py          # serial server + orchestration
├── scn6_driver.py          # existing SCN6 facade
├── scn6_dll.py             # existing DLL/TMBSCOM layer
│
└── gcode/
    ├── __init__.py
    ├── grammar.lark
    ├── commands.py
    ├── parser.py
    └── interpreter.py

The reason is that scn6_driver.py already is our machine/hardware abstraction. Adding another machine.py at this stage would mostly duplicate it.

Later, if we introduce multiple backends:

                 G-code
                    │
                    ▼
              Interpreter
                    │
                    ▼
             MachineBackend
              /          \
             ▼            ▼
       SCN6Driver      Simulator

then a machine/ package makes sense. Not yet.

So: delete machine.py and don't create it again for the first version.
