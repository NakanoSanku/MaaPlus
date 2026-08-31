from __future__ import annotations

from typing import Any, Callable

from .flow import FlowContext
from .runtime import Runtime


class Runner:
    """Composition/lifecycle boundary around a flow callable."""

    __slots__ = ("runtime",)

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    @classmethod
    def from_maa(
        cls,
        *,
        tasker: Any,
        controller: Any,
        resource: Any,
        bind: bool = True,
    ) -> Runner:
        if bind and not tasker.bind(resource, controller):
            raise RuntimeError("Failed to bind MaaFramework resource/controller to tasker")
        return cls(Runtime(tasker=tasker, controller=controller, resource=resource))

    def run(self, flow: Callable[[FlowContext], Any]) -> Any:
        return flow(FlowContext(self.runtime))

    def stop(self) -> None:
        self.runtime.stop()
