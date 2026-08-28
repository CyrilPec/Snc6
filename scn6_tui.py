"""
SCN6 Textual TUI

Controls the existing SCN6Driver / TMBSCOM DLL.

IMPORTANT:
    Physical motion is controlled by the existing driver safety checks.
    This TUI does not construct raw Termi-BUS frames.

Requirements:
    - Windows
    - 32-bit Python, as required by scn6_dll.py
    - Tmbscom.DLL
    - scn6_driver.py
    - scn6_dll.py
    - textual

Run:
    python scn6_tui.py
"""

from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Select,
    Static,
)

from scn6_driver import SCN6Driver
from scn6_dll import (
    AXIS_NUMBERS,
    MAX_AXIS_COUNT,
    SIO_DONE,
    SIO_ERROR,
    axis_name,
    status_name,
)


class SCN6TUI(App):
    """Textual control panel for the SCN6 controller."""

    TITLE = "SCN6 Driver TUI"
    SUB_TITLE = "TMBSCOM Motion Controller"

    CSS = """
    Screen {
        background: $surface;
    }

    #main {
        height: 1fr;
        padding: 1;
    }

    .panel {
        border: round $accent;
        padding: 1;
        margin-bottom: 1;
    }

    #connection {
        height: auto;
    }

    #axis_panel {
        height: 1fr;
        min-height: 10;
    }

    #motion_panel {
        height: auto;
    }

    #safety_panel {
        height: auto;
    }

    #log_panel {
        height: 12;
    }

    .row {
        height: 3;
        margin-bottom: 1;
    }

    .row Label {
        width: 14;
        padding-top: 1;
    }

    Input {
        width: 28;
    }

    Select {
        width: 20;
    }

    Button {
        margin-right: 1;
    }

    #status {
        text-style: bold;
        color: $warning;
    }

    #axis_table {
        height: 1fr;
    }

    #axis_header {
        color: $text-muted;
        text-style: bold;
    }

    .axis_row {
        height: 3;
    }

    .axis_cell {
        width: 1fr;
    }

    #warning {
        color: $warning;
        text-style: bold;
    }

    #log {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "connect", "Connect"),
        ("s", "servo_on", "Servo ON"),
        ("x", "servo_off", "Servo OFF"),
    ]

    def __init__(self) -> None:
        super().__init__()

        self.driver: SCN6Driver | None = None
        self.refresh_timer = None

    # ==========================================================
    # UI
    # ==========================================================

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main"):

            # --------------------------------------------------
            # Connection
            # --------------------------------------------------

            with Vertical(classes="panel", id="connection"):
                yield Label("SCN6 CONNECTION")

                with Horizontal(classes="row"):
                    yield Label("Port")
                    yield Input(
                        value="COM6",
                        id="port",
                    )

                    yield Label("Baud")
                    yield Input(
                        value="115200",
                        id="baud",
                    )

                    yield Button(
                        "CONNECT",
                        id="connect",
                        variant="success",
                    )

                    yield Button(
                        "DISCONNECT",
                        id="disconnect",
                        variant="error",
                    )

                yield Static(
                    "Disconnected",
                    id="status",
                )

            # --------------------------------------------------
            # Axis status
            # --------------------------------------------------

            with Vertical(classes="panel", id="axis_panel"):
                yield Label("AXIS STATUS")

                yield Static(
                    "AXIS     SERVO     RUN     ALARM     ORIGIN     PFIN     POSITION",
                    id="axis_header",
                )

                with Vertical(id="axis_table"):
                    for axis in AXIS_NUMBERS:
                        yield Static(
                            f"{axis_name(axis):>4}     --        --       --        --        --        --",
                            id=f"axis-{axis}",
                            classes="axis_row",
                        )

            # --------------------------------------------------
            # Motion controls
            # --------------------------------------------------

            with Vertical(classes="panel", id="motion_panel"):
                yield Label("MOTION CONTROL")

                with Horizontal(classes="row"):
                    yield Label("Axis")
                    yield Select(
                        [
                            (axis_name(axis), axis)
                            for axis in AXIS_NUMBERS
                        ],
                        value=0,
                        id="axis_select",
                    )

                    yield Label("Position")
                    yield Input(
                        value="0",
                        id="position",
                    )

                    yield Button(
                        "MOVE ABS",
                        id="move_abs",
                        variant="warning",
                    )

                with Horizontal(classes="row"):
                    yield Label("Increment")
                    yield Input(
                        value="1000",
                        id="increment",
                    )

                    yield Button(
                        "MOVE +",
                        id="move_plus",
                    )

                    yield Button(
                        "MOVE -",
                        id="move_minus",
                    )

                    yield Button(
                        "HOME",
                        id="home",
                        variant="warning",
                    )

            # --------------------------------------------------
            # Servo / alarm controls
            # --------------------------------------------------

            with Vertical(classes="panel", id="safety_panel"):
                yield Label("SERVO / SAFETY")

                with Horizontal(classes="row"):
                    yield Button(
                        "SERVO ON",
                        id="servo_on",
                        variant="success",
                    )

                    yield Button(
                        "SERVO OFF",
                        id="servo_off",
                        variant="error",
                    )

                    yield Button(
                        "RESET ALARM",
                        id="reset_alarm",
                        variant="warning",
                    )

                    yield Button(
                        "REFRESH",
                        id="refresh",
                    )

                yield Static(
                    "Physical movement requires operator confirmation.",
                    id="warning",
                )

            # --------------------------------------------------
            # Log
            # --------------------------------------------------

            with Vertical(classes="panel", id="log_panel"):
                yield Label("SCN6 LOG")
                yield Log(id="log")

        yield Footer()

    # ==========================================================
    # Lifecycle
    # ==========================================================

    def on_mount(self) -> None:
        self.log_message("SCN6 Textual TUI started.")
        self.log_message(
            "Driver is not connected. Press CONNECT."
        )

        self.refresh_timer = self.set_interval(
            1.0,
            self.update_status,
        )

    def on_unmount(self) -> None:
        self.close_driver()

    # ==========================================================
    # Logging
    # ==========================================================

    def log_message(self, message: str) -> None:
        log = self.query_one("#log", Log)

        timestamp = time.strftime("%H:%M:%S")

        log.write_line(
            f"[{timestamp}] {message}"
        )

    # ==========================================================
    # Helpers
    # ==========================================================

    def selected_axis(self) -> int:
        select = self.query_one("#axis_select", Select)

        if select.value is Select.BLANK:
            return 0

        return int(select.value)

    def set_status(
        self,
        text: str,
        color: str = "$warning",
    ) -> None:
        status = self.query_one("#status", Static)

        status.update(text)
        status.styles.color = color

    def require_driver(self) -> SCN6Driver | None:
        if self.driver is None:
            self.log_message(
                "ERROR: SCN6 driver is not connected."
            )
            return None

        if not self.driver.initialized:
            self.log_message(
                "ERROR: SCN6 driver is not initialized."
            )
            return None

        return self.driver

    def update_axis_row(
        self,
        axis: int,
        status: dict | None,
        position: int | None,
    ) -> None:

        widget = self.query_one(
            f"#axis-{axis}",
            Static,
        )

        if status is None:
            widget.update(
                f"{axis_name(axis):>4}     --        --       --        --        --        --"
            )
            return

        def state(value):
            if value is None:
                return "--"

            return "OK" if value == SIO_DONE else str(value)

        position_text = (
            str(position)
            if position is not None
            else "--"
        )

        widget.update(
            f"{axis_name(axis):>4}     "
            f"{state(status.get('servo')):<8} "
            f"{state(status.get('run')):<8} "
            f"{state(status.get('alarm')):<9} "
            f"{state(status.get('origin')):<10} "
            f"{state(status.get('pfin')):<8} "
            f"{position_text}"
        )

    # ==========================================================
    # Connection
    # ==========================================================

    def connect_driver(self) -> None:
        if self.driver is not None:
            self.log_message(
                "Driver is already connected."
            )
            return

        port = self.query_one(
            "#port",
            Input,
        ).value.strip()

        baud = self.query_one(
            "#baud",
            Input,
        ).value.strip()

        self.log_message(
            f"Connecting to SCN6 on {port} @ {baud}..."
        )

        try:
            # IMPORTANT:
            # The current scn6_driver.py inherits from
            # TmbsController, whose configuration currently
            # uses COM_PORT / BAUD_CODE constants in scn6_dll.py.
            #
            # We therefore keep the existing driver initialization
            # path here rather than creating a second DLL interface.

            self.driver = SCN6Driver()

            history = self.driver.initialize()

            final_result = (
                history[-1]
                if history
                else None
            )

            if not self.driver.initialized:
                self.log_message(
                    f"SCN6 initialization failed: {final_result}"
                )

                self.driver = None

                self.set_status(
                    "Connection failed",
                    "$error",
                )

                return

            self.driver.refresh_connected_axes()

            connected = [
                axis_name(axis)
                for axis in AXIS_NUMBERS
                if self.driver.axes[axis].connected
            ]

            self.set_status(
                "CONNECTED",
                "$success",
            )

            self.log_message(
                f"TMBSCOM state: "
                f"{self.driver.communication_state()} "
                f"({status_name(self.driver.communication_state())})"
            )

            self.log_message(
                "Connected axes: "
                + (
                    ", ".join(connected)
                    if connected
                    else "none"
                )
            )

            self.update_status()

        except Exception as exc:
            self.log_message(
                f"ERROR connecting to SCN6: {exc}"
            )

            self.driver = None

            self.set_status(
                "Connection failed",
                "$error",
            )

    def close_driver(self) -> None:
        if self.driver is None:
            return

        try:
            if self.driver.initialized:
                self.driver.close_tmbs()

        except Exception as exc:
            self.log_message(
                f"Error closing SCN6: {exc}"
            )

        finally:
            self.driver = None

    def disconnect_driver(self) -> None:
        self.log_message(
            "Disconnecting SCN6..."
        )

        self.close_driver()

        self.set_status(
            "DISCONNECTED",
            "$warning",
        )

        for axis in AXIS_NUMBERS:
            self.update_axis_row(
                axis,
                None,
                None,
            )

        self.log_message(
            "SCN6 disconnected."
        )

    # ==========================================================
    # Status monitoring
    # ==========================================================

    def update_status(self) -> None:
        driver = self.driver

        if driver is None:
            return

        if not driver.initialized:
            return

        try:
            driver.refresh_connected_axes()

            for axis in AXIS_NUMBERS:

                if not driver.axes[axis].connected:
                    self.update_axis_row(
                        axis,
                        None,
                        None,
                    )
                    continue

                status = driver.read_axis_status(axis)

                position = None

                if status is not None:
                    position, error = (
                        driver.read_controller_position(
                            axis
                        )
                    )

                    if error:
                        position = None

                self.update_axis_row(
                    axis,
                    status,
                    position,
                )

        except Exception as exc:
            self.log_message(
                f"Status update error: {exc}"
            )

    # ==========================================================
    # Motion
    # ==========================================================

    def move_absolute(self) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        axis = self.selected_axis()

        try:
            position = int(
                self.query_one(
                    "#position",
                    Input,
                ).value,
                0,
            )
        except ValueError:
            self.log_message(
                "ERROR: invalid absolute position."
            )
            return

        self.log_message(
            f"REQUEST: axis {axis_name(axis)} "
            f"absolute move -> {position}"
        )

        if not self.confirm_motion(
            f"Move axis {axis_name(axis)} "
            f"to absolute position {position}?"
        ):
            return

        try:
            result = driver.direct_move_absolute(
                axis,
                position,
            )

            self.log_message(
                f"move_abs axis {axis_name(axis)} "
                f"position={position} -> {result}"
            )

            if result == SIO_DONE:
                self.log_message(
                    "Absolute move accepted."
                )
            else:
                self.log_message(
                    "Absolute move rejected."
                )

        except Exception as exc:
            self.log_message(
                f"ERROR during absolute move: {exc}"
            )

    def move_incremental(self, distance: int) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        axis = self.selected_axis()

        self.log_message(
            f"REQUEST: axis {axis_name(axis)} "
            f"incremental move {distance}"
        )

        if not self.confirm_motion(
            f"Move axis {axis_name(axis)} "
            f"by {distance} pulses?"
        ):
            return

        try:
            result = driver.direct_move_incremental(
                axis,
                distance,
            )

            self.log_message(
                f"move_inc axis {axis_name(axis)} "
                f"distance={distance} -> {result}"
            )

            if result == SIO_DONE:
                self.log_message(
                    "Incremental move accepted."
                )
            else:
                self.log_message(
                    "Incremental move rejected."
                )

        except Exception as exc:
            self.log_message(
                f"ERROR during incremental move: {exc}"
            )

    # ==========================================================
    # Servo
    # ==========================================================

    def servo(self, enabled: bool) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        axis = self.selected_axis()

        function = (
            driver.set_son
            if enabled
            else driver.set_soff
        )

        if function is None:
            self.log_message(
                "ERROR: servo function is not available in DLL."
            )
            return

        action = (
            "SERVO ON"
            if enabled
            else "SERVO OFF"
        )

        self.log_message(
            f"REQUEST: {action} axis {axis_name(axis)}"
        )

        if not self.confirm_motion(
            f"{action} axis {axis_name(axis)}?"
        ):
            return

        try:
            result = function(axis)

            self.log_message(
                f"{action} axis {axis_name(axis)} "
                f"-> {result}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR changing servo state: {exc}"
            )

    # ==========================================================
    # Alarm reset
    # ==========================================================

    def reset_alarm(self) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        axis = self.selected_axis()

        if driver.reset_alarm is None:
            self.log_message(
                "ERROR: reset_alarm DLL export is not available."
            )
            return

        self.log_message(
            f"REQUEST: reset alarm axis {axis_name(axis)}"
        )

        if not self.confirm_motion(
            f"Reset alarm on axis {axis_name(axis)}?"
        ):
            return

        try:
            before = driver.read_axis_status(axis)

            result = driver.reset_alarm(axis)

            self.log_message(
                f"reset_alarm axis {axis_name(axis)} "
                f"-> {result}"
            )

            time.sleep(0.1)

            after = driver.read_axis_status(axis)

            if before:
                self.log_message(
                    f"Alarm before: {before.get('alarm')}"
                )

            if after:
                self.log_message(
                    f"Alarm after: {after.get('alarm')}"
                )

        except Exception as exc:
            self.log_message(
                f"ERROR resetting alarm: {exc}"
            )

    # ==========================================================
    # Homing
    # ==========================================================

    def home_axis(self) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        axis = self.selected_axis()

        if driver.move_org is None:
            self.log_message(
                "ERROR: move_org DLL export is not available."
            )
            return

        self.log_message(
            f"REQUEST: HOME axis {axis_name(axis)}"
        )

        if not self.confirm_motion(
            f"HOME axis {axis_name(axis)}?\n"
            "Homing can physically move the actuator."
        ):
            return

        try:
            status = driver.read_axis_status(axis)

            if status is None:
                return

            if status["alarm"] == SIO_DONE:
                self.log_message(
                    "HOME ABORTED: alarm is active."
                )
                return

            if status["servo"] != SIO_DONE:
                self.log_message(
                    "HOME ABORTED: servo is OFF."
                )
                return

            # Same default mode used by the CLI only if the
            # operator explicitly chooses it.
            mode = 0

            self.log_message(
                f"Starting homing: axis={axis_name(axis)} "
                f"mode={mode}"
            )

            driver.move_org(
                axis,
                mode,
            )

            self.log_message(
                "Homing command issued."
            )

        except Exception as exc:
            self.log_message(
                f"ERROR during homing: {exc}"
            )

    # ==========================================================
    # Confirmation
    # ==========================================================

    def confirm_motion(self, message: str) -> bool:
        """
        Textual confirmation dialog.

        This is intentionally simple: the user must press
        CONFIRM before a physical operation is sent.
        """

        from textual.screen import ModalScreen

        class ConfirmScreen(ModalScreen[bool]):
            CSS = """
            ConfirmScreen {
                align: center middle;
            }

            #dialog {
                width: 60;
                height: auto;
                padding: 2;
                border: thick $warning;
                background: $surface;
            }

            #message {
                margin-bottom: 2;
            }

            Button {
                margin-right: 1;
            }
            """

            def __init__(self, text: str):
                super().__init__()
                self.text = text

            def compose(self):
                with Vertical(id="dialog"):
                    yield Label(
                        "PHYSICAL ACTION",
                        id="title",
                    )

                    yield Static(
                        self.text,
                        id="message",
                    )

                    with Horizontal():
                        yield Button(
                            "CONFIRM",
                            id="confirm",
                            variant="warning",
                        )

                        yield Button(
                            "CANCEL",
                            id="cancel",
                        )

            def on_button_pressed(
                self,
                event: Button.Pressed,
            ):
                if event.button.id == "confirm":
                    self.dismiss(True)
                else:
                    self.dismiss(False)

        # Textual's push_screen is asynchronous.
        # For the main action handlers we use a callback.
        #
        # This method is therefore replaced by the callback-based
        # version below.
        return True

    # ==========================================================
    # Textual confirmation implementation
    # ==========================================================

    def request_confirmation(
        self,
        message: str,
        callback,
    ) -> None:

        from textual.screen import ModalScreen

        app = self

        class ConfirmScreen(ModalScreen[bool]):
            CSS = """
            ConfirmScreen {
                align: center middle;
            }

            #dialog {
                width: 64;
                height: auto;
                padding: 2;
                border: thick $warning;
                background: $surface;
            }

            #title {
                text-style: bold;
                color: $warning;
                margin-bottom: 1;
            }

            #message {
                margin-bottom: 2;
            }

            Button {
                margin-right: 1;
            }
            """

            def compose(self):
                with Vertical(id="dialog"):
                    yield Label(
                        "⚠ PHYSICAL ACTION",
                        id="title",
                    )

                    yield Static(
                        message,
                        id="message",
                    )

                    with Horizontal():
                        yield Button(
                            "CONFIRM",
                            id="confirm",
                            variant="warning",
                        )

                        yield Button(
                            "CANCEL",
                            id="cancel",
                        )

            def on_button_pressed(
                self,
                event: Button.Pressed,
            ):
                self.dismiss(
                    event.button.id == "confirm"
                )

        def result(confirmed: bool) -> None:
            if confirmed:
                callback()

        app.push_screen(
            ConfirmScreen(message),
            result,
        )

    # ==========================================================
    # Button events
    # ==========================================================

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:

        button = event.button.id

        if button == "connect":
            self.connect_driver()

        elif button == "disconnect":
            self.disconnect_driver()

        elif button == "refresh":
            self.update_status()

        elif button == "move_abs":
            self.request_confirmation(
                self.absolute_move_message(),
                self.move_absolute,
            )

        elif button == "move_plus":
            distance = self.increment_value()

            if distance is not None:
                self.request_confirmation(
                    self.increment_message(distance),
                    lambda: self.move_incremental(
                        distance
                    ),
                )

        elif button == "move_minus":
            distance = self.increment_value()

            if distance is not None:
                distance = -distance

                self.request_confirmation(
                    self.increment_message(distance),
                    lambda: self.move_incremental(
                        distance
                    ),
                )

        elif button == "servo_on":
            self.request_confirmation(
                f"Enable servo on axis "
                f"{axis_name(self.selected_axis())}?",
                lambda: self.servo(True),
            )

        elif button == "servo_off":
            self.request_confirmation(
                f"Disable servo on axis "
                f"{axis_name(self.selected_axis())}?",
                lambda: self.servo(False),
            )

        elif button == "reset_alarm":
            self.request_confirmation(
                f"Reset alarm on axis "
                f"{axis_name(self.selected_axis())}?",
                self.reset_alarm,
            )

        elif button == "home":
            self.request_confirmation(
                f"HOME axis "
                f"{axis_name(self.selected_axis())}?\n\n"
                "Homing can physically move the actuator.",
                self.home_axis,
            )

    # ==========================================================
    # Input parsing
    # ==========================================================

    def increment_value(self) -> int | None:
        text = self.query_one(
            "#increment",
            Input,
        ).value.strip()

        try:
            value = int(text, 0)

            if value <= 0:
                raise ValueError

            return value

        except ValueError:
            self.log_message(
                "ERROR: increment must be a positive integer."
            )

            return None

    def absolute_move_message(self) -> str:
        axis = self.selected_axis()

        text = self.query_one(
            "#position",
            Input,
        ).value.strip()

        try:
            position = int(text, 0)

        except ValueError:
            return (
                f"Invalid position: {text}"
            )

        return (
            f"Move axis {axis_name(axis)} "
            f"to absolute position {position}?\n\n"
            "This will physically move the actuator."
        )

    def increment_message(
        self,
        distance: int,
    ) -> str:
        axis = self.selected_axis()

        return (
            f"Move axis {axis_name(axis)} "
            f"by {distance} pulses?\n\n"
            "This will physically move the actuator."
        )

    # ==========================================================
    # Keyboard actions
    # ==========================================================

    def action_quit(self) -> None:
        self.exit()

    def action_refresh(self) -> None:
        self.update_status()

    def action_connect(self) -> None:
        self.connect_driver()

    def action_servo_on(self) -> None:
        self.request_confirmation(
            f"Enable servo on axis "
            f"{axis_name(self.selected_axis())}?",
            lambda: self.servo(True),
        )

    def action_servo_off(self) -> None:
        self.request_confirmation(
            f"Disable servo on axis "
            f"{axis_name(self.selected_axis())}?",
            lambda: self.servo(False),
        )


if __name__ == "__main__":
    SCN6TUI().run()
