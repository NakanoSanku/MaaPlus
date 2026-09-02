from __future__ import annotations

from collections.abc import Callable, Sequence
from math import hypot
from typing import TypeAlias

from .click import Point

SwipeInterpolator: TypeAlias = Callable[[Sequence[Point]], Sequence[Point]]
_Easing: TypeAlias = Callable[[float], float]


def direct(points: Sequence[Point]) -> tuple[Point, ...]:
    """Keep the caller-supplied swipe path unchanged."""
    return tuple(points)


def _validate_samples(samples: int) -> int:
    if not isinstance(samples, int) or isinstance(samples, bool):
        raise TypeError("samples must be an integer")
    if not 2 <= samples <= 1000:
        raise ValueError("samples must be between 2 and 1000")
    return samples


def _resample(points: Sequence[Point], samples: int, easing: _Easing) -> tuple[Point, ...]:
    path = tuple(points)
    if len(path) < 2:
        raise ValueError("swipe interpolation requires at least two points")

    segments: list[tuple[float, float, Point, Point]] = []
    distance = 0.0
    for start, end in zip(path, path[1:]):
        length = hypot(end[0] - start[0], end[1] - start[1])
        if length <= 0:
            continue
        segments.append((distance, distance + length, start, end))
        distance += length

    if distance <= 0:
        return (path[0], path[-1])

    resolved: list[Point] = []
    for index in range(samples):
        if index == 0:
            point = path[0]
        elif index == samples - 1:
            point = path[-1]
        else:
            progress = easing(index / (samples - 1))
            target = min(max(progress, 0.0), 1.0) * distance
            point = path[-1]
            for start_distance, end_distance, start, end in segments:
                if target <= end_distance:
                    ratio = (target - start_distance) / (end_distance - start_distance)
                    point = (
                        round(start[0] + (end[0] - start[0]) * ratio),
                        round(start[1] + (end[1] - start[1]) * ratio),
                    )
                    break

        if not resolved or resolved[-1] != point:
            resolved.append(point)

    if len(resolved) == 1:
        resolved.append(path[-1])
    elif resolved[-1] != path[-1]:
        resolved.append(path[-1])
    return tuple(resolved)


def _strategy(samples: int, easing: _Easing) -> SwipeInterpolator:
    sample_count = _validate_samples(samples)
    return lambda points: _resample(points, sample_count, easing)


def linear(samples: int = 20) -> SwipeInterpolator:
    """Resample a path using constant progress."""
    return _strategy(samples, lambda value: value)


def ease_in(samples: int = 20) -> SwipeInterpolator:
    """Resample a path that starts slowly and accelerates."""
    return _strategy(samples, lambda value: value * value)


def ease_out(samples: int = 20) -> SwipeInterpolator:
    """Resample a path that starts quickly and decelerates."""
    return _strategy(samples, lambda value: 1 - (1 - value) * (1 - value))


def ease_in_out(samples: int = 20) -> SwipeInterpolator:
    """Resample a path with smooth acceleration and deceleration."""
    return _strategy(samples, lambda value: value * value * (3 - 2 * value))
