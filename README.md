# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework keeps responsibility for recognition, resources, controllers, and native execution. MaaPlus only adds a small Python-side structure for locators, shared screenshots, simple result actions, and flow execution.

## Core API

The MVP intentionally keeps the public surface small:

- `Template` / `OCR` — describe how to match UI elements.
- `MatchResult` — thin wrapper around MaaFramework `RecognitionDetail`, adding truthiness and `click()`.
- `FlowContext` — shared screenshot plus `match()` and gesture coordination.
- `Runtime` — thin MaaFramework adapter.
- `Runner` — binds the runtime and executes a plain Python flow function.

There is no `Page`, `BaseFlow`, `require()`, `wait()`, retry DSL, state machine, or plugin layer.

## Installation

This repository currently targets Python 3.14+ and MaaFramework 5.12.3+.

```bash
uv sync
```

## Basic usage

```python
from maaplus import FlowContext, OCR, Template


class Login:
    START = Template("login/start.png", threshold=0.85)
    CONFIRM = OCR("确认")


def login(ctx: FlowContext) -> None:
    start = ctx.match(Login.START)
    if not start:
        return

    start.click()
    ctx.match(Login.CONFIRM).click()
```

A miss is simply false. `hit` and `box` are the only common convenience properties:

```python
result = ctx.match(Login.START)

if result:
    print(result.box)
```

Algorithm-specific data is not copied into MaaPlus. Access the original MaaFramework recognition detail when needed:

```python
maa_detail = result.detail
best_result = maa_detail.best_result
raw_detail = maa_detail.raw_detail
```

For example, template score or OCR text can be read from `best_result` according to the MaaFramework recognition type.

## Click point resolver

`click()` uses the center of the matched box by default and holds for 50 ms:

```python
ctx.match(Login.START).click()
ctx.match(Login.START).click(duration=120)
```

A custom click algorithm is just a function from `MatchResult` to `(x, y)`:

```python
from random import randrange

from maaplus import MatchResult


def random_point(result: MatchResult) -> tuple[int, int]:
    x, y, width, height = result.box
    return (
        randrange(x, x + width),
        randrange(y, y + height),
    )


ctx.match(Login.START).click(random_point, duration=80)
```

The resolver receives the whole `MatchResult`, so it may also use `result.detail` for recognition-specific positioning. MaaPlus does not define a strategy class hierarchy; custom positioning stays ordinary Python.

`click()` returns `False` when recognition missed. With the default resolver it also returns `False` when no matched box exists.

## Runtime gestures

Gesture durations are milliseconds.

`Runtime.click(point, duration)` is defined as one continuous press:

```text
touch_down(point)
    ↓ hold for duration
touch_up()
```

`Runtime.swipe(points, duration)` follows the supplied path:

```text
touch_down(points[0])
    ↓
touch_move(points[1])
    ↓
touch_move(points[2])
    ↓
...
    ↓
touch_move(points[-1])
    ↓
touch_up()
```

The total duration is divided evenly across the `len(points) - 1` path intervals. A swipe requires at least two points.

Flows normally use `FlowContext.swipe()` so the shared screenshot is invalidated after the gesture:

```python
ctx.swipe(
    [(200, 800), (220, 650), (260, 500), (300, 350)],
    duration=400,
)
```

## Running a flow

Controller discovery and resource loading remain normal MaaFramework code:

```python
from maa.resource import Resource
from maa.tasker import Tasker
from maaplus import Runner

resource = Resource()
resource.post_bundle("./resource").wait()

runner = Runner.from_maa(
    tasker=Tasker(),
    controller=controller,
    resource=resource,
)

runner.run(login)
```

See `examples/basic_adb.py` for a complete ADB example.

## Shared frame semantics

Consecutive matches reuse one screenshot:

```text
ctx.match(A) ─┐
ctx.match(B) ─┼─ same screenshot
ctx.match(C) ─┘
```

A successful action invalidates it:

```text
ctx.match(A).click()
        ↓
frame invalidated
        ↓
ctx.match(B) -> new screenshot
```

`ctx.refresh()` can force a new screenshot explicitly.

## Architecture

```text
Flow function
    ↓
FlowContext.match() / swipe()
    ↓
Locator → MatchResult
    ↓
Runtime click/swipe
    ↓
MaaFramework touch events
```

The rule is simple: MaaPlus should delete boilerplate, not create a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
