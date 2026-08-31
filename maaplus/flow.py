from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .locator import Locator, Rect
from .result import BoundMatch
from .runtime import RuntimeLike


class FlowContext:
    """Flow-scoped state: shared frame cache plus recognition/action entry points."""

    __slots__ = ("runtime", "_frame")

    def __init__(self, runtime: RuntimeLike) -> None:
        self.runtime = runtime
        self._frame: Any | None = None

    def screenshot(self) -> Any:
        """Return the current shared frame, capturing once if necessary."""
        if self._frame is None:
            self._frame = self.runtime.screenshot()
        return self._frame

    def refresh(self) -> Any:
        """Force a new screenshot and make it the current shared frame."""
        self._frame = self.runtime.screenshot()
        return self._frame

    def invalidate(self) -> None:
        """Mark the current frame stale without capturing immediately."""
        self._frame = None

    def find(self, locator: Locator) -> BoundMatch:
        result = self.runtime.recognize(locator, self.screenshot())
        return BoundMatch(result, self)

    def click_box(self, box: Rect) -> bool:
        success = self.runtime.click(box)
        if success:
            self.invalidate()
        return success


class Flow(ABC):
    @abstractmethod
    def run(self, ctx: FlowContext) -> Any:
        """Execute one business flow."""
        raise NotImplementedError
