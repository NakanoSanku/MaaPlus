from __future__ import annotations

from maaplus import NavigationState, Tick

from ..ui.common import CommonUI
from ..ui.draw import DrawUI
from ..ui.explore import ExploreUI
from ..ui.home import HomeUI
from .scene import Scene


class YYSNavigator:
    """Restore one stable application context, one navigation action per tick."""

    def ensure(self, target: Scene, tick: Tick) -> NavigationState:
        current = self._detect_scene(tick)

        if current is target:
            return NavigationState.READY

        # Unknown scenes include loading and transition frames. Wait for a fresh screenshot.
        if current is None:
            return NavigationState.WAITING

        # In this example HOME is the navigation hub.
        if current in {Scene.EXPLORE, Scene.DRAW}:
            if back := tick.match(CommonUI.BACK):
                back.click()
            return NavigationState.WAITING

        if current is Scene.HOME:
            if target is Scene.EXPLORE:
                if button := tick.match(HomeUI.EXPLORE):
                    button.click()
                return NavigationState.WAITING

            if target is Scene.DRAW:
                if button := tick.match(HomeUI.DRAW):
                    button.click()
                return NavigationState.WAITING

        return NavigationState.FAILED

    @staticmethod
    def _detect_scene(tick: Tick) -> Scene | None:
        if tick.match(HomeUI.MARKER):
            return Scene.HOME
        if tick.match(ExploreUI.MARKER):
            return Scene.EXPLORE
        if tick.match(DrawUI.MARKER):
            return Scene.DRAW
        return None
