from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, TypeAlias

from .locator import Rect

if TYPE_CHECKING:
    from maa.define import RecognitionDetail

Point: TypeAlias = tuple[int, int]
ClickResolver: TypeAlias = Callable[["MatchResult"], Point]


@dataclass(slots=True)
class MatchResult:
    """MaaFramework recognition result with click sugar."""

    detail: RecognitionDetail
    _click: Callable[[Point], bool] | None = field(default=None, repr=False)

    @property
    def hit(self) -> bool:
        return bool(self.detail.hit)

    @property
    def box(self) -> Rect | None:
        return tuple(self.detail.box) if self.detail.box is not None else None

    def __bool__(self) -> bool:
        return self.hit

    def click(self, resolver: ClickResolver | None = None) -> bool:
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

        return self._click(point)
