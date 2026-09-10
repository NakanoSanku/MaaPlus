"""Lifecycle management for independent MaaPlus applications on multiple devices."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from threading import RLock, Thread, get_ident
from time import monotonic
from typing import Any, TypeAlias
import weakref

from .app import App

logger = logging.getLogger(__name__)
AppFactory: TypeAlias = Callable[["InstanceConfig"], App[Any]]
_DEVICE_LOCK = RLock()
_DEVICE_LEASES: dict[str, weakref.ReferenceType[Any]] = {}


class InstanceState(Enum):
    """Lifecycle of a managed app, separate from the statuses of its tasks."""

    CREATED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()


class InstanceHealth(Enum):
    """Health derived from the run loop and retained task failures."""

    UNKNOWN = auto()
    HEALTHY = auto()
    DEGRADED = auto()
    FAILED = auto()


class InstanceControlError(RuntimeError):
    """Errors from a batch control operation, after all instances were addressed."""

    def __init__(self, errors: Mapping[str, BaseException]) -> None:
        self.errors = dict(errors)
        super().__init__("could not stop instances: " + ", ".join(self.errors))


@dataclass(frozen=True, slots=True)
class InstanceConfig:
    """Device identity and artifact paths passed to a per-instance app factory."""

    name: str
    device: str
    root_dir: str | Path = ".maaplus/instances"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("instance name must be a non-empty string")
        # These names must remain valid directory components on Windows and POSIX.
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(f"{prefix}{n}" for prefix in ("COM", "LPT") for n in range(1, 10))
        if (
            self.name != self.name.strip()
            or self.name.endswith(".")
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', self.name)
            or self.name.split(".")[0].upper() in reserved
        ):
            raise ValueError("instance name must be a valid directory component")
        if not isinstance(self.device, str) or not self.device.strip():
            raise ValueError("instance device must be a non-empty string")
        object.__setattr__(self, "device", self.device.strip())
        object.__setattr__(self, "root_dir", Path(self.root_dir).resolve())

    @property
    def directory(self) -> Path:
        return self.root_dir / self.name

    @property
    def debug_dir(self) -> Path:
        return self.directory / "debug"

    @property
    def trace_dir(self) -> Path:
        return self.directory / "trace"


@dataclass(frozen=True, slots=True)
class InstanceSnapshot:
    name: str
    device: str
    state: InstanceState
    error: BaseException | None = None
    health: InstanceHealth = InstanceHealth.UNKNOWN
    failed_tasks: int = 0
    current_task: str | None = None


@dataclass(slots=True)
class _ManagedInstance:
    config: InstanceConfig
    app: App[Any]
    state: InstanceState = InstanceState.CREATED
    future: Future[None] | None = None
    error: BaseException | None = None
    removing: bool = False
    worker_ident: int | None = None
    stop_future: Future[None] | None = None
    close_future: Future[None] | None = None
    lock: Any = field(default_factory=RLock, repr=False)


class InstanceManager:
    """Own the thread lifecycle of one independent App per device identifier.

    The factory creates Maa objects, stateful handlers, navigators, guards and evidence writers
    separately for each config. Device reservations apply across managers in this process.
    Run intervals use milliseconds; wait/stop/close timeouts use seconds.
    """

    def __init__(
        self,
        factory: AppFactory | None = None,
        *,
        root_dir: str | Path = ".maaplus/instances",
        max_workers: int | None = None,
        thread_name_prefix: str = "maaplus-instance",
    ) -> None:
        if factory is not None and not callable(factory):
            raise TypeError("instance factory must be callable")
        if max_workers is not None and (
            isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1
        ):
            raise ValueError("max_workers must be a positive integer")
        self._factory = factory
        self._root_dir = Path(root_dir).resolve()
        self._max_workers = max_workers
        self._thread_name_prefix = thread_name_prefix
        self._lock = RLock()
        self._instances: dict[str, _ManagedInstance] = {}
        self._pending_creates: set[str] = set()
        self._executor: ThreadPoolExecutor | None = None
        self._closed = False

    @property
    def instances(self) -> tuple[InstanceSnapshot, ...]:
        """Return snapshots in registration order."""
        with self._lock:
            return tuple(self._snapshot(item) for item in self._instances.values())

    def snapshot(self, name: str) -> InstanceSnapshot:
        return self._snapshot(self._get(name))

    def get(self, name: str) -> App[Any]:
        """Access an app to register or inspect its tasks."""
        return self._get(name).app

    def register(self, name: str, device: str, app: App[Any]) -> App[Any]:
        """Register an idle app and reserve its device until removal."""
        config = InstanceConfig(name, device, self._root_dir)
        with self._lock:
            self._ensure_open()
            self._ensure_available(config)
            self._acquire_device(config.device)
            try:
                self._validate_app(app)
                self._instances[name] = _ManagedInstance(config, app)
            except BaseException:
                self._release_device(config.device)
                raise
        return app

    def create(self, name: str, device: str) -> App[Any]:
        """Call the factory once and register the resulting app."""
        config: InstanceConfig
        with self._lock:
            self._ensure_open()
            if self._factory is None:
                raise RuntimeError("create() requires an instance factory")
            config = InstanceConfig(name, device, self._root_dir)
            self._ensure_available(config)
            self._acquire_device(config.device)
            self._pending_creates.add(config.name)

        try:
            app = self._factory(config)
        except BaseException:
            with self._lock:
                self._pending_creates.discard(config.name)
                self._release_device(config.device)
            raise

        validation_error: BaseException | None = None
        closed = False
        with self._lock:
            self._pending_creates.discard(config.name)
            closed = self._closed
            if not closed:
                try:
                    self._validate_app(app)
                except BaseException as exc:
                    validation_error = exc
                else:
                    self._instances[config.name] = _ManagedInstance(config, app)
            if closed or validation_error is not None:
                self._release_device(config.device)
        if closed:
            try:
                app.close()
            except Exception:
                logger.warning("instance factory rollback failed name=%s", config.name, exc_info=True)
            raise RuntimeError("instance manager is closed")
        if validation_error is not None:
            # The rejected object may alias an existing instance. Do not close it here.
            raise validation_error
        return app

    def create_many(
        self,
        devices: Mapping[str, str] | Iterable[str],
        *,
        name: Callable[[str], str] | None = None,
    ) -> tuple[App[Any], ...]:
        """Create a batch from ``{name: device}`` or device IDs and roll it back on failure."""
        if isinstance(devices, Mapping):
            pairs = tuple(devices.items())
        else:
            pairs = tuple(
                ((name(device) if name is not None else self._safe_device_name(device, index)), device)
                for index, device in enumerate(devices, 1)
            )
        with self._lock:
            self._ensure_open()
        created: list[str] = []
        try:
            for instance_name, device in pairs:
                self.create(instance_name, device)
                created.append(instance_name)
        except BaseException:
            for instance_name in reversed(created):
                try:
                    self.remove(instance_name)
                except Exception:
                    logger.warning("instance rollback failed name=%s", instance_name, exc_info=True)
            raise
        return tuple(self.get(instance_name) for instance_name in created)

    def start(self, name: str, *, interval: int = 0) -> Future[None]:
        """Submit an app run. Queued workers remain STARTING until initialized."""
        if isinstance(interval, bool) or not isinstance(interval, int) or interval < 0:
            raise ValueError("interval must be a non-negative integer in milliseconds")
        with self._lock:
            self._ensure_open()
            item = self._get(name)
            with item.lock:
                self._ensure_inactive(item)
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(
                        max_workers=self._max_workers,
                        thread_name_prefix=self._thread_name_prefix,
                    )
                item.state, item.error = InstanceState.STARTING, None
                item.stop_future = None
                try:
                    item.future = self._executor.submit(self._run, item, interval)
                except Exception as exc:
                    item.state, item.error = InstanceState.FAILED, exc
                    raise
                item.future.add_done_callback(lambda future, managed=item: self._future_done(managed, future))
                return item.future

    def start_all(self, *, interval: int = 0) -> dict[str, Future[None]]:
        """Start every app; already-active instances are rejected before submission."""
        with self._lock:
            self._ensure_open()
            for item in self._instances.values():
                with item.lock:
                    self._ensure_inactive(item)
            return {name: self.start(name, interval=interval) for name in self._instances}

    def pause(self, name: str) -> None:
        item = self._get(name)
        with item.lock:
            if item.state in {InstanceState.STARTING, InstanceState.RUNNING}:
                item.state = InstanceState.PAUSED
                item.app.pause()

    def resume(self, name: str) -> None:
        item = self._get(name)
        with item.lock:
            if item.state is InstanceState.PAUSED:
                item.state = InstanceState.RUNNING if item.app.running else InstanceState.STARTING
                item.app.resume()

    def pause_all(self) -> None:
        for item in self.instances:
            self.pause(item.name)

    def resume_all(self) -> None:
        for item in self.instances:
            self.resume(item.name)

    def stop(self, name: str, *, wait: bool = True, timeout: float | None = None) -> None:
        """Stop cooperatively; calls from this instance's worker never wait on that worker."""
        deadline = None if timeout is None else monotonic() + timeout
        item = self._get(name)
        request = self._dispatch_stop(item)
        if wait and not self._is_worker(item):
            request.result(timeout=self._remaining(deadline))
            self._join((item,), self._remaining(deadline))

    def stop_all(self, *, wait: bool = True, timeout: float | None = None) -> None:
        """Dispatch every stop independently; the timeout covers requests and worker joins."""
        deadline = None if timeout is None else monotonic() + timeout
        with self._lock:
            items = tuple(self._instances.values())
        requests = tuple((item, self._dispatch_stop(item)) for item in items)
        if wait:
            self._wait_controls(requests, deadline, join_workers=True)

    def wait(self, name: str, *, timeout: float | None = None) -> None:
        """Wait for one run and re-raise its error. A cancelled queued run is stopped normally."""
        item = self._get(name)
        with item.lock:
            future, error = item.future, item.error
            if item.worker_ident == get_ident():
                raise RuntimeError("an instance worker cannot wait for its own Future")
        if future is not None:
            try:
                future.result(timeout=timeout)
            except CancelledError:
                pass
        elif error is not None:
            raise error

    def remove(self, name: str, *, wait: bool = True, timeout: float | None = None) -> None:
        """Close an app and release its reservation after the worker has finished."""
        deadline = None if timeout is None else monotonic() + timeout
        item = self._get(name)
        if self._is_worker(item):
            raise RuntimeError("an instance worker cannot remove itself; stop it and remove later")
        with item.lock:
            if not wait and item.future is not None and not item.future.done():
                raise ValueError("removing an active instance requires wait=True")
            item.removing = True
        self._dispatch_stop(item)
        close_future = self._dispatch_close(item)
        close_future.result(timeout=self._remaining(deadline))
        with self._lock:
            if self._instances.get(name) is item:
                self._instances.pop(name)

    def close(self, *, wait: bool = True, timeout: float | None = None) -> None:
        """Stop workers and close owned resources, continuing cleanup after a timeout."""
        deadline = None if timeout is None else monotonic() + timeout
        with self._lock:
            self._closed = True
            executor = self._executor
            items = tuple(self._instances.values())
        for item in items:
            self._dispatch_stop(item)
        requests = tuple((item, self._dispatch_close(item)) for item in items)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)
        if wait:
            self._wait_controls(requests, deadline)

    def __enter__(self) -> InstanceManager:
        with self._lock:
            self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()

    def _run(self, item: _ManagedInstance, interval: int) -> None:
        with item.lock:
            item.worker_ident = get_ident()
        try:
            item.app.run(interval=interval, on_started=lambda: self._started(item))
        except BaseException as exc:
            with item.lock:
                item.state, item.error = InstanceState.FAILED, exc
            raise
        else:
            with item.lock:
                if item.error is None:
                    item.state = InstanceState.STOPPED
                else:
                    item.state = InstanceState.FAILED
        finally:
            with item.lock:
                item.worker_ident = None

    def _future_done(self, item: _ManagedInstance, future: Future[None]) -> None:
        if future.cancelled():
            with item.lock:
                if item.future is future and item.worker_ident is None:
                    item.state = InstanceState.STOPPED
                    item.error = None

    @staticmethod
    def _started(item: _ManagedInstance) -> None:
        with item.lock:
            if item.state is InstanceState.STOPPING:
                item.app.stop()
            elif item.state is InstanceState.PAUSED:
                item.app.pause()
            else:
                item.state = InstanceState.RUNNING

    def _dispatch_stop(self, item: _ManagedInstance) -> Future[None]:
        with item.lock:
            if item.stop_future is not None:
                return item.stop_future
            request: Future[None] = Future()
            item.stop_future = request
            future = item.future
            if future is not None and not future.done():
                item.state = InstanceState.STOPPING
            elif item.state is InstanceState.CREATED:
                item.state = InstanceState.STOPPED
        # Future callbacks may run inline, so cancellation must happen outside item.lock.
        if future is not None:
            future.cancel()

        def invoke() -> None:
            try:
                if not item.app.closed:
                    item.app.stop()
            except BaseException as exc:
                with item.lock:
                    item.state, item.error = InstanceState.FAILED, exc
                request.set_exception(exc)
            else:
                request.set_result(None)

        self._start_control_thread(item, "stop", invoke, request)
        return request

    def _dispatch_close(self, item: _ManagedInstance) -> Future[None]:
        with item.lock:
            if item.close_future is not None:
                return item.close_future
            request: Future[None] = Future()
            item.close_future = request
            item.removing = True
            stop_future, run_future = item.stop_future, item.future

        def invoke() -> None:
            error: BaseException | None = None
            if stop_future is not None:
                try:
                    stop_future.result()
                except BaseException as exc:
                    error = exc
            if run_future is not None:
                try:
                    run_future.exception()
                except CancelledError:
                    pass
            try:
                item.app.close()
            except BaseException as exc:
                if error is None:
                    error = exc
            finally:
                self._release_device(item.config.device)
            if error is not None:
                request.set_exception(error)
            else:
                request.set_result(None)

        self._start_control_thread(item, "close", invoke, request)
        return request

    def _start_control_thread(
        self, item: _ManagedInstance, operation: str, invoke: Callable[[], None],
        request: Future[None],
    ) -> None:
        try:
            Thread(
                target=invoke,
                name=f"{self._thread_name_prefix}-{operation}-{item.config.name}",
                daemon=True,
            ).start()
        except BaseException as exc:
            request.set_exception(exc)

    @staticmethod
    def _is_worker(item: _ManagedInstance) -> bool:
        with item.lock:
            return item.worker_ident == get_ident()

    @staticmethod
    def _join(
        items: tuple[_ManagedInstance, ...],
        timeout: float | None,
        *,
        skip_worker: bool = False,
    ) -> None:
        deadline = None if timeout is None else monotonic() + timeout
        for item in items:
            with item.lock:
                future = item.future
                worker_ident = item.worker_ident
            if worker_ident == get_ident():
                if skip_worker:
                    continue
                raise RuntimeError("an instance worker cannot wait for its own Future")
            if future is None:
                continue
            remaining = None if deadline is None else max(0.0, deadline - monotonic())
            try:
                future.exception(timeout=remaining)
            except CancelledError:
                pass
            except TimeoutError as exc:
                raise TimeoutError(f"instance {item.config.name!r} has not stopped") from exc

    @staticmethod
    def _remaining(deadline: float | None) -> float | None:
        return None if deadline is None else max(0.0, deadline - monotonic())

    def _wait_controls(
        self,
        requests: tuple[tuple[_ManagedInstance, Future[None]], ...],
        deadline: float | None,
        *,
        join_workers: bool = False,
    ) -> None:
        errors: dict[str, BaseException] = {}
        timeouts: dict[str, TimeoutError] = {}
        for item, request in requests:
            if self._is_worker(item):
                continue
            try:
                request.result(timeout=self._remaining(deadline))
            except TimeoutError as exc:
                if request.done():
                    errors[item.config.name] = exc
                else:
                    timeouts[item.config.name] = TimeoutError(
                        f"instance {item.config.name!r} has not stopped or closed"
                    )
            except BaseException as exc:
                errors[item.config.name] = exc
            if join_workers:
                try:
                    self._join((item,), self._remaining(deadline))
                except TimeoutError as exc:
                    timeouts[item.config.name] = exc
        if errors:
            for name, error in timeouts.items():
                errors.setdefault(name, error)
            raise InstanceControlError(errors)
        if timeouts:
            raise next(iter(timeouts.values()))

    def _get(self, name: str) -> _ManagedInstance:
        with self._lock:
            try:
                return self._instances[name]
            except KeyError as exc:
                raise KeyError(f"unknown instance {name!r}") from exc

    def _validate_app(self, app: App[Any]) -> None:
        if not isinstance(app, App):
            raise TypeError("instance factory must return an App")
        if app.closed:
            raise ValueError("cannot register a closed App")
        if app.running:
            raise ValueError("cannot register an already-running App")
        objects = self._owned_objects(app)
        for item in self._instances.values():
            existing = self._owned_objects(item.app)
            for label, obj in objects.items():
                if obj is not None and any(obj is other for other in existing.values()):
                    raise ValueError(f"{label} is shared with instance {item.config.name!r}")
            for label in ("debug", "trace"):
                attribute = "output_dir" if label == "debug" else "path"
                left = getattr(objects[label], attribute, None)
                right = getattr(existing[label], attribute, None)
                if left is not None and right is not None and Path(left).resolve() == Path(right).resolve():
                    raise ValueError(f"{label} output is shared with instance {item.config.name!r}")

    @staticmethod
    def _owned_objects(app: App[Any]) -> dict[str, Any]:
        runtime = app.scheduler.runtime
        return {
            "App": app, "Scheduler": app.scheduler, "Runtime": runtime,
            "Navigator": app.navigator, "Tasker": getattr(runtime, "tasker", None),
            "Controller": getattr(runtime, "controller", None),
            "Resource": getattr(runtime, "resource", None), "debug": getattr(runtime, "debug", None),
            "trace": app.scheduler.trace, "runtime trace": getattr(runtime, "trace", None),
        }

    def _ensure_available(self, config: InstanceConfig) -> None:
        if config.name in self._instances or config.name in self._pending_creates:
            raise ValueError(f"instance name {config.name!r} is already registered")
        for item in self._instances.values():
            if item.config.device == config.device:
                raise ValueError(f"device {config.device!r} is already assigned to an instance")
            if item.config.directory == config.directory:
                raise ValueError(f"instance directory is shared with {item.config.name!r}")

    def _acquire_device(self, device: str) -> None:
        with _DEVICE_LOCK:
            reference = _DEVICE_LEASES.get(device)
            owner = reference() if reference is not None else None
            if owner is self:
                raise ValueError(f"device {device!r} is already assigned to an instance")
            if owner is not None:
                raise ValueError(f"device {device!r} is already leased by another InstanceManager")
            _DEVICE_LEASES[device] = weakref.ref(self)

    def _release_device(self, device: str) -> None:
        with _DEVICE_LOCK:
            reference = _DEVICE_LEASES.get(device)
            if reference is not None and reference() is self:
                _DEVICE_LEASES.pop(device, None)

    @staticmethod
    def _ensure_inactive(item: _ManagedInstance) -> None:
        if (
            item.removing or item.app.closed
            or (item.future is not None and not item.future.done())
            or (item.stop_future is not None and not item.stop_future.done())
            or item.app.running
        ):
            raise RuntimeError(f"instance {item.config.name!r} is already active or being removed")

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("instance manager is closed")

    @staticmethod
    def _snapshot(item: _ManagedInstance) -> InstanceSnapshot:
        with item.lock:
            scheduler = item.app.scheduler
            failures = getattr(scheduler, "failures", ())
            current = item.app.current
            if item.state is InstanceState.FAILED:
                health = InstanceHealth.FAILED
            elif failures:
                health = InstanceHealth.DEGRADED
            elif item.state is InstanceState.CREATED:
                health = InstanceHealth.UNKNOWN
            else:
                health = InstanceHealth.HEALTHY
            return InstanceSnapshot(
                item.config.name,
                item.config.device,
                item.state,
                item.error,
                health,
                len(failures),
                current.name if current is not None else None,
            )

    @staticmethod
    def _safe_device_name(device: str, index: int) -> str:
        candidate = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", str(device)).strip(". ")
        return candidate or f"device-{index}"


__all__ = [
    "AppFactory", "InstanceConfig", "InstanceControlError", "InstanceManager",
    "InstanceHealth", "InstanceSnapshot", "InstanceState",
]
