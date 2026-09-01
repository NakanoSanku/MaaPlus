from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maa.pipeline import JRecognitionParam

from .runtime import MatchResult, Point, Runtime

if TYPE_CHECKING:
    import numpy


@dataclass(frozen=True, slots=True)
class Tick:
    """One task-handler decision over one fixed screenshot.

    Every ``match()`` call uses the same image captured for this scheduler tick, while actions are
    forwarded to ``Runtime``. Task handlers receive a ``Tick`` directly; application code never
    needs to pass ``runtime`` and ``image`` separately.
    """

    runtime: Runtime
    image: numpy.ndarray

    def match(self, locator: JRecognitionParam) -> MatchResult:
        return self.runtime.match(locator, self.image)

    def click(self, point: Point, duration: int = 50) -> bool:
        return self.runtime.click(point, duration)

    def swipe(self, points: Sequence[Point], duration: int) -> bool:
        return self.runtime.swipe(points, duration)
