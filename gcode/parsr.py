from pathlib import Path

from lark import Lark, Transformer

from .commands import (
    MachineCommand,
    ModeCommand,
    MoveCommand,
    StatusCommand,
)


class GCodeTransformer(Transformer):

    def start(self, items):
        return items[0]

    def empty(self, items):
        return None

    def comment(self, items):
        return None

    def G90(self, items):
        return ModeCommand(absolute=True)

    def G91(self, items):
        return ModeCommand(absolute=False)

    def M3(self, items):
        return MachineCommand("M3")

    def M5(self, items):
        return MachineCommand("M5")

    def M17(self, items):
        return MachineCommand("M17")

    def M18(self, items):
        return MachineCommand("M18")

    def M999(self, items):
        return MachineCommand("M999")

    def G28(self, items):
        return MachineCommand("G28")

    def M114(self, items):
        return StatusCommand()

    def motion(self, items):
        code = str(items[0])
        axes = {}
        feed = None

        for item in items[1:]:
            text = str(item)

            if text.startswith("F"):
                feed = float(text[1:])
            else:
                axis = text[0]
                value = float(text[1:])
                axes[axis] = value

        return MoveCommand(
            code=code,
            axes=axes,
            feed=feed,
        )


class GCodeParser:

    def __init__(self, grammar_path=None):
        if grammar_path is None:
            grammar_path = Path(__file__).with_name("grammar.lark")

        self.parser = Lark.open(
            str(grammar_path),
            parser="lalr",
            lexer="contextual",
            transformer=GCodeTransformer(),
        )

    def parse(self, line: str):
        return self.parser.parse(line.strip())
