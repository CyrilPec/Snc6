from textual.app import App
from textual.widgets import Button
from .confirm import ConfirmScreen
from .connection import ConnectionMixin
from .motion import MotionMixin
from .status import StatusMixin
from .ui import TUIWidgetsMixin

class SCN6TUI(TUIWidgetsMixin, ConnectionMixin, StatusMixin, MotionMixin, App):
    TITLE = "SCN6 Driver TUI"
    SUB_TITLE = "TMBSCOM Motion Controller"

    def __init__(self):
        super().__init__()
        self.driver = None

    def on_mount(self):
        self.log_message("SCN6 modular Textual TUI started.")
        self.log_message("Driver is not connected. Press CONNECT.")
        self.set_interval(1.0, self.update_status)

    def on_unmount(self):
        self.close_driver()

    def request_confirmation(self, message, callback):
        def result(confirmed):
            if confirmed: callback()
        self.push_screen(ConfirmScreen(message), result)

    def increment_value(self):
        try:
            value = int(self.query_one("#increment").value.strip(), 0)
            if value <= 0: raise ValueError
            return value
        except ValueError:
            self.log_message("ERROR: increment must be a positive integer.")
            return None

    def on_button_pressed(self, event: Button.Pressed):
        b = event.button.id
        if b == "connect": self.connect_driver()
        elif b == "disconnect": self.disconnect_driver()
        elif b == "refresh": self.update_status()
        elif b == "move_abs":
            self.request_confirmation(
                f"Move axis {self.selected_axis():X} to absolute position "
                f"{self.query_one('#position').value}?\n\nThis will physically move the actuator.",
                self.move_absolute)
        elif b in ("move_plus", "move_minus"):
            d = self.increment_value()
            if d is not None:
                d = d if b == "move_plus" else -d
                self.request_confirmation(
                    f"Move axis {self.selected_axis():X} by {d} pulses?\n\nThis will physically move the actuator.",
                    lambda: self.move_incremental(d))
        elif b == "servo_on":
            self.request_confirmation(f"Enable servo on axis {self.selected_axis():X}?",
                                      lambda: self.servo(True))
        elif b == "servo_off":
            self.request_confirmation(f"Disable servo on axis {self.selected_axis():X}?",
                                      lambda: self.servo(False))
        elif b == "reset_alarm":
            self.request_confirmation(f"Reset alarm on axis {self.selected_axis():X}?",
                                      self.reset_alarm)
        elif b == "home":
            self.request_confirmation(f"HOME axis {self.selected_axis():X}?\n\nHoming can physically move the actuator.",
                                      self.home_axis)

    def action_quit(self): self.exit()
    def action_refresh(self): self.update_status()
    def action_connect(self): self.connect_driver()
    def action_servo_on(self):
        self.request_confirmation(f"Enable servo on axis {self.selected_axis():X}?", lambda: self.servo(True))
    def action_servo_off(self):
        self.request_confirmation(f"Disable servo on axis {self.selected_axis():X}?", lambda: self.servo(False))

if __name__ == "__main__":
    SCN6TUI().run()
