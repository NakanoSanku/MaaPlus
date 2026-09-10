from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from heapq import heapify, heappop, heappush
from itertools import count
from threading import Condition
from time import monotonic
from typing import Any

from .debug import Debug
from .guard import Guard, GuardAbortError, GuardLoopError, GuardResult
from .interaction import InteractionConfig
from .runtime import Runtime
from .task import (
    ExecutionContext,
    ExecutionSummary,
    Task,
    TaskFailure,
    TaskResult,
    TaskStatus,
    TaskTimeoutError,
)
from .tick import Tick

logger = logging.getLogger(__name__)
_IDLE_WATCH = object()


@dataclass(slots=True)
class _Schedule:
    """Internal trigger that turns a task into ready work."""

    task: Task
    deadline: float
    trigger: str
    interval: float | None = None
    attempt: int = 0


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
        "_cancelled",
        "_executions",
        "_attempts",
        "_failures",
        "_statuses",
        "_summaries",
        "_recurring_intervals",
        "_guards",
        "_guard_streaks",
        "_guard_last_checked",
        "_guard_cooldowns",
        "_idle_watch_interval",
        "trace",
    )

    def __init__(
        self,
        runtime: Runtime,
        *,
        trace: Any | None = None,
        guards: Iterable[Guard] | None = None,
    ) -> None:
        self.runtime = runtime
        self.trace = trace if trace is not None else getattr(runtime, "trace", None)
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
        self._cancelled: set[Task] = set()
        self._executions: dict[Task, ExecutionContext] = {}
        self._attempts: dict[Task, int] = {}
        self._failures: dict[Task, TaskFailure] = {}
        self._statuses: dict[Task, TaskStatus] = {}
        self._summaries: dict[Task, ExecutionSummary] = {}
        self._recurring_intervals: dict[Task, int] = {}
        self._guards: list[Guard] = []
        self._guard_streaks: dict[Guard, int] = {}
        self._guard_last_checked: dict[Guard, float] = {}
        self._guard_cooldowns: dict[Guard, float] = {}
        self._idle_watch_interval: int | None = None
        for guard in guards or ():
            self.add_guard(guard)

    @classmethod
    def from_maa(
        cls,
        *,
        tasker: Any,
        controller: Any,
        resource: Any,
        bind: bool = True,
        interaction: InteractionConfig | None = None,
        debug: Debug | None = None,
        trace: Any | None = None,
        guards: Iterable[Guard] | None = None,
    ) -> Scheduler:
        if bind and not tasker.bind(resource, controller):
            raise RuntimeError("Failed to bind MaaFramework resource/controller to tasker")
        # ``inited`` is available in the official MaaFramework Python binding. Keep the
        # attribute check conditional so compatible light-weight bindings can omit it.
        if getattr(tasker, "inited", True) is False:
            raise RuntimeError("MaaFramework tasker is not initialized")
        attach_trace = getattr(trace, "attach", None)
        if callable(attach_trace):
            attach_trace(tasker)
        return cls(
            Runtime(
                tasker=tasker,
                controller=controller,
                resource=resource,
                interaction=interaction,
                debug=debug,
                trace=trace,
            ),
            trace=trace,
            guards=guards,
        )

    @property
    def guards(self) -> tuple[Guard, ...]:
        """Return global guards in their execution order."""
        with self._condition:
            return tuple(self._guards)

    def add_guard(self, guard: Guard) -> Guard:
        """Register one global guard; higher priority guards run first."""
        if not isinstance(guard, Guard):
            raise TypeError("guard must be a Guard instance")
        with self._condition:
            if any(existing.name == guard.name for existing in self._guards):
                raise ValueError(f"guard name already registered: {guard.name!r}")
            self._guards.append(guard)
            self._guards.sort(key=lambda item: -item.priority)
            self._guard_streaks[guard] = 0
            self._guard_last_checked.pop(guard, None)
            self._guard_cooldowns.pop(guard, None)
            self._condition.notify_all()
        return guard

    def remove_guard(self, guard: Guard) -> bool:
        """Remove a global guard and return whether it was registered."""
        with self._condition:
            try:
                self._guards.remove(guard)
            except ValueError:
                return False
            self._guard_streaks.pop(guard, None)
            self._guard_last_checked.pop(guard, None)
            self._guard_cooldowns.pop(guard, None)
            self._condition.notify_all()
        return True

    def watch_idle(self, interval: int = 1_000) -> None:
        """Keep the scheduler alive and run guards while no task is active.

        This is intended for global UI conditions such as notification dialogs that may appear
        between tasks. The interval is in milliseconds and must be positive.
        """
        if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
            raise ValueError("idle watch interval must be a positive integer in milliseconds")
        with self._condition:
            self._idle_watch_interval = interval
            self._condition.notify_all()

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

    def failure(self, task: Task) -> TaskFailure | None:
        """Return the last terminal failure for ``task``, if any."""
        with self._condition:
            return self._failures.get(task)

    @property
    def failures(self) -> tuple[TaskFailure, ...]:
        """Return terminal task failures retained by this scheduler."""
        with self._condition:
            return tuple(self._failures.values())

    def status(self, task: Task) -> TaskStatus:
        """Return the current lifecycle state for ``task``."""
        with self._condition:
            return self._statuses.get(task, TaskStatus.PENDING)

    def last_execution(self, task: Task) -> ExecutionSummary | None:
        """Return the most recent terminal execution summary for ``task``."""
        with self._condition:
            return self._summaries.get(task)

    def submit(self, task: Task) -> Task:
        """Request an immediate execution of ``task``.

        A task already current, ready, or suspended is not duplicated. Repeated requests coalesce
        into at most one pending execution that is released after the active execution completes.
        """
        logger.info("task requested task=%s priority=%d trigger=submit", task.name, task.priority)
        self._trace("task.requested", task=task.name, priority=task.priority, trigger="submit")
        with self._condition:
            self._statuses[task] = TaskStatus.PENDING
            self._request_task_locked(task)
            self._condition.notify_all()
        return task

    def cancel(self, task: Task) -> bool:
        """Cancel all queued and recurring executions of ``task``.

        If the task is currently inside a handler, that handler is allowed to finish its
        current tick and the execution is discarded before the next tick. This keeps
        cancellation cooperative and avoids interrupting a controller input half-way through.
        Returns ``True`` when the task had any active, queued, or scheduled work.
        """
        with self._condition:
            active = self._current is task
            active = active or any(ready_task is task for _, _, ready_task in self._ready)
            active = active or any(suspended_task is task for suspended_task in self._suspended)
            active = active or task in self._pending
            active = active or any(schedule.task is task for _, _, schedule in self._scheduled)

            self._pending.discard(task)
            self._ready = [item for item in self._ready if item[2] is not task]
            heapify(self._ready)
            self._scheduled = [
                item for item in self._scheduled if item[2].task is not task
            ]
            heapify(self._scheduled)
            self._suspended = [
                suspended_task
                for suspended_task in self._suspended
                if suspended_task is not task
            ]

            if self._current is task:
                if self._running:
                    self._cancelled.add(task)
                else:
                    # A stopped scheduler keeps its current task so it can be resumed. Once
                    # cancellation is requested outside the run loop, release that slot now.
                    self._current = None
                    self._current_yielded = False
                    self._cancelled.discard(task)
            else:
                self._cancelled.discard(task)
            if self._current is not task:
                self._executions.pop(task, None)
                self._attempts.pop(task, None)
            self._statuses[task] = TaskStatus.CANCELLED
            self._recurring_intervals.pop(task, None)
            self._condition.notify_all()

        if active:
            logger.info("task canceled task=%s", task.name)
        return active

    def resume_task(self, task: Task) -> Task:
        """Clear a terminal failure and request a fresh execution.

        Recurring tasks resume their previous interval; one-shot tasks are submitted immediately.
        """
        with self._condition:
            self._failures.pop(task, None)
            self._statuses[task] = TaskStatus.PENDING
            self._attempts[task] = 0
            self._executions.pop(task, None)
            interval = self._recurring_intervals.get(task)
            if interval is not None:
                self._scheduled = [
                    item for item in self._scheduled
                    if not (item[2].task is task and item[2].interval is not None)
                ]
                heapify(self._scheduled)
                self._add_schedule(
                    task,
                    monotonic() + interval / 1000,
                    trigger="every",
                    interval=interval / 1000,
                )
            else:
                self._request_task_locked(task)
            self._condition.notify_all()
        return task

    def after(self, task: Task, *, delay: int) -> Task:
        """Request one execution after ``delay`` milliseconds."""
        if delay < 0:
            raise ValueError("delay must be >= 0")

        logger.info(
            "task scheduled task=%s priority=%d trigger=after delay_ms=%d",
            task.name,
            task.priority,
            delay,
        )
        self._trace("task.scheduled", task=task.name, priority=task.priority, trigger="after", delay_ms=delay)
        with self._condition:
            self._statuses[task] = TaskStatus.PENDING
        self._add_schedule(task, monotonic() + delay / 1000, trigger="after")
        return task

    def at(self, task: Task, *, when: datetime) -> Task:
        """Request one execution at a wall-clock ``datetime``.

        Naive datetimes are interpreted in the process local timezone. A past datetime is due
        immediately. The wall-clock value is converted once to a monotonic deadline for waiting.
        """
        now = datetime.now(when.tzinfo) if when.tzinfo is not None else datetime.now()
        delay = max(0.0, (when - now).total_seconds())
        logger.info(
            "task scheduled task=%s priority=%d trigger=at when=%s",
            task.name,
            task.priority,
            when.isoformat(),
        )
        self._trace("task.scheduled", task=task.name, priority=task.priority, trigger="at", when=when)
        with self._condition:
            self._statuses[task] = TaskStatus.PENDING
        self._add_schedule(task, monotonic() + delay, trigger="at")
        return task

    def every(self, task: Task, *, interval: int) -> Task:
        """Request recurring executions every ``interval`` milliseconds.

        The first trigger happens after one interval. Recurrence follows the original monotonic
        timeline instead of ``now + interval`` so late execution does not cause schedule drift.
        Missed periods coalesce into one execution request.
        """
        if interval <= 0:
            raise ValueError("interval must be > 0")

        # One recurring trigger per task keeps repeated ``every()`` calls idempotent.
        with self._condition:
            self._scheduled = [
                item for item in self._scheduled
                if not (item[2].task is task and item[2].interval is not None)
            ]
            heapify(self._scheduled)

        logger.info(
            "task scheduled task=%s priority=%d trigger=every interval_ms=%d",
            task.name,
            task.priority,
            interval,
        )
        self._trace("task.scheduled", task=task.name, priority=task.priority, trigger="every", interval_ms=interval)
        with self._condition:
            self._recurring_intervals[task] = interval
            self._statuses[task] = TaskStatus.PENDING
        seconds = interval / 1000
        self._add_schedule(
            task,
            monotonic() + seconds,
            trigger="every",
            interval=seconds,
        )
        return task

    def tick(self, task: Task) -> TaskResult:
        """Capture one fresh screenshot and invoke one task handler."""
        return self._tick(task, ExecutionContext(task_name=task.name))

    def _tick(self, task: Task, execution: ExecutionContext) -> TaskResult:
        """Invoke one task handler with its current execution context."""
        tick_started = monotonic()
        self._check_timeout(task, execution)
        try:
            tick = Tick(
                runtime=self.runtime,
                image=self.runtime.screenshot(),
                execution=execution,
            )
            guard_started = monotonic()
            if self._run_guards(task, tick, execution):
                self._check_timeout(task, execution)
                guard_elapsed_ms = (monotonic() - guard_started) * 1000
                tick_elapsed_ms = (monotonic() - tick_started) * 1000
                logger.debug(
                    "global guard handled task=%s guard_ms=%.1f tick_ms=%.1f",
                    task.name,
                    guard_elapsed_ms,
                    tick_elapsed_ms,
                )
                self._trace(
                    "task.guard",
                    task=task.name,
                    attempt=execution.attempt,
                    guard_ms=round(guard_elapsed_ms, 3),
                    tick_ms=round(tick_elapsed_ms, 3),
                )
                # The guard may have changed the screen. Do not run a handler
                # against the stale image; the next tick gets a fresh one.
                return TaskResult.CONTINUE

            handler_started = monotonic()
            result = task.handler(tick)
        except Exception:
            logger.exception("task tick failed task=%s", task.name)
            raise

        self._check_timeout(task, execution)

        handler_elapsed_ms = (monotonic() - handler_started) * 1000
        tick_elapsed_ms = (monotonic() - tick_started) * 1000

        if not isinstance(result, TaskResult):
            logger.error(
                "invalid task result task=%s result_type=%s",
                task.name,
                type(result).__name__,
            )
            raise TypeError(
                f"Task {task.name!r} handler must return TaskResult, got {type(result).__name__}"
            )

        logger.debug(
            "handler result task=%s result=%s handler_ms=%.1f tick_ms=%.1f",
            task.name,
            result.name,
            handler_elapsed_ms,
            tick_elapsed_ms,
        )
        self._trace(
            "task.tick",
            task=task.name,
            attempt=execution.attempt,
            result=result,
            handler_ms=round(handler_elapsed_ms, 3),
            tick_ms=round(tick_elapsed_ms, 3),
        )
        return result

    def _run_guards(
        self,
        task: Task,
        tick: Tick,
        execution: ExecutionContext,
    ) -> bool:
        """Run global guards in priority order and report whether one handled the tick."""
        with self._condition:
            guards = tuple(self._guards)
        if not guards:
            return False

        checked: list[Guard] = []
        now = monotonic()
        for guard in guards:
            with self._condition:
                last_checked = self._guard_last_checked.get(guard)
                cooldown_until = self._guard_cooldowns.get(guard, 0.0)
                if cooldown_until > now or (
                    last_checked is not None and now - last_checked < guard.cadence / 1000
                ):
                    continue
                self._guard_last_checked[guard] = now
            checked.append(guard)
            raw_decision = guard.handler(tick)
            if raw_decision is None or raw_decision is False:
                decision = GuardResult.IGNORE
            elif raw_decision is True:
                decision = GuardResult.HANDLED
            else:
                decision = raw_decision
            if not isinstance(decision, GuardResult):
                raise TypeError(
                    f"Guard {guard.name!r} handler must return GuardResult, bool, or None; "
                    f"got {type(raw_decision).__name__}"
                )

            self._trace(
                "guard.checked",
                task=task.name,
                guard=guard.name,
                priority=guard.priority,
                decision=decision,
            )
            if decision is GuardResult.IGNORE:
                continue
            if decision is GuardResult.ABORT:
                raise GuardAbortError(guard.name)

            with self._condition:
                attempts = self._guard_streaks.get(guard, 0) + 1
                self._guard_streaks[guard] = attempts
                for other in guards:
                    if other is not guard:
                        self._guard_streaks[other] = 0
            if guard.max_consecutive is not None and attempts > guard.max_consecutive:
                raise GuardLoopError(guard.name, attempts)

            if decision is GuardResult.INVALIDATE:
                execution.invalidate_route()
            if guard.cooldown:
                with self._condition:
                    self._guard_cooldowns[guard] = monotonic() + guard.cooldown / 1000
            self._trace(
                "guard.handled",
                task=task.name,
                guard=guard.name,
                decision=decision,
                consecutive=attempts,
            )
            return True

        with self._condition:
            for guard in checked:
                self._guard_streaks[guard] = 0
        return False

    def _trace(self, event: str, **fields: Any) -> None:
        if self.trace is None:
            return
        try:
            self.trace.write(event, **fields)
        except Exception:
            logger.warning("trace write failed event=%s", event, exc_info=True)

    @staticmethod
    def _check_timeout(task: Task, execution: ExecutionContext) -> None:
        if task.timeout is None:
            return
        elapsed_ms = (monotonic() - execution.started_monotonic) * 1000
        if elapsed_ms > task.timeout:
            raise TaskTimeoutError(
                f"Task {task.name!r} exceeded timeout {task.timeout} ms "
                f"after {elapsed_ms:.1f} ms"
            )

    def run(self, *, interval: int = 0, on_started: Callable[[], None] | None = None) -> None:
        """Run scheduled work until no work remains or ``stop()`` is called.

        ``interval`` is the minimum delay in milliseconds between consecutive handler invocations
        of the same task. A newly selected or preempting task runs immediately. A higher-priority
        ready task may preempt the current task only after that handler explicitly returns
        ``TaskResult.YIELD``.

        A scheduler containing recurring ``every()`` work remains alive until ``stop()`` is called.
        ``on_started`` runs after lifecycle initialization and before the first tick, allowing an
        owner to apply a pending pause or stop without racing that initialization.
        """
        if interval < 0:
            raise ValueError("interval must be >= 0")

        with self._condition:
            if self._running:
                raise RuntimeError("Scheduler is already running")
            self._running = True
            self._paused = False
            self._stop_requested = False

        logger.info("scheduler started interval_ms=%d", interval)

        try:
            if on_started is not None:
                on_started()
            delay = 0
            while True:
                task = self._wait_for_task(delay)
                if task is _IDLE_WATCH:
                    self._run_idle_watch()
                    delay = 0
                    continue
                if task is None:
                    break

                with self._condition:
                    execution = self._executions.setdefault(
                        task,
                        ExecutionContext(
                            task_name=task.name,
                            attempt=self._attempts.pop(task, 0),
                        ),
                    )
                    self._statuses[task] = TaskStatus.RUNNING

                try:
                    result = self._tick(task, execution)
                except Exception as exc:
                    with self._condition:
                        self._handle_failure_locked(task, execution, exc)
                        self._condition.notify_all()
                    delay = 0
                    continue

                with self._condition:
                    cancelled = task in self._cancelled
                    if cancelled:
                        self._cancelled.discard(task)
                        if self._current is task:
                            logger.info("task canceled after tick task=%s", task.name)
                            self._current = None
                            self._current_yielded = False
                            self._executions.pop(task, None)
                            self._pending.discard(task)
                            self._statuses[task] = TaskStatus.CANCELLED
                            self._record_summary_locked(
                                task,
                                execution,
                                status=TaskStatus.CANCELLED,
                                result=None,
                                error=None,
                            )
                            delay = 0
                    elif self._current is task and result is TaskResult.DONE:
                        logger.info("task completed task=%s", task.name)
                        self._current = None
                        self._current_yielded = False
                        self._executions.pop(task, None)
                        self._statuses[task] = TaskStatus.DONE
                        self._record_summary_locked(
                            task,
                            execution,
                            status=TaskStatus.DONE,
                            result=result,
                            error=None,
                        )
                        self._release_pending_locked(task)
                        if any(item[2].task is task for item in self._scheduled) or self._task_active_locked(task):
                            self._statuses[task] = TaskStatus.PENDING
                        delay = 0
                    elif self._current is task:
                        self._statuses[task] = TaskStatus.RUNNING
                        self._current_yielded = result is TaskResult.YIELD
                        if self._current_yielded:
                            logger.debug("task yielded task=%s", task.name)
                        delay = interval
                    self._condition.notify_all()
        finally:
            with self._condition:
                self._running = False
                self._paused = False
                self._stop_requested = False
                self._condition.notify_all()
            logger.info("scheduler stopped")

    def pause(self) -> None:
        """Pause before the next task handler invocation without interrupting the current one."""
        with self._condition:
            if not self._running or self._paused:
                return
            self._paused = True
            if self._current is not None:
                self._statuses[self._current] = TaskStatus.PAUSED
            self._condition.notify_all()
        logger.info("scheduler paused")

    def resume(self) -> None:
        """Resume a paused scheduler loop."""
        with self._condition:
            if not self._running or not self._paused:
                return
            self._paused = False
            if self._current is not None:
                self._statuses[self._current] = TaskStatus.RUNNING
            self._condition.notify_all()
        logger.info("scheduler resumed")

    def stop(self) -> None:
        """Stop execution without discarding unfinished current or queued tasks."""
        with self._condition:
            was_running = self._running
            self._stop_requested = True
            self._paused = False
            if self._current is not None:
                execution = self._executions.get(self._current)
                if execution is not None:
                    execution.invalidate_route()
                self._statuses[self._current] = TaskStatus.PAUSED
            self._condition.notify_all()
        if was_running:
            logger.info("scheduler stop requested")
        self.runtime.stop()

    def _add_schedule(
        self,
        task: Task,
        deadline: float,
        *,
        trigger: str,
        interval: float | None = None,
        attempt: int = 0,
    ) -> None:
        schedule = _Schedule(
            task=task,
            deadline=deadline,
            trigger=trigger,
            interval=interval,
            attempt=attempt,
        )
        with self._condition:
            self._push_schedule_locked(schedule)
            self._condition.notify_all()

    def _wait_for_task(self, interval: int) -> Task | object | None:
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
                        if self._idle_watch_interval is None:
                            return None
                        wait_for = self._idle_watch_interval / 1000
                    else:
                        wait_for = max(0.0, self._scheduled[0][0] - monotonic())
                        if self._idle_watch_interval is not None:
                            wait_for = min(wait_for, self._idle_watch_interval / 1000)
                    woke = self._condition.wait(wait_for)
                    if not woke and self._idle_watch_interval is not None:
                        next_deadline = self._scheduled[0][0] if self._scheduled else None
                        if next_deadline is None or next_deadline > monotonic():
                            return _IDLE_WATCH
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

    def _run_idle_watch(self) -> None:
        with self._condition:
            guards = tuple(self._guards)
        if not guards:
            return
        idle_task = Task("__maaplus_idle_watch__", lambda tick: TaskResult.DONE)
        tick = Tick(runtime=self.runtime, image=self.runtime.screenshot())
        self._run_guards(
            idle_task,
            tick,
            ExecutionContext(task_name=idle_task.name),
        )

    def _activate_due_locked(self) -> None:
        now = monotonic()
        while self._scheduled and self._scheduled[0][0] <= now:
            _, _, schedule = heappop(self._scheduled)
            logger.info(
                "task trigger due task=%s priority=%d trigger=%s",
                schedule.task.name,
                schedule.task.priority,
                schedule.trigger,
            )
            self._request_task_with_attempt_locked(schedule.task, attempt=schedule.attempt)

            if schedule.interval is not None:
                next_deadline = schedule.deadline + schedule.interval
                while next_deadline <= now:
                    next_deadline += schedule.interval
                schedule.deadline = next_deadline
                self._push_schedule_locked(schedule)

    def _select_or_preempt_locked(self) -> bool:
        if self._current is None:
            suspended = self._suspended[-1] if self._suspended else None
            self._current = self._pop_next_locked()
            self._current_yielded = False
            if self._current is None:
                return False

            if self._current is suspended:
                execution = self._executions.get(self._current)
                if execution is not None:
                    execution.invalidate_route()
                logger.info(
                    "task resumed task=%s priority=%d",
                    self._current.name,
                    self._current.priority,
                )
            else:
                logger.info(
                    "task started task=%s priority=%d",
                    self._current.name,
                    self._current.priority,
                )
            return True

        if not self._current_yielded or not self._ready:
            return False

        candidate = self._ready[0][2]
        if candidate.priority <= self._current.priority:
            return False

        previous = self._current
        execution = self._executions.get(previous)
        if execution is not None:
            execution.invalidate_route()
        self._suspended.append(previous)
        self._statuses[previous] = TaskStatus.PAUSED
        self._current = self._pop_ready_locked()
        self._current_yielded = False
        logger.info(
            "task preempted task=%s priority=%d by=%s priority=%d",
            previous.name,
            previous.priority,
            self._current.name,
            self._current.priority,
        )
        logger.info(
            "task started task=%s priority=%d",
            self._current.name,
            self._current.priority,
        )
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
        self._request_task_with_attempt_locked(task, attempt=None)

    def _request_task_with_attempt_locked(self, task: Task, *, attempt: int | None) -> None:
        # An explicit submit after cancellation starts a fresh execution request.
        self._cancelled.discard(task)
        if attempt is None:
            self._attempts[task] = 0
            self._failures.pop(task, None)
        elif not self._task_active_locked(task):
            self._attempts[task] = attempt
            self._statuses[task] = TaskStatus.PENDING
        if self._task_active_locked(task):
            already_pending = task in self._pending
            self._pending.add(task)
            logger.debug(
                "task request coalesced task=%s pending_new=%s",
                task.name,
                not already_pending,
            )
            return
        self._push_ready_locked(task)
        logger.debug("task ready task=%s priority=%d", task.name, task.priority)

    def _handle_failure_locked(
        self,
        task: Task,
        execution: ExecutionContext,
        error: BaseException,
    ) -> None:
        if self._current is task:
            self._current = None
            self._current_yielded = False
        self._executions.pop(task, None)
        next_attempt = execution.attempt + 1
        if next_attempt <= task.retries:
            self._attempts[task] = next_attempt
            self._statuses[task] = TaskStatus.PENDING
            self._add_schedule(
                task,
                monotonic() + task.retry_delay / 1000,
                trigger="retry",
                attempt=next_attempt,
            )
            logger.warning(
                "task failed; retry scheduled task=%s attempt=%d/%d error=%s",
                task.name,
                next_attempt,
                task.retries,
                error,
            )
            self._trace(
                "task.failed",
                task=task.name,
                attempt=next_attempt,
                retries=task.retries,
                retry_scheduled=True,
                error=error,
            )
            return

        self._attempts.pop(task, None)
        self._failures[task] = TaskFailure(
            task_name=task.name,
            error=error,
            attempts=next_attempt,
            occurred_at=datetime.now(timezone.utc),
        )
        report_path = None
        failure_report = getattr(self.trace, "failure_report", None)
        if callable(failure_report):
            try:
                report_path = failure_report(
                    task.name,
                    error,
                    attempts=next_attempt,
                )
            except Exception:
                logger.warning("failure report failed task=%s", task.name, exc_info=True)
        self._statuses[task] = TaskStatus.FAILED
        self._record_summary_locked(
            task,
            execution,
            status=TaskStatus.FAILED,
            result=None,
            error=error,
            report_path=report_path,
        )
        logger.error(
            "task failed permanently task=%s attempts=%d error=%s",
            task.name,
            next_attempt,
            error,
        )
        if report_path is not None:
            logger.error("failure report task=%s path=%s", task.name, report_path)
        self._trace(
            "task.failed",
            task=task.name,
            attempt=next_attempt,
            retries=task.retries,
            retry_scheduled=False,
            error=error,
            traceback=self._format_exception(error),
            report_path=report_path,
        )
        if task in self._recurring_intervals and not task.continue_recurring:
            self._scheduled = [
                item for item in self._scheduled
                if item[2].task is not task or item[2].interval is None
            ]
            heapify(self._scheduled)
            logger.warning("recurring task paused after terminal failure task=%s", task.name)
        self._release_pending_locked(task)

    def _record_summary_locked(
        self,
        task: Task,
        execution: ExecutionContext,
        *,
        status: TaskStatus,
        result: TaskResult | None,
        error: BaseException | None,
        report_path: Any | None = None,
    ) -> None:
        self._summaries[task] = ExecutionSummary(
            task_name=task.name,
            status=status,
            result=result,
            attempts=execution.attempt + 1,
            started_at=execution.started_at,
            finished_at=datetime.now(timezone.utc),
            error=error,
            report_path=report_path,
        )

    @staticmethod
    def _format_exception(error: BaseException) -> str:
        import traceback

        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    def _release_pending_locked(self, task: Task) -> None:
        if task not in self._pending:
            return
        self._pending.remove(task)
        self._push_ready_locked(task)
        logger.debug("pending task released task=%s", task.name)

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
