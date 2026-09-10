# Development workflow

MaaPlus keeps inspection and diagnostics in the optional `maaplus[dev]` layer.

```bash
uv add "maaplus[dev]"
```

## First offline project

```bash
maaplus init my-game
cd my-game
uv sync
uv run python main.py
maaplus doctor
```

The scaffold includes a small fake Tasker and a fixture runner. Add a screenshot to `fixtures/`,
then replace the fake Tasker with the project's Maa objects when recognition resources are ready.
`bootstrap.py` is reserved for live setup, so the offline path never touches a device.

## Recognition-only inspection

`Inspector` calls only `post_recognition`; its result has no click, swipe, or controller method.

```python
from maaplus.dev import Inspector, TraceSession

with TraceSession() as trace:
    inspector = Inspector.from_maa(
        tasker=tasker,
        controller=controller,
        resource=resource,
        debug=trace.create_debug(),
        trace=trace,
    )
    result = inspector.inspect(UI.BATTLE, "fixtures/battle.png", label="battle")
    print(result.hit, result.box, result.annotated_path)
```

Array input requires an explicit channel order:

```python
result = inspector.inspect(UI.BATTLE, image, image_format="bgr")
```

Path input is loaded and converted to BGR. Inspection defaults to a 10-second cooperative wait
deadline; native work cannot be forcibly interrupted. `InspectionError` contains fixture path,
recognition type, job status, and trace path. Maa native raw/draw images are saved when available.

## Fixtures and assertions

`FixtureSet` reads images plus an optional `expected.json`:

```json
{
  "battle.png": {"hit": true, "box": [100, 200, 80, 40], "box_tolerance": 2},
  "loading.png": {"hit": false}
}
```

```python
results = inspector.inspect_set(UI.BATTLE, "fixtures", box_tolerance=1)
assert all(result.passed for result in results)
```

The default assertion checks `hit` and an optional `(x, y, width, height)` box. Per-fixture
`box_tolerance` overrides the run's tolerance. Projects can also call `assert_expected()` or add
ordinary Python assertions for custom fields.

## CLI inspection

```bash
maaplus inspect fixtures --locator ui:UI.BATTLE --factory offline:create_inspector --json report.json
```

References use `module:attribute`; nested attributes such as `demo.ui.explore:ExploreUI.BATTLE` are
supported. The factory returns an `Inspector` or a Tasker. Exit status is `0` for all passing
fixtures, `1` for assertion/recognition failures, and `2` for setup errors.

## Trace sessions and failure artifacts

```python
from maaplus import App
from maaplus.dev import TraceSession

with TraceSession(".maaplus/runs") as trace:
    with App.from_maa(
        tasker=tasker,
        controller=controller,
        resource=resource,
        debug=trace.create_debug(),
        trace=trace,
    ) as app:
        ...
```

Each session has a `run_id`, a separate `run.jsonl`, images, and failure directory. Recognition
events link directly to the debug PNG and image hash. Session debug writers keep the newest 200
images by default. On terminal failure, recent evidence is copied into the failure directory and
marked `retained` in the trace. Closing the session writes an image index; `close()` is idempotent,
and attached Maa sinks are removed automatically. Use `max_images=None` only for a deliberately
unbounded capture.

Terminal task failures produce `summary.md`, `summary.json`, and `traceback.txt`, with the task,
attempt count, error, trace path, and recent image evidence. `TaskHandle.last_execution.report_path`
points to the report when a `TraceSession` is active. `JsonlTrace` remains available for callers
that need manual append-file control.

Summarize a captured session from a terminal:

```bash
maaplus trace .maaplus/runs/<run-id>
```

## Task lifecycle

`TaskHandle.status` reports `PENDING`, `RUNNING`, `PAUSED`, `DONE`, `FAILED`, or `CANCELLED`.
`last_execution` contains the most recent terminal summary. Core memory retains only that summary;
the trace carries full history.

Periodic tasks pause after terminal failure. Call `handle.resume()` to restart with fresh state,
or explicitly set `continue_recurring=True` for a task that is safe to repeat after failure.
Task timeouts are cooperative and checked at tick boundaries.

## Read-only device diagnosis

```bash
maaplus doctor --resource resource
```

The doctor checks MaaFramework, NumPy, optional Pillow, resource existence, discovered ADB devices,
and their screenshot/input capabilities. It sends no device input. ADB examples accept `serial`
and require explicit selection when more than one device is available.

## Controller adapters and device discovery

`maaplus.dev` provides helpers around MaaFramework's native controllers:

- `find_adb_devices() -> list[DiscoveredDevice]`: Queries MaaFramework's native toolkit to discover connected emulators and ADB devices along with their optimal screencap and input methods.
- `create_adb_controller(serial=None, ...)`: Auto-connects to a discovered device or explicit serial with optimal settings pre-applied.
- `create_debug_controller`, `create_record_controller`, and `create_replay_controller`: Reuse MaaFramework's native development controllers. Controller replay covers controller operations and screenshots; project business code still owns its other side effects.

## UI Workbench dev tool

MaaPlus provides an interactive, single-HTML developer workbench (`tools/ui_workbench.html`)
to assist with UI layer creation, locator management, live device/emulator connection, visual
template cropping, and fixture backtesting.

### Launching the workbench

With the local backend bridge (recommended for live device control and MaaFramework recognition):

```bash
maaplus ui
# Or with explicit port / host:
maaplus ui --port 8080 --no-browser
# Or directly with Python:
uv run python tools/ui_workbench.py
```

### Standalone / Offline mode

The workbench is also a self-contained single HTML file (`tools/ui_workbench.html`). You can
double-click or open it directly in any modern browser (`file:///.../tools/ui_workbench.html`)
without running the backend:
- Paste (`Ctrl+V`) or drag-and-drop screenshots.
- Use interactive Pan & Zoom (wheel / space-drag).
- Probe pixel coordinates `(X, Y)` and exact color with the 9x9 pixel magnifier loupe.
- Select region of interest (ROI) and crop template images with one-click download.
- Manage UI classes and locators (`Template`, `OCR`, `FirstOf`, `AllOf`).
- Generate idiomatic MaaPlus Python UI definitions.

### Frontend Development & Rebuilding

The UI Workbench frontend is authored with **React 19**, **Tailwind CSS v4**, and **shadcn/ui** design patterns in `tools/frontend/`. It compiles into a single, zero-dependency offline bundle `tools/ui_workbench.html` using `vite-plugin-singlefile`:

```bash
# In tools/frontend
pnpm install   # or bun install
pnpm build     # or bun run build
```

The build automatically synchronizes and updates `tools/ui_workbench.html`.

