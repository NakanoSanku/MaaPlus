from __future__ import annotations

from pathlib import Path

from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maaplus import Flow, FlowContext, OCR, Runner, Template


ROOT = Path(__file__).resolve().parent
RESOURCE_DIR = ROOT / "resource"
DEBUG_DIR = ROOT / ".debug"


class Login:
    """Locators only describe how UI elements are recognized."""

    # Template paths are relative to RESOURCE_DIR / "image".
    START = Template("login/start.png", threshold=0.85)

    # Optional UI that may or may not appear.
    CLOSE_NOTICE = OCR(("关闭", "跳过"), roi=(900, 0, 380, 240))
    CONFIRM = OCR("确认", roi=(400, 350, 480, 360))


class LoginFlow(Flow):
    """Business decisions live here; no MaaFramework calls are needed."""

    def run(self, ctx: FlowContext) -> None:
        # Optional action: a miss simply returns False.
        # If it hits, click() invalidates the shared screenshot automatically.
        ctx.find(Login.CLOSE_NOTICE).click()

        # Required action: require() raises LocatorNotFound when START is absent.
        start = ctx.find(Login.START).require()
        print(f"START matched: box={start.box}, score={start.score}")
        start.click()

        # This find() gets a fresh screenshot because the previous click succeeded.
        # The confirmation dialog is optional.
        ctx.find(Login.CONFIRM).click()


def create_adb_controller() -> AdbController:
    """Keep environment-specific controller setup outside MaaPlus flows."""

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

    controller = create_adb_controller()
    resource = load_resource()
    tasker = Tasker()

    runner = Runner.from_maa(
        tasker=tasker,
        controller=controller,
        resource=resource,
    )

    try:
        runner.run(LoginFlow())
    finally:
        runner.stop()


if __name__ == "__main__":
    main()
