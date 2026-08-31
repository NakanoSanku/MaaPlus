# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework keeps responsibility for recognition, resources, controllers, and native execution. MaaPlus only adds a small Python-side runtime, match-result sugar, gesture helpers, and snapshot-driven flow execution.

## Core API

- `Template` — alias of MaaFramework `JTemplateMatch`.
- `OCR` — alias of MaaFramework `JOCR`.
- `MatchResult` — thin wrapper around MaaFramework `RecognitionDetail`, adding truthiness and `click()`.
- `Runtime` — screenshot, match, click, and swipe primitives over MaaFramework.
- `Runner` — owns flow ticks, the continuous run loop, pause/resume/stop state, and MaaFramework lifecycle.

There is no MaaPlus locator schema. `Runtime.match()` accepts MaaFramework `JRecognitionParam` directly, so MaaFramework recognition features are not copied or restricted by MaaPlus.

There is also no `Page`, `FlowContext`, `Session`, `BaseFlow`, `require()`, `wait()`, retry DSL, state machine, or plugin layer.

## Installation

This repository currently targets Python 3.14+ and MaaFramework 5.12.3+.

```bash
uv sync
```

## Recognition parameters

`Template` and `OCR` are only friendly aliases; they are the MaaFramework classes themselves:

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

Because MaaPlus does not rebuild these dataclasses, MaaFramework fields such as `roi_offset`, `replace`, and `color_filter` stay available automatically.

`Runtime.match()` accepts the complete MaaFramework `JRecognitionParam` family. Less-common recognition types can be imported directly from MaaFramework:

```python
from maa.pipeline import JFeatureMatch

feature = JFeatureMatch(template=["feature.png"])
result = runtime.match(feature, image)
```

## Flow semantics

A flow is an ordinary Python callable:

```python
flow(runtime, image) -> bool
```

One **tick** always means one fresh screenshot and one flow call:

```text
Runner.tick(flow)
      ↓
Runtime.screenshot()   # exactly once
      ↓
flow(runtime, image)
      ↓
all match(..., image) calls use that same image
```

Actions do not replace the image inside the current tick. The flow returns:

- `True` — run another tick with a fresh screenshot.
- `False` — the flow is complete.

Example:

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

    return False
```

The flow itself still owns all business decisions. The boolean only tells `Runner` whether another screenshot-driven tick is needed.

## Runner

Use `tick()` when the caller wants exactly one snapshot decision:

```python
continue_running = runner.tick(login)
```

Use `run()` when `Runner` should keep producing fresh ticks until the flow returns `False` or `stop()` is called:

```python
runner.run(login)
```

Execution looks like:

```text
run(flow)
   ↓
 screenshot #1 → flow → True
   ↓
 screenshot #2 → flow → True
   ↓
 screenshot #3 → flow → False
   ↓
 done
```

An optional tick interval is expressed in milliseconds:

```python
runner.run(login, interval=100)
```

### Pause and resume

`pause()` pauses the continuous `run()` loop before the next tick:

```python
runner.pause()
runner.resume()
```

Pause never interrupts the current tick. If a pause is requested while the flow is still matching or performing an action, that tick finishes normally. Runner then waits before capturing the next screenshot:

```text
tick #12
screenshot
   ↓
flow(runtime, image)
   │
   │ pause()
   ↓
current tick finishes
   ↓
PAUSED              # no new screenshot
   │
   │ resume()
   ↓
next tick
fresh screenshot
```

`Runner.running` stays `True` while paused because the run lifecycle is still active. `Runner.paused` reports whether that lifecycle is currently paused.

Calling `pause()` or `resume()` while Runner is idle is a no-op. `tick()` remains an explicit one-shot operation and is not controlled by the pause flag.

If a pause occurs while Runner is waiting for `interval`, the interval is restarted in full after `resume()`. This keeps timing semantics simple and avoids maintaining partial interval state.

### Stop and lifecycle

`Runner.stop()` requests the loop to stop and also forwards stop to the MaaFramework runtime. It wakes both paused waits and interval waits immediately, so a paused Runner can always be stopped cleanly.

The lifecycle states are intentionally simple:

```text
IDLE
  │ run()
  ▼
RUNNING ── pause() ──→ PAUSED
  ▲                     │
  └────── resume() ─────┘

RUNNING / PAUSED ── stop() or flow=False ──→ IDLE
```

Re-entering `run()` while it is already running raises `RuntimeError`.

Runner also supports context-manager cleanup:

```python
with Runner.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
) as runner:
    runner.run(login, interval=100)
```

Runner deliberately does not understand UI states, retries, transitions, or task graphs. It only owns the tick/run lifecycle.

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

## MaaFramework setup

Controller discovery and resource loading remain normal MaaFramework code. `Runner.from_maa()` only owns the final composition/bind step:

```python
from maa.resource import Resource
from maa.tasker import Tasker
from maaplus import Runner

resource = Resource()
resource.post_bundle("./resource").wait()

with Runner.from_maa(
    tasker=Tasker(),
    controller=controller,
    resource=resource,
) as runner:
    runner.run(login)
```

See `examples/basic_adb.py` for a complete ADB example.

## Architecture

```text
                    Runner
       tick / run / pause / resume / stop
                       │
             fresh screenshot per tick
                       ↓
          Business flow(runtime, image)
                       │
                 True / False
                       │
              ┌────────┴────────┐
              │                 │
          next tick            done

                    Runtime
              match / click / swipe
                       │
                       ↓
                  MaaFramework
```

Recognition descriptions are MaaFramework objects, not MaaPlus copies:

```text
JTemplateMatch / JOCR / other JRecognitionParam
                    ↓
              Runtime.match()
                    ↓
              MaaFramework
```

The rule is simple: MaaPlus should delete boilerplate, not create a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
