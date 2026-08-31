from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .errors import LocatorNotFound
from .locator import Locator, Rect


class _ActionContext(Protocol):
    def click_box(self, box: Rect) -> bool: ...


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Pure recognition result, independent from the controller/runtime."""

    locator: Locator
    hit: bool
    box: Rect | None = None
    score: float | None = None
    detail: Any = None
    raw_detail: dict[str, Any] | None = None

    def __bool__(self) -> bool:
        return self.hit


class BoundMatch:
    """A MatchResult bound to a FlowContext, enabling lightweight action chaining."""

    __slots__ = ("result", "_context")

    def __init__(self, result: MatchResult, context: _ActionContext) -> None:
        self.result = result
        self._context = context

    def __bool__(self) -> bool:
        return bool(self.result)

    @property
    def hit(self) -> bool:
        return self.result.hit

    @property
    def box(self) -> Rect | None:
        return self.result.box

    @property
    def score(self) -> float | None:
        return self.result.score

    @property
    def detail(self) -> Any:
        return self.result.detail

    def require(self) -> BoundMatch:
        if not self.hit:
            raise LocatorNotFound(f"Required locator was not found: {self.result.locator!r}")
        return self

    def click(self) -> bool:
        """Click the matched box. A miss is intentionally a no-op returning False."""
        if not self.hit:
            return False
        if self.box is None:
            raise LocatorNotFound(f"Matched locator has no clickable box: {self.result.locator!r}")
        return self._context.click_box(self.box)
