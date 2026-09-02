from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from .task import TaskHandler, TaskResult
from .tick import Tick

ContextT = TypeVar("ContextT")
logger = logging.getLogger(__name__)


class Navigator(Protocol[ContextT]):
    """Application-defined adapter that makes an external UI context available.

    ``ensure()`` receives the current ``Tick``. It returns ``True`` only when that snapshot already
    satisfies ``target`` and the wrapped task handler may run immediately. Otherwise it may perform
    one navigation action and returns ``False``; the result is observed on a later tick.
    """

    def ensure(self, target: ContextT, tick: Tick) -> bool: ...


@dataclass(slots=True)
class RoutedTaskHandler(Generic[ContextT]):
    """Task-handler wrapper that restores its required UI context before business logic."""

    handler: TaskHandler
    target: ContextT
    navigator: Navigator[ContextT]

    def __call__(self, tick: Tick) -> TaskResult:
        if not self.navigator.ensure(self.target, tick):
            logger.debug("context pending target=%r", self.target)
            return TaskResult.CONTINUE

        logger.debug("context ready target=%r", self.target)
        return self.handler(tick)


def routed(
    handler: TaskHandler,
    *,
    target: ContextT,
    navigator: Navigator[ContextT],
) -> RoutedTaskHandler[ContextT]:
    """Wrap ``handler`` so each execution or resume first restores ``target`` context."""
    return RoutedTaskHandler(handler=handler, target=target, navigator=navigator)
