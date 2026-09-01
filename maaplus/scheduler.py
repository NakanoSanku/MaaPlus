from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from heapq import heappop, heappush
from itertools import count
from threading import Condition
from time import monotonic
from typing import Any

from .runtime import Runtime
from .task import Task, TaskResult
from .tick import Tick


@dataclass(slots=True)
class _Schedule:
    """Internal trigger that turns a task into ready work."""

    task: Task
    deadline: float
    interval: float | None = None


class Scheduler:
    """Priority scheduler with explicit safe-point cooperative preemption."""

    __slots__ = (
        "runtime",
        "_condition",
        "_current",
        "_current_yielded",
        "_paused",
        "_pending",
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
        self._current_yielded = False
        self._paused = False
        self._pending: set[Task] = set()
        self._ready: list[tuple[int, int, Task]] = []
        self._running = False
        self._scheduled: list[tuple[float, int, _Schedule]] = []
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
        """Request an immediate execution of ``task``.

        A task already current, ready, or suspended is not duplicated. Repeated requests coalesce
        into at most one pending execution that is released after the active execution completes.
        """
        with self._condition:
            self._request_task_locked(task)
            self._condition.notify_all()
        return task

    def after(self, task: Task, *, delay: int) -> Task:
        """Request one execution after ``delay`` milliseconds."""
        if delay < 0:
            raise ValueError("delay must be >= 0")

        self._add_schedule(task, monotonic() + delay / 1000)
        return task

    def at(self, task: Task, *, when: datetime) -> Task:
        """Request one execution at a wall-clock ``datetime``.

        Naive datetimes are interpreted in the process local timezone. A past datetime is due
        immediately. The wall-clock value is converted once to a monotonic deadline for waiting.
        """
        now = datetime.now(when.tzinfo) if when.tzinfo is not None else datetime.now()
        delay = max(0.0, (when - now).total_seconds())
        self._add_schedule(task, monotonic() + delay)
        return task

    def every(self, task: Task, *, interval: int) -> Task:
        """Request recurring executions every ``interval`` milliseconds.

        The first trigger happens after one interval. Recurrence follows the original monotonic
        timeline instead of ``now + interval`` so late execution does not cause schedule drift.
        Missed periods coalesce into one execution request.
        """
        if interval <= 0:
            raise ValueError("interval must be > 0")

        seconds = interval / 1000
        self._add_schedule(task, monotonic() + seconds, interval=seconds)
        return task

    def tick(self, task: Task) -> TaskResult:
        """Capture one fresh screenshot and invoke one task handler."""
        tick = Tick(runtime=self.runtime, image=self.runtime.screenshot())
        result = task.handler(tick)
        if not isinstance(result, TaskResult):
            raise TypeError(
                f"Task {task.name!r} handler must return TaskResult, got {type(result).__name__}"
            )
        return result

    def run(self, *, interval: int = 0) -> None:
        """Run scheduled work until no work remains or ``stop()`` is called.

        ``interval`` is the minimum delay in milliseconds between consecutive handler invocations
        of the same task. A newly selected or preempting task runs immediately. A higher-priority
        ready task may preempt the current task only after that handler explicitly returns
        ``TaskResult.YIELD``.

        A scheduler containing recurring ``every()`` work remains alive until ``stop()`` is called.
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

                result = self.tick(task)

                with self._condition:
                    if self._current is task and result is TaskResult.DONE:
                        self._current = None
                        self._current_yielded = False
                        self._release_pending_locked(task)
                        delay = 0
                    elif self._current is task:
                        self._current_yielded = result is TaskResult.YIELD
                        delay = interval
                    self._condition.notify_all()
        finally:
            with self._condition:
                self._running = False
                self._paused = False
                self._stop_requested = False
                self._condition.notify_all()

    def pause(self) -> None:
        """Pause before the next task handler invocation without interrupting the current one."""
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
        """Stop execution without discarding unfinished current or queued tasks."""
        with self._condition:
            self._stop_requested = True
            self._paused = False
            self._condition.notify_all()
        self.runtime.stop()

    def _add_schedule(self, task: Task, deadline: float, *, interval: float | None = None) -> None:
        schedule = _Schedule(task=task, deadline=deadline, interval=interval)
        with self._condition:
            self._push_schedule_locked(schedule)
            self._condition.notify_all()

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
            _, _, schedule = heappop(self._scheduled)
            self._request_task_locked(schedule.task)

            if schedule.interval is not None:
                next_deadline = schedule.deadline + schedule.interval
                while next_deadline <= now:
                    next_deadline += schedule.interval
                schedule.deadline = next_deadline
                self._push_schedule_locked(schedule)

    def _select_or_preempt_locked(self) -> bool:
        if self._current is None:
            self._current = self._pop_next_locked()
            self._current_yielded = False
            return self._current is not None

        if not self._current_yielded or not self._ready:
            return False

        candidate = self._ready[0][2]
        if candidate.priority <= self._current.priority:
            return False

        self._suspended.append(self._current)
        self._current = self._pop_ready_locked()
        self._current_yielded = False
        return True

    def _pop_next_locked(self) -> Task | None:
        suspended = self._suspended[-1] if self._suspended else None
        ready = self._ready[0][2] if self._ready else None

        if suspended is None:
            return self._pop_ready_locked() if ready is not None else None
        if ready is None or suspended.priority >= ready.priority:
            return self._suspended.pop()
        return self._pop_ready_locked()

    def _request_task_locked(self, task: Task) -> None:
        if self._task_active_locked(task):
            self._pending.add(task)
            return
        self._push_ready_locked(task)

    def _release_pending_locked(self, task: Task) -> None:
        if task not in self._pending:
            return
        self._pending.remove(task)
        self._push_ready_locked(task)

    def _task_active_locked(self, task: Task) -> bool:
        if self._current is task:
            return True
        if any(ready_task is task for _, _, ready_task in self._ready):
            return True
        return any(suspended_task is task for suspended_task in self._suspended)

    def _push_ready_locked(self, task: Task) -> None:
        heappush(self._ready, (-task.priority, next(self._sequence), task))

    def _pop_ready_locked(self) -> Task:
        _, _, task = heappop(self._ready)
        return task

    def _push_schedule_locked(self, schedule: _Schedule) -> None:
        heappush(self._scheduled, (schedule.deadline, next(self._sequence), schedule))

    def __enter__(self) -> Scheduler:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.stop()
