"""Development helpers for deterministic MaaPlus inspection and fixtures.

This namespace is intentionally opt-in. It never sends controller input during inspection.
"""

from .controller import (
    DiscoveredDevice,
    create_adb_controller,
    create_debug_controller,
    create_record_controller,
    create_replay_controller,
    find_adb_devices,
)
from .doctor import DoctorCheck, run_doctor
from .fixtures import Fixture, FixtureAssertionError, FixtureSet, assert_expected
from .inspector import (
    FixtureInspection,
    InspectionError,
    InspectionResult,
    InspectionTimeoutError,
    Inspector,
)
from .trace import JsonlTrace, TaskerTraceSink, TraceSession

__all__ = [
    "DiscoveredDevice",
    "Fixture",
    "FixtureAssertionError",
    "FixtureSet",
    "FixtureInspection",
    "InspectionError",
    "InspectionResult",
    "InspectionTimeoutError",
    "Inspector",
    "JsonlTrace",
    "DoctorCheck",
    "TaskerTraceSink",
    "TraceSession",
    "assert_expected",
    "create_adb_controller",
    "create_debug_controller",
    "create_record_controller",
    "create_replay_controller",
    "find_adb_devices",
    "run_doctor",
]
