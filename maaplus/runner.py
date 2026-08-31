from __future__ import annotations

from typing import Any, Callable

from .runtime import Runtime


Flow = Callable[[Runtime, Any], Any]


class Runner:
    """Composition/lifecycle boundary around a flow callable."""

    __slots__ = ("runtime",)

    def __init__(self, runtime: Runtime) -> None:
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

    def run(self, flow: Flow) -> Any:
        """Capture one fresh screenshot, then run the flow against that fixed image."""
        return flow(self.runtime, self.runtime.screenshot())

    def stop(self) -> None:
        self.runtime.stop()
