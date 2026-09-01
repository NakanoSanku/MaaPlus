# MaaPlus

MaaPlus is a small code-first application layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

For normal application development, start with only these concepts:

- `Template` / `OCR` — describe what UI elements look like.
- `Tick` — one decision over one fixed screenshot.
- `CONTINUE` / `YIELD` / `DONE` — tell MaaPlus what should happen after that decision.
- `App` — register, schedule, route, and run tasks.

The lower-level `Runtime`, `Task`, `Scheduler`, and `RoutedFlow` APIs remain available when you need direct control, but they are not required for a first project.

## Installation

This repository currently targets Python 3.14+ and MaaFramework 5.12.3+.

```bash
uv sync
```

## Quick start

Define UI elements with normal MaaFramework recognition parameters:

```python
from maaplus import OCR, Template


class LoginUI:
    START = Template(
        template=["login/start.png"],
        threshold=[0.85],
    )
    CLOSE = OCR(expected=["关闭", "跳过"])
    CONFIRM = OCR(expected=["确认"])
```

Then write a flow that receives one `Tick`:

```python
from maaplus import CONTINUE, DONE, Tick


def login(tick: Tick):
    if close := tick.match(LoginUI.CLOSE):
        close.click()
        return CONTINUE

    if start := tick.match(LoginUI.START):
        start.click()
        return CONTINUE

    if confirm := tick.match(LoginUI.CONFIRM):
        confirm.click()
        return CONTINUE

    return DONE
```

Register and run it:

```python
from maaplus import App


with App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
) as app:
    app.task("login", login).submit()
    app.run(interval=100)
```

That is enough for a basic MaaPlus application.

## Tick

One flow call is one **tick**:

```text
fresh screenshot
      ↓
    Tick
      ↓
  flow(tick)
      ↓
CONTINUE / YIELD / DONE
```

Every `tick.match(...)` in that call uses the same screenshot automatically:

```python
if tick.match(UI.A):
    ...

if tick.match(UI.B):
    ...
```

You do not need to pass `runtime` and `image` through application code yourself.

Actions do not replace the current tick image. After a click or swipe, return from the flow and observe the resulting UI from a fresh screenshot on a later tick.

`Tick` also exposes direct actions when needed:

```python
tick.click((500, 300), duration=100)

tick.swipe(
    [(200, 800), (220, 650), (260, 500), (300, 350)],
    duration=400,
)
```

Recognition results still support action sugar:

```python
if button := tick.match(UI.BUTTON):
    button.click()
```

## CONTINUE, YIELD, DONE

These are aliases for `FlowResult` values, provided so application flows stay concise.

| Result | Meaning |
| --- | --- |
| `CONTINUE` | I am not finished and the current UI is still mine. Do not preempt me. |
| `YIELD` | I am not finished, but the current UI is safe for another task to take over. |
| `DONE` | This execution is complete and the UI may be handed to the next task. |

A battle flow commonly looks like this:

```python
from maaplus import CONTINUE, DONE, YIELD


def explore(tick):
    if tick.match(ExploreUI.BATTLE_RUNNING):
        return CONTINUE

    if result := tick.match(ExploreUI.BATTLE_RESULT):
        result.click()
        return CONTINUE

    if tick.match(ExploreUI.EXPLORE_READY):
        if explore_finished():
            return DONE
        return YIELD

    return CONTINUE
```

The important rule is:

```text
Tick boundary
    !=
safe task-switch boundary
```

Only `YIELD` explicitly makes an unfinished task preemptible.

## Tasks and scheduling

`App.task()` returns a `TaskHandle` with fluent scheduling methods:

```python
explore = app.task(
    "explore",
    ExploreFlow(),
    priority=10,
)

draw = app.task(
    "draw",
    DrawFlow(),
    priority=100,
)

explore.submit()
draw.after(30_000)
draw.every(3_600_000)
```

You can also schedule a wall-clock datetime:

```python
draw.at(target_datetime)
```

Higher numeric priority wins, but a high-priority task cannot interrupt an unfinished current task until that task returns `YIELD`.

The same task object has at most one active execution plus one pending execution request. Repeated triggers coalesce instead of building an unbounded backlog.

## Context navigation

Tasks often need different UI contexts. For example, an exploration task may run from the explore screen while a timed draw task needs the summon screen.

Give `App` a navigator:

```python
from enum import Enum, auto

from maaplus import Tick


class Scene(Enum):
    HOME = auto()
    EXPLORE = auto()
    DRAW = auto()


class GameNavigator:
    def ensure(self, target: Scene, tick: Tick) -> bool:
        if target is Scene.EXPLORE and tick.match(ExploreUI.MARKER):
            return True

        if target is Scene.DRAW and tick.match(DrawUI.MARKER):
            return True

        if tick.match(ExploreUI.MARKER):
            if back := tick.match(ExploreUI.BACK):
                back.click()
            return False

        if tick.match(DrawUI.MARKER):
            if back := tick.match(DrawUI.BACK):
                back.click()
            return False

        if tick.match(HomeUI.MARKER):
            if target is Scene.EXPLORE:
                if button := tick.match(HomeUI.EXPLORE):
                    button.click()
                return False

            if target is Scene.DRAW:
                if button := tick.match(HomeUI.DRAW):
                    button.click()
                return False

        return False
```

`ensure()` returns `True` only when the **current tick snapshot** already satisfies the target. If navigation performs an action, return `False` and let the next tick observe the result.

Declare task contexts on `App.task()`:

```python
app = App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
    navigator=GameNavigator(),
)

explore = app.task(
    "explore",
    ExploreFlow(),
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
draw.every(3_600_000)
app.run(interval=100)
```

`App` automatically composes context restoration around each task.

A preemption can therefore look like:

```text
ExploreFlow: battle running
      ↓
CONTINUE
      ↓
Draw task becomes ready
      ↓
ExploreFlow keeps running
      ↓
battle finishes, stable explore screen
      ↓
YIELD
      ↓
Draw gets control
      ↓
Navigator: EXPLORE -> ... -> DRAW
      ↓
DrawFlow
      ↓
DONE
      ↓
Explore resumes
      ↓
Navigator: DRAW -> ... -> EXPLORE
      ↓
original ExploreFlow continues
```

The suspended flow object keeps its Python state. The navigator restores the external UI context before that flow is called again.

A safe handoff point does **not** have to be one universal home screen. It only needs to be a state from which your navigator can safely take control.

## Stateful flows

Use callable objects for business progress that must survive multiple ticks or preemption:

```python
from maaplus import CONTINUE, DONE, YIELD, Tick


class ExploreFlow:
    def __init__(self) -> None:
        self.killed = 0

    def __call__(self, tick: Tick):
        if result := tick.match(ExploreUI.BATTLE_RESULT):
            result.click()
            self.killed += 1
            return CONTINUE

        if self.killed >= 10:
            return DONE

        if tick.match(ExploreUI.EXPLORE_READY):
            return YIELD

        return CONTINUE
```

This separates different kinds of state cleanly:

```text
Python/business progress
    -> flow object

Current UI scene
    -> current screenshot + navigator recognition

Safe handoff permission
    -> YIELD / DONE

Current/ready/suspended task execution
    -> Scheduler
```

MaaPlus does not add a global game-state manager.

## Recommended project layout

A small application can start with:

```text
my_project/
├── app.py
├── ui.py
├── navigation.py
├── flows.py
└── resource/
```

As the project grows, split by responsibility:

```text
my_project/
├── ui/
├── navigation/
├── flows/
├── tasks/
├── config/
└── bootstrap.py
```

Keep these boundaries simple:

- UI definitions describe recognition only.
- Navigator handles context movement only.
- Flows own business decisions and business state.
- App/TaskHandle own registration and scheduling.
- Scheduler stays unaware of application scenes.

## Advanced / low-level API

The high-level API is intentionally a facade over a smaller core rather than a second execution engine.

Conceptually:

```text
App.task(flow, context, priority)
             ↓
        Tick adapter
             ↓
   optional RoutedFlow
             ↓
            Task
             ↓
         Scheduler
             ↓
          Runtime
             ↓
       MaaFramework
```

Advanced users can use the lower-level pieces directly:

```python
from maaplus import FlowResult, Scheduler, Task


def low_level_flow(runtime, image) -> FlowResult:
    result = runtime.match(UI.BUTTON, image)
    if result:
        result.click()
        return FlowResult.CONTINUE
    return FlowResult.DONE


scheduler.submit(
    Task("low-level", low_level_flow, priority=10)
)
scheduler.run(interval=100)
```

### Runtime

`Runtime` is a thin synchronous facade over MaaFramework. It exposes screenshot, recognition, click, swipe, and stop primitives. It does not own screenshot caching, application scenes, flow state, or scheduling decisions.

### Scheduler

Scheduler owns ready work, timed and recurring triggers, priority selection, safe-point cooperative preemption, the suspended stack, coalescing, and pause/resume/stop lifecycle. It does not understand application scenes.

### RoutedFlow

`RoutedFlow` and `routed()` remain available for custom low-level composition. Normal `App.task(..., context=...)` usage performs this wiring automatically.

## Architecture

```text
                    Application
                        │
                App / TaskHandle
                  /           \
                 /             \
              Tick         Navigator
                 \             /
                  \           /
                 business Flow
                       │
                  FlowResult
                       │
          ┌────────────┴────────────┐
          │                         │
       routing                  scheduling
          │                         │
          └────────────┬────────────┘
                       ▼
                    Runtime
                       ▼
                  MaaFramework
```

The core rule remains: remove application boilerplate without rebuilding MaaFramework itself.

## Tests

```bash
python -m unittest discover -s tests -v
```
