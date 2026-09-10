from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from time import monotonic
from typing import Generic, Protocol, TypeVar

from .task import TaskHandler, TaskResult
from .tick import Tick

ContextT = TypeVar("ContextT")
logger = logging.getLogger(__name__)


class NavigationState(Enum):
    """Outcome of one context-restoration step."""

    READY = auto()
    WAITING = auto()
    FAILED = auto()


class NavigationError(RuntimeError):
    """Raised when context restoration exceeds its configured limits."""


class Navigator(Protocol[ContextT]):
    """Application-defined adapter that makes an external UI context available.

    ``ensure()`` receives the current ``Tick``. It returns ``READY`` only when that snapshot already
    satisfies ``target``. It may perform one navigation action and return ``WAITING``; a terminal
    ``FAILED`` result stops the routed task. Legacy boolean returns remain accepted.
    """

    def ensure(self, target: ContextT, tick: Tick) -> NavigationState: ...


@dataclass(slots=True)
class RoutedTaskHandler(Generic[ContextT]):
    """Task-handler wrapper that restores its required UI context before business logic."""

    handler: TaskHandler
    target: ContextT
    navigator: Navigator[ContextT]
    max_steps: int = 100
    timeout: int | None = 30_000
    yield_on_wait: bool = False

    def __call__(self, tick: Tick) -> TaskResult:
        context = getattr(tick, "context", None)
        # After reaching the target, the task owns the context until it yields
        # and another task takes over. This allows the business handler to
        # process private substates such as battles and result dialogs.
        # Direct calls without an ExecutionContext retain stateless behavior.
        if context is not None and context.route_ready:
            return self.handler(tick)

        raw_state = self.navigator.ensure(self.target, tick)
        if raw_state is True:
            state = NavigationState.READY
        elif raw_state is False:
            state = NavigationState.WAITING
        else:
            state = raw_state

        if not isinstance(state, NavigationState):
            raise TypeError("Navigator.ensure must return NavigationState or bool")

        if state is NavigationState.FAILED:
            raise NavigationError(f"failed to restore context {self.target!r}")
        if state is NavigationState.WAITING:
            if context is not None:
                context.route_steps += 1
                if context.route_started_monotonic is None:
                    context.route_started_monotonic = monotonic()
                if context.route_steps > self.max_steps:
                    raise NavigationError(
                        f"context {self.target!r} exceeded {self.max_steps} navigation steps"
                    )
                if (
                    self.timeout is not None
                    and context.route_started_monotonic is not None
                    and (monotonic() - context.route_started_monotonic) * 1000 > self.timeout
                ):
                    raise NavigationError(
                        f"context {self.target!r} exceeded navigation timeout {self.timeout} ms"
                    )
            logger.debug("context pending target=%r", self.target)
            return TaskResult.YIELD if self.yield_on_wait else TaskResult.CONTINUE

        logger.debug("context ready target=%r", self.target)
        if context is not None:
            context.route_ready = True
            context.route_steps = 0
            context.route_started_monotonic = None
        return self.handler(tick)


def routed(
    handler: TaskHandler,
    *,
    target: ContextT,
    navigator: Navigator[ContextT],
    max_steps: int = 100,
    timeout: int | None = 30_000,
    yield_on_wait: bool = False,
) -> RoutedTaskHandler[ContextT]:
    """Wrap ``handler`` so each execution or resume first restores ``target`` context."""
    if max_steps <= 0:
        raise ValueError("navigation max_steps must be > 0")
    if timeout is not None and timeout <= 0:
        raise ValueError("navigation timeout must be > 0")
    return RoutedTaskHandler(
        handler=handler,
        target=target,
        navigator=navigator,
        max_steps=max_steps,
        timeout=timeout,
        yield_on_wait=yield_on_wait,
    )
