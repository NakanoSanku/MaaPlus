from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, cast

from maa.pipeline import (
    JAnd,
    JColorMatch,
    JCustomRecognition,
    JDirectHit,
    JFeatureMatch,
    JNeuralNetworkClassify,
    JNeuralNetworkDetect,
    JOCR,
    JOr,
    JRecognitionParam,
    JRecognitionType,
    JRect,
    JTemplateMatch,
)

from .click import ClickResolver, Point, center
from .interaction import InteractionConfig
from .swipe import SwipeInterpolator
from .timing import Timing, resolve as resolve_timing

if TYPE_CHECKING:
    import numpy

    from maa.define import RecognitionDetail


_RECOGNITION_TYPES: dict[type[Any], JRecognitionType] = {
    JDirectHit: JRecognitionType.DirectHit,
    JTemplateMatch: JRecognitionType.TemplateMatch,
    JFeatureMatch: JRecognitionType.FeatureMatch,
    JColorMatch: JRecognitionType.ColorMatch,
    JOCR: JRecognitionType.OCR,
    JNeuralNetworkClassify: JRecognitionType.NeuralNetworkClassify,
    JNeuralNetworkDetect: JRecognitionType.NeuralNetworkDetect,
    JAnd: JRecognitionType.And,
    JOr: JRecognitionType.Or,
    JCustomRecognition: JRecognitionType.Custom,
}


def _recognition_type(locator: JRecognitionParam) -> JRecognitionType:
    try:
        return _RECOGNITION_TYPES[type(locator)]
    except KeyError as exc:
        raise TypeError(f"Unsupported recognition parameter: {type(locator).__name__}") from exc


@dataclass(slots=True)
class MatchResult:
    """MaaFramework recognition result with click sugar."""

    detail: RecognitionDetail
    _click: Callable[..., bool] | None = field(default=None, repr=False)
    _click_resolver: ClickResolver = field(default=center, repr=False)

    @property
    def hit(self) -> bool:
        return bool(self.detail.hit)

    @property
    def box(self) -> JRect | None:
        if self.detail.box is None:
            return None
        return cast(JRect, tuple(self.detail.box))

    def __bool__(self) -> bool:
        return self.hit

    def click(
        self,
        resolver: ClickResolver | None = None,
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
    ) -> bool:
        if not self.hit or self._click is None:
            return False

        point = (resolver or self._click_resolver)(self)

        if pre_delay is None and post_delay is None:
            if duration is None:
                return self._click(point)
            return self._click(point, duration)

        return self._click(
            point,
            duration,
            pre_delay=pre_delay,
            post_delay=post_delay,
        )


class Runtime:
    """Synchronous MaaFramework facade with configurable interaction behavior."""

    __slots__ = ("tasker", "controller", "resource", "interaction", "_last_input_end")

    def __init__(
        self,
        *,
        tasker: Any,
        controller: Any,
        resource: Any | None = None,
        interaction: InteractionConfig | None = None,
    ) -> None:
        self.tasker = tasker
        self.controller = controller
        self.resource = resource
        self.interaction = interaction or InteractionConfig()
        self._last_input_end: float | None = None

    def screenshot(self) -> numpy.ndarray:
        """Capture a fresh screenshot."""
        job = self.controller.post_screencap().wait()
        if not job.succeeded:
            raise RuntimeError("MaaFramework screencap failed")
        return job.get()

    def match(self, locator: JRecognitionParam, image: numpy.ndarray) -> MatchResult:
        """Run a MaaFramework recognition parameter against the supplied screenshot."""
        job = self.tasker.post_recognition(_recognition_type(locator), locator, image).wait()
        if not job.succeeded:
            raise RuntimeError(f"MaaFramework recognition failed: {locator!r}")

        task_detail = job.get()
        if task_detail is None:
            raise RuntimeError("MaaFramework recognition returned no task detail")

        recognition = next(
            (node.recognition for node in reversed(task_detail.nodes) if node.recognition is not None),
            None,
        )
        if recognition is None:
            raise RuntimeError("MaaFramework recognition returned no recognition detail")

        return MatchResult(
            recognition,
            self.click,
            self.interaction.click.resolver,
        )

    def click(
        self,
        point: Point,
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
    ) -> bool:
        """Press one point using runtime defaults unless an option is overridden."""
        config = self.interaction.click
        duration_ms = resolve_timing(
            config.duration if duration is None else duration,
            name="click duration",
        )
        pre_delay_ms = resolve_timing(
            config.pre_delay if pre_delay is None else pre_delay,
            name="click pre_delay",
        )
        post_delay_ms = resolve_timing(
            config.post_delay if post_delay is None else post_delay,
            name="click post_delay",
        )

        self._sleep(pre_delay_ms)
        self._wait_action_interval()

        self._touch_down(point)
        try:
            self._sleep(duration_ms)
        finally:
            self._touch_up()

        self._last_input_end = time.monotonic()
        self._sleep(post_delay_ms)
        return True

    def swipe(
        self,
        points: Sequence[Point],
        duration: Timing | None = None,
        *,
        pre_delay: Timing | None = None,
        post_delay: Timing | None = None,
        interpolation: SwipeInterpolator | None = None,
    ) -> bool:
        """Move through a point path using runtime defaults unless overridden."""
        raw_path = tuple(points)
        if len(raw_path) < 2:
            raise ValueError("swipe requires at least two points")

        config = self.interaction.swipe
        duration_ms = resolve_timing(
            config.duration if duration is None else duration,
            name="swipe duration",
        )
        pre_delay_ms = resolve_timing(
            config.pre_delay if pre_delay is None else pre_delay,
            name="swipe pre_delay",
        )
        post_delay_ms = resolve_timing(
            config.post_delay if post_delay is None else post_delay,
            name="swipe post_delay",
        )

        path = tuple((interpolation or config.interpolation)(raw_path))
        if len(path) < 2:
            raise ValueError("swipe interpolation must return at least two points")

        self._sleep(pre_delay_ms)
        self._wait_action_interval()

        self._touch_down(path[0])
        started_at = time.monotonic()
        step_duration = duration_ms / 1000 / (len(path) - 1)

        try:
            for index, point in enumerate(path[1:], 1):
                delay = started_at + step_duration * index - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                self._touch_move(point)
        finally:
            self._touch_up()

        self._last_input_end = time.monotonic()
        self._sleep(post_delay_ms)
        return True

    def _wait_action_interval(self) -> None:
        if self._last_input_end is None:
            return

        interval_ms = resolve_timing(
            self.interaction.action_interval,
            name="action_interval",
        )
        remaining = interval_ms / 1000 - (time.monotonic() - self._last_input_end)
        if remaining > 0:
            time.sleep(remaining)

    @staticmethod
    def _sleep(milliseconds: int) -> None:
        if milliseconds > 0:
            time.sleep(milliseconds / 1000)

    def _touch_down(self, point: Point) -> None:
        x, y = point
        job = self.controller.post_touch_down(x, y).wait()
        if not job.succeeded:
            raise RuntimeError(f"MaaFramework touch down failed at ({x}, {y})")

    def _touch_move(self, point: Point) -> None:
        x, y = point
        job = self.controller.post_touch_move(x, y).wait()
        if not job.succeeded:
            raise RuntimeError(f"MaaFramework touch move failed at ({x}, {y})")

    def _touch_up(self) -> None:
        job = self.controller.post_touch_up().wait()
        if not job.succeeded:
            raise RuntimeError("MaaFramework touch up failed")

    def stop(self) -> None:
        if not getattr(self.tasker, "running", False):
            return
        job = self.tasker.post_stop().wait()
        if not job.succeeded:
            raise RuntimeError("MaaFramework tasker stop failed")
