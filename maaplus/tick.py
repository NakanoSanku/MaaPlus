from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from maa.pipeline import JRecognitionParam

from .runtime import MatchResult, Point, Runtime
from .scheduler import Flow, FlowResult

if TYPE_CHECKING:
    import numpy


@dataclass(frozen=True, slots=True)
class Tick:
    """One flow decision over one fixed screenshot.

    ``Tick`` hides explicit screenshot plumbing from application flows. Every ``match()`` call uses
    the same image captured for this scheduler tick, while actions are forwarded to ``Runtime``.
    """

    runtime: Runtime
    image: numpy.ndarray

    def match(self, locator: JRecognitionParam) -> MatchResult:
        return self.runtime.match(locator, self.image)

    def click(self, point: Point, duration: int = 50) -> bool:
        return self.runtime.click(point, duration)

    def swipe(self, points: Sequence[Point], duration: int) -> bool:
        return self.runtime.swipe(points, duration)


TickFlow: TypeAlias = Callable[[Tick], FlowResult]


@dataclass(frozen=True, slots=True)
class _TickFlowAdapter:
    flow: TickFlow

    def __call__(self, runtime: Runtime, image: numpy.ndarray) -> FlowResult:
        return self.flow(Tick(runtime=runtime, image=image))


def ticked(flow: TickFlow) -> Flow:
    """Adapt a high-level ``flow(tick)`` callable to the low-level scheduler flow protocol."""
    return _TickFlowAdapter(flow)
