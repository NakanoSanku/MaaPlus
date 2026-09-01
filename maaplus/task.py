from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TypeAlias

from .tick import Tick


class TaskResult(Enum):
    """Result of one task-handler invocation.

    ``CONTINUE`` keeps ownership of the external UI state and therefore blocks preemption.
    ``YIELD`` keeps the execution alive but marks the current boundary as safe for preemption.
    ``DONE`` completes the execution and releases ownership entirely.
    """

    CONTINUE = auto()
    YIELD = auto()
    DONE = auto()


TaskHandler: TypeAlias = Callable[[Tick], TaskResult]


@dataclass(frozen=True, slots=True, eq=False)
class Task:
    """One schedulable task backed by a handler and priority."""

    name: str
    handler: TaskHandler
    priority: int = 0
