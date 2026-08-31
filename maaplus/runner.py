from __future__ import annotations

from typing import Any

from .errors import RuntimeOperationError
from .flow import Flow, FlowContext
from .runtime import Runtime, RuntimeLike


class Runner:
    """Small composition/lifecycle boundary around Flow execution."""

    __slots__ = ("runtime",)

    def __init__(self, runtime: RuntimeLike) -> None:
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
        """Create a Runner from MaaFramework objects.

        Controller connection and Resource loading stay explicit in MaaFramework for this MVP.
        """
        if bind and not tasker.bind(resource, controller):
            raise RuntimeOperationError("Failed to bind MaaFramework resource/controller to tasker")
        return cls(Runtime(tasker=tasker, controller=controller, resource=resource))

    def run(self, flow: Flow) -> Any:
        return flow.run(FlowContext(self.runtime))

    def stop(self) -> None:
        self.runtime.stop()
