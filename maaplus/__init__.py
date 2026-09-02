from maa.pipeline import JOCR as OCR
from maa.pipeline import JRecognitionParam as Locator
from maa.pipeline import JRect as Rect
from maa.pipeline import JTemplateMatch as Template

from . import path, point, timing
from .app import App, TaskHandle
from .geometry import PathInterpolator, Point, PointResolver
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
    "CONTINUE",
    "DONE",
    "InteractionConfig",
    "Locator",
    "MatchResult",
    "Navigator",
    "OCR",
    "PathInterpolator",
    "Point",
    "PointResolver",
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
    "path",
    "point",
    "routed",
    "timing",
]
