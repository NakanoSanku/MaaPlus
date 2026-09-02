# Logging

MaaPlus uses Python's standard `logging` package for observability. The library emits records under the `maaplus` namespace but never calls `logging.basicConfig()` and never installs handlers, so the application remains responsible for output format, destination, and verbosity.

## Namespaces

```text
maaplus.app
maaplus.scheduler
maaplus.routing
maaplus.runtime
maaplus.runtime.recognition
maaplus.runtime.controller
```

The intended levels are:

- `INFO` — scheduler lifecycle, triggers, task start/completion, preemption/resume, tasker stop.
- `DEBUG` — task-handler result and duration, screenshot duration, recognition details, resolved interaction timing and gestures, routing state, task registration and coalescing.
- `ERROR` — recognition/controller failures, invalid handler results, and task execution failures.

## Application configuration

A normal application can keep the root logger at `INFO`:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
```

For framework debugging, enable the MaaPlus namespace without turning every dependency to `DEBUG`:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
logging.getLogger("maaplus").setLevel(logging.DEBUG)
```

This exposes a chain similar to:

```text
INFO  maaplus.scheduler task started task=explore priority=10
DEBUG maaplus.runtime.recognition recognition type=TemplateMatch ... hit=True ...
DEBUG maaplus.runtime.controller click point=(...) duration_ms=67 pre_delay_ms=113 post_delay_ms=328
DEBUG maaplus.scheduler handler result task=explore result=YIELD handler_ms=... tick_ms=...
INFO  maaplus.scheduler task preempted task=explore priority=10 by=draw priority=100
DEBUG maaplus.routing context pending target=<Scene.DRAW: ...>
INFO  maaplus.scheduler task completed task=draw
INFO  maaplus.scheduler task resumed task=explore priority=10
```

MaaPlus deliberately does not add an event bus, custom log sink, or logging configuration DSL. Applications that need files, JSON, rotation, or GUI log capture can use normal Python logging handlers.
