# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework owns recognition, resources, controllers, and native execution. MaaPlus adds a small synchronous runtime, `MatchResult` action sugar, a snapshot-driven flow protocol, optional routed-flow composition, and a priority scheduler with explicit safe-point preemption.

## Core API

- `Template` — alias of MaaFramework `JTemplateMatch`.
- `OCR` — alias of MaaFramework `JOCR`.
- `MatchResult` — thin wrapper around MaaFramework `RecognitionDetail`, adding truthiness and `click()`.
- `Runtime` — screenshot, recognition, click, and swipe primitives.
- `FlowResult` — one tick's scheduling result: `CONTINUE`, `YIELD`, or `DONE`.
- `Task` — a named flow plus a priority.
- `Scheduler` — priority selection, timed/recurring triggers, safe-point cooperative preemption, pause/resume, and lifecycle.
- `Navigator` — application-defined protocol for restoring a required external UI context.
- `RoutedFlow` / `routed()` — optional composition that restores a context before business flow execution.

There is no MaaPlus recognition schema, page-object layer, retry DSL, task graph, worker pool, cron parser, global scene state machine, or custom business-state manager.

## Installation

This repository currently targets Python 3.14+ and MaaFramework 5.12.3+.

```bash
uv sync
```

## Recognition parameters

`Template` and `OCR` are MaaFramework classes directly:

```python
from maa.pipeline import JOCR, JTemplateMatch
from maaplus import OCR, Template

assert Template is JTemplateMatch
assert OCR is JOCR
```

Use the normal MaaFramework parameter schema:

```python
class Login:
    START = Template(
        template=["login/start.png"],
        threshold=[0.85],
        roi_offset=(0, 0, 0, 0),
    )

    CONFIRM = OCR(
        expected=["确认"],
        replace=[["確認", "确认"]],
        color_filter="white_text",
    )
```

`Runtime.match()` accepts MaaFramework `JRecognitionParam` directly, so MaaPlus does not rebuild or restrict recognition parameters.

## Flow / tick semantics

A flow is an ordinary Python callable:

```python
flow(runtime, image) -> FlowResult
```

One task **tick** always means one fresh screenshot and one flow call:

```text
Scheduler.tick(task)
        ↓
Runtime.screenshot()   # exactly once
        ↓
task.flow(runtime, image)
        ↓
all match(..., image) calls use the same snapshot
        ↓
FlowResult
```

Actions never replace the image inside the current tick. New UI state is evaluated only on a later tick with a fresh screenshot.

```python
from maaplus import FlowResult, OCR, Runtime, Template


class Login:
    START = Template(template=["login/start.png"], threshold=[0.85])
    CLOSE = OCR(expected=["关闭", "跳过"])
    CONFIRM = OCR(expected=["确认"])


def login(runtime: Runtime, image) -> FlowResult:
    close = runtime.match(Login.CLOSE, image)
    if close:
        close.click()
        return FlowResult.CONTINUE

    start = runtime.match(Login.START, image)
    if start:
        start.click()
        return FlowResult.CONTINUE

    confirm = runtime.match(Login.CONFIRM, image)
    if confirm:
        confirm.click()
        return FlowResult.CONTINUE

    return FlowResult.DONE
```

Boolean flow results are deliberately not accepted. Returning `True` or `False` raises `TypeError`; the scheduling meaning must be explicit.

## FlowResult and external UI ownership

A running task temporarily owns the device's external UI state. A Python tick ending does **not** automatically mean that another task can understand or safely take over that state.

`FlowResult` makes this ownership explicit:

| Result | Execution | External UI ownership | Preemptible |
| --- | --- | --- | --- |
| `CONTINUE` | unfinished | retained by current task | no |
| `YIELD` | unfinished | safe to hand off | yes |
| `DONE` | complete | released | task ends |

`CONTINUE` means the current task still owns the scene. This is appropriate for states such as an active battle, a transaction sequence, a login transition, or any other flow-private UI that another task or navigator is not expected to recover from.

`YIELD` means the execution still has work, but the current external state is safe for another task's navigation layer to take over. If a strictly higher-priority task is ready, Scheduler may suspend the current task there. If no higher-priority task is ready, the same task simply receives another tick.

`DONE` means this execution is complete and releases device ownership. It does not require every future task to directly recognize the current page; it requires the page to be a safe handoff state from which the application's navigation layer can continue.

MaaPlus deliberately does not define what a safe scene is. One application may use a home screen, another may allow several stable pages such as lobby, explore, shop, or draw. The scheduler records only whether the current flow yielded; it does not know about `HOME`, `BATTLE`, `SHOP`, or any other business scene.

A typical game flow can therefore express:

```python
from maaplus import FlowResult


def explore(runtime, image) -> FlowResult:
    if is_battle_running(runtime, image):
        play_battle(runtime, image)
        return FlowResult.CONTINUE

    if is_battle_result(runtime, image):
        close_result(runtime, image)
        return FlowResult.CONTINUE

    if is_explore_page(runtime, image):
        if explore_finished():
            return FlowResult.DONE
        return FlowResult.YIELD

    recover_explore_private_state(runtime, image)
    return FlowResult.CONTINUE
```

The important distinction is:

```text
Tick boundary
    ≠
safe preemption point
```

Only an explicit `YIELD` creates a safe preemption point for an unfinished execution.

## Routed flows and context restoration

A safe handoff state does not have to be the next task's business page.

For example, an exploration task may safely yield while still on the exploration page. A timed draw task can then take over, navigate from exploration to the draw page, do its work, and finish there. When exploration resumes, it must navigate from the draw page back to exploration before its business flow continues.

MaaPlus keeps this concern out of `Scheduler`. The optional `Navigator` / `RoutedFlow` composition handles it.

A navigator implements one method:

```python
navigator.ensure(target, runtime, image) -> bool
```

The contract is snapshot-based:

- return `True` only when the supplied snapshot already satisfies `target`; the wrapped business flow may run in the same tick;
- otherwise, optionally perform one navigation action based on that snapshot and return `False`;
- after `False`, `RoutedFlow` returns `FlowResult.CONTINUE`, so the navigation result is observed on a fresh screenshot during a later tick.

The context type is application-defined. It can be an enum, string, dataclass, or any other object meaningful to the application.

```python
from enum import Enum, auto

from maaplus import FlowResult, Task, routed


class Scene(Enum):
    EXPLORE = auto()
    DRAW = auto()


class GameNavigator:
    def ensure(self, target: Scene, runtime, image) -> bool:
        if target is Scene.EXPLORE:
            if is_explore(runtime, image):
                return True
            navigate_one_step_toward_explore(runtime, image)
            return False

        if target is Scene.DRAW:
            if is_draw(runtime, image):
                return True
            navigate_one_step_toward_draw(runtime, image)
            return False

        raise ValueError(f"Unsupported scene: {target}")


navigator = GameNavigator()

explore_task = Task(
    "explore",
    routed(ExploreFlow(), target=Scene.EXPLORE, navigator=navigator),
    priority=10,
)

draw_task = Task(
    "draw",
    routed(DrawFlow(), target=Scene.DRAW, navigator=navigator),
    priority=100,
)
```

The resulting handoff is:

```text
ExploreFlow: battle
      ↓
CONTINUE
      ↓
Draw task becomes ready
      ↓
ExploreFlow finishes battle and reaches stable explore page
      ↓
YIELD
      ↓
Scheduler suspends Explore task
      ↓
Draw RoutedFlow
      ↓
Navigator.ensure(DRAW): EXPLORE → ... → DRAW
      ↓
DrawFlow runs
      ↓
DONE on stable draw page
      ↓
Scheduler resumes Explore task
      ↓
Explore RoutedFlow
      ↓
Navigator.ensure(EXPLORE): DRAW → ... → EXPLORE
      ↓
original ExploreFlow object continues with its saved Python state
```

Navigation ticks deliberately return `CONTINUE`. This conservatively keeps device ownership with the task while it is between contexts. Once the required context is reached, the wrapped business flow again decides whether the next boundary is `CONTINUE`, `YIELD`, or `DONE`.

`Navigator` does not require a scene graph or global current-scene variable. An application can implement direct recognition rules, a hub-based strategy, a graph router, or any other navigation policy behind `ensure()`. Screenshot recognition remains the source of truth.

This keeps the two responsibilities orthogonal:

```text
FlowResult
    → may another execution take ownership now?

Navigator / RoutedFlow
    → after ownership changes, how does this execution restore its required context?
```

## Tasks and triggers

A `Task` describes **what should run** and its priority:

```python
from maaplus import Task

normal = Task("daily", daily_flow, priority=10)
timed = Task("timed-event", timed_event_flow, priority=100)
```

Higher numeric priority wins. Trigger APIs only decide **when the task becomes ready**:

```python
scheduler.submit(normal)  # now
scheduler.after(timed, delay=60_000)  # once, 60 seconds later
scheduler.at(timed, when=target_datetime)  # once, wall-clock datetime
scheduler.every(timed, interval=3_600_000)  # recurring, every hour
```

All millisecond APIs use integers. `at()` accepts either a naive local `datetime` or an aware `datetime`; past datetimes become ready immediately.

`after()` and `at()` are one-shot. `every()` first triggers after one interval and then stays registered until the scheduler is stopped or discarded. A scheduler with recurring work therefore remains alive instead of returning merely because no task is ready right now.

Recurring deadlines follow the original monotonic schedule timeline rather than `now + interval`, so late execution does not gradually shift the schedule. If several periods are missed, they coalesce into one execution request instead of being replayed as a backlog.

## Coalescing

The same `Task` object has at most one active execution plus one pending execution request.

If a trigger fires while that task is already current, ready, or suspended, Scheduler does not add another copy to the queue. It records one pending request instead. Additional triggers while pending are merged into that same request.

```text
Task already active
      ↓
trigger #1 → pending
trigger #2 → still one pending
trigger #3 → still one pending
      ↓
active execution finishes
      ↓
one new execution becomes ready
```

This applies to `submit()`, one-shot triggers, and recurring triggers. It prevents periodic work from building an unbounded backlog while the device is busy.

## Safe-point cooperative preemption

A higher-priority ready task does not automatically interrupt the current task at the next tick boundary. It waits until the current unfinished flow explicitly returns `FlowResult.YIELD`.

```text
normal tick #1: battle running
      ↓
returns CONTINUE
      ↓
high-priority timed task becomes ready
      ↓
normal tick #2: battle still running
      ↓
returns CONTINUE
      ↓
normal tick #3: back at handoff-safe scene
      ↓
returns YIELD
      ↓
normal is suspended
      ↓
timed task runs or restores its required context
      ↓
timed returns DONE
      ↓
normal resumes with a fresh screenshot and restores its own context if needed
```

Only a **strictly higher** priority task preempts a yielded current task. Equal-priority tasks wait instead of causing task switching.

A task that keeps returning `CONTINUE` keeps ownership even if higher-priority work is ready. That is intentional cooperative scheduling: the flow is responsible for eventually reaching a safe handoff point if it wants to permit preemption.

Suspended tasks use stack semantics, so nested preemption naturally unwinds:

```text
A(priority 10)  --YIELD-->
  ↓ preempted by
B(priority 100) --YIELD-->
  ↓ preempted by
C(priority 200)
  ↓ C DONE
B resumes
  ↓ B DONE
A resumes
```

When a preempting task finishes, the scheduler prefers the suspended task on an equal-priority tie. A ready task with a higher priority still runs first.

## Scheduler

Basic use:

```python
from maaplus import Scheduler, Task

with Scheduler.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
) as scheduler:
    scheduler.submit(Task("daily", daily_flow, priority=10))
    scheduler.after(Task("timed", timed_flow, priority=100), delay=60_000)
    scheduler.every(Task("periodic", periodic_flow, priority=50), interval=3_600_000)
    scheduler.run(interval=100)
```

`interval` is milliseconds between consecutive ticks of the **same current task**. A newly selected or actually preempting task runs immediately. A higher-priority ready task can become the preempting task only when the current task is at an explicit yielded boundary.

The scheduler exposes:

```python
scheduler.current
scheduler.running
scheduler.paused

scheduler.pause()
scheduler.resume()
scheduler.stop()
```

`pause()` does not interrupt the current tick; it blocks before the next screenshot. `resume()` continues scheduling from that boundary.

`stop()` wakes paused/timed/interval waits and forwards stop to MaaFramework work in progress. Unfinished current/queued work and registered recurring schedules remain on the scheduler object, so calling `run()` again can continue them; pause/resume is still the preferred mechanism for a temporary in-process pause.

## Task-local state versus world state

The scheduler does not understand business state. If a task needs Python state across ticks or preemption, use a callable object:

```python
from maaplus import FlowResult, Runtime


class DailyFlow:
    def __init__(self) -> None:
        self.step = 0

    def __call__(self, runtime: Runtime, image) -> FlowResult:
        # self.step survives normal ticks, navigation, and scheduler preemption.
        ...
        return FlowResult.CONTINUE


daily = Task("daily", DailyFlow(), priority=10)
```

This task-local state is different from the device's external world state:

```text
Python/business progress
    → stored by the flow object

Current UI scene
    → observed from screenshots

Whether the UI may be handed to another task
    → expressed by FlowResult.YIELD / DONE

How a task restores its required UI context
    → application Navigator wrapped by RoutedFlow
```

MaaPlus does not add a global `GameState` or scene registry. Screenshot recognition remains the source of truth for the external world.

## MatchResult

A miss is false; `hit` and `box` are common convenience properties:

```python
result = runtime.match(Login.START, image)

if result:
    print(result.box)
```

Recognition-specific values remain on the original MaaFramework detail:

```python
result.detail.best_result
result.detail.raw_detail
```

`MatchResult.click()` clicks the box center by default and holds for 50 ms:

```python
result.click()
result.click(duration=120)
```

A custom click position is a normal function:

```python
from random import randrange
from maaplus import MatchResult


def random_point(result: MatchResult) -> tuple[int, int]:
    x, y, width, height = result.box
    return randrange(x, x + width), randrange(y, y + height)


result.click(random_point, duration=80)
```

## Runtime gestures

Gesture durations are milliseconds.

```python
runtime.click((500, 300), duration=100)
```

means:

```text
touch_down(point)
hold
touch_up()
```

A swipe follows every supplied path point:

```python
runtime.swipe(
    [(200, 800), (220, 650), (260, 500), (300, 350)],
    duration=400,
)
```

The total duration is distributed over the path intervals.

## Architecture

```text
                          Scheduler
      ┌──────────────────────┼──────────────────────┐
      │                      │                      │
  ready heap          trigger/timed heap      suspended stack
      │                      │                      │
      └──────────────────────┼──────────────────────┘
                             ↓
                        current Task
                             ↓
                      fresh screenshot
                             ↓
                   optional RoutedFlow
                    /              \
          Navigator.ensure       business Flow
                    \              /
                     CONTINUE / YIELD / DONE
                             ↓
                          Runtime
                    match / click / swipe
                             ↓
                        MaaFramework
```

`Task` owns **what**. Trigger methods own **when**. Priority owns **who wants to run first**. `FlowResult.YIELD` owns **when an unfinished task may hand over the device**. `RoutedFlow` owns **how an execution restores its required context after selection or resume**. Scheduler remains unaware of business scenes.

The rule remains: delete boilerplate, do not build a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
