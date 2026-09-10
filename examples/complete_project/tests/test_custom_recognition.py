from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy
from maa.pipeline import JRecognitionType

from examples.complete_project.demo import bootstrap
from examples.complete_project.demo.custom_recognition import (
    ColorPoint,
    MultiPointColorRecognition,
)
from examples.complete_project.demo.ui.explore import ExploreUI
from maaplus import Runtime, Tick


class FakeResource:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.registered: dict[str, object] = {}

    def register_custom_recognition(self, name: str, recognition: object) -> bool:
        if self.result:
            self.registered[name] = recognition
        return self.result

    def post_bundle(self, path):
        return SimpleNamespace(wait=lambda: SimpleNamespace(succeeded=True))


def argument(image: numpy.ndarray, *, roi=(0, 0, 0, 0), param=""):
    return SimpleNamespace(image=image, roi=roi, custom_recognition_param=param)


class MultiPointColorRecognitionTests(unittest.TestCase):
    def test_matches_rgb_points_in_bgr_image_and_returns_enclosing_box(self) -> None:
        image = numpy.zeros((30, 40, 3), dtype=numpy.uint8)
        # RGB (255, 214, 80) stored in the BGR screenshot order.
        image[8, 10] = (80, 214, 255)
        image[9, 12] = (80, 214, 255)
        image[8, 11] = (80, 214, 255)

        recognition = MultiPointColorRecognition(
            [
                ColorPoint((4, 4), (255, 214, 80)),
                ColorPoint((6, 5), (255, 214, 80)),
                ColorPoint((5, 4), (255, 214, 80)),
            ],
            tolerance=0,
        )
        result = recognition.analyze(None, argument(image))

        assert result is not None
        self.assertEqual(result.box, (10, 8, 3, 2))
        self.assertEqual(result.detail["anchor"], [10, 8])
        self.assertEqual(result.detail["point_count"], 3)

    def test_roi_and_per_invocation_tolerance_are_applied(self) -> None:
        image = numpy.zeros((20, 20, 3), dtype=numpy.uint8)
        image[5, 6] = (82, 214, 255)
        recognition = MultiPointColorRecognition([((0, 0), (255, 214, 80))], tolerance=0)

        self.assertIsNone(recognition.analyze(None, argument(image, roi=(0, 0, 5, 20))))
        result = recognition.analyze(
            None,
            argument(image, roi=(5, 4, 4, 4), param='{"tolerance": 2}'),
        )
        self.assertIsNotNone(result)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            MultiPointColorRecognition([])
        with self.assertRaises(ValueError):
            ColorPoint((0, 0), (256, 0, 0))


class ExampleRegistrationTests(unittest.TestCase):
    def test_bootstrap_registers_the_recognizer_named_by_the_ui_locator(self) -> None:
        resource = FakeResource()
        with patch.object(bootstrap, "Resource", return_value=resource):
            self.assertIs(bootstrap.load_resource(), resource)

        self.assertIsInstance(
            resource.registered[ExploreUI.BATTLE.custom_recognition],
            MultiPointColorRecognition,
        )

    def test_bootstrap_reports_native_registration_failure(self) -> None:
        resource = FakeResource(result=False)
        with self.assertRaisesRegex(RuntimeError, "Failed to register"):
            with patch.object(bootstrap, "Resource", return_value=resource):
                bootstrap.load_resource()

    def test_tick_passes_the_native_locator_and_snapshot_to_maa(self) -> None:
        image = numpy.zeros((20, 20, 3), dtype=numpy.uint8)
        recognition = SimpleNamespace(hit=True, box=(6, 5, 13, 13))
        job = Mock(succeeded=True)
        job.wait.return_value = job
        job.get.return_value = SimpleNamespace(nodes=[SimpleNamespace(recognition=recognition)])
        tasker = Mock()
        tasker.post_recognition.return_value = job
        tick = Tick(Runtime(tasker=tasker, controller=object()), image)

        result = tick.match(ExploreUI.BATTLE)

        self.assertTrue(result)
        self.assertIs(result.detail, recognition)
        tasker.post_recognition.assert_called_once_with(
            JRecognitionType.Custom, ExploreUI.BATTLE, image
        )


if __name__ == "__main__":
    unittest.main()
