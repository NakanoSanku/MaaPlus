from __future__ import annotations

from typing import Any

from .locator import Locator, Rect
from .match import MatchResult


class FlowContext:
    """Shared frame plus recognition/action entry points for one flow run."""

    __slots__ = ("runtime", "_frame")

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self._frame: Any | None = None

    def screenshot(self) -> Any:
        if self._frame is None:
            self._frame = self.runtime.screenshot()
        return self._frame

    def refresh(self) -> Any:
        self._frame = self.runtime.screenshot()
        return self._frame

    def invalidate(self) -> None:
        self._frame = None

    def match(self, locator: Locator) -> MatchResult:
        result = self.runtime.recognize(locator, self.screenshot())
        result._click = self.click_box
        return result

    def click_box(self, box: Rect) -> bool:
        success = self.runtime.click(box)
        if success:
            self.invalidate()
        return success
