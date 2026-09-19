from __future__ import annotations

import unittest
from dataclasses import asdict
from types import SimpleNamespace

from maa.pipeline import JAnd, JOr, JRecognitionType
from maaplus import Runtime


class FakeRecognitionJob:
    succeeded = True

    def __init__(self, recognition) -> None:
        self.task_detail = SimpleNamespace(nodes=[SimpleNamespace(recognition=recognition)])

    def wait(self):
        return self

    def get(self):
        return self.task_detail


class FakeTasker:
    running = False

    def __init__(self, recognition) -> None:
        self.recognition = recognition
        self.calls: list[tuple[object, object, object]] = []

    def post_recognition(self, recognition_type, param, image):
        self.calls.append((recognition_type, param, image))
        return FakeRecognitionJob(self.recognition)


class NativeCompositionTests(unittest.TestCase):
    def assert_passed_through(self, locator, expected_type) -> None:
        detail = SimpleNamespace(hit=True, box=(10, 20, 30, 40))
        tasker = FakeTasker(detail)
        runtime = Runtime(tasker=tasker, controller=SimpleNamespace())
        image = object()
        original = asdict(locator)

        result = runtime.match(locator, image)

        recognition_type, param, passed_image = tasker.calls[0]
        self.assertEqual(recognition_type, expected_type)
        self.assertIs(param, locator)
        self.assertIs(passed_image, image)
        self.assertIs(result.detail, detail)
        self.assertEqual(asdict(param), original)

    def test_runtime_passes_native_or_without_rebuilding(self) -> None:
        self.assert_passed_through(
            JOr(any_of=[
                {"recognition": {"type": "TemplateMatch", "param": {"template": ["start.png"]}}},
                {"recognition": {"type": "OCR", "param": {"expected": ["挑战"]}}},
            ]),
            JRecognitionType.Or,
        )

    def test_runtime_preserves_native_and_box_index(self) -> None:
        self.assert_passed_through(
            JAnd(all_of=[
                {"recognition": {"type": "TemplateMatch", "param": {"template": ["battle/icon.png"]}}},
                {"recognition": {"type": "OCR", "param": {"expected": ["自动"]}}},
            ], box_index=1),
            JRecognitionType.And,
        )

    def test_runtime_preserves_nested_native_compositions(self) -> None:
        self.assert_passed_through(
            JOr(any_of=[
                {"recognition": {"type": "And", "param": {
                    "all_of": [
                        {"recognition": {"type": "TemplateMatch", "param": {"template": ["battle/icon.png"]}}},
                        {"recognition": {"type": "OCR", "param": {"expected": ["自动"]}}},
                    ],
                    "box_index": 1,
                }}},
                {"recognition": {"type": "OCR", "param": {"expected": ["战斗中"]}}},
            ]),
            JRecognitionType.Or,
        )


if __name__ == "__main__":
    unittest.main()
