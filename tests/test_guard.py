from __future__ import annotations

import unittest
from threading import Event, Thread

from maaplus import (
    Guard,
    GuardAbortError,
    GuardLoopError,
    GuardResult,
    Scheduler,
    Task,
    DONE,
    CONTINUE,
)


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0

    def screenshot(self):
        self.frames += 1
        return object()

    def stop(self) -> None:
        pass


class GuardTests(unittest.TestCase):
    def test_handled_guard_runs_before_handler_and_discards_stale_tick(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        guard_calls = 0
        handler_calls = 0

        def notice_guard(tick):
            nonlocal guard_calls
            guard_calls += 1
            return GuardResult.HANDLED if guard_calls == 1 else GuardResult.IGNORE

        def task_handler(tick):
            nonlocal handler_calls
            handler_calls += 1
            return DONE

        scheduler.add_guard(Guard("notice", notice_guard))
        scheduler.submit(Task("work", task_handler))
        scheduler.run()

        self.assertEqual(runtime.frames, 2)
        self.assertEqual(guard_calls, 2)
        self.assertEqual(handler_calls, 1)

    def test_guard_runs_even_while_current_task_keeps_ownership(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        guard_calls = 0
        handler_calls = 0

        def notice_guard(tick):
            nonlocal guard_calls
            guard_calls += 1
            return GuardResult.HANDLED if guard_calls == 2 else GuardResult.IGNORE

        def task_handler(tick):
            nonlocal handler_calls
            handler_calls += 1
            return CONTINUE if handler_calls == 1 else DONE

        scheduler.add_guard(Guard("notice", notice_guard))
        scheduler.submit(Task("work", task_handler))
        scheduler.run()

        self.assertEqual(guard_calls, 3)
        self.assertEqual(handler_calls, 2)

    def test_invalidate_guard_forces_route_on_next_tick(self) -> None:
        from maaplus import App

        runtime = FakeRuntime()
        app = App.from_runtime(runtime)
        guard_calls = 0
        route_calls = 0
        handler_calls = 0

        class Navigator:
            def ensure(self, target, tick):
                nonlocal route_calls
                route_calls += 1
                return True

        app.navigator = Navigator()

        def guard_handler(tick):
            nonlocal guard_calls
            guard_calls += 1
            if guard_calls == 2:
                return GuardResult.INVALIDATE
            return GuardResult.IGNORE

        def task_handler(tick):
            nonlocal handler_calls
            handler_calls += 1
            return CONTINUE if handler_calls < 3 else DONE

        app.guard("scene-reset", guard_handler)
        app.task("work", task_handler, context="scene").submit()
        app.run()

        self.assertEqual(route_calls, 2)
        self.assertEqual(handler_calls, 3)

    def test_guard_loop_becomes_task_failure(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        scheduler.add_guard(Guard("stuck", lambda tick: True, max_consecutive=2))
        task = Task("work", lambda tick: DONE)

        scheduler.submit(task)
        scheduler.run()

        self.assertIsInstance(scheduler.failure(task).error, GuardLoopError)

    def test_abort_guard_becomes_task_failure(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        scheduler.add_guard(Guard("fatal", lambda tick: GuardResult.ABORT))
        task = Task("work", lambda tick: DONE)

        scheduler.submit(task)
        scheduler.run()

        self.assertIsInstance(scheduler.failure(task).error, GuardAbortError)

    def test_guard_cadence_and_cooldown_skip_expensive_checks(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        guard_calls = 0
        handler_calls = 0

        def notice_guard(tick):
            nonlocal guard_calls
            guard_calls += 1
            return GuardResult.HANDLED

        def task_handler(tick):
            nonlocal handler_calls
            handler_calls += 1
            return CONTINUE if handler_calls == 1 else DONE

        scheduler.add_guard(Guard("notice", notice_guard, cadence=10_000, cooldown=10_000))
        scheduler.submit(Task("work", task_handler))
        scheduler.run()

        self.assertEqual(guard_calls, 1)
        self.assertEqual(handler_calls, 2)

    def test_idle_watch_runs_guards_without_tasks(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        checked = Event()
        scheduler.add_guard(Guard("notice", lambda tick: checked.set() or GuardResult.IGNORE))
        scheduler.watch_idle(10)
        worker = Thread(target=scheduler.run, daemon=True)
        worker.start()
        self.assertTrue(checked.wait(1))
        scheduler.stop()
        worker.join(1)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
