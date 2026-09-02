from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from maa.pipeline import JRecognitionParam

from .runtime import MatchResult, Point, Runtime
from .swipe import SwipeInterpolator
from .timing import Timing

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

    def click(
        self,
        point: Point,
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
    ) -> bool:
        if pre_delay is None and post_delay is None:
            if duration is None:
                return self.runtime.click(point)
            return self.runtime.click(point, duration)

        return self.runtime.click(
            point,
            duration,
            pre_delay=pre_delay,
            post_delay=post_delay,
        )

    def swipe(
        self,
        points: Sequence[Point],
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
        interpolation: SwipeInterpolator | None = None,
    ) -> bool:
        if pre_delay is None and post_delay is None and interpolation is None:
            if duration is None:
                return self.runtime.swipe(points)
            return self.runtime.swipe(points, duration)

        return self.runtime.swipe(
            points,
            duration,
            pre_delay=pre_delay,
            post_delay=post_delay,
            interpolation=interpolation,
        )
