from __future__ import annotations

import random as _random
from collections.abc import Callable
from typing import TypeAlias

TimingResolver: TypeAlias = Callable[[], int]
Timing: TypeAlias = int | TimingResolver


def _validate_milliseconds(value: int, *, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must resolve to an integer number of milliseconds")
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def fixed(milliseconds: int) -> TimingResolver:
    """Return a timing strategy that always resolves to ``milliseconds``."""
    value = _validate_milliseconds(milliseconds, name="milliseconds")
    return lambda: value


def random(min_ms: int, max_ms: int) -> TimingResolver:
    """Return a timing strategy that samples an inclusive millisecond range per use."""
    minimum = _validate_milliseconds(min_ms, name="min_ms")
    maximum = _validate_milliseconds(max_ms, name="max_ms")
    if minimum > maximum:
        raise ValueError("min_ms must be <= max_ms")

    return lambda: _random.randint(minimum, maximum)


def resolve(value: Timing, *, name: str = "timing") -> int:
    """Resolve a fixed or dynamic timing value and validate the result."""
    resolved = value() if callable(value) else value
    return _validate_milliseconds(resolved, name=name)
