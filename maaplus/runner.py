from __future__ import annotations

from threading import Condition
from time import monotonic
from typing import TYPE_CHECKING, Any, Callable

from .runtime import Runtime

if TYPE_CHECKING:
    import numpy

Flow = Callable[[Runtime, "numpy.ndarray"], bool]


class Runner:
    """Run snapshot-driven flows and own their execution lifecycle."""

    __slots__ = (
        "runtime",
        "_condition",
        "_paused",
        "_running",
        "_stop_requested",
    )

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self._condition = Condition()
        self._paused = False
        self._running = False
        self._stop_requested = False

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
        with self._condition:
            return self._running

    @property
    def paused(self) -> bool:
        with self._condition:
            return self._paused

    def tick(self, flow: Flow) -> bool:
        """Capture one fresh screenshot and execute one flow decision tick."""
        return flow(self.runtime, self.runtime.screenshot())

    def run(self, flow: Flow, *, interval: int = 0) -> None:
        """Run fresh-screenshot ticks until the flow returns ``False`` or ``stop()`` is called.

        ``interval`` is the delay between ticks in milliseconds. ``pause()`` never interrupts
        the current tick; it blocks before the next screenshot. If a pause happens during the
        interval, the full interval starts again after ``resume()``.
        """
        if interval < 0:
            raise ValueError("interval must be >= 0")

        with self._condition:
            if self._running:
                raise RuntimeError("Runner is already running")
            self._running = True
            self._paused = False
            self._stop_requested = False

        try:
            delay = 0
            while self._wait_for_next_tick(delay):
                if not self.tick(flow):
                    break
                delay = interval
        finally:
            with self._condition:
                self._running = False
                self._paused = False
                self._stop_requested = False
                self._condition.notify_all()

    def pause(self) -> None:
        """Pause before the next tick without interrupting the current tick."""
        with self._condition:
            if not self._running or self._paused:
                return
            self._paused = True
            self._condition.notify_all()

    def resume(self) -> None:
        """Resume a paused run loop."""
        with self._condition:
            if not self._running or not self._paused:
                return
            self._paused = False
            self._condition.notify_all()

    def stop(self) -> None:
        """Request the runner loop to stop and stop MaaFramework work in progress."""
        with self._condition:
            self._stop_requested = True
            self._paused = False
            self._condition.notify_all()
        self.runtime.stop()

    def _wait_for_next_tick(self, interval: int) -> bool:
        delay = interval / 1000

        with self._condition:
            while True:
                if self._stop_requested:
                    return False

                while self._paused and not self._stop_requested:
                    self._condition.wait()

                if self._stop_requested:
                    return False
                if delay <= 0:
                    return True

                deadline = monotonic() + delay
                while not self._paused and not self._stop_requested:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        return True
                    self._condition.wait(remaining)

                # A pause restarts the full interval after resume. Stop exits immediately.

    def __enter__(self) -> Runner:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.stop()
