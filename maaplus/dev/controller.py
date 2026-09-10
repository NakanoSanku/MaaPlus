"""Small factories around MaaFramework's development controllers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def create_debug_controller(read_path: str | Path) -> Any:
    """Create MaaFramework's image-directory controller.

    It cycles screenshots from ``read_path`` and reports input operations as successful without
    sending them to a device. It is intended for fixture inspection, not full task replay.
    """
    from maa.controller import DbgController

    return DbgController(read_path)


def create_record_controller(inner: Any, recording_path: str | Path) -> Any:
    """Wrap a live controller with MaaFramework's JSONL operation recorder."""
    from maa.controller import RecordController

    return RecordController(inner, recording_path)


def create_replay_controller(recording_path: str | Path) -> Any:
    """Create MaaFramework's controller-operation replay controller."""
    from maa.controller import ReplayController

    return ReplayController(recording_path)
