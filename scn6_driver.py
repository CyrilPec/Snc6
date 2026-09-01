"""SCN6 driver API facade over the TMBSCOM DLL binding.
This v20 layer is intentionally thin: it preserves the tested v18 behavior
while giving TUI/Mach3/LinuxCNC a stable import point that is independent of
the command-line interface.
"""
from scn6_dll import TmbsController
class SCN6Driver(TmbsController):
    """Public SCN6 hardware-driver interface.
    The inherited methods are the tested TMBSCOM implementation. 
    New hardware features should be added here or below this API, not to the CLI.
    """
    def axis_status(self, axis):
        return self.read_axis_status(axis)
    def axis_position(self, axis):
        return self.read_controller_position(axis)
    def connected_axes(self):
        return self.axes
    def prepare_absolute(self, axis, position):
        return self.prepare_absolute_move(axis, position)
    def prepare_incremental(self, axis, distance):
        return self.prepare_incremental_move(axis, distance)
    def execute_prepared(self):
        return self.start_prepared_moves()