from __future__ import annotations

import random as _random

from .geometry import Point, PointResolver, Rect


def _validate_rect(rect: Rect) -> Rect:
    x, y, width, height = rect
    if width <= 0 or height <= 0:
        raise ValueError("area must have positive width and height")
    return x, y, width, height


def center(rect: Rect) -> Point:
    """Resolve the center point of a rectangular area."""
    x, y, width, height = _validate_rect(rect)
    return x + width // 2, y + height // 2


def random(padding: float = 0.0) -> PointResolver:
    """Resolve a random point inside a rectangular area.

    ``padding`` is the excluded fraction on each edge and must be in ``[0, 0.5)``.
    For example, ``padding=0.15`` restricts points to the inner 70% area.
    """
    if not 0 <= padding < 0.5:
        raise ValueError("padding must be in [0, 0.5)")

    def resolve(rect: Rect) -> Point:
        x, y, width, height = _validate_rect(rect)
        pad_x = int(width * padding)
        pad_y = int(height * padding)
        return (
            _random.randint(x + pad_x, x + width - 1 - pad_x),
            _random.randint(y + pad_y, y + height - 1 - pad_y),
        )

    return resolve


def relative(x_ratio: float, y_ratio: float) -> PointResolver:
    """Resolve a stable relative point within a rectangular area."""
    if not 0 <= x_ratio <= 1:
        raise ValueError("x_ratio must be in [0, 1]")
    if not 0 <= y_ratio <= 1:
        raise ValueError("y_ratio must be in [0, 1]")

    def resolve(rect: Rect) -> Point:
        x, y, width, height = _validate_rect(rect)
        return (
            x + round((width - 1) * x_ratio),
            y + round((height - 1) * y_ratio),
        )

    return resolve
