# Global guards

Global guards handle UI conditions that can appear over any task, such as notification dialogs,
connection prompts, and maintenance screens. They run after the scheduler captures a screenshot and
before context routing or the task handler. A guard and the task therefore inspect the same `Tick`
image.

```python
from maaplus import App, GuardResult, OCR, Tick


def notice_guard(tick: Tick):
    if notice := tick.match(OCR(expected=["知道了", "关闭"])):
        notice.click()
        return GuardResult.HANDLED
    return GuardResult.IGNORE


app = App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
)
app.guard("notice", notice_guard, priority=100)
```

Use `cadence` to limit how often an expensive check runs and `cooldown` to leave a short gap after
it handles a condition. Both are milliseconds; zero keeps the default per-tick behavior:

```python
app.guard("notice", notice_guard, priority=100, cadence=250, cooldown=500)
```

The scheduler checks guards in descending numeric priority. A guard may return `GuardResult` values,
or the shorthand `True`/`False`:

| Result | Meaning |
| --- | --- |
| `IGNORE` / `False` / `None` | Continue to the next guard and then the task. |
| `HANDLED` / `True` | The guard handled the current screenshot. Skip the task handler and take a fresh screenshot on the next tick. |
| `INVALIDATE` | Handle the condition and require context routing again before the task resumes. |
| `ABORT` | Fail the current task with `GuardAbortError`. |

`HANDLED` keeps the current task's execution and UI ownership. This allows a transient popup to be
dismissed without losing task-local state. `INVALIDATE` is useful when the recovery action returns to
the home screen or otherwise changes the task's scene.

Guards are checked even while the current task returns `CONTINUE`, so they do not depend on normal
task preemption. If a guard keeps returning `HANDLED` without clearing the condition,
`max_consecutive` (default `3`) raises `GuardLoopError`; set it to `None` only for a deliberately
repeatable guard.

By default the scheduler stops when its task queue becomes idle. Call `app.watch_idle(interval)` to
keep it alive and run the guards periodically between tasks. This is useful for notifications that
can appear while the application is otherwise waiting; stop the app or its instance manager when
the watcher should end.

Register guards at application setup or pass them through `App.from_maa(..., guards=[...])` and
`App.from_runtime(..., guards=[...])`. Use cheap Template or Color locators for frequent guards and
reserve OCR for conditions that need it. Guards run only when the scheduler has an active tick; an
idle scheduler does not capture screenshots for monitoring.
