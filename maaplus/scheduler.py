from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from threading import Condition
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable

from .runtime import Runtime

if TYPE_CHECKING:
    import numpy

Flow = Callable[[Runtime, "numpy.ndarray"], bool]


@dataclass(frozen=True, slots=True, eq=False)
class Task:
    """One schedulable flow execution."""

    name: str
    flow: Flow
    priority: int = 0


class Scheduler:
    """Priority scheduler with tick-boundary cooperative preemption."""

    __slots__ = (
        "runtime",
        "_condition",
        "_current",
        "_paused",
        "_ready",
        "_running",
        "_scheduled",
        "_sequence",
        "_stop_requested",
        "_suspended",
    )

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self._condition = Condition()
        self._current: Task | None = None
        self._paused = False
        self._ready: list[tuple[int, int, Task]] = []
        self._running = False
        self._scheduled: list[tuple[float, int, Task]] = []
        self._sequence = count()
        self._stop_requested = False
        self._suspended: list[Task] = []

    @classmethod
    def from_maa(
        cls,
        *,
        tasker: Any,
        controller: Any,
        resource: Any,
        bind: bool = True,
    ) -> Scheduler:
        if bind and not tasker.bind(resource, controller):
            raise RuntimeError("Failed to bind MaaFramework resource/controller to tasker")
        return cls(Runtime(tasker=tasker, controller=controller, resource=resource))

    @property
    def running(self) -> bool:
        with self._condition:
            return self._running

    @property
    def paused(self) -> bool:
        with self._condition:
            return self._paused

    @property
    def current(self) -> Task | None:
        with self._condition:
            return self._current

    def submit(self, task: Task) -> Task:
        """Make a task ready to run immediately."""
        with self._condition:
            self._push_ready_locked(task)
            self._condition.notify_all()
        return task

    def schedule(self, task: Task, *, delay: int) -> Task:
        """Make a task ready after ``delay`` milliseconds."""
        if delay < 0:
            raise ValueError("delay must be >= 0")

        deadline = monotonic() + delay / 1000
        with self._condition:
            heappush(self._scheduled, (deadline, next(self._sequence), task))
            self._condition.notify_all()
        return task

    def tick(self, task: Task) -> bool:
        """Capture one fresh screenshot and execute one task decision tick."""
        return task.flow(self.runtime, self.runtime.screenshot())

    def run(self, *, interval: int = 0) -> None:
        """Run scheduled work until no work remains or ``stop()`` is called.

        ``interval`` is the minimum delay in milliseconds between consecutive ticks of the same
        task. A newly selected or preempting task runs immediately. Preemption only happens between
        ticks, never inside a flow call or gesture.
        """
        if interval < 0:
            raise ValueError("interval must be >= 0")

        with self._condition:
            if self._running:
                raise RuntimeError("Scheduler is already running")
            self._running = True
            self._paused = False
            self._stop_requested = False

        try:
            delay = 0
            while True:
                task = self._wait_for_task(delay)
                if task is None:
                    break

                keep_running = self.tick(task)

                with self._condition:
                    if self._current is task and not keep_running:
                        self._current = None
                        delay = 0
                    else:
                        delay = interval
                    self._condition.notify_all()
        finally:
            with self._condition:
                self._running = False
                self._paused = False
                self._stop_requested = False
                self._condition.notify_all()

    def pause(self) -> None:
        """Pause before the next task tick without interrupting the current tick."""
        with self._condition:
            if not self._running or self._paused:
                return
            self._paused = True
            self._condition.notify_all()

    def resume(self) -> None:
        """Resume a paused scheduler loop."""
        with self._condition:
            if not self._running or not self._paused:
                return
            self._paused = False
            self._condition.notify_all()

    def stop(self) -> None:
        """Stop the scheduler loop and MaaFramework work in progress."""
        with self._condition:
            self._stop_requested = True
            self._paused = False
            self._condition.notify_all()
        self.runtime.stop()

    def _wait_for_task(self, interval: int) -> Task | None:
        delay = interval / 1000
        interval_deadline: float | None = None

        with self._condition:
            while True:
                if self._stop_requested:
                    return None

                while self._paused and not self._stop_requested:
                    self._condition.wait()
                    interval_deadline = None

                if self._stop_requested:
                    return None

                self._activate_due_locked()
                switched = self._select_or_preempt_locked()

                if self._current is None:
                    if not self._scheduled:
                        return None
                    wait_for = max(0.0, self._scheduled[0][0] - monotonic())
                    self._condition.wait(wait_for)
                    continue

                if switched or delay <= 0:
                    return self._current

                if interval_deadline is None:
                    interval_deadline = monotonic() + delay

                now = monotonic()
                remaining = interval_deadline - now
                if remaining <= 0:
                    return self._current

                if self._scheduled:
                    until_scheduled = max(0.0, self._scheduled[0][0] - now)
                    remaining = min(remaining, until_scheduled)

                self._condition.wait(remaining)

    def _activate_due_locked(self) -> None:
        now = monotonic()
        while self._scheduled and self._scheduled[0][0] <= now:
            _, _, task = heappop(self._scheduled)
            self._push_ready_locked(task)

    def _select_or_preempt_locked(self) -> bool:
        if self._current is None:
            self._current = self._pop_next_locked()
            return self._current is not None

        if not self._ready:
            return False

        candidate = self._ready[0][2]
        if candidate.priority <= self._current.priority:
            return False

        self._suspended.append(self._current)
        self._current = self._pop_ready_locked()
        return True

    def _pop_next_locked(self) -> Task | None:
        suspended = self._suspended[-1] if self._suspended else None
        ready = self._ready[0][2] if self._ready else None

        if suspended is None:
            return self._pop_ready_locked() if ready is not None else None
        if ready is None or suspended.priority >= ready.priority:
            return self._suspended.pop()
        return self._pop_ready_locked()

    def _push_ready_locked(self, task: Task) -> None:
        heappush(self._ready, (-task.priority, next(self._sequence), task))

    def _pop_ready_locked(self) -> Task:
        _, _, task = heappop(self._ready)
        return task

    def __enter__(self) -> Scheduler:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.stop()
