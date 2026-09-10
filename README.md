# MaaPlus

MaaPlus is a small code-first application layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

For normal application development, start with these concepts:

- `Template` / `OCR` — describe what UI elements look like.
- `Task` — one schedulable piece of work.
- `TaskHandler` — the business logic executed for that task.
- `Tick` — one handler invocation over one fixed screenshot.
- `CONTINUE` / `YIELD` / `DONE` — tell MaaPlus what should happen after the handler returns.
- `App` — register, schedule, route, and run tasks.

The core relationship is intentionally small:

```text
Task
 ├── name
 ├── priority
 └── handler(tick)
          ↓
   CONTINUE / YIELD / DONE
```

The lower-level `Runtime` and `Scheduler` APIs remain available when direct control is useful, but they are not required for a first project.

## Installation

MaaPlus 1.4 targets Python 3.10+ and MaaFramework 5.13.0+.

```bash
uv sync --dev
```

For the offline inspection workflow and project scaffold:

```bash
uv add "maaplus[dev]"
```

For a runnable offline first project:

```bash
maaplus init my-game
cd my-game
uv sync
uv run python main.py
maaplus doctor
```

Put a screenshot in `fixtures/` before running the generated offline example. Live device setup is
kept in `bootstrap.py` and is not required for the first recognition result.

After a run, summarize an evidence session with:

```bash
maaplus trace .maaplus/runs/<run-id>
```

To build a wheel and source archive:

```bash
uv build
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

Write a task handler:

```python
from maaplus import CONTINUE, DONE, Tick


def login_handler(tick: Tick):
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

Register and run the task:

```python
from maaplus import App


with App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
) as app:
    app.task("login", login_handler).submit()
    app.run(interval=100)
```

That is enough for a basic MaaPlus application.

## Multiple device instances

Use `InstanceManager` when the same application should run independently on more than one device.
The factory receives the device identifier and must create fresh MaaFramework objects, navigators,
guards, traces, and debug writers for each instance:

```python
from maaplus import InstanceManager


def build_app(config):
    return create_app(
        serial=config.device,
        debug_dir=config.debug_dir,
        configure_global_options=False,
    )


with InstanceManager(build_app, max_workers=2) as fleet:
    # Configure MaaFramework's process-wide options once before creating the fleet.
    fleet.create("phone-a", "emulator-5554")
    fleet.create("phone-b", "emulator-5556")
    for name in ("phone-a", "phone-b"):
        fleet.get(name).task("daily", daily_handler).submit()
    futures = fleet.start_all(interval=100)
    for future in futures.values():
        future.result()
```

The manager rejects duplicate instance names and device identifiers, keeps per-instance artifact
directories, and exposes lifecycle state and health through `fleet.instances` or
`fleet.snapshot(name)` (`health`, `failed_tasks`, and `current_task`). It uses a bounded thread
executor in the current release. See the [multiple device guide](docs/instances.md) for the factory
contract and isolation rules.

## Bounding-box debugging

Debug images are opt-in. Install the small image extra and pass a `Debug` sink while creating the
application:

```bash
uv add "maaplus[debug]"
```

```python
from maaplus import App, Debug

app = App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
    debug=Debug(".debug", max_images=200),
)
```

Every `tick.match()` then writes a PNG containing the original screenshot, the static recognition
ROI, and the returned hit box. `MatchResult.debug_path` points to that file. Green means a hit,
blue means the search ROI, and red means a miss. The original screenshot coordinates stay unchanged;
the caption is appended below the image. For an ad-hoc probe, draw any areas without another
recognition call:

```python
path = tick.draw((100, 200, 80, 40), label="battle probe")
```

The PNG also stores the full coordinates and label as `maaplus` metadata. Draw failures are logged
and do not stop a recognition tick; explicit `tick.draw()` validation errors are raised.

See the [bounding-box debugging guide](docs/debugging.md) for retention, ROI, and output details.

## Task and TaskHandler

A `Task` is only a schedulable identity:

```text
Task
 ├── name
 ├── handler
 └── priority
```

Its handler follows one standard signature everywhere in MaaPlus:

```python
handler(tick: Tick) -> TaskResult
```

There is no second low-level `(runtime, image)` handler signature. Scheduler itself creates the `Tick` and invokes `Task.handler` directly.

Simple handlers can be functions:

```python
def claim_reward(tick):
    if reward := tick.match(UI.REWARD):
        reward.click()
        return CONTINUE

    return DONE
```

Stateful handlers can be callable objects:

```python
class ExploreHandler:
    def __init__(self) -> None:
        self.killed = 0

    def __call__(self, tick):
        if result := tick.match(ExploreUI.BATTLE_RESULT):
            result.click()
            self.killed += 1
            return CONTINUE

        if self.killed >= 10:
            return DONE

        return YIELD
```

The same handler object survives multiple ticks and scheduler preemption. Use `tick.context.state`
for state that must reset at the start of each scheduled execution.

Scheduled executions now expose a fresh `tick.context` with a mutable `state` dictionary and attempt
number. Periodic runs do not reuse the previous execution context:

```python
def collect(tick):
    state = tick.context.state
    state["seen"] = state.get("seen", 0) + 1
    return DONE if state["seen"] >= 3 else CONTINUE

app.task("collect", collect, timeout=60_000, retries=2, retry_delay=500)
```

Timeouts and retries are measured in milliseconds. A task failure is isolated from unrelated ready
tasks; after retries are exhausted, `handle.failure` contains the exception and attempt count.
`handle.status` exposes the current lifecycle and `handle.last_execution` exposes the most recent
terminal summary. A failed task can be restarted with `handle.resume()`.

Periodic tasks pause after a terminal failure by default. Opt into continued periodic attempts only
when the task is safe to repeat:

```python
app.task("heartbeat", heartbeat, continue_recurring=True).every(60_000)
```

## Tick

Each handler invocation receives one `Tick`:

```text
fresh screenshot
      ↓
     Tick
      ↓
TaskHandler
      ↓
 TaskResult
```

Every `tick.match(...)` during that invocation uses the same screenshot automatically:

```python
if tick.match(UI.A):
    ...

if tick.match(UI.B):
    ...
```

You do not need to pass `runtime` and `image` through application code.

Actions do not replace the current tick image. After a click or swipe, return from the handler and observe the resulting UI from a fresh screenshot on a later tick.

`Tick` exposes direct actions when needed:

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

## TaskResult: CONTINUE, YIELD, DONE

`CONTINUE`, `YIELD`, and `DONE` are short aliases for `TaskResult` values.

| Result | Meaning |
| --- | --- |
| `CONTINUE` | This execution is unfinished and still owns the current UI. Do not preempt it. |
| `YIELD` | This execution is unfinished, but the current UI is safe for another task to take over. |
| `DONE` | This execution is complete and releases the UI. |

A battle-oriented handler commonly looks like this:

```python
from maaplus import CONTINUE, DONE, YIELD


def explore_handler(tick):
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
handler invocation ends
        !=
safe task-switch boundary
```

Only `YIELD` explicitly makes an unfinished task preemptible.

## Tasks and scheduling

`App.task()` returns a `TaskHandle` with fluent scheduling methods:

```python
explore = app.task(
    "explore",
    ExploreHandler(),
    priority=10,
)

draw = app.task(
    "draw",
    DrawHandler(),
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

Cancel a one-shot or recurring handle when it is no longer needed:

```python
draw.every(3_600_000)
draw.cancel()
```

Cancellation is cooperative. If the handler is already running, its current tick finishes and
the scheduler discards the task before taking another screenshot.

Higher numeric priority wins, but a high-priority task cannot interrupt an unfinished current task until that task returns `YIELD`.

The same `Task` object has at most one active execution plus one pending execution request. Repeated triggers coalesce instead of building an unbounded backlog.

## Context navigation

Tasks often need different UI contexts. For example, an exploration task may require the explore screen while a timed draw task requires the summon screen.

Define application contexts and a navigator:

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

`ensure()` returns `True` only when the current tick snapshot already satisfies the target. If navigation performs an action, return `False` and let the next tick observe the result.

Give the navigator to `App` and declare contexts on tasks:

```python
app = App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
    navigator=GameNavigator(),
)

explore = app.task(
    "explore",
    ExploreHandler(),
    context=Scene.EXPLORE,
    priority=10,
)

draw = app.task(
    "draw",
    DrawHandler(),
    context=Scene.DRAW,
    priority=100,
)

explore.submit()
draw.every(3_600_000)
app.run(interval=100)
```

`App` automatically wraps the handler with context restoration. Routing runs when an execution first
becomes active. After the navigator returns `READY`, later ticks call the task handler directly so
the handler can own private substates such as battles and result dialogs. If a higher-priority task
preempts it, the scheduler invalidates the route; the navigator runs again before the suspended
handler resumes. Pausing the scheduler does not invalidate the route because no other task can take
over the UI.

A preemption can therefore look like:

```text
ExploreHandler: battle running
        ↓
     CONTINUE
        ↓
Draw task becomes ready
        ↓
ExploreHandler keeps running
        ↓
battle finishes, stable explore screen
        ↓
      YIELD
        ↓
Draw gets control
        ↓
Navigator: EXPLORE -> ... -> DRAW
        ↓
DrawHandler
        ↓
      DONE
        ↓
Explore task resumes
        ↓
Navigator: DRAW -> ... -> EXPLORE
        ↓
original ExploreHandler continues
```

The suspended handler object keeps its Python state. The navigator restores the external UI context
before that handler is called again after preemption. The navigator does not need to recognize every
internal state owned by the handler.

A safe handoff point does not have to be one universal home screen. It only needs to be a state from which the navigator can safely take control.

## State ownership

Different kinds of state have different owners:

```text
Business progress
    -> TaskHandler object

Current UI scene
    -> Navigator recognition when a task activates or resumes; handler-owned state between activations

Safe handoff permission
    -> TaskResult.YIELD / DONE

Current / ready / suspended execution
    -> Scheduler
```

MaaPlus deliberately does not add a global game-state manager.

Recurring tasks reuse the same handler object. If a field represents execution-local state, reset it before returning `DONE` so the next recurring execution starts cleanly.

## Recommended project layout

For a small application:

```text
my_project/
├── app.py
├── ui.py
├── navigation.py
├── handlers.py
└── resource/
```

As the project grows:

```text
my_project/
├── ui/
├── navigation/
├── handlers/
├── tasks/
├── config/
└── bootstrap.py
```

Keep the boundaries simple:

- UI definitions describe recognition only.
- Navigator handles context movement only.
- Task handlers own business decisions and task-local state.
- Task registration owns priorities and trigger policy.
- Scheduler stays unaware of application scenes.

See `examples/complete_project/` for a copyable project structure.

## Advanced API

The high-level API is a facade over a small core, not a second execution engine.

Conceptually:

```text
App.task(handler, context, priority)
              ↓
     optional routing wrapper
              ↓
             Task
              ↓
          Scheduler
              ↓
       fresh screenshot
              ↓
             Tick
              ↓
       Task.handler(tick)
              ↓
          TaskResult
              ↓
           Runtime
              ↓
        MaaFramework
```

### Task

The core task model is directly usable:

```python
from maaplus import DONE, Scheduler, Task


task = Task(
    "direct",
    lambda tick: DONE,
    priority=10,
)

scheduler.submit(task)
scheduler.run()
```

There is no separate task-handler protocol for advanced use. Direct `Task` construction and `App.task()` use the same `handler(tick)` contract.

### Runtime

`Runtime` is a thin synchronous facade over MaaFramework. It exposes screenshot, recognition, click, swipe, and stop primitives. It does not own screenshot caching, application scenes, handler state, or scheduling decisions.

### Scheduler

Scheduler owns ready work, timed and recurring triggers, priority selection, safe-point cooperative preemption, the suspended stack, coalescing, and pause/resume/stop lifecycle. It does not understand application scenes.

### RoutedTaskHandler

`RoutedTaskHandler` and `routed()` remain available for explicit composition:

```python
from maaplus import Task, routed


handler = routed(
    DrawHandler(),
    target=Scene.DRAW,
    navigator=navigator,
)

task = Task("draw", handler, priority=100)
```

Normal `App.task(..., context=...)` usage performs this wiring automatically. The route is checked on
activation and after preemption, then skipped while the task retains UI ownership.

Navigation can return `NavigationState.READY`, `WAITING`, or `FAILED`. Routed tasks enforce a
navigation step limit and timeout, so a loading or unknown screen cannot silently hold higher-
priority work forever.

`App.task(..., context=...)` accepts `navigation_max_steps`, `navigation_timeout`, and
`yield_on_wait`. Waiting keeps UI ownership by default; `yield_on_wait=True` explicitly permits a
safe navigation task to yield while its context is loading.

## Global guards

Use a global guard for UI conditions that may appear over any task, such as notification dialogs or
connection prompts. Guards run after one screenshot is captured and before context routing or the
task handler, so they can handle a popup even while the current task returns `CONTINUE`:

```python
from maaplus import GuardResult, OCR, Tick


def notice_guard(tick: Tick):
    if notice := tick.match(OCR(expected=["知道了", "关闭"])):
        notice.click()
        return GuardResult.HANDLED
    return GuardResult.IGNORE


app.guard("notice", notice_guard, priority=100)
```

`HANDLED` skips the current task handler and takes a fresh screenshot on the next tick. Return
`INVALIDATE` when recovery changes the scene and routing must run again. Return `ABORT` for a fatal
condition. Guards run in descending priority order and stop after the first non-`IGNORE` result. A
guard that handles too many consecutive ticks raises `GuardLoopError` by default; configure
`max_consecutive=None` only when repeated handling is intentional. See the [global guard guide](docs/guards.md).

## Architecture

```text
                    Application
                        │
                App / TaskHandle
                        │
                       Task
                   /          \
                  /            \
             priority        handler
                                │
                  optional context routing
                                │
                              Tick
                                │
                  CONTINUE / YIELD / DONE
                                │
                            Scheduler
                                │
                             Runtime
                                │
                          MaaFramework
```

The core rule remains: remove application boilerplate without rebuilding MaaFramework itself.

## Examples

- `examples/basic_adb.py` — minimal first-contact example.
- `examples/complete_project/` — recommended multi-task project structure with navigation, preemption, and recurring work.
- [Custom recognition example](examples/complete_project/CUSTOM_RECOGNITION.md) — an application-owned multi-point color recognizer using MaaFramework's native interfaces.
- [Development workflow](docs/development.md) — fixture inspection, controller adapters, traces, and project scaffolding.
- [Global guards](docs/guards.md) — cross-task popup and exceptional UI handling.
- [Offline example](examples/fixture_project/README.md) — recognition, assertions, task state, and trace without a device.

## Tests

```bash
uv run pytest
```

See [CHANGELOG.md](CHANGELOG.md) for the release history.
