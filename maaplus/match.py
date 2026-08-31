from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .locator import Rect


@dataclass(slots=True)
class Match:
    """Recognition result with an optional lightweight click binding."""

    hit: bool
    box: Rect | None = None
    score: float | None = None
    detail: Any = None
    raw_detail: dict[str, Any] | None = None
    _click: Callable[[Rect], bool] | None = field(default=None, repr=False)

    def __bool__(self) -> bool:
        return self.hit

    def click(self) -> bool:
        if not self.hit or self.box is None or self._click is None:
            return False
        return self._click(self.box)
