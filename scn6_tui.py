"""
SCN6 Driver TUI
================

Textual interface for the existing SCN6Driver / TMBSCOM DLL.

The existing driver remains the hardware interface.
This file provides the operator interface and configuration UI.

Configuration:
    Scn6.ini

The TUI loads/saves Scn6.ini through scn6_config.py and applies the
communication settings to scn6_dll before SCN6Driver.initialize().

Requirements:
    Python 3.12 32-bit
    textual
    Tmbscom.DLL
    scn6_driver.py
    scn6_dll.py
    scn6_config.py
    Scn6.ini

Run:
    py -3.12-32 scn6_tui.py
"""

from __future__ import annotations

import configparser
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Select,
    Static,
)

import scn6_dll
from scn6_config import SCN6Config, load_config
from scn6_driver import SCN6Driver


# ============================================================
# Configuration
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
INI_PATH = BASE_DIR / "Scn6.ini"

DEFAULT_CONFIG = SCN6Config()


# TMBSCOM baud-code mapping used by the DLL.
#
# The INI stores the human-readable baud rate.
# The DLL initialization function expects the TMBS baud code.
#
# 0x14 is the value already used by the existing driver for 115200.
BAUD_CODES = {
    9600: 0x0A,
    19200: 0x0C,
    38400: 0x0E,
    57600: 0x10,
    115200: 0x14,
}

BAUD_OPTIONS = [
    (str(baud), baud)
    for baud in BAUD_CODES
]


# ============================================================
# Confirmation dialog
# ============================================================

class ConfirmScreen(ModalScreen[bool]):
    """Confirmation dialog for physical SCN6 operations."""

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
        color: $warning;
        text-style: bold;
        margin-bottom: 1;
    }

    #message {
        margin-bottom: 2;
    }

    Button {
        margin-right: 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(
                "⚠ PHYSICAL ACTION",
                id="title",
            )

            yield Static(
                self.message,
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
    ) -> None:
        self.dismiss(
            event.button.id == "confirm"
        )


# ============================================================
# SCN6 TUI
# ============================================================

class SCN6TUI(App):
    """Textual control panel for the SCN6 controller."""

    TITLE = "SCN6 Driver"
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
        width: 12;
        padding-top: 1;
    }

    Input {
        width: 20;
    }

    Select {
        width: 18;
    }

    Button {
        margin-right: 1;
    }

    #status {
        text-style: bold;
        color: $warning;
    }

    #ini_status {
        color: $text-muted;
    }

    #axis_header {
        color: $text-muted;
        text-style: bold;
    }

    .axis_row {
        height: 3;
    }

    #warning {
        color: $warning;
        text-style: bold;
    }

    #log {
        height: 1fr;
    }

    #save_ini {
        margin-left: 2;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "connect", "Connect"),
        ("d", "disconnect", "Disconnect"),
        ("s", "servo_on", "Servo ON"),
        ("x", "servo_off", "Servo OFF"),
    ]

    def __init__(self) -> None:
        super().__init__()

        self.driver: SCN6Driver | None = None
        self.config: SCN6Config = DEFAULT_CONFIG
        self.refresh_timer = None

        self.load_ini_config()

    # ========================================================
    # UI
    # ========================================================

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(id="main"):

            # ------------------------------------------------
            # CONNECTION / CONFIGURATION
            # ------------------------------------------------

            with Vertical(
                classes="panel",
                id="connection",
            ):
                yield Label(
                    "SCN6 CONNECTION / CONFIGURATION"
                )

                with Horizontal(classes="row"):
                    yield Label("INI")

                    yield Static(
                        str(INI_PATH.name),
                        id="ini_status",
                    )

                    yield Button(
                        "RELOAD INI",
                        id="reload_ini",
                    )

                    yield Button(
                        "SAVE INI",
                        id="save_ini",
                    )

                with Horizontal(classes="row"):
                    yield Label("Port")

                    yield Input(
                        id="port",
                        value=self.config.port,
                    )

                    yield Label("Baud")

                    yield Select(
                        BAUD_OPTIONS,
                        value=self.config.baud
                        if self.config.baud in BAUD_CODES
                        else 115200,
                        id="baud",
                    )

                    yield Label("NRT")

                    yield Input(
                        id="nrt",
                        value=str(self.config.nrt),
                    )

                with Horizontal(classes="row"):
                    yield Label("Reset")

                    yield Checkbox(
                        "Enable reset",
                        value=self.config.reset,
                        id="reset",
                    )

                    yield Label("Automatic")

                    yield Checkbox(
                        "Enable automatic",
                        value=self.config.automatic,
                        id="automatic",
                    )

                with Horizontal(classes="row"):
                    yield Label("Axis min")

                    yield Input(
                        id="axis_min",
                        value=format(
                            self.config.axis_min,
                            "X",
                        ),
                    )

                    yield Label("Axis max")

                    yield Input(
                        id="axis_max",
                        value=format(
                            self.config.axis_max,
                            "X",
                        ),
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
                    "DISCONNECTED",
                    id="status",
                )

            # ------------------------------------------------
            # AXIS STATUS
            # ------------------------------------------------

            with Vertical(
                classes="panel",
                id="axis_panel",
            ):
                yield Label("AXIS STATUS")

                yield Static(
                    "AXIS   SERVO   RUN   ALARM   ORIGIN   PFIN   POSITION",
                    id="axis_header",
                )

                with Vertical(id="axis_table"):
                    for axis in range(16):
                        yield Static(
                            self.axis_line(
                                axis,
                                None,
                                None,
                            ),
                            id=f"axis-{axis}",
                            classes="axis_row",
                        )

            # ------------------------------------------------
            # MOTION
            # ------------------------------------------------

            with Vertical(
                classes="panel",
                id="motion_panel",
            ):
                yield Label("MANUAL MOTION")

                with Horizontal(classes="row"):
                    yield Label("Axis")

                    yield Select(
                        [
                            (
                                format(axis, "X"),
                                axis,
                            )
                            for axis in range(16)
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

            # ------------------------------------------------
            # SAFETY
            # ------------------------------------------------

            with Vertical(
                classes="panel",
                id="safety_panel",
            ):
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

            # ------------------------------------------------
            # LOG
            # ------------------------------------------------

            with Vertical(
                classes="panel",
                id="log_panel",
            ):
                yield Label("SCN6 LOG")
                yield Log(id="log")

        yield Footer()

    # ========================================================
    # Lifecycle
    # ========================================================

    def on_mount(self) -> None:
        self.log_message(
            "SCN6 Textual TUI started."
        )

        self.log_message(
            f"Configuration: {INI_PATH}"
        )

        self.log_message(
            f"Configured port: {self.config.port}"
        )

        self.log_message(
            f"Configured baud: {self.config.baud}"
        )

        self.log_message(
            f"Configured axes: "
            f"{self.config.axis_min:X}.."
            f"{self.config.axis_max:X}"
        )

        self.set_axis_selector_range()

        self.refresh_timer = self.set_interval(
            1.0,
            self.update_status,
        )

    def on_unmount(self) -> None:
        self.close_driver()

    # ========================================================
    # Configuration
    # ========================================================

    def load_ini_config(self) -> None:
        """Load Scn6.ini using the repository config loader."""

        try:
            self.config = load_config(
                str(INI_PATH)
            )

        except Exception as exc:
            self.config = DEFAULT_CONFIG

            # This is before the Textual log exists.
            # Store the error for on_mount().
            self._config_error = str(exc)

        else:
            self._config_error = None

    def save_ini_config(self) -> bool:
        """
        Save current UI configuration to Scn6.ini.

        Uses the same section/key names as scn6_config.py.
        """

        try:
            port = self.query_one(
                "#port",
                Input,
            ).value.strip()

            nrt = int(
                self.query_one(
                    "#nrt",
                    Input,
                ).value.strip(),
                0,
            )

            axis_min = self.parse_axis(
                self.query_one(
                    "#axis_min",
                    Input,
                ).value
            )

            axis_max = self.parse_axis(
                self.query_one(
                    "#axis_max",
                    Input,
                ).value
            )

            baud_select = self.query_one(
                "#baud",
                Select,
            )

            if baud_select.value is Select.BLANK:
                raise ValueError(
                    "Baud rate is not selected."
                )

            baud = int(baud_select.value)

            reset = self.query_one(
                "#reset",
                Checkbox,
            ).value

            automatic = self.query_one(
                "#automatic",
                Checkbox,
            ).value

            if not port:
                raise ValueError(
                    "COM port cannot be empty."
                )

            if nrt < 0:
                raise ValueError(
                    "NRT must be >= 0."
                )

            if not 0 <= axis_min <= axis_max <= 15:
                raise ValueError(
                    "Axis range must be inside 0..F."
                )

            parser = configparser.ConfigParser()

            parser["communication"] = {
                "port": port,
                "baud": str(baud),
                "nrt": str(nrt),
                "reset": str(reset).lower(),
                "automatic": str(automatic).lower(),
            }

            parser["driver"] = {
                "axis_min": format(
                    axis_min,
                    "X",
                ),
                "axis_max": format(
                    axis_max,
                    "X",
                ),
            }

            with INI_PATH.open(
                "w",
                encoding="utf-8",
            ) as file:
                parser.write(file)

            self.config = SCN6Config(
                port=port,
                baud=baud,
                nrt=nrt,
                reset=reset,
                automatic=automatic,
                axis_min=axis_min,
                axis_max=axis_max,
            )

            self.log_message(
                f"Configuration saved: {INI_PATH.name}"
            )

            self.set_axis_selector_range()

            return True

        except Exception as exc:
            self.log_message(
                f"ERROR saving INI: {exc}"
            )
            return False

    def reload_ini_config(self) -> None:
        if self.driver is not None:
            self.log_message(
                "Disconnect before reloading configuration."
            )
            return

        try:
            self.config = load_config(
                str(INI_PATH)
            )

            self.query_one(
                "#port",
                Input,
            ).value = self.config.port

            self.query_one(
                "#baud",
                Select,
            ).value = (
                self.config.baud
                if self.config.baud in BAUD_CODES
                else 115200
            )

            self.query_one(
                "#nrt",
                Input,
            ).value = str(self.config.nrt)

            self.query_one(
                "#reset",
                Checkbox,
            ).value = self.config.reset

            self.query_one(
                "#automatic",
                Checkbox,
            ).value = self.config.automatic

            self.query_one(
                "#axis_min",
                Input,
            ).value = format(
                self.config.axis_min,
                "X",
            )

            self.query_one(
                "#axis_max",
                Input,
            ).value = format(
                self.config.axis_max,
                "X",
            )

            self.set_axis_selector_range()

            self.log_message(
                f"Reloaded {INI_PATH.name}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR loading INI: {exc}"
            )

    def apply_config_to_driver(self) -> None:
        """
        Apply SCN6Config to the existing DLL-driver globals.

        The current TmbsController.initialize() uses these globals
        directly. We therefore preserve the existing driver code and
        inject the configuration here.

        No new hardware protocol is introduced.
        """

        if self.config.baud not in BAUD_CODES:
            raise ValueError(
                f"Unsupported baud rate: "
                f"{self.config.baud}"
            )

        scn6_dll.COM_PORT = self.config.port
        scn6_dll.BAUD_CODE = BAUD_CODES[
            self.config.baud
        ]
        scn6_dll.NRT = self.config.nrt
        scn6_dll.RESET = self.config.reset
        scn6_dll.AUTOMATIC = self.config.automatic

    # ========================================================
    # Axis helpers
    # ========================================================

    def active_axes(self) -> range:
        return range(
            self.config.axis_min,
            self.config.axis_max + 1,
        )

    def set_axis_selector_range(self) -> None:
        select = self.query_one(
            "#axis_select",
            Select,
        )

        options = [
            (
                format(axis, "X"),
                axis,
            )
            for axis in self.active_axes()
        ]

        select.set_options(options)

        if options:
            select.value = options[0][1]

        for axis in range(16):
            widget = self.query_one(
                f"#axis-{axis}",
                Static,
            )

            if axis in self.active_axes():
                widget.display = True
            else:
                widget.display = False

    @staticmethod
    def parse_axis(value: str) -> int:
        text = value.strip().upper()

        if len(text) == 1 and text in "0123456789ABCDEF":
            result = int(text, 16)
        else:
            result = int(text, 0)

        if not 0 <= result <= 15:
            raise ValueError(
                "Axis must be in range 0..F."
            )

        return result

    def selected_axis(self) -> int:
        select = self.query_one(
            "#axis_select",
            Select,
        )

        if select.value is Select.BLANK:
            raise ValueError(
                "No axis selected."
            )

        return int(select.value)

    # ========================================================
    # Logging
    # ========================================================

    def log_message(self, message: str) -> None:
        try:
            log = self.query_one(
                "#log",
                Log,
            )

            timestamp = time.strftime(
                "%H:%M:%S"
            )

            log.write_line(
                f"[{timestamp}] {message}"
            )

        except Exception:
            pass

    # ========================================================
    # Status
    # ========================================================

    def set_status(
        self,
        text: str,
        color: str = "$warning",
    ) -> None:
        status = self.query_one(
            "#status",
            Static,
        )

        status.update(text)
        status.styles.color = color

    @staticmethod
    def result_text(value) -> str:
        if value is None:
            return "--"

        return str(value)

    def axis_line(
        self,
        axis: int,
        status: dict | None,
        position: int | None,
    ) -> str:

        name = format(axis, "X")

        if status is None:
            return (
                f"{name:^5} "
                f"{'--':^7} "
                f"{'--':^6} "
                f"{'--':^8} "
                f"{'--':^9} "
                f"{'--':^7} "
                f"{'--':>12}"
            )

        return (
            f"{name:^5} "
            f"{self.result_text(status.get('servo')):^7} "
            f"{self.result_text(status.get('run')):^6} "
            f"{self.result_text(status.get('alarm')):^8} "
            f"{self.result_text(status.get('origin')):^9} "
            f"{self.result_text(status.get('pfin')):^7} "
            f"{self.result_text(position):>12}"
        )

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

        widget.update(
            self.axis_line(
                axis,
                status,
                position,
            )
        )

    # ========================================================
    # Connection
    # ========================================================

    def connect_driver(self) -> None:
        if self.driver is not None:
            self.log_message(
                "SCN6 driver is already connected."
            )
            return

        # Save current UI values first.
        if not self.save_ini_config():
            return

        try:
            self.apply_config_to_driver()

        except Exception as exc:
            self.log_message(
                f"ERROR applying configuration: {exc}"
            )
            return

        self.log_message(
            "Initializing SCN6..."
        )

        self.log_message(
            f"Port={self.config.port}, "
            f"Baud={self.config.baud}, "
            f"NRT={self.config.nrt}, "
            f"Reset={self.config.reset}, "
            f"Automatic={self.config.automatic}"
        )

        try:
            self.driver = SCN6Driver()

            history = self.driver.initialize()

            final_result = (
                history[-1]
                if history
                else None
            )

            if not self.driver.initialized:
                self.log_message(
                    f"SCN6 initialization failed: "
                    f"{final_result}"
                )

                self.close_driver()

                self.set_status(
                    "CONNECTION FAILED",
                    "$error",
                )

                return

            self.driver.refresh_connected_axes()

            connected = [
                format(axis, "X")
                for axis in self.active_axes()
                if self.driver.axes[axis].connected
            ]

            self.set_status(
                "CONNECTED",
                "$success",
            )

            self.log_message(
                "TMBS state: "
                f"{self.driver.communication_state()}"
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

            self.close_driver()

            self.set_status(
                "CONNECTION FAILED",
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

        for axis in range(16):
            self.update_axis_row(
                axis,
                None,
                None,
            )

        self.log_message(
            "SCN6 disconnected."
        )

    # ========================================================
    # Live status
    # ========================================================

    def update_status(self) -> None:
        driver = self.driver

        if driver is None:
            return

        if not driver.initialized:
            return

        try:
            driver.refresh_connected_axes()

            for axis in self.active_axes():

                if not driver.axes[axis].connected:
                    self.update_axis_row(
                        axis,
                        None,
                        None,
                    )
                    continue

                status = driver.read_axis_status(
                    axis
                )

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

    # ========================================================
    # Motion safety
    # ========================================================

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

    def request_confirmation(
        self,
        message: str,
        callback,
    ) -> None:

        def result(confirmed: bool) -> None:
            if confirmed:
                callback()

        self.push_screen(
            ConfirmScreen(message),
            result,
        )

    # ========================================================
    # Absolute movement
    # ========================================================

    def move_absolute(self) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        try:
            axis = self.selected_axis()

            position = int(
                self.query_one(
                    "#position",
                    Input,
                ).value.strip(),
                0,
            )

        except ValueError as exc:
            self.log_message(
                f"ERROR: invalid move parameters: {exc}"
            )
            return

        self.log_message(
            f"ABS MOVE request: "
            f"axis={axis:X}, position={position}"
        )

        try:
            result = driver.direct_move_absolute(
                axis,
                position,
            )

            self.log_message(
                f"ABS MOVE result: {result}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR absolute move: {exc}"
            )

    # ========================================================
    # Incremental movement
    # ========================================================

    def move_incremental(
        self,
        distance: int,
    ) -> None:

        driver = self.require_driver()

        if driver is None:
            return

        try:
            axis = self.selected_axis()

            self.log_message(
                f"INC MOVE request: "
                f"axis={axis:X}, distance={distance}"
            )

            result = driver.direct_move_incremental(
                axis,
                distance,
            )

            self.log_message(
                f"INC MOVE result: {result}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR incremental move: {exc}"
            )

    def increment_value(self) -> int | None:
        try:
            value = int(
                self.query_one(
                    "#increment",
                    Input,
                ).value.strip(),
                0,
            )

            if value <= 0:
                raise ValueError(
                    "increment must be > 0"
                )

            return value

        except ValueError as exc:
            self.log_message(
                f"ERROR: {exc}"
            )
            return None

    # ========================================================
    # Servo
    # ========================================================

    def set_servo(
        self,
        enabled: bool,
    ) -> None:

        driver = self.require_driver()

        if driver is None:
            return

        try:
            axis = self.selected_axis()

        except ValueError as exc:
            self.log_message(
                f"ERROR: {exc}"
            )
            return

        function = (
            driver.set_son
            if enabled
            else driver.set_soff
        )

        if function is None:
            self.log_message(
                "ERROR: servo command is not available "
                "in TMBSCOM.DLL."
            )
            return

        action = (
            "SERVO ON"
            if enabled
            else "SERVO OFF"
        )

        try:
            result = function(axis)

            self.log_message(
                f"{action} axis={axis:X}: {result}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR {action}: {exc}"
            )

    # ========================================================
    # Alarm reset
    # ========================================================

    def reset_alarm_axis(self) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        try:
            axis = self.selected_axis()

        except ValueError as exc:
            self.log_message(
                f"ERROR: {exc}"
            )
            return

        if driver.reset_alarm is None:
            self.log_message(
                "ERROR: reset_alarm is not available "
                "in TMBSCOM.DLL."
            )
            return

        try:
            result = driver.reset_alarm(axis)

            self.log_message(
                f"RESET ALARM axis={axis:X}: {result}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR resetting alarm: {exc}"
            )

    # ========================================================
    # Homing
    # ========================================================

    def home_axis(self) -> None:
        driver = self.require_driver()

        if driver is None:
            return

        try:
            axis = self.selected_axis()

        except ValueError as exc:
            self.log_message(
                f"ERROR: {exc}"
            )
            return

        if driver.move_org is None:
            self.log_message(
                "ERROR: move_org is not available "
                "in TMBSCOM.DLL."
            )
            return

        try:
            status = driver.read_axis_status(axis)

            if status is None:
                self.log_message(
                    "HOME aborted: unable to read axis status."
                )
                return

            if status.get("alarm") == scn6_dll.SIO_DONE:
                self.log_message(
                    "HOME aborted: axis has an active alarm."
                )
                return

            if status.get("servo") != scn6_dll.SIO_DONE:
                self.log_message(
                    "HOME aborted: servo is OFF."
                )
                return

            # Existing driver/DLL API requires an integer mode.
            mode = 0

            result = driver.move_org(
                axis,
                mode,
            )

            self.log_message(
                f"HOME axis={axis:X}, "
                f"mode={mode}, result={result}"
            )

        except Exception as exc:
            self.log_message(
                f"ERROR homing axis {axis:X}: {exc}"
            )

    # ========================================================
    # Button events
    # ========================================================

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ) -> None:

        button = event.button.id

        if button == "connect":
            self.connect_driver()

        elif button == "disconnect":
            self.disconnect_driver()

        elif button == "reload_ini":
            self.reload_ini_config()

        elif button == "save_ini":
            self.save_ini_config()

        elif button == "refresh":
            self.update_status()

        elif button == "move_abs":
            self.request_confirmation(
                self.absolute_confirmation_text(),
                self.move_absolute,
            )

        elif button == "move_plus":
            distance = self.increment_value()

            if distance is not None:
                self.request_confirmation(
                    self.increment_confirmation_text(
                        distance
                    ),
                    lambda: self.move_incremental(
                        distance
                    ),
                )

        elif button == "move_minus":
            distance = self.increment_value()

            if distance is not None:
                self.request_confirmation(
                    self.increment_confirmation_text(
                        -distance
                    ),
                    lambda: self.move_incremental(
                        -distance
                    ),
                )

        elif button == "servo_on":
            try:
                axis = self.selected_axis()
            except ValueError:
                return

            self.request_confirmation(
                f"Enable servo on axis {axis:X}?",
                lambda: self.set_servo(True),
            )

        elif button == "servo_off":
            try:
                axis = self.selected_axis()
            except ValueError:
                return

            self.request_confirmation(
                f"Disable servo on axis {axis:X}?",
                lambda: self.set_servo(False),
            )

        elif button == "reset_alarm":
            try:
                axis = self.selected_axis()
            except ValueError:
                return

            self.request_confirmation(
                f"Reset alarm on axis {axis:X}?",
                self.reset_alarm_axis,
            )

        elif button == "home":
            try:
                axis = self.selected_axis()
            except ValueError:
                return

            self.request_confirmation(
                f"HOME axis {axis:X}?\n\n"
                "The axis may physically move.",
                self.home_axis,
            )

    # ========================================================
    # Confirmation text
    # ========================================================

    def absolute_confirmation_text(self) -> str:
        try:
            axis = self.selected_axis()

            position = int(
                self.query_one(
                    "#position",
                    Input,
                ).value.strip(),
                0,
            )

            return (
                f"Move axis {axis:X} to "
                f"absolute position {position}?\n\n"
                "The actuator may physically move."
            )

        except ValueError:
            return (
                "Invalid absolute position."
            )

    def increment_confirmation_text(
        self,
        distance: int,
    ) -> str:

        try:
            axis = self.selected_axis()

            return (
                f"Move axis {axis:X} by "
                f"{distance} pulses?\n\n"
                "The actuator may physically move."
            )

        except ValueError:
            return "Invalid axis."

    # ========================================================
    # Keyboard actions
    # ========================================================

    def action_refresh(self) -> None:
        self.update_status()

    def action_connect(self) -> None:
        self.connect_driver()

    def action_disconnect(self) -> None:
        self.disconnect_driver()

    def action_servo_on(self) -> None:
        try:
            axis = self.selected_axis()
        except ValueError:
            return

        self.request_confirmation(
            f"Enable servo on axis {axis:X}?",
            lambda: self.set_servo(True),
        )

    def action_servo_off(self) -> None:
        try:
            axis = self.selected_axis()
        except ValueError:
            return

        self.request_confirmation(
            f"Disable servo on axis {axis:X}?",
            lambda: self.set_servo(False),
        )

    # ========================================================
    # Exit
    # ========================================================

    def action_quit(self) -> None:
        self.exit()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    SCN6TUI().run()
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
