from scn6_dll import SIO_DONE, axis_name

class MotionMixin:
    def move_absolute(self):
        driver = self.require_driver()
        if driver is None: return
        axis = self.selected_axis()
        try: position = int(self.query_one("#position").value, 0)
        except ValueError:
            self.log_message("ERROR: invalid absolute position."); return
        try:
            result = driver.direct_move_absolute(axis, position)
            self.log_message(f"move_abs axis {axis_name(axis)} position={position} -> {result}")
        except Exception as exc:
            self.log_message(f"ERROR during absolute move: {exc}")

    def move_incremental(self, distance):
        driver = self.require_driver()
        if driver is None: return
        axis = self.selected_axis()
        try:
            result = driver.direct_move_incremental(axis, distance)
            self.log_message(f"move_inc axis {axis_name(axis)} distance={distance} -> {result}")
        except Exception as exc:
            self.log_message(f"ERROR during incremental move: {exc}")

    def servo(self, enabled):
        driver = self.require_driver()
        if driver is None: return
        axis = self.selected_axis()
        fn = driver.set_son if enabled else driver.set_soff
        if fn is None:
            self.log_message("ERROR: servo DLL function is unavailable."); return
        try:
            self.log_message(f"{'SERVO ON' if enabled else 'SERVO OFF'} axis {axis_name(axis)} -> {fn(axis)}")
        except Exception as exc:
            self.log_message(f"ERROR changing servo state: {exc}")

    def reset_alarm(self):
        driver = self.require_driver()
        if driver is None: return
        axis = self.selected_axis()
        if driver.reset_alarm is None:
            self.log_message("ERROR: reset_alarm DLL export is unavailable."); return
        try: self.log_message(f"reset_alarm axis {axis_name(axis)} -> {driver.reset_alarm(axis)}")
        except Exception as exc: self.log_message(f"ERROR resetting alarm: {exc}")

    def home_axis(self):
        driver = self.require_driver()
        if driver is None: return
        axis = self.selected_axis()
        if driver.move_org is None:
            self.log_message("ERROR: move_org DLL export is unavailable."); return
        try:
            status = driver.read_axis_status(axis)
            if status is None: return
            if status["alarm"] == SIO_DONE:
                self.log_message("HOME ABORTED: alarm is active."); return
            if status["servo"] != SIO_DONE:
                self.log_message("HOME ABORTED: servo is OFF."); return
            driver.move_org(axis, 0)
            self.log_message(f"Homing command issued: axis={axis_name(axis)} mode=0")
        except Exception as exc: self.log_message(f"ERROR during homing: {exc}")
