from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeAlias

from maa.pipeline import JRect as Rect

Point: TypeAlias = tuple[int, int]
PointResolver: TypeAlias = Callable[[Rect], Point]
PathInterpolator: TypeAlias = Callable[[Sequence[Point]], Sequence[Point]]
