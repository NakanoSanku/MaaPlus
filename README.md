# MaaPlus

MaaPlus is a minimal code-first layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework).

MaaFramework keeps responsibility for recognition, resources, controllers, and native execution. MaaPlus only adds a small Python-side structure for locators, shared screenshots, simple match actions, and flow execution.

## Core API

The MVP intentionally keeps the public surface small:

- `Template` / `OCR` — describe how to find UI elements.
- `Match` — recognition result with `hit`, `box`, `score`, `detail`, and `click()`.
- `FlowContext` — shared screenshot plus `find()`.
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
    start = ctx.find(Login.START)
    if not start:
        return

    start.click()
    ctx.find(Login.CONFIRM).click()
```

A miss is simply false:

```python
match = ctx.find(Login.START)

if match:
    print(match.box, match.score)
```

`click()` returns `False` when the match missed or has no clickable box.

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

Consecutive finds reuse one screenshot:

```text
ctx.find(A) ─┐
ctx.find(B) ─┼─ same screenshot
ctx.find(C) ─┘
```

A successful action invalidates it:

```text
ctx.find(A).click()
        ↓
frame invalidated
        ↓
ctx.find(B) -> new screenshot
```

`ctx.refresh()` can force a new screenshot explicitly.

## Architecture

```text
Flow function
    ↓
FlowContext
    ↓
Locator → Match
    ↓
Runtime
    ↓
MaaFramework
```

The rule is simple: MaaPlus should delete boilerplate, not create a second automation framework.

## Tests

```bash
python -m unittest discover -s tests -v
```
