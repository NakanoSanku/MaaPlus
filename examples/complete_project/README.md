# Complete project example

This example shows the recommended MaaPlus application structure for a project with multiple UI contexts, long-running work, a higher-priority recurring task, and runtime-level interaction defaults.

The scenario is intentionally game-like:

- `explore` runs as the normal task.
- battle UI is private to `ExploreHandler`, so it returns `CONTINUE` while fighting.
- a stable explore screen is a handoff-safe point, so it returns `YIELD`.
- `draw` is a higher-priority recurring task.
- `App` restores `Scene.DRAW` before `DrawHandler` runs and again when a suspended task resumes.
- when drawing finishes, the suspended explore task resumes and `App` restores `Scene.EXPLORE` before calling `ExploreHandler` again.
- after a task reaches its target scene, its handler owns that scene until it yields; Navigator does not need to recognize every private battle or result state.
- `bootstrap.py` configures randomized point selection, press duration, UI settle delays, action spacing, and path interpolation once for the whole application.

## Structure

```text
complete_project/
├── main.py
├── README.md
├── CUSTOM_RECOGNITION.md
├── demo/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── custom_recognition.py
│   ├── tasks.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── home.py
│   │   ├── explore.py
│   │   └── draw.py
│   ├── navigation/
│   │   ├── __init__.py
│   │   ├── scene.py
│   │   └── navigator.py
│   └── handlers/
│       ├── __init__.py
│       ├── explore.py
│       └── draw.py
├── resource/
│   └── README.md
└── tests/
    └── test_custom_recognition.py
```

The layering is deliberate:

```text
main
  ↓
bootstrap
  ↓
tasks
  ↓
App.task(context=...)
  ↓
Navigator + Task Handler
  ↓
UI definitions
  ↓
MaaPlus / MaaFramework
```

- `ui/` only describes recognition parameters.
- `navigation/` only detects and restores UI contexts.
- `handlers/` owns business decisions and task-local state.
- `tasks.py` owns task registration, priorities, and trigger policy.
- `bootstrap.py` owns MaaFramework, `InteractionConfig`, and App construction.
- `bootstrap.py` also enables opt-in bounding-box snapshots under `.debug/`.
- `custom_recognition.py` owns custom recognition algorithms and their registration names.
- `main.py` only starts the application.

A task handler is simply a callable with the standard MaaPlus signature:

```python
def handler(tick):
    ...
    return CONTINUE  # or YIELD / DONE
```

Stateful handlers can be callable objects, which lets business progress survive multiple ticks and scheduler preemption.

## Interaction defaults

`demo/bootstrap.py` centralizes game-input behavior while reusing action-independent geometry strategies:

```python
INTERACTION = InteractionConfig(
    click=ClickConfig(
        resolver=point.random(padding=0.15),
        duration=timing.random(40, 90),
        pre_delay=timing.random(80, 150),
        post_delay=timing.random(250, 450),
    ),
    swipe=SwipeConfig(
        duration=timing.random(300, 500),
        post_delay=timing.random(250, 400),
        interpolation=path.ease_in_out(samples=20),
    ),
    action_interval=timing.random(60, 120),
)
```

`point.*` strategies are general `Rect -> Point` helpers and are not limited to click targets. For example, the same resolver can choose randomized swipe start/end points before calling `tick.swipe(...)`.

Normal handlers still just call `result.click()` or `tick.swipe(...)`. A particular action can override a default when needed, for example `result.click(duration=1200)` or `result.click(pre_delay=0)`.

Keep interaction delays short. Multi-second waits for loading, network responses, or battle state changes belong in task-handler state recognition rather than long sleeps, so the scheduler can keep reaching explicit `YIELD` safe points.

## Debug snapshots

The example enables `Debug` in `demo/bootstrap.py` and keeps the newest 200 annotated screenshots
under `.debug/`. Every `tick.match()` records its ROI and result box; `result.debug_path` can be
printed when investigating a specific branch. A handler can mark a one-off area with
`tick.draw((x, y, width, height), label="...")`.

Install the optional image dependency before running the example:

```bash
uv sync --extra debug
```

## Custom multi-point color recognition

The example registers a pure NumPy recognizer while loading the MaaFramework `Resource`:

```python
resource.register_custom_recognition(
    "MultiPointColor",
    MultiPointColorRecognition(
        points=(
            ColorPoint((0, 0), (255, 214, 80)),
            ColorPoint((12, 0), (255, 214, 80)),
            ColorPoint((0, 12), (255, 214, 80)),
        ),
        tolerance=12,
    ),
)
```

The UI definition refers to that registration by name:

```python
from maa.pipeline import JCustomRecognition

BATTLE = JCustomRecognition(
    custom_recognition="MultiPointColor",
    roi=(0, 0, 0, 0),
    custom_recognition_param={"tolerance": 18},
)
```

`ColorPoint` values are RGB. MaaFramework supplies screenshots as BGR, and the example performs the
conversion inside the recognizer. The first point is the anchor; all points must match within the
configured per-channel tolerance. A successful result returns a bounding box, so existing
`tick.match(...).click()` code works unchanged.

For a different custom algorithm, inherit `maa.custom_recognition.CustomRecognition`, implement
`analyze(context, argv)`, return `CustomRecognition.AnalyzeResult(box=..., detail=...)`, and pass
the instance to `resource.register_custom_recognition()`. The callback receives `argv.image`,
`argv.roi`, and the JSON string supplied by `custom_recognition_param`.

## Run

The recognition resources in this example are placeholders. Add templates matching the paths listed in `resource/README.md`, then run from the repository root:

```bash
uv run --extra debug python examples/complete_project/main.py
```

For development, change the draw trigger in `demo/tasks.py` from hourly recurrence to something like:

```python
draw.after(10_000)
```

so the preemption and context restore path can be observed quickly.
