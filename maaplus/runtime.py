from __future__ import annotations

from typing import Any

from ._maa import compile_locator
from .locator import Locator
from .match import MatchResult, Point


class Runtime:
    """Thin synchronous facade over MaaFramework."""

    __slots__ = ("tasker", "controller", "resource")

    def __init__(self, *, tasker: Any, controller: Any, resource: Any | None = None) -> None:
        self.tasker = tasker
        self.controller = controller
        self.resource = resource

    def screenshot(self) -> Any:
        job = self.controller.post_screencap().wait()
        if not job.succeeded:
            raise RuntimeError("MaaFramework screencap failed")
        return job.get()

    def recognize(self, locator: Locator, frame: Any) -> MatchResult:
        recognition_type, params = compile_locator(locator)
        job = self.tasker.post_recognition(recognition_type, params, frame).wait()
        if not job.succeeded:
            raise RuntimeError(f"MaaFramework recognition failed: {locator!r}")

        task_detail = job.get()
        if task_detail is None:
            raise RuntimeError("MaaFramework recognition returned no task detail")

        recognition = next(
            (node.recognition for node in reversed(task_detail.nodes) if node.recognition is not None),
            None,
        )
        if recognition is None:
            raise RuntimeError("MaaFramework recognition returned no recognition detail")

        return MatchResult(recognition)

    def click(self, point: Point) -> bool:
        x, y = point
        job = self.controller.post_click(x, y).wait()
        if not job.succeeded:
            raise RuntimeError(f"MaaFramework click failed at ({x}, {y})")
        return True

    def stop(self) -> None:
        if not getattr(self.tasker, "running", False):
            return
        job = self.tasker.post_stop().wait()
        if not job.succeeded:
            raise RuntimeError("MaaFramework tasker stop failed")
