from gcode.parser import GCodeParser

parser = GCodeParser()

for line in [
    "G90",
    "G0 X100",
    "G1 X200 F500",
    "G1 X250 Y20 F300",
    "M3",
    "M5",
    "M114",
]:
    print(line, "=>", parser.parse(line))
