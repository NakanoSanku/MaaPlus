from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from .interaction import InteractionConfig
from .routing import Navigator, routed
from .scheduler import Scheduler
from .task import Task, TaskHandler

ContextT = TypeVar("ContextT")


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


class App(Generic[ContextT]):
    """Opinionated facade for normal MaaPlus application development.

    Application code defines task handlers with ``handler(tick)`` and registers them through
    ``task()``. ``App`` owns the mechanical Task/routing/Scheduler composition while the underlying
    low-level APIs remain available for advanced use.
    """

    __slots__ = ("scheduler", "navigator")

    def __init__(
        self,
        scheduler: Scheduler,
        *,
        navigator: Navigator[ContextT] | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.navigator = navigator

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
    ) -> App[ContextT]:
        return cls(
            Scheduler.from_maa(
                tasker=tasker,
                controller=controller,
                resource=resource,
                bind=bind,
                interaction=interaction,
            ),
            navigator=navigator,
        )

    def task(
        self,
        name: str,
        handler: TaskHandler,
        *,
        context: ContextT | None = None,
        priority: int = 0,
    ) -> TaskHandle:
        task_handler = handler

        if context is not None:
            if self.navigator is None:
                raise ValueError("context requires App(navigator=...)")
            task_handler = routed(
                task_handler,
                target=context,
                navigator=self.navigator,
            )

        return TaskHandle(
            scheduler=self.scheduler,
            task=Task(name=name, handler=task_handler, priority=priority),
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

    def run(self, *, interval: int = 0) -> None:
        self.scheduler.run(interval=interval)

    def pause(self) -> None:
        self.scheduler.pause()

    def resume(self) -> None:
        self.scheduler.resume()

    def stop(self) -> None:
        self.scheduler.stop()

    def __enter__(self) -> App[ContextT]:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.stop()
