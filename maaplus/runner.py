from __future__ import annotations

from threading import Event
from typing import TYPE_CHECKING, Any, Callable

from .runtime import Runtime

if TYPE_CHECKING:
    import numpy

Flow = Callable[[Runtime, "numpy.ndarray"], bool]


class Runner:
    """Run snapshot-driven flows and own their execution lifecycle."""

    __slots__ = ("runtime", "_running", "_stop_event")

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self._running = False
        self._stop_event = Event()

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

    @property
    def running(self) -> bool:
        return self._running

    def tick(self, flow: Flow) -> bool:
        """Capture one fresh screenshot and execute one flow decision tick."""
        return flow(self.runtime, self.runtime.screenshot())

    def run(self, flow: Flow, *, interval: int = 0) -> None:
        """Run fresh-screenshot ticks until the flow returns ``False`` or ``stop()`` is called.

        ``interval`` is the delay between ticks in milliseconds.
        """
        if interval < 0:
            raise ValueError("interval must be >= 0")
        if self._running:
            raise RuntimeError("Runner is already running")

        self._running = True
        self._stop_event.clear()

        try:
            while not self._stop_event.is_set():
                if not self.tick(flow):
                    break
                if interval > 0 and self._stop_event.wait(interval / 1000):
                    break
        finally:
            self._running = False

    def stop(self) -> None:
        """Request the runner loop to stop and stop MaaFramework work in progress."""
        self._stop_event.set()
        self.runtime.stop()

    def __enter__(self) -> Runner:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.stop()
