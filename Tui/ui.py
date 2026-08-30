from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Log, Select, Static
from scn6_dll import AXIS_NUMBERS, axis_name

class TUIWidgetsMixin:
    CSS = '''
    Screen { background: $surface; }
    #main { height: 1fr; padding: 1; }
    .panel { border: round $accent; padding: 1; margin-bottom: 1; }
    #connection { height: auto; }
    #axis_panel { height: 1fr; min-height: 10; }
    #motion_panel, #safety_panel { height: auto; }
    #log_panel { height: 12; }
    .row { height: 3; margin-bottom: 1; }
    .row Label { width: 14; padding-top: 1; }
    Input { width: 28; }
    Select { width: 20; }
    Button { margin-right: 1; }
    #status { text-style: bold; color: $warning; }
    #axis_table { height: 1fr; }
    #axis_header { color: $text-muted; text-style: bold; }
    .axis_row { height: 3; }
    #warning { color: $warning; text-style: bold; }
    #log { height: 1fr; }
    '''
    BINDINGS = [
        ("q", "quit", "Quit"), ("r", "refresh", "Refresh"),
        ("c", "connect", "Connect"), ("s", "servo_on", "Servo ON"),
        ("x", "servo_off", "Servo OFF"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main"):
            with Vertical(classes="panel", id="connection"):
                yield Label("SCN6 CONNECTION")
                with Horizontal(classes="row"):
                    yield Label("Port")
                    yield Input(value="COM6", id="port")
                    yield Label("Baud")
                    yield Input(value="115200", id="baud")
                    yield Button("CONNECT", id="connect", variant="success")
                    yield Button("DISCONNECT", id="disconnect", variant="error")
                yield Static("Disconnected", id="status")
            with Vertical(classes="panel", id="axis_panel"):
                yield Label("AXIS STATUS")
                yield Static("AXIS     SERVO     RUN     ALARM     ORIGIN     PFIN     POSITION", id="axis_header")
                with Vertical(id="axis_table"):
                    for axis in AXIS_NUMBERS:
                        yield Static(
                            f"{axis_name(axis):>4}     --        --       --        --        --        --",
                            id=f"axis-{axis}", classes="axis_row")
            with Vertical(classes="panel", id="motion_panel"):
                yield Label("MOTION CONTROL")
                with Horizontal(classes="row"):
                    yield Label("Axis")
                    yield Select([(axis_name(a), a) for a in AXIS_NUMBERS], value=0, id="axis_select")
                    yield Label("Position")
                    yield Input(value="0", id="position")
                    yield Button("MOVE ABS", id="move_abs", variant="warning")
                with Horizontal(classes="row"):
                    yield Label("Increment")
                    yield Input(value="1000", id="increment")
                    yield Button("MOVE +", id="move_plus")
                    yield Button("MOVE -", id="move_minus")
                    yield Button("HOME", id="home", variant="warning")
            with Vertical(classes="panel", id="safety_panel"):
                yield Label("SERVO / SAFETY")
                with Horizontal(classes="row"):
                    yield Button("SERVO ON", id="servo_on", variant="success")
                    yield Button("SERVO OFF", id="servo_off", variant="error")
                    yield Button("RESET ALARM", id="reset_alarm", variant="warning")
                    yield Button("REFRESH", id="refresh")
                yield Static("Physical movement requires operator confirmation.", id="warning")
            with Vertical(classes="panel", id="log_panel"):
                yield Label("SCN6 LOG")
                yield Log(id="log")
        yield Footer()

    def selected_axis(self):
        value = self.query_one("#axis_select", Select).value
        return 0 if value is Select.BLANK else int(value)

    def set_status(self, text, color="yellow"):
        w = self.query_one("#status", Static)
        w.update(text)
        w.styles.color = color


    def log_message(self, message):
        import time
        self.query_one("#log", Log).write_line(f"[{time.strftime('%H:%M:%S')}] {message}")
