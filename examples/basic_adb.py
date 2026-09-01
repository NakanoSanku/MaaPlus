from __future__ import annotations

from pathlib import Path

from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maaplus import App, CONTINUE, DONE, OCR, Template, Tick


ROOT = Path(__file__).resolve().parent
RESOURCE_DIR = ROOT / "resource"
DEBUG_DIR = ROOT / ".debug"


class Login:
    START = Template(
        template=["login/start.png"],
        threshold=[0.85],
    )
    CLOSE_NOTICE = OCR(
        expected=["关闭", "跳过"],
        roi=(900, 0, 380, 240),
    )
    CONFIRM = OCR(
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


def create_adb_controller() -> AdbController:
    devices = Toolkit.find_adb_devices()
    if not devices:
        raise RuntimeError("No ADB device found")

    device = devices[0]
    controller = AdbController(
        adb_path=device.adb_path,
        address=device.address,
        screencap_methods=device.screencap_methods,
        input_methods=device.input_methods,
        config=device.config,
    )

    job = controller.post_connection().wait()
    if not job.succeeded:
        raise RuntimeError(f"Failed to connect ADB device: {device.address}")
    return controller


def load_resource() -> Resource:
    resource = Resource()
    job = resource.post_bundle(str(RESOURCE_DIR)).wait()
    if not job.succeeded:
        raise RuntimeError(f"Failed to load MaaFramework resource: {RESOURCE_DIR}")
    return resource


def main() -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    Toolkit.init_option(str(DEBUG_DIR))

    with App.from_maa(
        tasker=Tasker(),
        controller=create_adb_controller(),
        resource=load_resource(),
    ) as app:
        app.task("login", login_handler, priority=10).submit()
        app.run(interval=100)


if __name__ == "__main__":
    main()
