from __future__ import annotations

import random as _random
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from .runtime import MatchResult

Point: TypeAlias = tuple[int, int]
ClickResolver: TypeAlias = Callable[["MatchResult"], Point]


def _box(result: MatchResult) -> tuple[int, int, int, int]:
    box = result.box
    if box is None:
        raise ValueError("MatchResult has no box")

    x, y, width, height = box
    if width <= 0 or height <= 0:
        raise ValueError("MatchResult box must have positive width and height")
    return x, y, width, height


def center(result: MatchResult) -> Point:
    """Resolve the center point of the recognition box."""
    x, y, width, height = _box(result)
    return x + width // 2, y + height // 2


def random(padding: float = 0.0) -> ClickResolver:
    """Resolve a random point inside the recognition box.

    ``padding`` is the excluded fraction on each edge and must be in ``[0, 0.5)``.
    For example, ``padding=0.15`` restricts clicks to the inner 70% area.
    """
    if not 0 <= padding < 0.5:
        raise ValueError("padding must be in [0, 0.5)")

    def resolve(result: MatchResult) -> Point:
        x, y, width, height = _box(result)
        pad_x = int(width * padding)
        pad_y = int(height * padding)
        return (
            _random.randint(x + pad_x, x + width - 1 - pad_x),
            _random.randint(y + pad_y, y + height - 1 - pad_y),
        )

    return resolve


def relative(x_ratio: float, y_ratio: float) -> ClickResolver:
    """Resolve a stable relative point within the recognition box."""
    if not 0 <= x_ratio <= 1:
        raise ValueError("x_ratio must be in [0, 1]")
    if not 0 <= y_ratio <= 1:
        raise ValueError("y_ratio must be in [0, 1]")

    def resolve(result: MatchResult) -> Point:
        x, y, width, height = _box(result)
        return (
            x + round((width - 1) * x_ratio),
            y + round((height - 1) * y_ratio),
        )

    return resolve
