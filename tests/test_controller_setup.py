from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, create_autospec, patch

import pytest
from maa.controller import AdbController
from maa.toolkit import AdbDevice

from examples import basic_adb
from examples.complete_project.demo import bootstrap
from maaplus.dev import run_doctor


def device(address: str) -> AdbDevice:
    return AdbDevice(
        name=address,
        adb_path=Path("emulator") / "adb.exe",
        address=address,
        screencap_methods=4,
        input_methods=8,
        config={"display_id": 1},
    )


@pytest.fixture(params=[basic_adb, bootstrap], ids=["basic", "complete"])
def startup(request, monkeypatch, tmp_path):
    module = request.param
    toolkit = SimpleNamespace(init_option=Mock(), find_adb_devices=Mock())
    controller = create_autospec(AdbController)
    connection = Mock(succeeded=True)
    connection.wait.return_value = connection
    controller.return_value.post_connection.return_value = connection
    bind_app = Mock(return_value=MagicMock())
    monkeypatch.setattr(module, "DEBUG_DIR", tmp_path)
    monkeypatch.setattr(module, "Toolkit", toolkit)
    monkeypatch.setattr(module, "AdbController", controller)
    monkeypatch.setattr(module, "Tasker", Mock())
    monkeypatch.setattr(module, "load_resource", Mock())
    monkeypatch.setattr(module, "App", SimpleNamespace(from_maa=bind_app))
    return SimpleNamespace(
        run=module.main if module is basic_adb else module.create_app,
        discover=toolkit.find_adb_devices,
        controller=controller,
        connection=connection,
        bind_app=bind_app,
    )


@pytest.mark.parametrize("serial", [None, "emulator-5556"])
def test_startup_connects_selected_device_with_discovered_capabilities(startup, serial):
    selected = device(serial or "emulator-5554")
    startup.discover.return_value = (
        [selected] if serial is None else [device("emulator-5554"), selected]
    )
    startup.run(serial=serial)

    startup.controller.assert_called_once_with(
        adb_path=selected.adb_path,
        address=selected.address,
        screencap_methods=selected.screencap_methods,
        input_methods=selected.input_methods,
        config=selected.config,
    )
    startup.connection.wait.assert_called_once_with()
    assert startup.bind_app.call_args.kwargs["controller"] is startup.controller.return_value


@pytest.mark.parametrize(
    "addresses, serial, error",
    [
        ([], None, "No ADB device"),
        (["emulator-5554", "emulator-5556"], None, "Multiple ADB devices"),
        (["emulator-5554"], "emulator-5556", "No ADB device"),
    ],
)
def test_startup_rejects_missing_or_ambiguous_device_before_connecting(
    startup, addresses, serial, error
):
    startup.discover.return_value = [device(address) for address in addresses]

    with pytest.raises(RuntimeError, match=error):
        startup.run(serial=serial)

    startup.controller.assert_not_called()
    startup.bind_app.assert_not_called()


def test_startup_does_not_bind_app_after_connection_failure(startup):
    startup.discover.return_value = [device("emulator-5554")]
    startup.connection.succeeded = False

    with pytest.raises(RuntimeError, match="Failed to connect ADB device: emulator-5554"):
        startup.run()

    startup.bind_app.assert_not_called()


def test_doctor_reports_native_device_capabilities():
    with patch("maa.toolkit.Toolkit.find_adb_devices", return_value=[device("emulator-5554")]):
        check = next(check for check in run_doctor() if check.name == "adb")

    assert check.ok
    assert check.detail == "emulator-5554 (screen=4, input=8)"


def test_doctor_preserves_discovery_error_for_diagnosis():
    with patch("maa.toolkit.Toolkit.find_adb_devices", side_effect=RuntimeError("probe failed")):
        check = next(check for check in run_doctor() if check.name == "adb")

    assert not check.ok
    assert check.optional
    assert check.detail == "diagnostic failed: probe failed"
