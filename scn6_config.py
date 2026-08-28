"""SCN6 v21 configuration loader.

Only communication and low-level driver settings belong here.
CNC-specific axis naming/mapping remains outside this file.
"""
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SCN6Config:
    port: str = "COM1"
    baud: int = 115200
    nrt: int = 2
    reset: bool = False
    automatic: bool = False
    axis_min: int = 0
    axis_max: int = 15


def load_config(path="scn6.ini"):
    parser = ConfigParser()
    path = Path(path)

    if not path.exists():
        return SCN6Config()

    parser.read(path, encoding="utf-8")
    comm = parser["communication"] if parser.has_section("communication") else {}
    drv = parser["driver"] if parser.has_section("driver") else {}

    def get_int(section, key, default):
        return int(str(section.get(key, default)).strip(), 0)

    def get_bool(section, key, default):
        value = str(section.get(key, default)).strip().lower()
        if value not in {"true", "false", "yes", "no", "on", "off", "1", "0"}:
            raise ValueError(f"Invalid boolean value for {key}: {value}")
        return value in {"true", "yes", "on", "1"}

    axis_min = int(str(drv.get("axis_min", "0")).strip(), 16)
    axis_max = int(str(drv.get("axis_max", "F")).strip(), 16)

    if not 0 <= axis_min <= axis_max <= 15:
        raise ValueError("axis_min/axis_max must define a range within 0..F")

    return SCN6Config(
        port=str(comm.get("port", "COM1")).strip(),
        baud=get_int(comm, "baud", 115200),
        nrt=get_int(comm, "nrt", 2),
        reset=get_bool(comm, "reset", False),
        automatic=get_bool(comm, "automatic", False),
        axis_min=axis_min,
        axis_max=axis_max,
    )
