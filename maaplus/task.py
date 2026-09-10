from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from time import monotonic
from typing import Any, TypeAlias

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


class TaskStatus(Enum):
    """Observable lifecycle state of a scheduled task."""

    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    DONE = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(slots=True)
class ExecutionContext:
    """Fresh state owned by one scheduled execution of a task."""

    task_name: str
    attempt: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_monotonic: float = field(default_factory=monotonic, repr=False)
    # Scheduler-owned routing state. It is cleared when a suspended task is
    # activated again, so routed tasks restore their context after preemption
    # while still handling private screens between activations.
    route_ready: bool = False
    route_steps: int = 0
    route_started_monotonic: float | None = None

    def invalidate_route(self) -> None:
        """Require context restoration before this execution runs again."""
        self.route_ready = False
        self.route_steps = 0
        self.route_started_monotonic = None


@dataclass(frozen=True, slots=True)
class TaskFailure:
    """Terminal failure information retained by a scheduler."""

    task_name: str
    error: BaseException
    attempts: int
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class ExecutionSummary:
    """The most recent completed, failed, or cancelled task execution."""

    task_name: str
    status: TaskStatus
    result: TaskResult | None
    attempts: int
    started_at: datetime
    finished_at: datetime
    error: BaseException | None = None
    report_path: Any | None = None


class TaskTimeoutError(TimeoutError):
    """Raised when a task execution exceeds its configured deadline."""


TaskHandler: TypeAlias = Callable[[Tick], TaskResult]


@dataclass(frozen=True, slots=True, eq=False)
class Task:
    """One schedulable task backed by a handler and priority."""

    name: str
    handler: TaskHandler
    priority: int = 0
    timeout: int | None = None
    retries: int = 0
    retry_delay: int = 0
    continue_recurring: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("task name must be a non-empty string")
        if not isinstance(self.priority, int) or isinstance(self.priority, bool):
            raise TypeError("task priority must be an integer")
        if not callable(self.handler):
            raise TypeError("task handler must be callable")
        if self.timeout is not None and (
            not isinstance(self.timeout, int) or isinstance(self.timeout, bool) or self.timeout <= 0
        ):
            raise ValueError("task timeout must be a positive integer in milliseconds")
        if not isinstance(self.retries, int) or isinstance(self.retries, bool) or self.retries < 0:
            raise ValueError("task retries must be a non-negative integer")
        if not isinstance(self.retry_delay, int) or isinstance(self.retry_delay, bool) or self.retry_delay < 0:
            raise ValueError("task retry_delay must be a non-negative integer in milliseconds")
        if not isinstance(self.continue_recurring, bool):
            raise TypeError("task continue_recurring must be a boolean")
