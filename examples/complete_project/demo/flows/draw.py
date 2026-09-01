from __future__ import annotations

from maaplus import CONTINUE, DONE, Tick

from ..ui.draw import DrawUI


class DrawFlow:
    """Recurring high-priority task.

    The same flow object is reused across executions, so execution-local state is reset before
    returning DONE.
    """

    def __init__(self) -> None:
        self._started = False

    def __call__(self, tick: Tick):
        if close := tick.match(DrawUI.RESULT_CLOSE):
            close.click()
            return CONTINUE

        if confirm := tick.match(DrawUI.CONFIRM):
            confirm.click()
            return CONTINUE

        if free := tick.match(DrawUI.FREE_DRAW):
            print("[draw] free draw available")
            self._started = True
            free.click()
            return CONTINUE

        if tick.match(DrawUI.MARKER):
            if self._started:
                print("[draw] completed")
                self._started = False
                return DONE

            print("[draw] nothing to do")
            return DONE

        return CONTINUE
