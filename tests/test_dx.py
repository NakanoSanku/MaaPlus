from __future__ import annotations

import unittest

from maaplus import App, CONTINUE, DONE, YIELD, Scheduler, TaskHandler, TaskResult, Tick


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.stopped = False

    def screenshot(self):
        self.frames += 1
        return object()

    def match(self, locator, image):
        return locator, image

    def click(self, point, duration=50) -> bool:
        return True

    def swipe(self, points, duration) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True


class FakeNavigator:
    def __init__(self, current: str) -> None:
        self.current = current
        self.transitions: list[tuple[str, str]] = []
        self.images: list[object] = []

    def ensure(self, target: str, tick: Tick) -> bool:
        self.images.append(tick.image)
        if self.current == target:
            return True
        self.transitions.append((self.current, target))
        self.current = target
        return False


class TickTests(unittest.TestCase):
    def test_tick_match_uses_fixed_snapshot(self) -> None:
        runtime = FakeRuntime()
        image = object()
        tick = Tick(runtime=runtime, image=image)

        locator = object()
        passed_locator, passed_image = tick.match(locator)  # type: ignore[arg-type]

        self.assertIs(passed_locator, locator)
        self.assertIs(passed_image, image)

    def test_short_result_aliases_are_task_results(self) -> None:
        self.assertIs(CONTINUE, TaskResult.CONTINUE)
        self.assertIs(YIELD, TaskResult.YIELD)
        self.assertIs(DONE, TaskResult.DONE)

    def test_task_handler_type_accepts_tick_callable(self) -> None:
        handler: TaskHandler = lambda tick: DONE
        self.assertIs(handler(Tick(FakeRuntime(), object())), DONE)


class AppTests(unittest.TestCase):
    def test_app_task_submit_runs_handler(self) -> None:
        runtime = FakeRuntime()
        app = App(Scheduler(runtime))
        seen: list[Tick] = []

        app.task("simple", lambda tick: seen.append(tick) or DONE).submit()
        app.run()

        self.assertEqual(len(seen), 1)
        self.assertEqual(runtime.frames, 1)
        self.assertIs(seen[0].runtime, runtime)

    def test_context_requires_navigator(self) -> None:
        app = App(Scheduler(FakeRuntime()))

        with self.assertRaisesRegex(ValueError, "context requires"):
            app.task("routed", lambda tick: DONE, context="draw")

    def test_routed_task_skips_navigation_while_it_owns_context(self) -> None:
        runtime = FakeRuntime()
        navigator = FakeNavigator("explore")
        app = App(Scheduler(runtime), navigator=navigator)
        calls = 0

        def handler(tick):
            nonlocal calls
            calls += 1
            if calls == 1:
                # The task owns internal screens after activation; Navigator
                # must not pull it back to the public scene on the next tick.
                navigator.current = "battle"
            return CONTINUE if calls == 1 else DONE

        app.task("explore", handler, context="explore").submit()
        app.run()

        self.assertEqual(calls, 2)
        self.assertEqual(len(navigator.images), 1)
        self.assertEqual(navigator.transitions, [])

    def test_task_handle_every_delegates_to_scheduler(self) -> None:
        runtime = FakeRuntime()
        app = App(Scheduler(runtime))
        ticks = 0

        def handler(tick: Tick):
            nonlocal ticks
            ticks += 1
            if ticks == 2:
                app.stop()
            return DONE

        app.task("periodic", handler).every(1)
        app.run()

        self.assertEqual(ticks, 2)
        self.assertTrue(runtime.stopped)

    def test_task_handle_cancel_stops_a_recurring_task(self) -> None:
        runtime = FakeRuntime()
        app = App.from_runtime(runtime)
        calls = 0
        handle = None

        def handler(tick: Tick):
            nonlocal calls
            calls += 1
            assert handle is not None
            handle.cancel()
            return YIELD

        handle = app.task("periodic", handler).every(1)
        app.run()

        self.assertEqual(calls, 1)
        self.assertFalse(app.running)

    def test_task_handle_cancel_removes_future_trigger(self) -> None:
        runtime = FakeRuntime()
        app = App.from_runtime(runtime)
        handle = app.task("future", lambda tick: DONE).after(100)

        self.assertTrue(handle.cancel())
        app.run()
        self.assertEqual(runtime.frames, 0)

    def test_task_rejects_invalid_identity(self) -> None:
        with self.assertRaises(ValueError):
            from maaplus import Task

            Task("", lambda tick: DONE)

        with self.assertRaises(TypeError):
            from maaplus import Task

            Task("invalid", lambda tick: DONE, priority=True)

    def test_preempting_task_routes_and_suspended_task_restores_context(self) -> None:
        runtime = FakeRuntime()
        navigator = FakeNavigator("explore")
        app = App(Scheduler(runtime), navigator=navigator)
        order: list[str] = []
        explore_ticks = 0

        draw = app.task(
            "draw",
            lambda tick: order.append("draw") or DONE,
            context="draw",
            priority=100,
        )

        def explore_handler(tick: Tick):
            nonlocal explore_ticks
            explore_ticks += 1
            order.append(f"explore-{explore_ticks}")
            if explore_ticks == 1:
                draw.submit()
                return YIELD
            return DONE

        app.task(
            "explore",
            explore_handler,
            context="explore",
            priority=10,
        ).submit()

        app.run()

        self.assertEqual(order, ["explore-1", "draw", "explore-2"])
        self.assertEqual(
            navigator.transitions,
            [("explore", "draw"), ("draw", "explore")],
        )
        self.assertEqual(runtime.frames, 5)


if __name__ == "__main__":
    unittest.main()
