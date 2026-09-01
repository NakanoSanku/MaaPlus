from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, Protocol, TypeVar

from .routing import routed
from .scheduler import Scheduler, Task
from .tick import Tick, TickFlow, ticked

ContextT = TypeVar("ContextT")


class Navigator(Protocol[ContextT]):
    """High-level application navigator used by ``App``.

    ``ensure()`` receives the current ``Tick``. Return ``True`` only when the current snapshot
    already satisfies ``target``. Otherwise perform at most one navigation step and return
    ``False`` so the result is observed from a fresh screenshot on the next tick.
    """

    def ensure(self, target: ContextT, tick: Tick) -> bool: ...


@dataclass(frozen=True, slots=True)
class _NavigatorAdapter(Generic[ContextT]):
    navigator: Navigator[ContextT]

    def ensure(self, target: ContextT, runtime: Any, image: Any) -> bool:
        return self.navigator.ensure(target, Tick(runtime=runtime, image=image))


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
    """Opinionated facade for the common MaaPlus application workflow.

    Application code normally defines ``flow(tick)`` callables and registers them through
    ``task()``. ``App`` owns the mechanical Tick/Task/RoutedFlow/Scheduler composition while the
    underlying low-level APIs remain available for advanced use.
    """

    __slots__ = ("scheduler", "navigator", "_navigator_adapter")

    def __init__(
        self,
        scheduler: Scheduler,
        *,
        navigator: Navigator[ContextT] | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.navigator = navigator
        self._navigator_adapter = (
            _NavigatorAdapter(navigator) if navigator is not None else None
        )

    @classmethod
    def from_maa(
        cls,
        *,
        tasker: Any,
        controller: Any,
        resource: Any,
        navigator: Navigator[ContextT] | None = None,
        bind: bool = True,
    ) -> App[ContextT]:
        return cls(
            Scheduler.from_maa(
                tasker=tasker,
                controller=controller,
                resource=resource,
                bind=bind,
            ),
            navigator=navigator,
        )

    def task(
        self,
        name: str,
        flow: TickFlow,
        *,
        context: ContextT | None = None,
        priority: int = 0,
    ) -> TaskHandle:
        scheduler_flow = ticked(flow)

        if context is not None:
            if self._navigator_adapter is None:
                raise ValueError("context requires App(navigator=...)")
            scheduler_flow = routed(
                scheduler_flow,
                target=context,
                navigator=self._navigator_adapter,
            )

        return TaskHandle(
            scheduler=self.scheduler,
            task=Task(name=name, flow=scheduler_flow, priority=priority),
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
