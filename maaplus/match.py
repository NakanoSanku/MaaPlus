from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .locator import Rect

if TYPE_CHECKING:
    from maa.define import RecognitionDetail


@dataclass(slots=True)
class Match:
    """Thin wrapper around MaaFramework RecognitionDetail with click sugar."""

    detail: RecognitionDetail
    _click: Callable[[Rect], bool] | None = field(default=None, repr=False)

    @property
    def hit(self) -> bool:
        return bool(self.detail.hit)

    @property
    def box(self) -> Rect | None:
        return tuple(self.detail.box) if self.detail.box is not None else None

    def __bool__(self) -> bool:
        return self.hit

    def click(self) -> bool:
        box = self.box
        if not self.hit or box is None or self._click is None:
            return False
        return self._click(box)
