from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, TypeAlias, cast

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

if TYPE_CHECKING:
    import numpy

    from maa.define import RecognitionDetail

Point: TypeAlias = tuple[int, int]
ClickResolver: TypeAlias = Callable[["MatchResult"], Point]

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
    _click: Callable[[Point, int], bool] | None = field(default=None, repr=False)

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

    def click(self, resolver: ClickResolver | None = None, duration: int = 50) -> bool:
        if not self.hit or self._click is None:
            return False

        if resolver is None:
            box = self.box
            if box is None:
                return False
            x, y, width, height = box
            point = (x + width // 2, y + height // 2)
        else:
            point = resolver(self)

        return self._click(point, duration)


class Runtime:
    """Thin synchronous facade over MaaFramework."""

    __slots__ = ("tasker", "controller", "resource")

    def __init__(self, *, tasker: Any, controller: Any, resource: Any | None = None) -> None:
        self.tasker = tasker
        self.controller = controller
        self.resource = resource

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

        return MatchResult(recognition, self.click)

    def click(self, point: Point, duration: int = 50) -> bool:
        """Press one point for ``duration`` milliseconds."""
        if duration < 0:
            raise ValueError("duration must be >= 0")

        self._touch_down(point)
        try:
            time.sleep(duration / 1000)
        finally:
            self._touch_up()
        return True

    def swipe(self, points: Sequence[Point], duration: int) -> bool:
        """Move through a point path over ``duration`` milliseconds."""
        path = tuple(points)
        if len(path) < 2:
            raise ValueError("swipe requires at least two points")
        if duration < 0:
            raise ValueError("duration must be >= 0")

        self._touch_down(path[0])
        started_at = time.monotonic()
        step_duration = duration / 1000 / (len(path) - 1)

        try:
            for index, point in enumerate(path[1:], 1):
                delay = started_at + step_duration * index - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                self._touch_move(point)
        finally:
            self._touch_up()

        return True

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
