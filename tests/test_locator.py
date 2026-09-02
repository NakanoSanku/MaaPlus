from __future__ import annotations

import json
import unittest
from dataclasses import asdict
from types import SimpleNamespace

from maa.pipeline import JOr, JRecognitionType
from maaplus import FirstOf, OCR, Runtime, Template


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


class FirstOfTests(unittest.TestCase):
    def test_requires_at_least_one_locator(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one locator"):
            FirstOf()

    def test_builds_native_maa_or_with_inline_recognitions(self) -> None:
        template = Template(template=["start.png"], threshold=[0.85])
        ocr = OCR(expected=["挑战"], threshold=0.6)

        locator = FirstOf(template, ocr)

        self.assertIsInstance(locator, JOr)
        self.assertEqual(len(locator.any_of), 2)

        template_inline = locator.any_of[0]["recognition"]
        self.assertEqual(template_inline["type"], JRecognitionType.TemplateMatch)
        self.assertEqual(template_inline["param"]["template"], ["start.png"])
        self.assertEqual(template_inline["param"]["threshold"], [0.85])

        ocr_inline = locator.any_of[1]["recognition"]
        self.assertEqual(ocr_inline["type"], JRecognitionType.OCR)
        self.assertEqual(ocr_inline["param"]["expected"], ["挑战"])
        self.assertEqual(ocr_inline["param"]["threshold"], 0.6)

    def test_serializes_as_tasker_post_recognition_payload(self) -> None:
        locator = FirstOf(
            Template(template=["start.png"]),
            OCR(expected=["挑战"]),
        )

        payload = asdict(locator)
        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertIn('"any_of"', encoded)
        self.assertIn('"TemplateMatch"', encoded)
        self.assertIn('"OCR"', encoded)
        self.assertIn("挑战", encoded)

    def test_runtime_treats_first_of_as_normal_locator(self) -> None:
        detail = SimpleNamespace(hit=True, box=(10, 20, 30, 40))
        tasker = FakeTasker(detail)
        runtime = Runtime(tasker=tasker, controller=SimpleNamespace())
        image = object()
        locator = FirstOf(
            Template(template=["start.png"]),
            OCR(expected=["挑战"]),
        )

        result = runtime.match(locator, image)

        recognition_type, param, passed_image = tasker.calls[0]
        self.assertEqual(recognition_type, JRecognitionType.Or)
        self.assertIs(param, locator)
        self.assertIs(passed_image, image)
        self.assertIs(result.detail, detail)

    def test_supports_nested_first_of(self) -> None:
        nested = FirstOf(
            FirstOf(
                Template(template=["start_a.png"]),
                Template(template=["start_b.png"]),
            ),
            OCR(expected=["挑战"]),
        )

        first_inline = nested.any_of[0]["recognition"]
        self.assertEqual(first_inline["type"], JRecognitionType.Or)
        self.assertEqual(len(first_inline["param"]["any_of"]), 2)


if __name__ == "__main__":
    unittest.main()
