from scn6_dll import AXIS_NUMBERS, SIO_DONE, axis_name

class StatusMixin:
    def update_axis_row(self, axis, status, position):
        w = self.query_one(f"#axis-{axis}")
        if status is None:
            w.update(f"{axis_name(axis):>4}     --        --       --        --        --        --")
            return
        def state(v):
            return "--" if v is None else ("OK" if v == SIO_DONE else str(v))
        p = "--" if position is None else str(position)
        w.update(f"{axis_name(axis):>4}     {state(status.get('servo')):<8} "
                 f"{state(status.get('run')):<8} {state(status.get('alarm')):<9} "
                 f"{state(status.get('origin')):<10} {state(status.get('pfin')):<8} {p}")

    def update_status(self):
        driver = self.driver
        if driver is None or not driver.initialized:
            return
        try:
            driver.refresh_connected_axes()
            for axis in AXIS_NUMBERS:
                if not driver.axes[axis].connected:
                    self.update_axis_row(axis, None, None)
                    continue
                status = driver.read_axis_status(axis)
                position = None
                if status is not None:
                    position, error = driver.read_controller_position(axis)
                    if error:
                        position = None
                self.update_axis_row(axis, status, position)
        except Exception as exc:
            self.log_message(f"Status update error: {exc}")
