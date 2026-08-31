# MaaPlus

MaaPlus is a small code-first enhancement layer on top of [MaaFramework](https://github.com/MaaXYZ/MaaFramework). It keeps MaaFramework responsible for recognition, controller, resource, and native execution, while making Python business flows easier to structure and test.

## MVP scope

The first MVP intentionally stays small:

- `Template` / `OCR`: immutable locator descriptions; no screenshots or actions inside locators.
- `FlowContext`: one shared screenshot for consecutive recognitions.
- `MatchResult` / `BoundMatch`: pure result data plus optional chainable actions.
- `Runtime`: thin synchronous wrapper over MaaFramework direct recognition and controller APIs.
- `Flow`: business decisions and action order only.
- `Runner`: flow execution boundary and MaaFramework binding helper.

A successful action invalidates the shared frame. The next `find()` captures a fresh screenshot automatically.

## Installation

This repository currently targets Python 3.14+ and MaaFramework 5.12.3+.

```bash
uv sync
```

## Basic usage

Define locators without business behavior:

```python
from maaplus import OCR, Template


class Login:
    START = Template("login/start.png", threshold=0.85)
    CONFIRM = OCR("确认")
```

Write a flow using the shared context:

```python
from maaplus import Flow, FlowContext


class LoginFlow(Flow):
    def run(self, ctx: FlowContext) -> None:
        ctx.find(Login.START).require().click()
        ctx.find(Login.CONFIRM).click()  # optional: returns False when not found
```

Create and connect your MaaFramework `Controller`, load your `Resource`, then hand them to MaaPlus:

```python
from maa.tasker import Tasker
from maaplus import Runner

# controller = ...                       # choose ADB / Win32 / custom controller
# controller.post_connection().wait()
# resource = Resource()
# resource.post_bundle("./resource").wait()

tasker = Tasker()
runner = Runner.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
)
runner.run(LoginFlow())
```

Controller discovery/creation and resource loading remain explicit MaaFramework concerns in the MVP because their configuration is environment-specific.

## Frame semantics

```text
ctx.find(A) ─┐
ctx.find(B) ─┼─ use the same screenshot
ctx.find(C) ─┘

ctx.find(A).click()
        │
        └─ invalidate cached screenshot

ctx.find(B)
        └─ capture a new screenshot
```

Use `ctx.refresh()` to force a new frame immediately, or `ctx.invalidate()` to mark the current frame stale.

## Design boundary

```text
Flow            business decisions
  ↓
FlowContext     shared frame + action coordination
  ↓
Locator/Result  recognition description + result data
  ↓
Runtime         MaaFramework adapter
  ↓
MaaFramework    Resource / Tasker / Controller / Recognition
```

MaaPlus should remain a thin layer. New MaaFramework capabilities should normally be exposed through small adapters rather than reimplemented.

## Tests

The core flow behavior can be tested without loading MaaFramework native libraries:

```bash
python -m unittest discover -s tests -v
```
