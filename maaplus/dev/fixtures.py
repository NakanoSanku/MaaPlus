"""Fixture discovery and expected-result assertions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


@dataclass(frozen=True, slots=True)
class Fixture:
    path: Path
    expected: dict[str, Any]


class FixtureAssertionError(AssertionError):
    """Raised when a recognition result does not satisfy fixture expectations."""


def assert_expected(result: Any, expected: dict[str, Any], *, box_tolerance: int = 0) -> None:
    """Apply the default hit and rectangle assertions for one fixture."""
    if not isinstance(box_tolerance, int) or isinstance(box_tolerance, bool) or box_tolerance < 0:
        raise ValueError("box_tolerance must be a non-negative integer")
    if "hit" in expected and bool(result.hit) is not bool(expected["hit"]):
        raise FixtureAssertionError(
            f"expected hit={bool(expected['hit'])}, got hit={bool(result.hit)}"
        )
    if "box" not in expected:
        return
    actual = result.box
    target = expected["box"]
    if actual is None:
        raise FixtureAssertionError(f"expected box={target!r}, got no box")
    if not isinstance(target, (list, tuple)) or len(target) != 4:
        raise ValueError("expected box must contain four coordinates")
    tolerance = int(expected.get("box_tolerance", box_tolerance))
    if tolerance < 0:
        raise ValueError("box_tolerance must be non-negative")
    if any(abs(int(left) - int(right)) > tolerance for left, right in zip(actual, target)):
        raise FixtureAssertionError(
            f"expected box={tuple(target)!r} ±{tolerance}, got box={actual!r}"
        )


class FixtureSet:
    """A directory of screenshots with optional ``expected.json`` records."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        expected_path = self.directory / "expected.json"
        if expected_path.exists():
            payload = json.loads(expected_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("expected.json must contain an object keyed by image filename")
            self._expected = payload
        else:
            self._expected = {}

    def __iter__(self) -> Iterator[Fixture]:
        for path in sorted(self.directory.iterdir()):
            if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES:
                expected = self._expected.get(path.name, {})
                if not isinstance(expected, dict):
                    raise ValueError(f"expected entry for {path.name!r} must be an object")
                yield Fixture(path=path, expected=expected)

    def __len__(self) -> int:
        return sum(1 for _ in self)
