from . import path, point, timing
from .app import App, TaskHandle
from .debug import Debug
from .guard import Guard, GuardAbortError, GuardHandler, GuardLoopError, GuardResult
from .geometry import PathInterpolator, Point, PointResolver, Rect
from .interaction import ClickConfig, InteractionConfig, SwipeConfig
from .instances import (
    AppFactory,
    InstanceConfig,
    InstanceControlError,
    InstanceHealth,
    InstanceManager,
    InstanceSnapshot,
    InstanceState,
)
from .locator import AllOf, FirstOf, Locator, OCR, Template
from .routing import NavigationError, NavigationState, Navigator, RoutedTaskHandler, routed
from .runtime import MatchResult, Runtime
from .scheduler import Scheduler
from .task import (
    ExecutionContext,
    ExecutionSummary,
    Task,
    TaskFailure,
    TaskHandler,
    TaskResult,
    TaskStatus,
    TaskTimeoutError,
)
from .tick import Tick
from .timing import Timing, TimingResolver

__version__ = "1.4.0"

CONTINUE = TaskResult.CONTINUE
YIELD = TaskResult.YIELD
DONE = TaskResult.DONE

__all__ = [
    "AllOf",
    "AppFactory",
    "App",
    "ClickConfig",
    "CONTINUE",
    "Debug",
    "Guard",
    "GuardAbortError",
    "GuardHandler",
    "GuardLoopError",
    "GuardResult",
    "DONE",
    "ExecutionContext",
    "ExecutionSummary",
    "FirstOf",
    "InteractionConfig",
    "InstanceConfig",
    "InstanceControlError",
    "InstanceHealth",
    "InstanceManager",
    "InstanceSnapshot",
    "InstanceState",
    "Locator",
    "MatchResult",
    "NavigationError",
    "NavigationState",
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
    "TaskFailure",
    "TaskHandle",
    "TaskHandler",
    "TaskResult",
    "TaskStatus",
    "TaskTimeoutError",
    "Template",
    "Tick",
    "Timing",
    "TimingResolver",
    "YIELD",
    "__version__",
    "path",
    "point",
    "routed",
    "timing",
]
