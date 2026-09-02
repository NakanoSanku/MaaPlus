from maa.pipeline import JOCR as OCR
from maa.pipeline import JRecognitionParam as Locator
from maa.pipeline import JRect as Rect
from maa.pipeline import JTemplateMatch as Template

from . import click, swipe, timing
from .app import App, TaskHandle
from .click import ClickResolver, Point
from .interaction import ClickConfig, InteractionConfig, SwipeConfig
from .routing import Navigator, RoutedTaskHandler, routed
from .runtime import MatchResult, Runtime
from .scheduler import Scheduler
from .task import Task, TaskHandler, TaskResult
from .tick import Tick
from .timing import Timing, TimingResolver

CONTINUE = TaskResult.CONTINUE
YIELD = TaskResult.YIELD
DONE = TaskResult.DONE

__all__ = [
    "App",
    "ClickConfig",
    "ClickResolver",
    "CONTINUE",
    "DONE",
    "InteractionConfig",
    "Locator",
    "MatchResult",
    "Navigator",
    "OCR",
    "Point",
    "Rect",
    "RoutedTaskHandler",
    "Runtime",
    "Scheduler",
    "SwipeConfig",
    "Task",
    "TaskHandle",
    "TaskHandler",
    "TaskResult",
    "Template",
    "Tick",
    "Timing",
    "TimingResolver",
    "YIELD",
    "click",
    "routed",
    "swipe",
    "timing",
]
