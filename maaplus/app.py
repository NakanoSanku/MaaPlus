from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from .debug import Debug
from .guard import Guard, GuardHandler
from .interaction import InteractionConfig
from .routing import Navigator, routed
from .scheduler import Scheduler
from .task import ExecutionSummary, Task, TaskFailure, TaskHandler, TaskStatus

ContextT = TypeVar("ContextT")
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TaskHandle:
    """Fluent scheduling handle returned by ``App.task()``."""

    scheduler: Scheduler
    task: Task

    def submit(self) -> TaskHandle:
        self.scheduler.submit(self.task)
        return self

    def after(self, delay: int) -> TaskHandle:
        self.scheduler.after(self.task, delay=delay)
        return self

    def at(self, when: datetime) -> TaskHandle:
        self.scheduler.at(self.task, when=when)
        return self

    def every(self, interval: int) -> TaskHandle:
        self.scheduler.every(self.task, interval=interval)
        return self

    def cancel(self) -> bool:
        """Cancel queued, recurring, or currently running work for this task."""
        return self.scheduler.cancel(self.task)

    def resume(self) -> TaskHandle:
        """Resume a failed or paused task with a fresh execution context."""
        self.scheduler.resume_task(self.task)
        return self

    @property
    def failure(self) -> TaskFailure | None:
        """Return the last terminal failure for this task."""
        return self.scheduler.failure(self.task)

    @property
    def status(self) -> TaskStatus:
        return self.scheduler.status(self.task)

    @property
    def last_execution(self) -> ExecutionSummary | None:
        return self.scheduler.last_execution(self.task)


class App(Generic[ContextT]):
    """Opinionated facade for normal MaaPlus application development.

    Application code defines task handlers with ``handler(tick)`` and registers them through
    ``task()``. ``App`` owns the mechanical Task/routing/Scheduler composition while the underlying
    low-level APIs remain available for advanced use.
    """

    __slots__ = ("scheduler", "navigator", "_closed")

    def __init__(
        self,
        scheduler: Scheduler,
        *,
        navigator: Navigator[ContextT] | None = None,
        guards: Iterable[Guard] | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.navigator = navigator
        self._closed = False
        for guard in guards or ():
            self.scheduler.add_guard(guard)

    @classmethod
    def from_maa(
        cls,
        *,
        tasker: Any,
        controller: Any,
        resource: Any,
        navigator: Navigator[ContextT] | None = None,
        bind: bool = True,
        interaction: InteractionConfig | None = None,
        debug: Debug | None = None,
        trace: Any | None = None,
        guards: Iterable[Guard] | None = None,
    ) -> App[ContextT]:
        return cls(
            Scheduler.from_maa(
                tasker=tasker,
                controller=controller,
                resource=resource,
                bind=bind,
                interaction=interaction,
                debug=debug,
                trace=trace,
            ),
            navigator=navigator,
            guards=guards,
        )

    @classmethod
    def from_runtime(
        cls,
        runtime: Any,
        *,
        navigator: Navigator[ContextT] | None = None,
        trace: Any | None = None,
        guards: Iterable[Guard] | None = None,
    ) -> App[ContextT]:
        """Create an application around an already configured runtime."""
        attach_trace = getattr(trace, "attach", None)
        tasker = getattr(runtime, "tasker", None)
        if callable(attach_trace) and tasker is not None:
            attach_trace(tasker)
        return cls(Scheduler(runtime, trace=trace), navigator=navigator, guards=guards)

    def guard(
        self,
        name: str,
        handler: GuardHandler,
        *,
        priority: int = 0,
        max_consecutive: int | None = 3,
        cadence: int = 0,
        cooldown: int = 0,
    ) -> Guard:
        """Register one global guard checked before routed task handlers."""
        return self.scheduler.add_guard(
            Guard(
                name=name,
                handler=handler,
                priority=priority,
                max_consecutive=max_consecutive,
                cadence=cadence,
                cooldown=cooldown,
            )
        )

    def task(
        self,
        name: str,
        handler: TaskHandler,
        *,
        context: ContextT | None = None,
        priority: int = 0,
        timeout: int | None = None,
        retries: int = 0,
        retry_delay: int = 0,
        continue_recurring: bool = False,
        navigation_max_steps: int = 100,
        navigation_timeout: int | None = 30_000,
        yield_on_wait: bool = False,
    ) -> TaskHandle:
        task_handler = handler

        if context is not None:
            if self.navigator is None:
                raise ValueError("context requires App(navigator=...)")
            task_handler = routed(
                task_handler,
                target=context,
                navigator=self.navigator,
                max_steps=navigation_max_steps,
                timeout=navigation_timeout,
                yield_on_wait=yield_on_wait,
            )

        task = Task(
            name=name,
            handler=task_handler,
            priority=priority,
            timeout=timeout,
            retries=retries,
            retry_delay=retry_delay,
            continue_recurring=continue_recurring,
        )
        logger.debug(
            "task registered task=%s priority=%d context=%r",
            name,
            priority,
            context,
        )
        return TaskHandle(
            scheduler=self.scheduler,
            task=task,
        )

    @property
    def running(self) -> bool:
        return self.scheduler.running

    @property
    def paused(self) -> bool:
        return self.scheduler.paused

    @property
    def current(self) -> Task | None:
        return self.scheduler.current

    def run(self, *, interval: int = 0, on_started: Callable[[], None] | None = None) -> None:
        """Run work; ``on_started`` runs before the first tick for lifecycle coordination."""
        if self._closed:
            raise RuntimeError("App is closed")
        self.scheduler.run(interval=interval, on_started=on_started)

    def pause(self) -> None:
        self.scheduler.pause()

    def resume(self) -> None:
        self.scheduler.resume()

    def stop(self) -> None:
        self.scheduler.stop()

    def watch_idle(self, interval: int = 1_000) -> None:
        """Keep checking global guards while no task is active."""
        self.scheduler.watch_idle(interval)

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        """Stop execution and close owned runtime and trace resources."""
        if self._closed:
            return
        errors: list[BaseException] = []
        if self.running:
            try:
                self.stop()
            except BaseException as exc:
                errors.append(exc)

        resources = [self.scheduler.trace, getattr(self.scheduler.runtime, "trace", None)]
        resources.append(self.scheduler.runtime)
        seen: set[int] = set()
        for resource in resources:
            if resource is None or id(resource) in seen:
                continue
            seen.add(id(resource))
            close = getattr(resource, "close", None)
            if not callable(close):
                continue
            try:
                close()
            except BaseException as exc:
                errors.append(exc)
        self._closed = True
        if errors:
            raise errors[0]

    def __enter__(self) -> App[ContextT]:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()
