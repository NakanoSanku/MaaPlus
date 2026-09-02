# Complete project example

This example shows the recommended MaaPlus application structure for a project with multiple UI contexts, long-running work, a higher-priority recurring task, and runtime-level interaction defaults.

The scenario is intentionally game-like:

- `explore` runs as the normal task.
- battle UI is private to `ExploreHandler`, so it returns `CONTINUE` while fighting.
- a stable explore screen is a handoff-safe point, so it returns `YIELD`.
- `draw` is a higher-priority recurring task.
- `App` restores `Scene.DRAW` before `DrawHandler` runs.
- when drawing finishes, the suspended explore task resumes and `App` restores `Scene.EXPLORE` before calling `ExploreHandler` again.
- `bootstrap.py` configures randomized click positions, press duration, UI settle delays, action spacing, and swipe interpolation once for the whole application.

## Structure

```text
complete_project/
├── main.py
├── README.md
├── demo/
│   ├── __init__.py
│   ├── bootstrap.py
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
└── resource/
    └── README.md
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
- `main.py` only starts the application.

A task handler is simply a callable with the standard MaaPlus signature:

```python
def handler(tick):
    ...
    return CONTINUE  # or YIELD / DONE
```

Stateful handlers can be callable objects, which lets business progress survive multiple ticks and scheduler preemption.

## Interaction defaults

`demo/bootstrap.py` centralizes game-input behavior:

```python
INTERACTION = InteractionConfig(
    click=ClickConfig(
        resolver=click.random(padding=0.15),
        duration=timing.random(40, 90),
        pre_delay=timing.random(80, 150),
        post_delay=timing.random(250, 450),
    ),
    swipe=SwipeConfig(
        duration=timing.random(300, 500),
        post_delay=timing.random(250, 400),
        interpolation=swipe.ease_in_out(samples=20),
    ),
    action_interval=timing.random(60, 120),
)
```

Normal handlers still just call `result.click()` or `tick.swipe(...)`. A particular action can override a default when needed, for example `result.click(duration=1200)` or `result.click(pre_delay=0)`.

Keep interaction delays short. Multi-second waits for loading, network responses, or battle state changes belong in task-handler state recognition rather than long sleeps, so the scheduler can keep reaching explicit `YIELD` safe points.

## Run

The recognition resources in this example are placeholders. Add templates matching the paths listed in `resource/README.md`, then run from the repository root:

```bash
python examples/complete_project/main.py
```

For development, change the draw trigger in `demo/tasks.py` from hourly recurrence to something like:

```python
draw.after(10_000)
```

so the preemption and context restore path can be observed quickly.
