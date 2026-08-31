from __future__ import annotations

from typing import Any, Protocol

from ._maa import compile_locator
from .errors import RuntimeOperationError
from .locator import Locator, Rect
from .result import MatchResult


class RuntimeLike(Protocol):
    def screenshot(self) -> Any: ...
    def recognize(self, locator: Locator, frame: Any) -> MatchResult: ...
    def click(self, box: Rect) -> bool: ...
    def stop(self) -> None: ...


class Runtime:
    """Thin synchronous facade over an already-created MaaFramework Tasker/Controller."""

    __slots__ = ("tasker", "controller", "resource")

    def __init__(self, *, tasker: Any, controller: Any, resource: Any | None = None) -> None:
        self.tasker = tasker
        self.controller = controller
        self.resource = resource

    def screenshot(self) -> Any:
        job = self.controller.post_screencap().wait()
        if not job.succeeded:
            raise RuntimeOperationError("MaaFramework screencap failed")
        return job.get()

    def recognize(self, locator: Locator, frame: Any) -> MatchResult:
        recognition_type, params = compile_locator(locator)
        job = self.tasker.post_recognition(recognition_type, params, frame).wait()
        if not job.succeeded:
            raise RuntimeOperationError(f"MaaFramework recognition failed: {locator!r}")

        task_detail = job.get()
        if task_detail is None:
            raise RuntimeOperationError("MaaFramework recognition returned no task detail")

        recognition = None
        for node in reversed(task_detail.nodes):
            if node.recognition is not None:
                recognition = node.recognition
                break
        if recognition is None:
            raise RuntimeOperationError("MaaFramework recognition returned no recognition detail")

        box = tuple(recognition.box) if recognition.box is not None else None
        best = recognition.best_result
        score = getattr(best, "score", None) if best is not None else None

        return MatchResult(
            locator=locator,
            hit=recognition.hit,
            box=box,
            score=score,
            detail=best,
            raw_detail=recognition.raw_detail,
        )

    def click(self, box: Rect) -> bool:
        x, y, width, height = box
        point_x = x + width // 2
        point_y = y + height // 2
        job = self.controller.post_click(point_x, point_y).wait()
        if not job.succeeded:
            raise RuntimeOperationError(f"MaaFramework click failed at ({point_x}, {point_y})")
        return True

    def stop(self) -> None:
        if not getattr(self.tasker, "running", False):
            return
        job = self.tasker.post_stop().wait()
        if not job.succeeded:
            raise RuntimeOperationError("MaaFramework tasker stop failed")
