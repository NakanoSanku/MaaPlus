from __future__ import annotations

import time
import unittest
from types import SimpleNamespace

from maaplus import (
    DONE,
    ExecutionContext,
    NavigationError,
    NavigationState,
    Scheduler,
    Task,
    TaskResult,
    TaskStatus,
    routed,
)


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.stopped = False

    def screenshot(self):
        self.frames += 1
        return object()

    def stop(self):
        self.stopped = True


class RecoveryTests(unittest.TestCase):
    def test_handler_exception_retries_then_allows_other_tasks_to_run(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        attempts = 0
        ran_other = False

        def flaky(tick):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary")
            return DONE

        def other(tick):
            nonlocal ran_other
            ran_other = True
            return DONE

        flaky_task = Task("flaky", flaky, priority=10, retries=1)
        scheduler.submit(flaky_task)
        scheduler.submit(Task("other", other, priority=1))
        scheduler.run()

        self.assertEqual(attempts, 2)
        self.assertTrue(ran_other)
        self.assertIsNone(scheduler.failure(flaky_task))

    def test_exhausted_failure_is_retained_without_stopping_scheduler(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        task = Task("broken", lambda tick: (_ for _ in ()).throw(ValueError("bad")))
        good = Task("good", lambda tick: DONE)
        scheduler.submit(task)
        scheduler.submit(good)
        scheduler.run()

        failure = scheduler.failure(task)
        self.assertIsNotNone(failure)
        self.assertIsInstance(failure.error, ValueError)
        self.assertEqual(failure.attempts, 1)
        self.assertEqual(runtime.frames, 2)

    def test_execution_timeout_becomes_task_failure(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)

        def slow(tick):
            time.sleep(0.003)
            return DONE

        task = Task("slow", slow, timeout=1)
        scheduler.submit(task)
        scheduler.run()

        self.assertIsNotNone(scheduler.failure(task))
        self.assertEqual(scheduler.failure(task).attempts, 1)

    def test_each_periodic_run_gets_fresh_execution_context(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        contexts: list[ExecutionContext] = []

        def handler(tick):
            assert tick.context is not None
            contexts.append(tick.context)
            if len(contexts) == 2:
                scheduler.stop()
            return DONE

        scheduler.every(Task("periodic", handler), interval=1)
        scheduler.run()

        self.assertEqual(len(contexts), 2)
        self.assertIsNot(contexts[0], contexts[1])

    def test_structured_navigation_failure_is_terminal(self) -> None:
        class Navigator:
            def ensure(self, target, tick):
                return NavigationState.FAILED

        handler = routed(lambda tick: DONE, target="battle", navigator=Navigator())
        with self.assertRaises(NavigationError):
            handler(SimpleNamespace(context=None))

    def test_navigation_can_yield_while_waiting(self) -> None:
        class Navigator:
            def ensure(self, target, tick):
                return NavigationState.WAITING

        handler = routed(
            lambda tick: DONE,
            target="battle",
            navigator=Navigator(),
            yield_on_wait=True,
        )
        self.assertIs(
            handler(SimpleNamespace(context=ExecutionContext("navigation"))),
            TaskResult.YIELD,
        )

    def test_task_status_summary_and_resume(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        calls = 0

        def broken(tick):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("bad")
            return DONE

        task = Task("recoverable", broken)
        scheduler.submit(task)
        scheduler.run()
        self.assertEqual(scheduler.status(task), TaskStatus.FAILED)
        self.assertEqual(scheduler.last_execution(task).status, TaskStatus.FAILED)
        scheduler.resume_task(task)
        scheduler.run()
        self.assertEqual(scheduler.status(task), TaskStatus.DONE)
        self.assertEqual(scheduler.last_execution(task).result, DONE)

    def test_terminal_periodic_failure_pauses_until_resumed(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        calls = 0

        def broken(tick):
            nonlocal calls
            calls += 1
            scheduler.stop()
            return (_ for _ in ()).throw(ValueError("bad"))

        task = Task("periodic-broken", broken)
        scheduler.every(task, interval=1)

        scheduler.run()
        self.assertEqual(calls, 1)
        self.assertEqual(scheduler.status(task), TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
