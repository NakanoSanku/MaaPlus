from __future__ import annotations

from pathlib import Path

from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maa.pipeline import JOCR, JTemplateMatch
from maaplus import App, CONTINUE, DONE, Tick


ROOT = Path(__file__).resolve().parent
RESOURCE_DIR = ROOT / "resource"
DEBUG_DIR = ROOT / ".debug"


class Login:
    START = JTemplateMatch(
        template=["login/start.png"],
        threshold=[0.85],
    )
    CLOSE_NOTICE = JOCR(
        expected=["关闭", "跳过"],
        roi=(900, 0, 380, 240),
    )
    CONFIRM = JOCR(
        expected=["确认"],
        roi=(400, 350, 480, 360),
    )


def login_handler(tick: Tick):
    if close := tick.match(Login.CLOSE_NOTICE):
        close.click()
        return CONTINUE

    if start := tick.match(Login.START):
        print(f"START matched: box={start.box}")
        start.click()
        return CONTINUE

    if confirm := tick.match(Login.CONFIRM):
        confirm.click()
        return CONTINUE

    return DONE


def load_resource() -> Resource:
    resource = Resource()
    job = resource.post_bundle(str(RESOURCE_DIR)).wait()
    if not job.succeeded:
        raise RuntimeError(f"Failed to load MaaFramework resource: {RESOURCE_DIR}")
    return resource


def main(*, serial: str | None = None) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    Toolkit.init_option(str(DEBUG_DIR))

    devices = Toolkit.find_adb_devices()
    if serial is not None:
        devices = [device for device in devices if device.address == serial]
    if not devices:
        raise RuntimeError(f"No ADB device found for serial={serial!r}; check device discovery")
    if len(devices) > 1:
        candidates = ", ".join(device.address for device in devices)
        raise RuntimeError(f"Multiple ADB devices found ({candidates}); pass serial=... explicitly")

    device = devices[0]
    controller = AdbController(
        adb_path=device.adb_path,
        address=device.address,
        screencap_methods=device.screencap_methods,
        input_methods=device.input_methods,
        config=device.config,
    )
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError(f"Failed to connect ADB device: {device.address}")

    with App.from_maa(
        tasker=Tasker(),
        controller=controller,
        resource=load_resource(),
    ) as app:
        app.task("login", login_handler, priority=10).submit()
        app.run(interval=100)


if __name__ == "__main__":
    main()
