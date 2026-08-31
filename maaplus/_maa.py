from __future__ import annotations

from typing import Any

from .locator import Locator, OCR, Template


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, tuple):
        return list(value)
    return [value]


def compile_locator(locator: Locator) -> tuple[Any, Any]:
    """Compile a MaaPlus locator to MaaFramework 5.12 recognition parameters.

    MaaFramework is imported lazily so pure Flow/Locator tests do not need native libraries loaded.
    """
    from maa.pipeline import JOCR, JRecognitionType, JTemplateMatch

    if isinstance(locator, Template):
        return (
            JRecognitionType.TemplateMatch,
            JTemplateMatch(
                template=_as_list(locator.template),
                roi=locator.roi,
                threshold=_as_list(locator.threshold),
                order_by=locator.order_by,
                index=locator.index,
                method=locator.method,
                green_mask=locator.green_mask,
            ),
        )

    if isinstance(locator, OCR):
        expected = [] if locator.expected == () else _as_list(locator.expected)
        return (
            JRecognitionType.OCR,
            JOCR(
                expected=expected,
                roi=locator.roi,
                threshold=locator.threshold,
                order_by=locator.order_by,
                index=locator.index,
                only_rec=locator.only_rec,
                model=locator.model,
            ),
        )

    raise TypeError(f"Unsupported locator type: {type(locator).__name__}")
