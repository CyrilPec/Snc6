from dataclasses import dataclass, field

from .commands import (
    MachineCommand,
    ModeCommand,
    MoveCommand,
    StatusCommand,
)


@dataclass
class MachineState:
    absolute: bool = True
    feed: float | None = None
    positions: dict[str, float] = field(
        default_factory=lambda: {
            "X": 0.0,
            "Y": 0.0,
            "Z": 0.0,
            "A": 0.0,
            "B": 0.0,
            "C": 0.0,
        }
    )


class GCodeInterpreter:

    def __init__(self, machine):
        self.machine = machine
        self.state = MachineState()

    def execute(self, command):

        if command is None:
            return "ok"

        if isinstance(command, ModeCommand):
            self.state.absolute = command.absolute
            return "ok"

        if isinstance(command, MoveCommand):
            if command.feed is not None:
                self.state.feed = command.feed

            return self._move(command)

        if isinstance(command, MachineCommand):
            return self._machine_command(command.code)

        if isinstance(command, StatusCommand):
            return self.machine.status()

        raise ValueError(
            f"Unsupported command: {command!r}"
        )

    def _move(self, command):

        targets = {}

        for axis, value in command.axes.items():

            if axis not in self.state.positions:
                raise ValueError(
                    f"Unsupported axis: {axis}"
                )

            if self.state.absolute:
                targets[axis] = value
            else:
                targets[axis] = (
                    self.state.positions[axis] + value
                )

        if not targets:
            return "ok"

        result = self.machine.move(
            targets,
            absolute=self.state.absolute,
            feed=self.state.feed,
            rapid=command.code in ("G0", "G00"),
        )

        if result:
            for axis, position in targets.items():
                self.state.positions[axis] = position

        return "ok" if result else "error: move rejected"

    def _machine_command(self, code):

        if code == "M3":
            return "ok" if self.machine.servo(True) else \
                "error: servo ON failed"

        if code == "M5":
            return "ok" if self.machine.servo(False) else \
                "error: servo OFF failed"

        if code == "M17":
            return "ok" if self.machine.servo(True) else \
                "error: servo ON failed"

        if code == "M18":
            return "ok" if self.machine.servo(False) else \
                "error: servo OFF failed"

        if code == "M999":
            return (
                "ok"
                if self.machine.reset_alarm()
                else "error: alarm reset failed"
            )

        if code == "G28":
            return (
                "ok"
                if self.machine.home()
                else "error: homing failed"
            )

        raise ValueError(f"Unsupported machine command: {code}")
