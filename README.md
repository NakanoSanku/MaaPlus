# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework owns recognition, resources, controllers, and native execution. MaaPlus adds a small synchronous runtime, `MatchResult` action sugar, a snapshot-driven flow protocol, and a priority scheduler with explicit safe-point preemption.

## Core API

- `Template` — alias of MaaFramework `JTemplateMatch`.
- `OCR` — alias of MaaFramework `JOCR`.
- `MatchResult` — thin wrapper around MaaFramework `RecognitionDetail`, adding truthiness and `click()`.
- `Runtime` — screenshot, recognition, click, and swipe primitives.
- `FlowResult` — one tick's scheduling result: `CONTINUE`, `YIELD`, or `DONE`.
- `Task` — a named flow plus a priority.
- `Scheduler` — priority selection, timed/recurring triggers, safe-point cooperative preemption, pause/resume, and lifecycle.

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

`CONTINUE` means the current task still owns the scene. This is appropriate for states such as an active battle, a transaction sequence, a login transition, or any other flow-private UI that another task is not expected to understand.

`YIELD` means the execution still has work, but the current scene is a safe handoff point. If a strictly higher-priority task is ready, Scheduler may suspend the current task there. If no higher-priority task is ready, the same task simply receives another tick.

`DONE` means this execution is complete and releases device ownership. A flow should return `DONE` only from a state that is safe to leave behind for whatever task Scheduler may choose next.

MaaPlus deliberately does not define what a safe scene is. One application may use a home screen, another may use a lobby or idle screen. The scheduler records only whether the current flow yielded; it does not know about `HOME`, `BATTLE`, `SHOP`, or any other business scene.

A typical game flow can therefore express:

```python
from maaplus import FlowResult


def daily(runtime, image) -> FlowResult:
    if is_battle_running(runtime, image):
        play_battle(runtime, image)
        return FlowResult.CONTINUE

    if is_battle_result(runtime, image):
        close_result(runtime, image)
        return FlowResult.CONTINUE

    if is_home(runtime, image):
        if daily_finished():
            return FlowResult.DONE
        return FlowResult.YIELD

    recover_known_scene(runtime, image)
    return FlowResult.CONTINUE
```

The important distinction is:

```text
Tick boundary
    ≠
safe preemption point
```

Only an explicit `YIELD` creates a safe preemption point for an unfinished execution.

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
normal tick #3: back at safe home scene
      ↓
returns YIELD
      ↓
normal is suspended
      ↓
timed task runs
      ↓
timed returns DONE
      ↓
normal resumes with a fresh screenshot
```

This prevents a newly selected task from inheriting an arbitrary flow-private scene that it cannot recognize or recover from.

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
        # self.step survives normal ticks and scheduler preemption.
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
```

MaaPlus does not add a global `GameState` or scene registry. Screenshot recognition remains the source of truth for the external world, while `FlowResult` only expresses the ownership boundary needed by Scheduler.

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
                   flow(runtime, image)
                             ↓
                CONTINUE / YIELD / DONE
                             ↓
                          Runtime
                    match / click / swipe
                             ↓
                        MaaFramework
```

`Task` owns **what**. Trigger methods own **when**. Priority owns **who wants to run first**. `FlowResult.YIELD` owns **when an unfinished task may actually hand over the device**. Preemption is the consequence of both priority and an explicit safe handoff point.

The rule remains: delete boilerplate, do not build a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
