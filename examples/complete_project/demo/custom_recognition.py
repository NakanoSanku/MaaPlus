"""Example-owned multi-point color recognizer using MaaFramework and NumPy."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeAlias

import numpy
from maa.custom_recognition import CustomRecognition

Point: TypeAlias = tuple[int, int]
Rect: TypeAlias = tuple[int, int, int, int]

Color: TypeAlias = tuple[int, int, int]


def _validate_color(color: Sequence[int]) -> Color:
    values = tuple(color)
    if len(values) != 3:
        raise ValueError("color must contain exactly three channels (R, G, B)")
    if any(not isinstance(channel, int) or isinstance(channel, bool) for channel in values):
        raise TypeError("color channels must be integers")
    if any(channel < 0 or channel > 255 for channel in values):
        raise ValueError("color channels must be between 0 and 255")
    return values  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ColorPoint:
    """One expected RGB sample relative to the recognizer's anchor point."""

    offset: Point
    color: Color

    def __post_init__(self) -> None:
        x, y = self.offset
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in (x, y)):
            raise TypeError("color point offsets must be integers")
        object.__setattr__(self, "color", _validate_color(self.color))


class MultiPointColorRecognition(CustomRecognition):
    """Find a group of RGB samples at fixed offsets inside the current ROI.

    The first point is the anchor.  Every candidate anchor pixel is checked against all points;
    the returned box encloses the matched points.  ``argv.image`` is BGR, as provided by
    MaaFramework, while the public ``ColorPoint.color`` values are RGB for readability.

    The optional custom parameter is a JSON object.  Currently ``tolerance`` can override the
    default per invocation, for example ``{"tolerance": 18}``.
    """

    def __init__(
        self,
        points: Sequence[ColorPoint | tuple[Point, Color]],
        *,
        tolerance: int = 12,
    ) -> None:
        super().__init__()
        normalized = tuple(
            point if isinstance(point, ColorPoint) else ColorPoint(point[0], point[1])
            for point in points
        )
        if not normalized:
            raise ValueError("MultiPointColorRecognition requires at least one point")
        if not isinstance(tolerance, int) or isinstance(tolerance, bool):
            raise TypeError("tolerance must be an integer")
        if not 0 <= tolerance <= 255:
            raise ValueError("tolerance must be between 0 and 255")
        self.points = normalized
        self.tolerance = tolerance

    def analyze(
        self,
        context: Any,
        argv: CustomRecognition.AnalyzeArg,
    ) -> CustomRecognition.AnalyzeResult | None:
        del context
        image = numpy.asarray(argv.image)
        if image.ndim != 3 or image.shape[2] < 3:
            raise ValueError("MultiPointColorRecognition requires a BGR image")

        tolerance = self._resolve_tolerance(argv.custom_recognition_param)
        height, width = image.shape[:2]
        roi_x, roi_y, roi_width, roi_height = self._normalize_roi(argv.roi, width, height)
        offsets = tuple(point.offset for point in self.points)
        anchor_offset_x, anchor_offset_y = offsets[0]
        relative_offsets = tuple(
            (x - anchor_offset_x, y - anchor_offset_y) for x, y in offsets
        )

        # Keep every sampled point inside the ROI and image.  The anchor candidate can therefore
        # be searched with one vectorized mask instead of a Python loop over every pixel.
        min_offset_x = min(x for x, _ in relative_offsets)
        max_offset_x = max(x for x, _ in relative_offsets)
        min_offset_y = min(y for _, y in relative_offsets)
        max_offset_y = max(y for _, y in relative_offsets)
        roi_right = min(roi_x + roi_width, width)
        roi_bottom = min(roi_y + roi_height, height)
        x_start = max(roi_x, -min_offset_x, 0)
        x_stop = min(roi_right - 1, width - 1 - max_offset_x)
        y_start = max(roi_y, -min_offset_y, 0)
        y_stop = min(roi_bottom - 1, height - 1 - max_offset_y)
        if x_start > x_stop or y_start > y_stop:
            return None

        yy, xx = numpy.mgrid[y_start : y_stop + 1, x_start : x_stop + 1]
        # MaaFramework supplies BGR; reverse the view so user-facing colors remain RGB.
        rgb = image[..., :3][..., ::-1]
        matched = numpy.ones(xx.shape, dtype=bool)
        for point, (offset_x, offset_y) in zip(self.points, relative_offsets):
            sample = rgb[yy + offset_y, xx + offset_x].astype(numpy.int16)
            target = numpy.asarray(point.color, dtype=numpy.int16)
            matched &= numpy.max(numpy.abs(sample - target), axis=2) <= tolerance

        hits = numpy.argwhere(matched)
        if hits.size == 0:
            return None

        # argwhere is row-major, which makes the selected match deterministic.
        anchor_y = y_start + int(hits[0, 0])
        anchor_x = x_start + int(hits[0, 1])
        matched_points = [
            (anchor_x + x, anchor_y + y) for x, y in relative_offsets
        ]
        min_x = min(x for x, _ in matched_points)
        max_x = max(x for x, _ in matched_points)
        min_y = min(y for _, y in matched_points)
        max_y = max(y for _, y in matched_points)

        box: Rect = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
        return CustomRecognition.AnalyzeResult(
            box=box,
            detail={
                "algorithm": "multi_point_color",
                "anchor": [anchor_x, anchor_y],
                "matched_points": [list(point) for point in matched_points],
                "point_count": len(self.points),
                "tolerance": tolerance,
            },
        )

    @staticmethod
    def _normalize_roi(roi: Rect, width: int, height: int) -> Rect:
        x, y, roi_width, roi_height = (int(value) for value in roi)
        # MaaFramework uses a zero-sized ROI to mean the complete image.
        if roi_width <= 0 or roi_height <= 0:
            return 0, 0, width, height
        return x, y, roi_width, roi_height

    def _resolve_tolerance(self, raw_param: str) -> int:
        if not raw_param or raw_param == "null":
            return self.tolerance
        try:
            payload = json.loads(raw_param)
        except json.JSONDecodeError as exc:
            raise ValueError("custom_recognition_param must be valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise TypeError("custom_recognition_param must be a JSON object")
        value = payload.get("tolerance", self.tolerance)
        if not isinstance(value, int) or isinstance(value, bool):
            raise TypeError("custom tolerance must be an integer")
        if not 0 <= value <= 255:
            raise ValueError("custom tolerance must be between 0 and 255")
        return value


def create_custom_recognitions() -> dict[str, MultiPointColorRecognition]:
    """Build the recognizers and keep their registration names in one place.

    The sample points describe a small three-pixel marker. Replace them with stable pixels from
    the target game's UI. Colors are RGB even though MaaFramework passes the image as BGR.
    """
    return {
        "MultiPointColor": MultiPointColorRecognition(
            points=(
                ColorPoint((0, 0), (255, 214, 80)),
                ColorPoint((12, 0), (255, 214, 80)),
                ColorPoint((0, 12), (255, 214, 80)),
            ),
            tolerance=12,
        )
    }
