from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy
from PIL import Image

from maaplus import App, CONTINUE, DONE, Runtime, Template
from maaplus.dev import Inspector, TraceSession


class _Job:
    def __init__(self, value):
        self.succeeded = True
        self._value = value

    def wait(self):
        return self

    def get(self):
        return self._value


class FixtureTasker:
    def post_recognition(self, reco_type, locator, image):
        height, width = image.shape[:2]
        hit = bool(image.max())
        detail = SimpleNamespace(
            hit=hit,
            box=(0, 0, width, height) if hit else None,
            raw_detail={"offline": True},
        )
        return _Job(SimpleNamespace(nodes=[SimpleNamespace(recognition=detail)]))


class FixtureController:
    def __init__(self, image):
        self.image = image

    def post_screencap(self):
        return _Job(self.image)

    def stop(self):
        pass


UI_READY = Template(template=["ready.png"])


def main() -> int:
    root = Path(__file__).resolve().parent
    output = root / ".maaplus"
    image = numpy.zeros((80, 120, 3), dtype=numpy.uint8)
    image[20:60, 30:90] = (80, 214, 255)  # a visible BGR marker
    fixture_path = output / "ready.png"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image[..., ::-1]).save(fixture_path)

    tasker = FixtureTasker()
    controller = FixtureController(image)
    with TraceSession(output / "runs") as trace:
        debug = trace.create_debug()
        inspection = Inspector(tasker, debug=debug, trace=trace).inspect(
            UI_READY,
            fixture_path,
            label="offline-ready",
        )
        print(f"inspection: hit={inspection.hit} box={inspection.box}")

        runtime = Runtime(
            tasker=tasker,
            controller=controller,
            debug=debug,
            trace=trace,
        )
        with App.from_runtime(runtime) as app:
            handle = app.task("offline-ready", lambda tick: DONE if tick.match(UI_READY) else CONTINUE)
            handle.submit()
            app.run()
            print(f"task: status={handle.status.name} result={handle.last_execution.result.name}")
        print(f"trace: {trace.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
