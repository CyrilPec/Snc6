from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MoveCommand:
    code: str
    axes: dict[str, float] = field(default_factory=dict)
    feed: Optional[float] = None


@dataclass
class ModeCommand:
    absolute: bool


@dataclass
class MachineCommand:
    code: str


@dataclass
class StatusCommand:
    pass
