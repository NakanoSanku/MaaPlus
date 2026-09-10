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


from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    """Represents an ADB device discovered by MaaFramework."""

    name: str
    address: str
    adb_path: Path
    screencap_methods: int
    input_methods: int
    config: dict[str, Any]


def find_adb_devices() -> list[DiscoveredDevice]:
    """Find available ADB devices using MaaFramework's toolkit discovery."""
    try:
        from maa.toolkit import Toolkit

        raw_devices = Toolkit.find_adb_devices()
    except Exception:
        return []

    results: list[DiscoveredDevice] = []
    for d in raw_devices:
        results.append(
            DiscoveredDevice(
                name=getattr(d, "name", "") or str(getattr(d, "address", "ADB Device")),
                address=str(getattr(d, "address", "")),
                adb_path=Path(getattr(d, "adb_path", "adb")),
                screencap_methods=int(getattr(d, "screencap_methods", 0)),
                input_methods=int(getattr(d, "input_methods", 0)),
                config=dict(getattr(d, "config", {}) or {}),
            )
        )
    return results


def create_adb_controller(
    serial: str | None = None,
    *,
    adb_path: str | Path | None = None,
    screencap_methods: int | None = None,
    input_methods: int | None = None,
    config: dict[str, Any] | None = None,
) -> Any:
    """Connect to an ADB device using MaaFramework and return a connected AdbController.

    If ``serial`` is omitted and exactly one device is discovered, auto-connects to it.
    If multiple devices are found and ``serial`` is omitted, raises ``RuntimeError``.
    """
    from maa.controller import AdbController

    devices = find_adb_devices()

    target_device: DiscoveredDevice | None = None
    if serial is not None:
        matches = [d for d in devices if d.address == serial]
        if matches:
            target_device = matches[0]
    elif len(devices) == 1:
        target_device = devices[0]
    elif len(devices) > 1:
        candidates = ", ".join(d.address for d in devices)
        raise RuntimeError(f"Multiple ADB devices found ({candidates}); pass serial=... explicitly")

    if target_device is not None:
        ctrl_adb_path = Path(adb_path) if adb_path else target_device.adb_path
        ctrl_address = target_device.address
        ctrl_screen = (
            screencap_methods if screencap_methods is not None else target_device.screencap_methods
        )
        ctrl_input = (
            input_methods if input_methods is not None else target_device.input_methods
        )
        ctrl_config = config if config is not None else target_device.config
    else:
        if serial is None:
            raise RuntimeError("No ADB device found; ensure device/emulator is running")
        ctrl_adb_path = Path(adb_path) if adb_path else Path("adb")
        ctrl_address = serial
        ctrl_screen = screencap_methods or 0
        ctrl_input = input_methods or 0
        ctrl_config = config or {}

    controller = AdbController(
        adb_path=ctrl_adb_path,
        address=ctrl_address,
        screencap_methods=ctrl_screen,
        input_methods=ctrl_input,
        config=ctrl_config,
    )
    job = controller.post_connection().wait()
    if not job.succeeded:
        raise RuntimeError(f"Failed to connect ADB device: {ctrl_address}")
    return controller

