from __future__ import annotations

from pathlib import Path

from maa.resource import Resource
from maa.tasker import Tasker
from maa.toolkit import Toolkit

from maaplus import (
    App,
    ClickConfig,
    Debug,
    InteractionConfig,
    SwipeConfig,
    path,
    point,
    timing,
)
from maaplus.dev import create_adb_controller

from .navigation.navigator import YYSNavigator
from .navigation.scene import Scene
from .custom_recognition import create_custom_recognitions

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "resource"
DEBUG_DIR = ROOT / ".debug"

INTERACTION = InteractionConfig(
    click=ClickConfig(
        resolver=point.random(padding=0.15),
        duration=timing.random(40, 90),
        pre_delay=timing.random(80, 150),
        post_delay=timing.random(250, 450),
    ),
    swipe=SwipeConfig(
        duration=timing.random(300, 500),
        post_delay=timing.random(250, 400),
        interpolation=path.ease_in_out(samples=20),
    ),
    action_interval=timing.random(60, 120),
)


def load_resource() -> Resource:
    resource = Resource()
    job = resource.post_bundle(str(RESOURCE_DIR)).wait()
    if not job.succeeded:
        raise RuntimeError(f"Failed to load resource: {RESOURCE_DIR}")
    for name, recognition in create_custom_recognitions().items():
        # MaaFramework Resource retains registered Python callbacks for its lifetime.
        if not resource.register_custom_recognition(name, recognition):
            raise RuntimeError(f"Failed to register custom recognition: {name}")
    return resource


def create_app(
    *,
    serial: str | None = None,
    debug_dir: str | Path | None = None,
    configure_global_options: bool = True,
) -> App[Scene]:
    selected_debug_dir = Path(debug_dir) if debug_dir is not None else DEBUG_DIR
    selected_debug_dir.mkdir(parents=True, exist_ok=True)
    if configure_global_options:
        Toolkit.init_option(
            str(selected_debug_dir),
            {"save_draw": True, "save_on_error": True, "draw_quality": 85},
        )

    return App.from_maa(
        tasker=Tasker(),
        controller=create_adb_controller(serial=serial),
        resource=load_resource(),
        navigator=YYSNavigator(),
        interaction=INTERACTION,
        debug=Debug(selected_debug_dir, max_images=200),
    )
