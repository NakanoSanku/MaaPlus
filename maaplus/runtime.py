from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)
recognition_logger = logging.getLogger(f"{__name__}.recognition")
controller_logger = logging.getLogger(f"{__name__}.controller")


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
        started = time.perf_counter()
        job = self.controller.post_screencap().wait()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if not job.succeeded:
            logger.error("screenshot failed elapsed_ms=%.1f", elapsed_ms)
            raise RuntimeError("MaaFramework screencap failed")

        image = job.get()
        logger.debug("screenshot captured elapsed_ms=%.1f", elapsed_ms)
        return image

    def match(self, locator: JRecognitionParam, image: numpy.ndarray) -> MatchResult:
        """Run a MaaFramework recognition parameter against the supplied screenshot."""
        recognition_type = _recognition_type(locator)
        type_name = getattr(recognition_type, "name", str(recognition_type))
        started = time.perf_counter()
        job = self.tasker.post_recognition(recognition_type, locator, image).wait()
        if not job.succeeded:
            elapsed_ms = (time.perf_counter() - started) * 1000
            recognition_logger.error(
                "recognition failed type=%s locator=%r elapsed_ms=%.1f",
                type_name,
                locator,
                elapsed_ms,
            )
            raise RuntimeError(f"MaaFramework recognition failed: {locator!r}")

        task_detail = job.get()
        if task_detail is None:
            recognition_logger.error(
                "recognition returned no task detail type=%s locator=%r",
                type_name,
                locator,
            )
            raise RuntimeError("MaaFramework recognition returned no task detail")

        recognition = next(
            (node.recognition for node in reversed(task_detail.nodes) if node.recognition is not None),
            None,
        )
        if recognition is None:
            recognition_logger.error(
                "recognition returned no detail type=%s locator=%r",
                type_name,
                locator,
            )
            raise RuntimeError("MaaFramework recognition returned no recognition detail")

        result = MatchResult(
            recognition,
            self.click,
            self.interaction.click.resolver,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        recognition_logger.debug(
            "recognition type=%s locator=%r hit=%s box=%s elapsed_ms=%.1f",
            type_name,
            locator,
            result.hit,
            result.box,
            elapsed_ms,
        )
        return result

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

        controller_logger.debug(
            "click point=%s duration_ms=%d pre_delay_ms=%d post_delay_ms=%d",
            point,
            duration_ms,
            pre_delay_ms,
            post_delay_ms,
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

        controller_logger.debug(
            "swipe points=%s path=%s duration_ms=%d pre_delay_ms=%d post_delay_ms=%d",
            raw_path,
            path,
            duration_ms,
            pre_delay_ms,
            post_delay_ms,
        )

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
            controller_logger.debug(
                "action interval wait interval_ms=%d remaining_ms=%.1f",
                interval_ms,
                remaining * 1000,
            )
            time.sleep(remaining)

    @staticmethod
    def _sleep(milliseconds: int) -> None:
        if milliseconds > 0:
            time.sleep(milliseconds / 1000)

    def _touch_down(self, point: Point) -> None:
        x, y = point
        job = self.controller.post_touch_down(x, y).wait()
        if not job.succeeded:
            controller_logger.error("touch down failed point=%s", point)
            raise RuntimeError(f"MaaFramework touch down failed at ({x}, {y})")

    def _touch_move(self, point: Point) -> None:
        x, y = point
        job = self.controller.post_touch_move(x, y).wait()
        if not job.succeeded:
            controller_logger.error("touch move failed point=%s", point)
            raise RuntimeError(f"MaaFramework touch move failed at ({x}, {y})")

    def _touch_up(self) -> None:
        job = self.controller.post_touch_up().wait()
        if not job.succeeded:
            controller_logger.error("touch up failed")
            raise RuntimeError("MaaFramework touch up failed")

    def stop(self) -> None:
        if not getattr(self.tasker, "running", False):
            return
        logger.info("tasker stop requested")
        job = self.tasker.post_stop().wait()
        if not job.succeeded:
            logger.error("tasker stop failed")
            raise RuntimeError("MaaFramework tasker stop failed")
        logger.info("tasker stopped")
