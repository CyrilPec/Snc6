from scn6_driver import SCN6Driver
from scn6_dll import SIO_DONE

class SCN6Machine:

    def __init__(self, axis_map=None):
        self.driver = SCN6Driver()

        self.axis_map = axis_map or {
            "X": 0,
            "Y": 1,
            "Z": 2,
            "A": 3,
            "B": 4,
            "C": 5,
        }

    def initialize(self):
        history = self.driver.initialize()

        return bool(self.driver.initialized), history

    def _axis_number(self, axis):
        try:
            return self.axis_map[axis.upper()]
        except KeyError:
            raise ValueError(
                f"No SCN6 axis mapping for {axis}"
            )

    def move(
        self,
        targets,
        absolute=True,
        feed=None,
        rapid=False,
    ):
        """
        Execute a G0/G1 move.

        Current SCN6 driver supports prepared multi-axis
        dispatch, but it is NOT hardware-synchronized.
        """

        self.driver.clear_motion_buffer()

        for axis, value in targets.items():

            axis_number = self._axis_number(axis)

            if absolute:
                accepted = (
                    self.driver.prepare_absolute_move(
                        axis_number,
                        int(round(value)),
                    )
                )
            else:
                accepted = (
                    self.driver.prepare_incremental_move(
                        axis_number,
                        int(round(value)),
                    )
                )

            if not accepted:
                self.driver.clear_motion_buffer()
                return False

        accepted = self.driver.start_prepared_moves()

        if not accepted:
            self.driver.clear_motion_buffer()
            return False

        # Current driver implementation provides completion
        # monitoring through PFIN/ALARM.
        completed = self.driver.wait_for_prepared_axes(
            timeout=30.0,
            interval=0.05,
        )

        self.driver.clear_motion_buffer()

        return completed

    def servo(self, enabled):
        for axis in self.driver.connected_axes():
            if not self.driver.axis_is_connected(axis):
                continue

            function = (
                self.driver.set_son
                if enabled
                else self.driver.set_soff
            )

            if function is None:
                return False

            result = function(axis)

            if result != SIO_DONE:
                return False

        return True

    def reset_alarm(self):
        if self.driver.reset_alarm is None:
            return False

        success = True

        for axis in self.driver.connected_axes():
            if not self.driver.axis_is_connected(axis):
                continue

            result = self.driver.reset_alarm(axis)

            if result != SIO_DONE:
                success = False

        return success

    def home(self):
        """
        First implementation: home all connected axes using
        mode 0.

        We will make the homing mode configurable after we
        verify the required SCN6/TERMI-BUS behavior.
        """

        if self.driver.move_org is None:
            return False

        success = True

        for axis in self.driver.connected_axes():

            if not self.driver.axis_is_connected(axis):
                continue

            result = self.driver.move_org(axis, 0)

            if result != SIO_DONE:
                success = False

        return success

    def status(self):

        result = []

        for axis in self.driver.connected_axes():

            if not self.driver.axis_is_connected(axis):
                continue

            status = self.driver.read_axis_status(axis)

            position, error = (
                self.driver.read_controller_position(axis)
            )

            result.append(
                {
                    "axis": axis,
                    "status": status,
                    "position": position,
                    "position_error": error,
                }
            )

        return result

    def close(self):
        close = getattr(
            self.driver,
            "close_tmbs",
            None,
        )

        if close:
            return close()

        return None
