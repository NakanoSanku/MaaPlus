"""Read-only environment diagnostics for live MaaPlus projects."""

from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    optional: bool = False


def run_doctor(*, resource_dir: str | Path | None = None) -> list[DoctorCheck]:
    checks: list[DoctorCheck] = []
    checks.append(_module_check("maa", "MaaFramework import"))
    checks.append(_module_check("numpy", "NumPy import"))
    checks.append(_module_check("PIL", "Pillow import", optional=True))

    if resource_dir is not None:
        path = Path(resource_dir)
        checks.append(DoctorCheck("resource", path.exists(), str(path)))

    try:
        from maa.toolkit import Toolkit

        devices = Toolkit.find_adb_devices()
        if devices:
            detail = "; ".join(
                f"{getattr(device, 'address', '<unknown>')} "
                f"(screen={getattr(device, 'screencap_methods', ())}, "
                f"input={getattr(device, 'input_methods', ())})"
                for device in devices
            )
            checks.append(DoctorCheck("adb", True, detail))
        else:
            checks.append(DoctorCheck("adb", False, "no ADB device discovered", optional=True))
    except Exception as exc:
        checks.append(DoctorCheck("adb", False, f"diagnostic failed: {exc}", optional=True))

    try:
        version = importlib.metadata.version("maafw")
    except importlib.metadata.PackageNotFoundError:
        version = "not installed"
    checks.append(DoctorCheck("maafw-version", version != "not installed", version))
    return checks


def _module_check(module_name: str, label: str, *, optional: bool = False) -> DoctorCheck:
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", None)
        return DoctorCheck(label, True, str(version or "available"), optional=optional)
    except Exception as exc:
        return DoctorCheck(label, False, str(exc), optional=optional)
