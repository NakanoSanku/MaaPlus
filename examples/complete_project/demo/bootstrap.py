from __future__ import annotations

from pathlib import Path

from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maaplus import (
    App,
    ClickConfig,
    InteractionConfig,
    SwipeConfig,
    click,
    swipe,
    timing,
)

from .navigation.navigator import YYSNavigator
from .navigation.scene import Scene

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "resource"
DEBUG_DIR = ROOT / ".debug"

INTERACTION = InteractionConfig(
    click=ClickConfig(
        resolver=click.random(padding=0.15),
        duration=timing.random(40, 90),
        pre_delay=timing.random(80, 150),
        post_delay=timing.random(250, 450),
    ),
    swipe=SwipeConfig(
        duration=timing.random(300, 500),
        post_delay=timing.random(250, 400),
        interpolation=swipe.ease_in_out(samples=20),
    ),
    action_interval=timing.random(60, 120),
)


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
        raise RuntimeError(f"Failed to load resource: {RESOURCE_DIR}")
    return resource


def create_app() -> App[Scene]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    Toolkit.init_option(str(DEBUG_DIR))

    return App.from_maa(
        tasker=Tasker(),
        controller=create_adb_controller(),
        resource=load_resource(),
        navigator=YYSNavigator(),
        interaction=INTERACTION,
    )
