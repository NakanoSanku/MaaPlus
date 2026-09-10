from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias

from .tick import Tick


class GuardResult(Enum):
    """Decision returned by one global guard for the current screenshot."""

    IGNORE = auto()
    HANDLED = auto()
    INVALIDATE = auto()
    ABORT = auto()


class GuardAbortError(RuntimeError):
    """Raised when a guard reports a fatal global UI condition."""

    def __init__(self, guard_name: str) -> None:
        self.guard_name = guard_name
        super().__init__(f"guard {guard_name!r} requested task abort")


class GuardLoopError(RuntimeError):
    """Raised when one guard keeps handling the same visible condition."""

    def __init__(self, guard_name: str, attempts: int) -> None:
        self.guard_name = guard_name
        self.attempts = attempts
        super().__init__(
            f"guard {guard_name!r} handled {attempts} consecutive ticks without clearing the condition"
        )


GuardHandler: TypeAlias = Callable[[Tick], GuardResult | bool | None]


@dataclass(frozen=True, slots=True, eq=False)
class Guard:
    """One ordered, application-wide check performed before a task handler.

    ``cadence`` limits how often the handler is evaluated and ``cooldown`` delays the next
    evaluation after a handled condition. Both values are milliseconds and default to zero.
    """

    name: str
    handler: GuardHandler
    priority: int = 0
    max_consecutive: int | None = 3
    cadence: int = 0
    cooldown: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("guard name must be a non-empty string")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise TypeError("guard priority must be an integer")
        if not callable(self.handler):
            raise TypeError("guard handler must be callable")
        if self.max_consecutive is not None and (
            not isinstance(self.max_consecutive, int)
            or isinstance(self.max_consecutive, bool)
            or self.max_consecutive <= 0
        ):
            raise ValueError("guard max_consecutive must be a positive integer or None")
        for field_name, value in (("cadence", self.cadence), ("cooldown", self.cooldown)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"guard {field_name} must be a non-negative integer")
