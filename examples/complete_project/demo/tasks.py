from __future__ import annotations

from maaplus import App

from .flows.draw import DrawFlow
from .flows.explore import ExploreFlow
from .navigation.scene import Scene

DRAW_INTERVAL = 60 * 60 * 1000


def register_tasks(app: App[Scene]) -> None:
    explore = app.task(
        "explore",
        ExploreFlow(max_monsters=10),
        context=Scene.EXPLORE,
        priority=10,
    )

    draw = app.task(
        "draw",
        DrawFlow(),
        context=Scene.DRAW,
        priority=100,
    )

    explore.submit()
    draw.every(DRAW_INTERVAL)

    # During development it is often easier to replace the recurring trigger above with:
    # draw.after(10_000)
