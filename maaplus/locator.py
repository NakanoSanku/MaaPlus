from __future__ import annotations

from dataclasses import asdict
from typing import Any

from maa.pipeline import (
    JAnd,
    JColorMatch,
    JCustomRecognition,
    JDirectHit,
    JFeatureMatch,
    JNeuralNetworkClassify,
    JNeuralNetworkDetect,
    JOCR,
    JOr,
    JRecognitionParam,
    JRecognitionType,
    JTemplateMatch,
)

Locator = JRecognitionParam
Template = JTemplateMatch
OCR = JOCR


_RECOGNITION_TYPES: dict[type[Any], JRecognitionType] = {
    JDirectHit: JRecognitionType.DirectHit,
    JTemplateMatch: JRecognitionType.TemplateMatch,
    JFeatureMatch: JRecognitionType.FeatureMatch,
    JColorMatch: JRecognitionType.ColorMatch,
    JOCR: JRecognitionType.OCR,
    JNeuralNetworkClassify: JRecognitionType.NeuralNetworkClassify,
    JNeuralNetworkDetect: JRecognitionType.NeuralNetworkDetect,
    JAnd: JRecognitionType.And,
    JOr: JRecognitionType.Or,
    JCustomRecognition: JRecognitionType.Custom,
}


def recognition_type(locator: Locator) -> JRecognitionType:
    """Resolve the MaaFramework recognition type for a locator."""
    try:
        return _RECOGNITION_TYPES[type(locator)]
    except KeyError as exc:
        raise TypeError(f"Unsupported recognition parameter: {type(locator).__name__}") from exc


def _inline(locator: Locator) -> dict[str, Any]:
    """Convert a native recognition parameter to an inline sub-recognition."""
    return {
        "recognition": {
            "type": recognition_type(locator),
            "param": asdict(locator),
        }
    }


def _sub_recognitions(name: str, locators: tuple[Locator, ...]) -> list[dict[str, Any]]:
    if not locators:
        raise ValueError(f"{name} requires at least one locator")
    return [_inline(locator) for locator in locators]


def FirstOf(*locators: Locator) -> JOr:
    """Match the first successful locator using MaaFramework's native Or recognition."""
    return JOr(any_of=_sub_recognitions("FirstOf", locators))


def AllOf(*locators: Locator, box_index: int = 0) -> JAnd:
    """Require every locator to match using MaaFramework's native And recognition.

    ``box_index`` selects which successful sub-recognition supplies the resulting
    match box, and therefore the default target used by ``MatchResult.click()``.
    """
    all_of = _sub_recognitions("AllOf", locators)
    if not 0 <= box_index < len(locators):
        raise ValueError(
            f"AllOf box_index must be between 0 and {len(locators) - 1}, got {box_index}"
        )
    return JAnd(all_of=all_of, box_index=box_index)
