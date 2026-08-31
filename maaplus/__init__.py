from maa.pipeline import JOCR as OCR
from maa.pipeline import JRecognitionParam as Locator
from maa.pipeline import JRect as Rect
from maa.pipeline import JTemplateMatch as Template

from .runner import Runner
from .runtime import MatchResult, Runtime

__all__ = [
    "Locator",
    "MatchResult",
    "OCR",
    "Rect",
    "Runner",
    "Runtime",
    "Template",
]
