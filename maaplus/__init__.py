from maa.pipeline import JOCR as OCR
from maa.pipeline import JRecognitionParam as Locator
from maa.pipeline import JRect as Rect
from maa.pipeline import JTemplateMatch as Template

from .app import App, TaskHandle
from .routing import Navigator, RoutedTaskHandler, routed
from .runtime import MatchResult, Runtime
from .scheduler import Scheduler
from .task import Task, TaskHandler, TaskResult
from .tick import Tick

CONTINUE = TaskResult.CONTINUE
YIELD = TaskResult.YIELD
DONE = TaskResult.DONE

__all__ = [
    "App",
    "CONTINUE",
    "DONE",
    "Locator",
    "MatchResult",
    "Navigator",
    "OCR",
    "Rect",
    "RoutedTaskHandler",
    "Runtime",
    "Scheduler",
    "Task",
    "TaskHandle",
    "TaskHandler",
    "TaskResult",
    "Template",
    "Tick",
    "YIELD",
    "routed",
]
