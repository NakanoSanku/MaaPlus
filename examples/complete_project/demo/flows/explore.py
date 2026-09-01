from __future__ import annotations

from maaplus import CONTINUE, DONE, YIELD, Tick

from ..ui.explore import ExploreUI


class ExploreFlow:
    """Long-running exploration task with explicit handoff-safe points."""

    def __init__(self, *, max_monsters: int) -> None:
        self.max_monsters = max_monsters
        self.killed = 0
        self._battle_started = False

    def __call__(self, tick: Tick):
        # Battle UI is flow-private. A higher-priority task must wait.
        if tick.match(ExploreUI.BATTLE):
            self._battle_started = True
            return CONTINUE

        if result := tick.match(ExploreUI.BATTLE_RESULT):
            if self._battle_started:
                self.killed += 1
                self._battle_started = False
                print(f"[explore] defeated {self.killed}/{self.max_monsters}")

            if confirm := tick.match(ExploreUI.RESULT_CONFIRM):
                confirm.click()
            else:
                result.click()
            return CONTINUE

        # DONE is returned only from a stable context that Navigator can take over from.
        if self.killed >= self.max_monsters:
            if tick.match(ExploreUI.MARKER):
                print("[explore] completed")
                return DONE
            return CONTINUE

        if monster := tick.match(ExploreUI.MONSTER):
            print("[explore] start battle")
            monster.click()
            return CONTINUE

        # Stable exploration screen: unfinished, but safe for a higher-priority handoff.
        if tick.match(ExploreUI.MARKER):
            return YIELD

        return CONTINUE
