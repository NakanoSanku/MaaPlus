# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework owns recognition, resources, controllers, and native execution. MaaPlus adds a small synchronous runtime, `MatchResult` action sugar, and a snapshot-driven priority scheduler.

## Core API

- `Template` — alias of MaaFramework `JTemplateMatch`.
- `OCR` — alias of MaaFramework `JOCR`.
- `MatchResult` — thin wrapper around MaaFramework `RecognitionDetail`, adding truthiness and `click()`.
- `Runtime` — screenshot, recognition, click, and swipe primitives.
- `Task` — a named flow plus a priority.
- `Scheduler` — priority selection, timed/recurring triggers, cooperative preemption, pause/resume, and lifecycle.

There is no MaaPlus recognition schema, page-object layer, retry DSL, task graph, worker pool, cron parser, or custom state machine.

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
flow(runtime, image) -> bool
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
```

The flow returns:

- `True` — this task still has work and may need another tick later.
- `False` — this execution is complete.

Actions never replace the image inside the current tick. New UI state is evaluated only on a later tick with a fresh screenshot.

```python
from maaplus import OCR, Runtime, Template


class Login:
    START = Template(template=["login/start.png"], threshold=[0.85])
    CLOSE = OCR(expected=["关闭", "跳过"])
    CONFIRM = OCR(expected=["确认"])


def login(runtime: Runtime, image) -> bool:
    close = runtime.match(Login.CLOSE, image)
    if close:
        close.click()
        return True

    start = runtime.match(Login.START, image)
    if start:
        start.click()
        return True

    confirm = runtime.match(Login.CONFIRM, image)
    if confirm:
        confirm.click()

    return False
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

## Cooperative preemption

Preemption happens **only between ticks**. MaaPlus never interrupts a recognition call, click, swipe, or flow function in the middle.

```text
normal tick #1
      ↓
high-priority timed task becomes due
      ↓
current tick finishes
      ↓
normal is suspended
      ↓
timed tick #1
      ↓
timed completes
      ↓
normal resumes with a fresh screenshot
      ↓
normal tick #2
```

Only a **strictly higher** priority task preempts the current task. Equal priority tasks wait instead of causing task switching.

Suspended tasks use stack semantics, so nested preemption naturally unwinds:

```text
A(priority 10)
  ↓ preempted by
B(priority 100)
  ↓ preempted by
C(priority 200)
  ↓ C done
B resumes
  ↓ B done
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

`interval` is milliseconds between consecutive ticks of the **same current task**. A newly selected or preempting task runs immediately.

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

## Task-local state

The scheduler does not understand business state. If a task needs Python state across ticks or preemption, use a callable object:

```python
class DailyFlow:
    def __init__(self) -> None:
        self.step = 0

    def __call__(self, runtime: Runtime, image) -> bool:
        # self.step survives normal ticks and scheduler preemption.
        ...


daily = Task("daily", DailyFlow(), priority=10)
```

This keeps task business state inside the task instead of teaching the scheduler about application-specific states.

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
                          Runtime
                    match / click / swipe
                             ↓
                        MaaFramework
```

`Task` owns **what**. Trigger methods own **when**. Priority owns **which task runs first**. Preemption is only the consequence of those priority decisions.

The rule remains: delete boilerplate, do not build a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
