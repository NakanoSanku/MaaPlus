from __future__ import annotations

from pathlib import Path
from threading import Event

import pytest

from maaplus import (
    App, CONTINUE, DONE, GuardResult, InstanceConfig, InstanceControlError,
    InstanceHealth, InstanceManager, InstanceState, Scheduler,
)
from maaplus.dev import TraceSession


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.stops = 0

    def screenshot(self):
        self.frames += 1
        return object()

    def stop(self) -> None:
        self.stops += 1


class ControlledApp(App):
    def __init__(self) -> None:
        super().__init__(Scheduler(FakeRuntime()))
        self.entered = Event()
        self.release = Event()
        self.initialized = Event()
        self.task("work", self.work).submit()

    def work(self, tick):
        self.entered.set()
        self.release.wait(3)
        return DONE if self.release.is_set() else CONTINUE

    def run(self, *, interval=0, on_started=None):
        def started():
            if on_started is not None:
                on_started()
            self.initialized.set()

        super().run(interval=interval, on_started=started)

    def stop(self):
        super().stop()
        self.release.set()


class DelayedStartApp(ControlledApp):
    def __init__(self):
        super().__init__()
        self.before_start = Event()
        self.allow_start = Event()

    def run(self, *, interval=0, on_started=None):
        self.before_start.set()
        assert self.allow_start.wait(3)
        super().run(interval=interval, on_started=on_started)


class FailingApp(App):
    def run(self, *, interval=0, on_started=None):
        raise RuntimeError("worker failed")


def make_app(config=None):
    return App.from_runtime(FakeRuntime())


def test_factory_configs_and_device_reservations_are_isolated(tmp_path):
    configs = []

    def factory(config):
        configs.append(config)
        return make_app()

    with InstanceManager(factory, root_dir=tmp_path) as fleet:
        first, second = fleet.create_many({"alpha": "emulator-5554", "beta": "emulator-5556"})
        assert first is not second
        assert first.scheduler.runtime is not second.scheduler.runtime
        assert configs[0].debug_dir == tmp_path / "alpha" / "debug"
        assert configs[1].trace_dir == tmp_path / "beta" / "trace"
        with pytest.raises(ValueError, match="already assigned"):
            fleet.create("gamma", "emulator-5554")
        with pytest.raises(ValueError, match="already registered"):
            fleet.create("alpha", "another-device")


def test_independent_apps_run_concurrently_and_pause_separately():
    with InstanceManager(lambda config: ControlledApp(), max_workers=2) as fleet:
        first, second = fleet.create_many({"alpha": "device-a", "beta": "device-b"})
        fleet.start_all(interval=17)
        assert first.entered.wait(2)
        assert second.entered.wait(2)
        fleet.pause("alpha")
        assert first.paused
        assert not second.paused
        assert fleet.snapshot("alpha").state is InstanceState.PAUSED
        fleet.resume("alpha")
        assert not first.paused
        fleet.stop_all(timeout=2)
        assert all(item.state is InstanceState.STOPPED for item in fleet.instances)


def test_pending_stop_is_reapplied_after_scheduler_initialization():
    with InstanceManager(lambda config: DelayedStartApp()) as fleet:
        app = fleet.create("alpha", "device-a")
        fleet.start("alpha")
        assert app.before_start.wait(2)
        try:
            fleet.stop("alpha", wait=False)
            assert fleet.snapshot("alpha").state is InstanceState.STOPPING
        finally:
            app.allow_start.set()
        fleet.wait("alpha", timeout=2)
        assert app.scheduler.runtime.frames == 0
        assert fleet.snapshot("alpha").state is InstanceState.STOPPED


def test_pending_pause_prevents_first_tick_until_resumed():
    with InstanceManager(lambda config: DelayedStartApp()) as fleet:
        app = fleet.create("alpha", "device-a")
        fleet.start("alpha")
        assert app.before_start.wait(2)
        try:
            fleet.pause("alpha")
        finally:
            app.allow_start.set()
        assert app.initialized.wait(2)
        assert app.paused
        assert app.scheduler.runtime.frames == 0
        fleet.resume("alpha")
        assert app.entered.wait(2)
        fleet.stop("alpha", timeout=2)


def test_queued_run_can_be_stopped_without_later_starting():
    with InstanceManager(lambda config: ControlledApp(), max_workers=1) as fleet:
        first, second = fleet.create_many({"alpha": "device-a", "beta": "device-b"})
        fleet.start("alpha")
        assert first.entered.wait(2)
        future = fleet.start("beta")
        assert fleet.snapshot("beta").state is InstanceState.STARTING
        fleet.stop("beta", timeout=1)
        assert future.cancelled()
        fleet.wait("beta", timeout=1)
        fleet.stop("alpha", timeout=2)
        assert not second.initialized.is_set()
        assert second.scheduler.runtime.frames == 0
        assert fleet.snapshot("beta").state is InstanceState.STOPPED


def test_queued_pause_survives_worker_start():
    with InstanceManager(lambda config: ControlledApp(), max_workers=1) as fleet:
        first, second = fleet.create_many({"alpha": "device-a", "beta": "device-b"})
        fleet.start("alpha")
        assert first.entered.wait(2)
        fleet.start("beta")
        fleet.pause("beta")
        fleet.stop("alpha", timeout=2)
        assert second.initialized.wait(2)
        assert second.paused
        assert second.scheduler.runtime.frames == 0
        fleet.resume("beta")
        assert second.entered.wait(2)


def test_create_many_rollback_preserves_existing_instances():
    with InstanceManager(make_app) as fleet:
        existing = fleet.create("existing", "device-existing")
        with pytest.raises(ValueError, match="already assigned"):
            fleet.create_many({"alpha": "device-a", "beta": "device-existing"})
        assert [item.name for item in fleet.instances] == ["existing"]
        assert fleet.get("existing") is existing
        assert existing.scheduler.runtime.stops == 0


def test_worker_exception_is_observable_and_does_not_break_other_instances():
    with InstanceManager(max_workers=2) as fleet:
        fleet.register("broken", "device-a", FailingApp(Scheduler(FakeRuntime())))
        healthy = fleet.register("healthy", "device-b", make_app())
        task = healthy.task("once", lambda tick: DONE).submit()
        fleet.start_all()
        with pytest.raises(RuntimeError, match="worker failed"):
            fleet.wait("broken", timeout=2)
        fleet.wait("healthy", timeout=2)
        assert fleet.snapshot("broken").state is InstanceState.FAILED
        assert isinstance(fleet.snapshot("broken").error, RuntimeError)
        assert fleet.snapshot("healthy").state is InstanceState.STOPPED
        assert task.last_execution.error is None
    # Cleanup does not re-raise an already-observed worker exception.


def test_remove_waits_before_releasing_device():
    with InstanceManager(lambda config: ControlledApp()) as fleet:
        app = fleet.create("alpha", "device-a")
        fleet.start("alpha")
        assert app.entered.wait(2)
        with pytest.raises(ValueError, match="wait=True"):
            fleet.remove("alpha", wait=False)
        fleet.remove("alpha", timeout=2)
        assert fleet.instances == ()
        fleet.create("replacement", "device-a")


def test_remove_timeout_keeps_instance_available_for_retry():
    entered, release = Event(), Event()

    class SlowStopApp(App):
        def stop(self):
            entered.set()
            release.wait(2)

    fleet = InstanceManager()
    fleet.register("alpha", "device-a", SlowStopApp(Scheduler(FakeRuntime())))
    try:
        with pytest.raises(TimeoutError):
            fleet.remove("alpha", timeout=0.03)
        assert fleet.snapshot("alpha").state is InstanceState.STOPPED
        assert entered.wait(1)
        release.set()
        fleet.remove("alpha", timeout=2)
        assert fleet.instances == ()
    finally:
        release.set()
        fleet.close(timeout=2)


def test_shared_runtime_or_evidence_directory_is_rejected(tmp_path):
    with InstanceManager() as fleet:
        runtime = FakeRuntime()
        runtime.debug = type("DebugSink", (), {"output_dir": tmp_path})()
        fleet.register("alpha", "device-a", App.from_runtime(runtime))
        with pytest.raises(ValueError, match="Runtime is shared"):
            fleet.register("beta", "device-b", App.from_runtime(runtime))
        other = FakeRuntime()
        other.debug = type("DebugSink", (), {"output_dir": tmp_path})()
        with pytest.raises(ValueError, match="debug output is shared"):
            fleet.register("beta", "device-b", App.from_runtime(other))


def test_stop_all_requests_all_devices_before_waiting():
    releases = [Event(), Event()]
    with InstanceManager() as fleet:
        for index, name in enumerate(("alpha", "beta")):
            runtime = FakeRuntime()
            runtime.stop = releases[index].set
            app = App.from_runtime(runtime)

            def work(tick):
                assert all(event.wait(2) for event in releases)
                return DONE

            app.task("work", work).submit()
            fleet.register(name, f"device-{index}", app)
        fleet.start_all()
        fleet.stop_all(timeout=2)
        assert all(event.is_set() for event in releases)


def test_close_timeout_does_not_release_active_instance_or_allow_restart():
    entered, release = Event(), Event()
    fleet = InstanceManager(make_app)
    app = fleet.create("alpha", "device-a")

    def work(tick):
        entered.set()
        assert release.wait(3)
        return DONE

    app.task("work", work).submit()
    fleet.start("alpha")
    assert entered.wait(2)
    try:
        with pytest.raises(TimeoutError, match="has not stopped"):
            fleet.close(timeout=0)
        assert fleet.snapshot("alpha").state is InstanceState.STOPPING
        with pytest.raises(RuntimeError, match="closed"):
            fleet.start("alpha")
    finally:
        release.set()
        fleet.wait("alpha", timeout=2)
        fleet.close(timeout=2)


def test_close_timeout_bounds_a_blocking_app_stop_hook():
    entered, release = Event(), Event()

    class BlockingStopApp(App):
        def stop(self):
            entered.set()
            release.wait(2)

    fleet = InstanceManager()
    fleet.register("alpha", "device-a", BlockingStopApp(Scheduler(FakeRuntime())))
    import threading
    result = []

    def close_with_timeout():
        try:
            fleet.close(timeout=0.05)
        except BaseException as exc:
            result.append(exc)

    closer = threading.Thread(target=close_with_timeout, daemon=True)
    closer.start()
    try:
        assert entered.wait(1)
        closer.join(1)
        assert not closer.is_alive()
        assert result and isinstance(result[0], TimeoutError)
    finally:
        release.set()
        fleet.close(timeout=2)


def test_batch_stop_reports_all_control_errors():
    class StopFailureApp(App):
        def stop(self):
            raise RuntimeError("stop failed")

    fleet = InstanceManager()
    fleet.register("broken", "device-a", StopFailureApp(Scheduler(FakeRuntime())))
    healthy = fleet.register("healthy", "device-b", make_app())
    with pytest.raises(InstanceControlError) as result:
        fleet.close()
    assert set(result.value.errors) == {"broken"}
    assert healthy.scheduler.runtime.stops >= 1


def test_instance_worker_can_request_its_own_stop_without_deadlocking():
    fleet = InstanceManager(max_workers=1)
    app = make_app()
    fleet.register("alpha", "device-a", app)

    def stop_from_handler(tick):
        fleet.stop("alpha")
        return DONE

    app.task("stop", stop_from_handler).submit()
    fleet.start("alpha")
    fleet.wait("alpha", timeout=2)
    assert fleet.snapshot("alpha").state is InstanceState.STOPPED
    fleet.close()


def test_instance_worker_can_close_manager_without_deadlocking():
    fleet = InstanceManager(max_workers=1)
    app = make_app()
    fleet.register("alpha", "device-a", app)

    def close_from_handler(tick):
        fleet.close()
        return DONE

    app.task("close", close_from_handler).submit()
    future = fleet.start("alpha")
    future.result(timeout=2)
    assert fleet.snapshot("alpha").state is InstanceState.STOPPED
    for _ in range(20):
        if app.closed:
            break
        import time
        time.sleep(0.01)
    assert app.closed


def test_factory_does_not_hold_manager_lock_while_blocked(tmp_path):
    entered, release = Event(), Event()

    def factory(config):
        entered.set()
        assert release.wait(2)
        return make_app()

    fleet = InstanceManager(factory, root_dir=tmp_path)
    fleet.register("alpha", "device-a", make_app())
    import threading

    creator = threading.Thread(target=lambda: fleet.create("beta", "device-b"), daemon=True)
    creator.start()
    assert entered.wait(2)
    fleet.stop("alpha", timeout=1)
    release.set()
    creator.join(2)
    assert not creator.is_alive()
    fleet.close()


def test_device_lease_is_shared_between_managers_and_released_on_close():
    first = InstanceManager()
    second = InstanceManager()
    first.register("alpha", "device-a", make_app())
    with pytest.raises(ValueError, match="leased"):
        second.register("beta", "device-a", make_app())
    first.close()
    second.register("beta", "device-a", make_app())
    second.close()


def test_external_cancel_updates_snapshot_state():
    with InstanceManager(lambda config: ControlledApp(), max_workers=1) as fleet:
        first, second = fleet.create_many({"alpha": "device-a", "beta": "device-b"})
        fleet.start("alpha")
        assert first.entered.wait(2)
        future = fleet.start("beta")
        assert future.cancel()
        fleet.wait("beta", timeout=1)
        assert fleet.snapshot("beta").state is InstanceState.STOPPED
        fleet.stop("alpha", timeout=2)


def test_task_failures_degrade_instance_health():
    with InstanceManager(make_app) as fleet:
        app = fleet.create("alpha", "device-a")

        def fail(tick):
            raise ValueError("bad task")

        app.task("bad", fail).submit()
        fleet.start("alpha")
        fleet.wait("alpha", timeout=2)
        snapshot = fleet.snapshot("alpha")
        assert snapshot.state is InstanceState.STOPPED
        assert snapshot.health is InstanceHealth.DEGRADED
        assert snapshot.failed_tasks == 1


def test_manager_closes_trace_session_after_run(tmp_path):
    trace = TraceSession(tmp_path)
    fleet = InstanceManager()
    app = App.from_runtime(FakeRuntime(), trace=trace)
    app.task("once", lambda tick: DONE).submit()
    fleet.register("alpha", "device-a", app)
    fleet.start("alpha")
    fleet.wait("alpha", timeout=2)
    fleet.close()
    assert trace._closed
    assert trace.trace._closed
    assert (trace.directory / "index.json").is_file()


def test_guards_and_execution_state_do_not_leak_between_apps():
    with InstanceManager(make_app, max_workers=2) as fleet:
        first, second = fleet.create_many({"alpha": "device-a", "beta": "device-b"})
        seen = {}

        def factory(name):
            def work(tick):
                assert tick.context.state == {}
                tick.context.state["owner"] = name
                seen[name] = tick.context
                return DONE
            return work

        def notice(tick):
            return GuardResult.HANDLED if first.scheduler.runtime.frames == 1 else GuardResult.IGNORE

        first.guard("notice", notice)
        first.task("same-name", factory("alpha")).submit()
        second.task("same-name", factory("beta")).submit()
        fleet.start_all()
        fleet.wait("alpha", timeout=2)
        fleet.wait("beta", timeout=2)
        assert first.scheduler.runtime.frames == 2
        assert second.scheduler.runtime.frames == 1
        assert seen["alpha"] is not seen["beta"]


@pytest.mark.parametrize("name", ["../escape", "..", "a/b", r"a\b", "device:1234", "CON", "name."])
def test_instance_names_cannot_escape_or_conflict_with_artifact_paths(name):
    with pytest.raises(ValueError):
        InstanceConfig(name, "device-a")
