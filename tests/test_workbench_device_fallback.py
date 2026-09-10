from __future__ import annotations

import subprocess
from pathlib import Path

import tools.ui_workbench as workbench
from tools.ui_workbench import DeviceBridge


def completed(args: list[str], *, stdout: bytes = b"", stderr: bytes = b"", returncode: int = 0):
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_raw_adb_discovery_is_available_without_maa_device_helpers(tmp_path: Path, monkeypatch):
    bridge = DeviceBridge(tmp_path)
    monkeypatch.setattr(workbench, "MAA_DEVICE_AVAILABLE", False)

    def fake_run(cls, args, *, adb_path="adb", timeout=5):
        assert args == ["devices", "-l"]
        return completed(
            args,
            stdout=(
                b"List of devices attached\n"
                b"emulator-5554 device product:sdk model:Pixel_8 device:emu transport_id:1\n"
            ),
        )

    monkeypatch.setattr(DeviceBridge, "_run_adb", classmethod(fake_run))
    monkeypatch.setattr(DeviceBridge, "_resolve_adb_path", staticmethod(lambda adb_path="adb": "/sdk/adb"))

    devices = bridge.discover_devices()
    assert devices == [
        {
            "address": "emulator-5554",
            "name": "Pixel 8",
            "adb_path": "/sdk/adb",
            "screencap_methods": 0,
            "input_methods": 0,
            "config": {
                "product": "sdk",
                "model": "Pixel_8",
                "device": "emu",
                "transport_id": "1",
            },
            "source": "adb",
            "connected": False,
        }
    ]


def test_connect_uses_verified_raw_adb_instead_of_mock_success(tmp_path: Path, monkeypatch):
    bridge = DeviceBridge(tmp_path)
    monkeypatch.setattr(workbench, "MAA_DEVICE_AVAILABLE", False)
    monkeypatch.setattr(bridge, "_verify_raw_adb", lambda address, adb_path: "/sdk/adb")

    result = bridge.connect("127.0.0.1:5555")

    assert result == {
        "success": True,
        "address": "127.0.0.1:5555",
        "mode": "adb_fallback",
    }
    assert bridge.connected_device == {
        "address": "127.0.0.1:5555",
        "adb_path": "/sdk/adb",
        "mode": "adb_fallback",
    }


def test_connect_reports_failure_when_real_adb_connection_cannot_be_verified(tmp_path: Path, monkeypatch):
    bridge = DeviceBridge(tmp_path)
    monkeypatch.setattr(workbench, "MAA_DEVICE_AVAILABLE", False)

    def fail_verify(address, adb_path):
        raise RuntimeError("device unauthorized")

    monkeypatch.setattr(bridge, "_verify_raw_adb", fail_verify)
    result = bridge.connect("emulator-5554")

    assert result["success"] is False
    assert "device unauthorized" in result["error"]
    assert bridge.connected_device is None


def test_network_device_runs_adb_connect_then_rechecks_state(tmp_path: Path, monkeypatch):
    bridge = DeviceBridge(tmp_path)
    calls: list[list[str]] = []

    def fake_run(cls, args, *, adb_path="adb", timeout=5):
        calls.append(args)
        if args == ["-s", "127.0.0.1:5555", "get-state"] and calls.count(args) == 1:
            return completed(args, stderr=b"device not found", returncode=1)
        if args == ["connect", "127.0.0.1:5555"]:
            return completed(args, stdout=b"connected to 127.0.0.1:5555\n")
        if args == ["-s", "127.0.0.1:5555", "get-state"]:
            return completed(args, stdout=b"device\n")
        raise AssertionError(args)

    monkeypatch.setattr(DeviceBridge, "_resolve_adb_path", staticmethod(lambda adb_path="adb": "/sdk/adb"))
    monkeypatch.setattr(DeviceBridge, "_run_adb", classmethod(fake_run))

    assert bridge._verify_raw_adb("127.0.0.1:5555", "adb") == "/sdk/adb"
    assert calls == [
        ["-s", "127.0.0.1:5555", "get-state"],
        ["connect", "127.0.0.1:5555"],
        ["-s", "127.0.0.1:5555", "get-state"],
    ]
