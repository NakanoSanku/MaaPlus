from maa.pipeline import JOCR as OCR
from maa.pipeline import JRecognitionParam as Locator
from maa.pipeline import JRect as Rect
from maa.pipeline import JTemplateMatch as Template

from .app import App, Navigator, TaskHandle
from .routing import RoutedFlow, routed
from .runtime import MatchResult, Runtime
from .scheduler import FlowResult, Scheduler, Task
from .tick import Tick, ticked

CONTINUE = FlowResult.CONTINUE
YIELD = FlowResult.YIELD
DONE = FlowResult.DONE

__all__ = [
    "App",
    "CONTINUE",
    "DONE",
    "FlowResult",
    "Locator",
    "MatchResult",
    "Navigator",
    "OCR",
    "Rect",
    "RoutedFlow",
    "Runtime",
    "Scheduler",
    "Task",
    "TaskHandle",
    "Template",
    "Tick",
    "YIELD",
    "routed",
    "ticked",
]
