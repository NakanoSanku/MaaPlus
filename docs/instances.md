# Multiple device instances

`InstanceManager` manages one independent `App` per device. It does not share a controller,
runtime, navigator, guard, trace, or debug writer between instances.

```python
from maaplus import App, InstanceManager
from maaplus.dev import create_adb_controller


def build_app(config):
    # Construct every Maa object and every stateful application object here.
    # Use config.device when creating the ADB controller.
    return App.from_maa(
        tasker=create_tasker(),
        controller=create_adb_controller(serial=config.device),
        resource=load_resource(),
        navigator=create_navigator(),
        debug=create_debug(config.debug_dir),
        trace=create_trace(config.trace_dir),
    )


with InstanceManager(build_app, root_dir=".maaplus/instances", max_workers=2) as fleet:
    fleet.create("phone-a", "emulator-5554")
    fleet.create("phone-b", "emulator-5556")

    for app in (fleet.get("phone-a"), fleet.get("phone-b")):
        app.task("daily", daily_handler).submit()

    futures = fleet.start_all(interval=100)
    for future in futures.values():
        future.result()
```

The factory receives an immutable `InstanceConfig` with `name`, `device`, `directory`,
`debug_dir`, and `trace_dir`. The manager rejects duplicate names and duplicate device identifiers,
so two instances cannot accidentally control the same device.

For a batch, pass `{instance_name: device_id}` to `create_many()`. A plain iterable of device IDs is
also accepted; provide `name=lambda device: ...` when its generated names are not suitable.

MaaFramework process-wide options should be configured once before creating the fleet. Per-instance
`Debug` and `TraceSession` objects can still use the directories from `InstanceConfig`.

The first backend is a bounded thread executor. `start()` returns a `Future`; `start_all()` returns
one future per instance. `pause`, `resume`, `stop`, and their `*_all` counterparts are cooperative,
matching the existing `App` lifecycle. A run-loop exception puts the instance in `FAILED` and is
re-raised by `wait()`; task failures remain observable through `TaskHandle.failure` and make the
snapshot health `InstanceHealth.DEGRADED` (with `failed_tasks` and `current_task` available for
monitoring).

`remove()` and `close()` call `App.close()` after the run worker has stopped. This closes attached
trace sessions and any runtime resources that expose a `close()` method. A manager-wide device lease
also prevents two managers in the same process from controlling the same device concurrently; the
lease is released only after the instance cleanup finishes. Calling `stop()` or `close()` from an
instance's own task is safe and does not wait on that worker.

Use one `App` with multiple tasks when work targets the same device. Registering two apps for the
same device is rejected because the framework does not arbitrate competing input streams.

The manager currently runs in one process. Process-level isolation is intentionally a separate
backend because MaaFramework objects and Python callbacks are not generally transferable through a
process pool.
