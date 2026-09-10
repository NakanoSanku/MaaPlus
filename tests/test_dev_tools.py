from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock

import numpy

from maa.pipeline import JRecognitionType
from maaplus import DONE, Scheduler, Task, Template
from maaplus.dev import FixtureSet, Inspector, JsonlTrace, TaskerTraceSink, TraceSession, assert_expected


class DevToolsTests(unittest.TestCase):
    def test_fixture_set_discovers_images_and_expected_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "b.png").write_bytes(b"placeholder")
            (root / "a.jpg").write_bytes(b"placeholder")
            (root / "ignore.txt").write_text("ignore", encoding="utf-8")
            (root / "expected.json").write_text(
                json.dumps({"a.jpg": {"hit": True}}, ensure_ascii=False), encoding="utf-8"
            )

            fixtures = list(FixtureSet(root))

        self.assertEqual([fixture.path.name for fixture in fixtures], ["a.jpg", "b.png"])
        self.assertEqual(fixtures[0].expected, {"hit": True})

    def test_inspector_only_posts_recognition_and_writes_trace(self) -> None:
        image = numpy.zeros((20, 30, 3), dtype=numpy.uint8)
        detail = SimpleNamespace(
            hit=True,
            box=(4, 5, 8, 6),
            raw_detail={"score": 0.93},
            raw_image=image.copy(),
            draw_images=[image.copy()],
        )
        job = Mock(succeeded=True)
        job.wait.return_value = job
        job.get.return_value = SimpleNamespace(nodes=[SimpleNamespace(recognition=detail)])
        tasker = Mock()
        tasker.post_recognition.return_value = job

        with tempfile.TemporaryDirectory() as directory:
            trace = JsonlTrace(Path(directory) / "run.jsonl")
            result = Inspector(tasker, output_dir=Path(directory) / "images", trace=trace).inspect(
                Template(template=["button.png"]), image, label="button", image_format="bgr"
            )
            trace.close()
            events = [json.loads(line) for line in (Path(directory) / "run.jsonl").read_text().splitlines()]

        tasker.post_recognition.assert_called_once_with(JRecognitionType.TemplateMatch, ANY, image)
        self.assertTrue(result.hit)
        self.assertEqual(result.box, (4, 5, 8, 6))
        self.assertEqual(result.raw_detail, {"score": 0.93})
        self.assertIsNotNone(result.annotated_path)
        self.assertIsNotNone(result.raw_path)
        self.assertEqual(len(result.draw_paths), 1)
        self.assertEqual(events[0]["event"], "inspection")
        self.assertEqual(events[0]["label"], "button")

    def test_tasker_trace_sink_writes_raw_notification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            trace = JsonlTrace(Path(directory) / "maa.jsonl")
            sink = TaskerTraceSink(trace).sink
            sink.on_raw_notification(None, "Tasker.Task.Starting", {"task_id": 7})
            trace.close()
            event = json.loads((Path(directory) / "maa.jsonl").read_text().strip())

        self.assertEqual(event["event"], "maa.notification")
        self.assertEqual(event["details"]["task_id"], 7)

    def test_scheduler_trace_captures_task_lifecycle(self) -> None:
        class Runtime:
            def screenshot(self):
                return numpy.zeros((2, 2, 3), dtype=numpy.uint8)

            def stop(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.jsonl"
            trace = JsonlTrace(path)
            scheduler = Scheduler(Runtime(), trace=trace)
            task = Task("probe", lambda tick: DONE)
            scheduler.submit(task)
            scheduler.run()
            trace.close()
            events = [json.loads(line)["event"] for line in path.read_text().splitlines()]

        self.assertEqual(events, ["task.requested", "task.tick"])

    def test_trace_session_isolates_runs_and_is_idempotently_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session = TraceSession(directory, run_id="run-1")
            session.write("test", value=1)
            session.close()
            session.close()
            record = json.loads((Path(directory) / "run-1" / "run.jsonl").read_text().strip())

        self.assertEqual(record["run_id"], "run-1")
        self.assertEqual(record["sequence"], 1)

    def test_fixture_default_assertion_supports_box_tolerance(self) -> None:
        result = SimpleNamespace(hit=True, box=(10, 20, 30, 40))
        assert_expected(result, {"hit": True, "box": [11, 19, 30, 40]}, box_tolerance=1)

    def test_trace_session_writes_failure_bundle(self) -> None:
        class Runtime:
            def screenshot(self):
                return numpy.zeros((2, 2, 3), dtype=numpy.uint8)

            def stop(self):
                pass

        from maaplus import Scheduler, Task

        with tempfile.TemporaryDirectory() as directory:
            with TraceSession(directory) as trace:
                scheduler = Scheduler(Runtime(), trace=trace)
                task = Task("broken", lambda tick: (_ for _ in ()).throw(ValueError("bad")))
                scheduler.submit(task)
                scheduler.run()
                report = scheduler.last_execution(task).report_path
                self.assertTrue(report.is_file())
                self.assertTrue((report.parent / "summary.json").is_file())
                self.assertTrue((report.parent / "traceback.txt").is_file())


if __name__ == "__main__":
    unittest.main()
