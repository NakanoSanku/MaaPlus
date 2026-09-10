from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy

try:
    from PIL import Image
except ImportError:  # Optional ``maaplus[debug]`` dependency is absent.
    Image = None  # type: ignore[assignment]

from maaplus import Debug, Runtime, Template, Tick
from maaplus.debug import _static_roi


@unittest.skipIf(Image is None, "Pillow extra is not installed")
class DebugTests(unittest.TestCase):
    def test_draw_preserves_source_and_writes_metadata(self) -> None:
        image = numpy.zeros((20, 30, 3), dtype=numpy.uint8)
        original = image.copy()
        with tempfile.TemporaryDirectory() as directory:
            path = Debug(directory).draw(image, (2, 3, 5, 4), label="battle")
            self.assertTrue(path.exists())
            self.assertTrue(numpy.array_equal(image, original))
            with Image.open(path) as rendered:
                payload = json.loads(rendered.info["maaplus"])
                self.assertEqual(rendered.size, (480, 84))
                self.assertEqual(payload["image_size"], [30, 20])
                self.assertEqual(payload["boxes"][0]["box"], [2, 3, 5, 4])

    def test_retention_keeps_newest_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            debug = Debug(directory, max_images=2)
            for _ in range(3):
                debug.draw(numpy.zeros((4, 4, 3), dtype=numpy.uint8))
            self.assertEqual(len(list(Path(directory).glob("maaplus-*.png"))), 2)

    def test_tick_draw_is_noop_when_disabled(self) -> None:
        runtime = Runtime(tasker=object(), controller=object())
        self.assertIsNone(Tick(runtime, numpy.zeros((4, 4, 3), dtype=numpy.uint8)).draw((0, 0, 2, 2)))

    def test_runtime_match_attaches_debug_path_without_mutating_image(self) -> None:
        image = numpy.zeros((20, 30, 3), dtype=numpy.uint8)
        detail = SimpleNamespace(hit=True, box=(4, 5, 8, 6))
        job = Mock(succeeded=True)
        job.wait.return_value = job
        job.get.return_value = SimpleNamespace(nodes=[SimpleNamespace(recognition=detail)])
        tasker = Mock()
        tasker.post_recognition.return_value = job
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(
                tasker=tasker, controller=object(), debug=Debug(directory)
            )
            result = runtime.match(Template(template=["button.png"]), image)
            self.assertTrue(result.hit)
            self.assertIsNotNone(result.debug_path)
            self.assertTrue(result.debug_path.is_file())
            self.assertTrue(numpy.array_equal(image, numpy.zeros_like(image)))

    def test_runtime_trace_links_debug_path_and_image_hash(self) -> None:
        image = numpy.zeros((4, 4, 3), dtype=numpy.uint8)
        detail = SimpleNamespace(hit=False, box=None)
        job = Mock(succeeded=True)
        job.wait.return_value = job
        job.get.return_value = SimpleNamespace(nodes=[SimpleNamespace(recognition=detail)])
        tasker = Mock()
        tasker.post_recognition.return_value = job
        trace = Mock()
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(tasker=tasker, controller=object(), debug=Debug(directory), trace=trace)
            result = runtime.match(Template(template=["button.png"]), image)

        event_name = trace.write.call_args.args[0]
        event = trace.write.call_args.kwargs
        self.assertEqual(event_name, "recognition")
        self.assertEqual(event["debug_path"], result.debug_path)
        self.assertTrue(event["image_sha256"])

    def test_static_roi_follows_maa_zero_negative_and_offset_rules(self) -> None:
        self.assertEqual(_static_roi(Template(template=[], roi=(10, 20, 0, 0)), 100, 80), (10, 20, 90, 60))
        self.assertEqual(_static_roi(Template(template=[], roi=(-10, -20, -30, -40)), 100, 80), (60, 20, 30, 40))
        self.assertEqual(_static_roi(Template(template=[], roi=(10, 20, 30, 40), roi_offset=(2, 3, 4, 5)), 100, 80), (12, 23, 34, 45))


if __name__ == "__main__":
    unittest.main()
