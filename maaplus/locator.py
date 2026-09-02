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


def FirstOf(*locators: Locator) -> JOr:
    """Match the first successful locator using MaaFramework's native Or recognition."""
    if not locators:
        raise ValueError("FirstOf requires at least one locator")

    return JOr(any_of=[_inline(locator) for locator in locators])
