from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, Protocol, TypeVar

from .runtime import Runtime
from .scheduler import Flow, FlowResult

if TYPE_CHECKING:
    import numpy

ContextT = TypeVar("ContextT")


class Navigator(Protocol[ContextT]):
    """Application-defined adapter that makes an external UI context available.

    ``ensure()`` receives the current tick snapshot. It returns ``True`` only when that snapshot
    already satisfies ``target`` and the wrapped business flow may run immediately. Otherwise it
    may perform one navigation action and returns ``False``; the result is observed on a later tick.
    """

    def ensure(self, target: ContextT, runtime: Runtime, image: numpy.ndarray) -> bool: ...


@dataclass(slots=True)
class RoutedFlow(Generic[ContextT]):
    """Flow wrapper that restores its required external UI context before running business logic."""

    flow: Flow
    target: ContextT
    navigator: Navigator[ContextT]

    def __call__(self, runtime: Runtime, image: numpy.ndarray) -> FlowResult:
        if not self.navigator.ensure(self.target, runtime, image):
            return FlowResult.CONTINUE
        return self.flow(runtime, image)


def routed(
    flow: Flow,
    *,
    target: ContextT,
    navigator: Navigator[ContextT],
) -> RoutedFlow[ContextT]:
    """Wrap ``flow`` so each execution or resume first restores ``target`` context."""
    return RoutedFlow(flow=flow, target=target, navigator=navigator)
