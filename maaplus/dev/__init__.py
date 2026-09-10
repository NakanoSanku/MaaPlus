"""Development helpers for deterministic MaaPlus inspection and fixtures.

This namespace is intentionally opt-in. It never sends controller input during inspection.
"""

from .controller import create_debug_controller, create_record_controller, create_replay_controller
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
    "create_debug_controller",
    "create_record_controller",
    "create_replay_controller",
    "run_doctor",
]
