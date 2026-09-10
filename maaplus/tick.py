from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .geometry import PathInterpolator, Point, PointResolver, Rect
from .locator import Locator
from .runtime import MatchResult, Runtime
from .timing import Timing

if TYPE_CHECKING:
    import numpy

    from .task import ExecutionContext


@dataclass(frozen=True, slots=True)
class Tick:
    """One task-handler decision over one fixed screenshot.

    Every ``match()`` call uses the same image captured for this scheduler tick, while actions are
    forwarded to ``Runtime``. Task handlers receive a ``Tick`` directly; application code never
    needs to pass ``runtime`` and ``image`` separately.
    """

    runtime: Runtime
    image: numpy.ndarray
    execution: ExecutionContext | None = None

    @property
    def context(self) -> ExecutionContext | None:
        """State for this task execution, fresh for each scheduled run."""
        return self.execution

    def match(self, locator: Locator, *, label: str | None = None) -> MatchResult:
        """Recognize on this snapshot; an optional label identifies the debug image."""
        if label is None:
            return self.runtime.match(locator, self.image)
        return self.runtime.match(locator, self.image, label=label)

    def draw(
        self, *boxes: Rect, label: str = "debug",
        color: tuple[int, int, int] = (64, 224, 128),
    ) -> Path | None:
        """Save this snapshot with boxes; return None when debug is disabled."""
        return self.runtime.draw(self.image, *boxes, label=label, color=color)

    def click(
        self,
        point: Point,
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
    ) -> bool:
        """Click one exact point."""
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

    def click_area(
        self,
        area: Rect,
        resolver: PointResolver | None = None,
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
    ) -> bool:
        """Resolve a point inside one rectangular area and click it."""
        return self.runtime.click_area(
            area,
            resolver=resolver,
            duration=duration,
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
        interpolation: PathInterpolator | None = None,
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
