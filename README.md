# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework keeps responsibility for recognition, resources, controllers, and native execution. MaaPlus only adds a small Python-side structure for locators, match results, gestures, and flow execution.

## Core API

- `Template` / `OCR` — describe how to match UI elements.
- `MatchResult` — thin wrapper around MaaFramework `RecognitionDetail`, adding truthiness and `click()`.
- `Runtime` — screenshot, match, click, and swipe primitives over MaaFramework.
- `Runner` — captures one screenshot and executes a plain Python flow function against it.

There is no `Page`, `FlowContext`, `Session`, `BaseFlow`, `require()`, `wait()`, retry DSL, state machine, or plugin layer.

## Installation

This repository currently targets Python 3.14+ and MaaFramework 5.12.3+.

```bash
uv sync
```

## Flow semantics

One `Runner.run(flow)` call is one decision tick over one fixed screenshot.

```text
runner.run(flow)
      ↓
Runtime.screenshot()   # exactly once
      ↓
flow(runtime, image)
      ↓
all match(..., image) calls use that same image
```

Clicks and swipes do not replace the current image. To observe the UI after an action, run the flow again; the next `Runner.run(flow)` captures a fresh screenshot.

This means flows are best written as one-snapshot state decisions:

```python
from maaplus import OCR, Runtime, Template


class Login:
    START = Template("login/start.png", threshold=0.85)
    CLOSE = OCR(("关闭", "跳过"))
    CONFIRM = OCR("确认")


def login(runtime: Runtime, image) -> None:
    close = runtime.match(Login.CLOSE, image)
    if close:
        close.click()
        return

    start = runtime.match(Login.START, image)
    if start:
        start.click()
        return

    confirm = runtime.match(Login.CONFIRM, image)
    if confirm:
        confirm.click()
```

Call `runner.run(login)` again when the next screen state should be evaluated.

## MatchResult

A miss is simply false. `hit` and `box` are the common convenience properties:

```python
result = runtime.match(Login.START, image)

if result:
    print(result.box)
```

Algorithm-specific data is not copied into MaaPlus. Access the original MaaFramework recognition detail when needed:

```python
maa_detail = result.detail
best_result = maa_detail.best_result
raw_detail = maa_detail.raw_detail
```

## Click resolver

`MatchResult.click()` uses the center of the matched box by default and holds for 50 ms:

```python
result.click()
result.click(duration=120)
```

A custom click position is just a function from `MatchResult` to `(x, y)`:

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

`Runtime.click(point, duration)` is one continuous press:

```text
touch_down(point)
    ↓ hold for duration
touch_up()
```

```python
runtime.click((500, 300), duration=100)
```

`Runtime.swipe(points, duration)` follows the supplied path from the first point to the last:

```text
touch_down(points[0])
    ↓
touch_move(points[1])
    ↓
touch_move(points[2])
    ↓
...
    ↓
touch_up()
```

The total duration is divided evenly across the `len(points) - 1` path intervals.

```python
runtime.swipe(
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

## Architecture

```text
Business flow(runtime, image)
          ↑
Runner -- captures one image per run
          ↓
       Runtime
   screenshot / match
    click / swipe
          ↓
    MaaFramework
```

`Runtime` has no screenshot cache. The image used by a flow is explicit and immutable for that run.

The rule is simple: MaaPlus should delete boilerplate, not create a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
