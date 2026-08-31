from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeAlias

Rect: TypeAlias = tuple[int, int, int, int]


def _tuple_or_scalar(value: str | Sequence[str]) -> str | tuple[str, ...]:
    if isinstance(value, str):
        return value
    return tuple(value)


def _float_tuple_or_scalar(value: float | Sequence[float]) -> float | tuple[float, ...]:
    if isinstance(value, (int, float)):
        return float(value)
    return tuple(float(item) for item in value)


@dataclass(frozen=True, slots=True, init=False)
class Template:
    """TemplateMatch locator description.

    This object only describes recognition. It never captures a frame or performs an action.
    """

    template: str | tuple[str, ...]
    threshold: float | tuple[float, ...]
    roi: Rect
    order_by: str
    index: int
    method: int
    green_mask: bool

    def __init__(
        self,
        template: str | Sequence[str],
        *,
        threshold: float | Sequence[float] = 0.7,
        roi: Rect = (0, 0, 0, 0),
        order_by: str = "Horizontal",
        index: int = 0,
        method: int = 5,
        green_mask: bool = False,
    ) -> None:
        object.__setattr__(self, "template", _tuple_or_scalar(template))
        object.__setattr__(self, "threshold", _float_tuple_or_scalar(threshold))
        object.__setattr__(self, "roi", roi)
        object.__setattr__(self, "order_by", order_by)
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "green_mask", green_mask)


@dataclass(frozen=True, slots=True, init=False)
class OCR:
    """OCR locator description."""

    expected: str | tuple[str, ...]
    threshold: float
    roi: Rect
    order_by: str
    index: int
    only_rec: bool
    model: str

    def __init__(
        self,
        expected: str | Sequence[str] = (),
        *,
        threshold: float = 0.3,
        roi: Rect = (0, 0, 0, 0),
        order_by: str = "Horizontal",
        index: int = 0,
        only_rec: bool = False,
        model: str = "",
    ) -> None:
        object.__setattr__(self, "expected", _tuple_or_scalar(expected))
        object.__setattr__(self, "threshold", float(threshold))
        object.__setattr__(self, "roi", roi)
        object.__setattr__(self, "order_by", order_by)
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "only_rec", only_rec)
        object.__setattr__(self, "model", model)


Locator: TypeAlias = Template | OCR
