from textual.app import App
from textual.widgets import Button

from .confirm import ConfirmScreen
from .connection import ConnectionMixin
from .motion import MotionMixin
from .status import StatusMixin
from .ui import TUIWidgetsMixin


class SCN6TUI(
    TUIWidgetsMixin,
    ConnectionMixin,
    StatusMixin,
    MotionMixin,
    App,
):
    TITLE = "SCN6 Driver TUI"
    SUB_TITLE = "TMBSCOM Motion Controller"

    def __init__(self):
        super().__init__()
        self.driver = None

    def on_mount(self):
        self.log_message("SCN6 modular Textual TUI started.")
        self.log_message("Driver is not connected. Press CONNECT.")
        self.set_interval(1.0, self.update_status)

    def request_confirmation(self, message, callback):
        def result(confirmed):
            if confirmed:
                callback()

        self.push_screen(ConfirmScreen(message), result)

    def increment_value(self):
        try:
            value = int(
                self.query_one("#increment").value.strip(),
                0,
            )

            if value <= 0:
                raise ValueError

            return value

        except ValueError:
            self.log_message(
                "ERROR: increment must be a positive integer."
            )
            return None

    def on_button_pressed(self, event: Button.Pressed):
        button_id = event.button.id

        if button_id == "connect":
            self.connect_driver()

        elif button_id == "disconnect":
            self.disconnect_driver()

        elif button_id == "refresh":
            self.update_status()

        elif button_id == "move_abs":
            self.request_confirmation(
                f"Move axis {self.selected_axis():X} to absolute "
                f"position {self.query_one('#position').value}?\n\n"
                "This will physically move the actuator.",
                self.move_absolute,
            )

        elif button_id in ("move_plus", "move_minus"):
            distance = self.increment_value()

            if distance is not None:
                if button_id == "move_minus":
                    distance = -distance

                self.request_confirmation(
                    f"Move axis {self.selected_axis():X} "
                    f"by {distance} pulses?\n\n"
                    "This will physically move the actuator.",
                    lambda: self.move_incremental(distance),
                )

        elif button_id == "servo_on":
            self.request_confirmation(
                f"Enable servo on axis {self.selected_axis():X}?",
                lambda: self.servo(True),
            )

        elif button_id == "servo_off":
            self.request_confirmation(
                f"Disable servo on axis {self.selected_axis():X}?",
                lambda: self.servo(False),
            )

        elif button_id == "reset_alarm":
            self.request_confirmation(
                f"Reset alarm on axis {self.selected_axis():X}?",
                self.reset_alarm,
            )

        elif button_id == "home":
            self.request_confirmation(
                f"HOME axis {self.selected_axis():X}?\n\n"
                "Homing can physically move the actuator.",
                self.home_axis,
            )

    def action_quit(self):
        self.close_driver()
        self.exit()

    def action_refresh(self):
        self.update_status()

    def action_connect(self):
        self.connect_driver()

    def action_servo_on(self):
        self.request_confirmation(
            f"Enable servo on axis {self.selected_axis():X}?",
            lambda: self.servo(True),
        )

    def action_servo_off(self):
        self.request_confirmation(
            f"Disable servo on axis {self.selected_axis():X}?",
            lambda: self.servo(False),
        )

    def on_unmount(self):
        try:
            self.close_driver()
        except Exception:
            pass


if __name__ == "__main__":
    SCN6TUI().run()
