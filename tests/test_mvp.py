from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from threading import Event, Thread
from types import SimpleNamespace

from maa.pipeline import JOCR, JFeatureMatch, JRecognitionType, JTemplateMatch
from maaplus import MatchResult, OCR, Runtime, Scheduler, Task, TaskResult, Template, Tick, point, routed


def make_match(hit: bool, box=None, click_area=None) -> MatchResult:
    return MatchResult(SimpleNamespace(hit=hit, box=box), click_area)


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.matches: list[tuple[object, object]] = []
        self.clicks: list[tuple[tuple[int, int], int]] = []
        self.hits: dict[int, tuple[bool, object]] = {}
        self.stopped = False

    def screenshot(self) -> object:
        self.frames += 1
        return object()

    def match(self, locator, image) -> MatchResult:
        self.matches.append((locator, image))
        hit, box = self.hits.get(id(locator), (False, None))
        return make_match(hit, box, self.click_area)

    def click_area(
        self,
        area,
        resolver=None,
        duration=None,
        *,
        pre_delay=None,
        post_delay=None,
    ) -> bool:
        resolved_point = (resolver or point.center)(area)
        return self.click(resolved_point, 50 if duration is None else duration)

    def click(self, point, duration=50) -> bool:
        self.clicks.append((point, duration))
        return True

    def swipe(self, points, duration) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True


class FakeNavigator:
    def __init__(self, current: str) -> None:
        self.current = current
        self.transitions: list[tuple[str, str]] = []

    def ensure(self, target: str, tick: Tick) -> bool:
        if self.current == target:
            return True
        self.transitions.append((self.current, target))
        self.current = target
        return False


class FakeJob:
    succeeded = True

    def wait(self):
        return self


class FakeController:
    def __init__(self) -> None:
        self.events: list[tuple] = []

    def post_touch_down(self, x, y):
        self.events.append(("down", x, y))
        return FakeJob()

    def post_touch_move(self, x, y):
        self.events.append(("move", x, y))
        return FakeJob()

    def post_touch_up(self):
        self.events.append(("up",))
        return FakeJob()


class FakeRecognitionJob(FakeJob):
    def __init__(self, recognition) -> None:
        self.task_detail = SimpleNamespace(nodes=[SimpleNamespace(recognition=recognition)])

    def get(self):
        return self.task_detail


class FakeTasker:
    running = False

    def __init__(self, recognition) -> None:
        self.recognition = recognition
        self.calls: list[tuple[object, object, object]] = []

    def post_recognition(self, recognition_type, param, image):
        self.calls.append((recognition_type, param, image))
        return FakeRecognitionJob(self.recognition)


class RecognitionParamTests(unittest.TestCase):
    def test_common_aliases_are_native_maa_classes(self) -> None:
        self.assertIs(Template, JTemplateMatch)
        self.assertIs(OCR, JOCR)

    def test_runtime_passes_template_param_through_without_rebuilding(self) -> None:
        detail = SimpleNamespace(hit=True, box=(1, 2, 3, 4))
        tasker = FakeTasker(detail)
        runtime = Runtime(tasker=tasker, controller=FakeController())
        image = object()
        locator = Template(
            template=["button.png"],
            threshold=[0.85],
            roi_offset=(1, 2, 3, 4),
        )

        result = runtime.match(locator, image)

        recognition_type, param, passed_image = tasker.calls[0]
        self.assertEqual(recognition_type, JRecognitionType.TemplateMatch)
        self.assertIs(param, locator)
        self.assertIs(passed_image, image)
        self.assertIs(result.detail, detail)

    def test_runtime_preserves_ocr_specific_fields(self) -> None:
        detail = SimpleNamespace(hit=False, box=None)
        tasker = FakeTasker(detail)
        runtime = Runtime(tasker=tasker, controller=FakeController())
        locator = OCR(
            expected=["确认"],
            replace=[["確認", "确认"]],
            color_filter="white_text",
        )

        runtime.match(locator, object())

        recognition_type, param, _ = tasker.calls[0]
        self.assertEqual(recognition_type, JRecognitionType.OCR)
        self.assertIs(param, locator)
        self.assertEqual(param.replace, [["確認", "确认"]])
        self.assertEqual(param.color_filter, "white_text")

    def test_runtime_accepts_other_maa_recognition_params(self) -> None:
        detail = SimpleNamespace(hit=False, box=None)
        tasker = FakeTasker(detail)
        runtime = Runtime(tasker=tasker, controller=FakeController())
        locator = JFeatureMatch(template=["feature.png"])

        runtime.match(locator, object())

        recognition_type, param, _ = tasker.calls[0]
        self.assertEqual(recognition_type, JRecognitionType.FeatureMatch)
        self.assertIs(param, locator)


class TaskHandlerTests(unittest.TestCase):
    def test_scheduler_invokes_handler_with_one_fixed_tick_snapshot(self) -> None:
        runtime = FakeRuntime()
        first = Template(template=["first.png"])
        second = Template(template=["second.png"])
        runtime.hits[id(first)] = (True, (10, 20, 30, 40))
        runtime.hits[id(second)] = (True, (50, 60, 20, 20))
        scheduler = Scheduler(runtime)
        seen_tick: Tick | None = None

        def handler(tick: Tick) -> TaskResult:
            nonlocal seen_tick
            seen_tick = tick
            first_result = tick.match(first)
            second_result = tick.match(second)
            self.assertTrue(first_result)
            self.assertTrue(second_result)
            first_result.click()
            tick.match(second)
            return TaskResult.DONE

        task = Task("snapshot", handler)
        self.assertIs(scheduler.tick(task), TaskResult.DONE)
        self.assertEqual(runtime.frames, 1)
        self.assertIsNotNone(seen_tick)
        self.assertTrue(all(image is seen_tick.image for _, image in runtime.matches))
        self.assertEqual(runtime.clicks, [((25, 40), 50)])

    def test_scheduler_rejects_non_task_result(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        task = Task("legacy", lambda tick: True)  # type: ignore[arg-type]

        with self.assertRaisesRegex(TypeError, "handler must return TaskResult"):
            scheduler.tick(task)

    def test_task_exposes_handler_not_flow(self) -> None:
        handler = lambda tick: TaskResult.DONE
        task = Task("handler", handler)

        self.assertIs(task.handler, handler)
        self.assertFalse(hasattr(task, "flow"))

    def test_custom_click_resolver_and_duration(self) -> None:
        runtime = FakeRuntime()
        locator = Template(template=["button.png"])
        runtime.hits[id(locator)] = (True, (10, 20, 30, 40))
        image = runtime.screenshot()

        def bottom_right(area: tuple[int, int, int, int]) -> tuple[int, int]:
            x, y, width, height = area
            return x + width - 1, y + height - 1

        self.assertTrue(runtime.match(locator, image).click(bottom_right, duration=120))
        self.assertEqual(runtime.clicks, [((39, 59), 120)])

    def test_match_result_keeps_original_detail(self) -> None:
        detail = SimpleNamespace(hit=True, box=(1, 2, 3, 4), raw_detail={"foo": "bar"})
        result = MatchResult(detail)

        self.assertIs(result.detail, detail)
        self.assertEqual(result.box, (1, 2, 3, 4))


class RuntimeGestureTests(unittest.TestCase):
    def test_click_is_touch_down_hold_up(self) -> None:
        controller = FakeController()
        runtime = Runtime(tasker=SimpleNamespace(running=False), controller=controller)

        self.assertTrue(runtime.click((100, 200), 0))
        self.assertEqual(controller.events, [("down", 100, 200), ("up",)])

    def test_swipe_follows_path_with_touch_moves(self) -> None:
        controller = FakeController()
        runtime = Runtime(tasker=SimpleNamespace(running=False), controller=controller)

        self.assertTrue(runtime.swipe([(0, 0), (10, 20), (30, 40)], 0))
        self.assertEqual(
            controller.events,
            [
                ("down", 0, 0),
                ("move", 10, 20),
                ("move", 30, 40),
                ("up",),
            ],
        )

    def test_swipe_requires_two_points(self) -> None:
        runtime = Runtime(tasker=SimpleNamespace(running=False), controller=FakeController())

        with self.assertRaises(ValueError):
            runtime.swipe([(0, 0)], 100)


class RoutedTaskHandlerTests(unittest.TestCase):
    def test_routed_handler_navigates_before_business_handler(self) -> None:
        runtime = FakeRuntime()
        navigator = FakeNavigator("explore")
        calls: list[str] = []
        handler = routed(
            lambda tick: calls.append("draw") or TaskResult.DONE,
            target="draw",
            navigator=navigator,
        )

        self.assertIs(handler(Tick(runtime, object())), TaskResult.CONTINUE)
        self.assertEqual(calls, [])
        self.assertEqual(navigator.transitions, [("explore", "draw")])

        self.assertIs(handler(Tick(runtime, object())), TaskResult.DONE)
        self.assertEqual(calls, ["draw"])

    def test_scheduler_routes_preempting_and_restored_task_handlers(self) -> None:
        runtime = FakeRuntime()
        navigator = FakeNavigator("explore")
        scheduler = Scheduler(runtime)
        order: list[str] = []
        explore_ticks = 0

        draw = Task(
            "draw",
            routed(
                lambda tick: order.append("draw") or TaskResult.DONE,
                target="draw",
                navigator=navigator,
            ),
            priority=100,
        )

        def explore_handler(tick: Tick) -> TaskResult:
            nonlocal explore_ticks
            explore_ticks += 1
            order.append(f"explore-{explore_ticks}")
            if explore_ticks == 1:
                scheduler.submit(draw)
                return TaskResult.YIELD
            return TaskResult.DONE

        explore = Task(
            "explore",
            routed(explore_handler, target="explore", navigator=navigator),
            priority=10,
        )

        scheduler.submit(explore)
        scheduler.run()

        self.assertEqual(order, ["explore-1", "draw", "explore-2"])
        self.assertEqual(
            navigator.transitions,
            [("explore", "draw"), ("draw", "explore")],
        )
        self.assertEqual(runtime.frames, 5)


class SchedulerTests(unittest.TestCase):
    def test_highest_priority_ready_task_runs_first(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        order: list[str] = []

        scheduler.submit(
            Task("low", lambda tick: order.append("low") or TaskResult.DONE, priority=10)
        )
        scheduler.submit(
            Task("high", lambda tick: order.append("high") or TaskResult.DONE, priority=100)
        )
        scheduler.run()

        self.assertEqual(order, ["high", "low"])
        self.assertEqual(runtime.frames, 2)

    def test_higher_priority_task_preempts_after_explicit_yield_and_resumes(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        order: list[str] = []
        low_ticks = 0

        high = Task(
            "high",
            lambda tick: order.append("high") or TaskResult.DONE,
            priority=100,
        )

        def low_handler(tick: Tick) -> TaskResult:
            nonlocal low_ticks
            low_ticks += 1
            order.append(f"low-{low_ticks}")
            if low_ticks == 1:
                scheduler.submit(high)
                return TaskResult.YIELD
            return TaskResult.DONE

        low = Task("low", low_handler, priority=10)
        scheduler.submit(low)
        scheduler.run()

        self.assertEqual(order, ["low-1", "high", "low-2"])
        self.assertEqual(runtime.frames, 3)
        self.assertIsNone(scheduler.current)

    def test_higher_priority_task_waits_until_current_reaches_safe_yield_point(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        order: list[str] = []
        battle_ticks = 0

        high = Task(
            "timed",
            lambda tick: order.append("timed") or TaskResult.DONE,
            priority=100,
        )

        def battle_handler(tick: Tick) -> TaskResult:
            nonlocal battle_ticks
            battle_ticks += 1
            order.append(f"battle-{battle_ticks}")
            if battle_ticks == 1:
                scheduler.submit(high)
                return TaskResult.CONTINUE
            if battle_ticks == 2:
                return TaskResult.YIELD
            return TaskResult.DONE

        scheduler.submit(Task("battle", battle_handler, priority=10))
        scheduler.run()

        self.assertEqual(order, ["battle-1", "battle-2", "timed", "battle-3"])
        self.assertEqual(runtime.frames, 4)

    def test_due_after_task_preempts_current_task_after_yield(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        order: list[str] = []
        normal_ticks = 0

        timed = Task(
            "timed",
            lambda tick: order.append("timed") or TaskResult.DONE,
            priority=100,
        )

        def normal_handler(tick: Tick) -> TaskResult:
            nonlocal normal_ticks
            normal_ticks += 1
            order.append(f"normal-{normal_ticks}")
            if normal_ticks == 1:
                scheduler.after(timed, delay=0)
                return TaskResult.YIELD
            return TaskResult.DONE

        scheduler.submit(Task("normal", normal_handler, priority=10))
        scheduler.run()

        self.assertEqual(order, ["normal-1", "timed", "normal-2"])

    def test_at_runs_wall_clock_task(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        ran = Event()
        task = Task("at", lambda tick: ran.set() or TaskResult.DONE)

        scheduler.at(task, when=datetime.now() + timedelta(milliseconds=10))
        scheduler.run()

        self.assertTrue(ran.is_set())
        self.assertEqual(runtime.frames, 1)

    def test_every_runs_repeatedly_until_stopped(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        ticks = 0

        def handler(tick: Tick) -> TaskResult:
            nonlocal ticks
            ticks += 1
            if ticks == 3:
                scheduler.stop()
            return TaskResult.DONE

        scheduler.every(Task("periodic", handler), interval=1)
        scheduler.run()

        self.assertEqual(ticks, 3)
        self.assertEqual(runtime.frames, 3)
        self.assertTrue(runtime.stopped)

    def test_repeated_requests_for_same_task_coalesce_to_one_pending_execution(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        runs = 0

        def handler(tick: Tick) -> TaskResult:
            nonlocal runs
            runs += 1
            return TaskResult.DONE

        task = Task("coalesced", handler)
        scheduler.submit(task)
        scheduler.submit(task)
        scheduler.submit(task)
        scheduler.run()

        self.assertEqual(runs, 2)
        self.assertEqual(runtime.frames, 2)

    def test_equal_or_lower_priority_does_not_preempt_yielded_current_task(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        order: list[str] = []
        primary_ticks = 0

        equal = Task(
            "equal",
            lambda tick: order.append("equal") or TaskResult.DONE,
            priority=10,
        )

        def primary_handler(tick: Tick) -> TaskResult:
            nonlocal primary_ticks
            primary_ticks += 1
            order.append(f"primary-{primary_ticks}")
            if primary_ticks == 1:
                scheduler.submit(equal)
                return TaskResult.YIELD
            return TaskResult.DONE

        scheduler.submit(Task("primary", primary_handler, priority=10))
        scheduler.run()

        self.assertEqual(order, ["primary-1", "primary-2", "equal"])

    def test_future_after_task_keeps_scheduler_alive_until_due(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        ran = Event()
        task = Task("future", lambda tick: ran.set() or TaskResult.DONE, priority=10)

        scheduler.after(task, delay=10)
        scheduler.run()

        self.assertTrue(ran.is_set())
        self.assertEqual(runtime.frames, 1)

    def test_pause_blocks_before_next_handler_and_resume_continues(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        pause_requested = Event()
        ticks = 0

        def handler(tick: Tick) -> TaskResult:
            nonlocal ticks
            ticks += 1
            if ticks == 1:
                scheduler.pause()
                pause_requested.set()
                return TaskResult.CONTINUE
            return TaskResult.DONE

        scheduler.submit(Task("pause", handler))
        thread = Thread(target=scheduler.run, daemon=True)
        thread.start()

        self.assertTrue(pause_requested.wait(1))
        self.assertTrue(scheduler.running)
        self.assertTrue(scheduler.paused)
        self.assertEqual(runtime.frames, 1)

        scheduler.resume()
        thread.join(1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(ticks, 2)
        self.assertEqual(runtime.frames, 2)
        self.assertFalse(scheduler.running)
        self.assertFalse(scheduler.paused)

    def test_stop_exits_while_paused(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        pause_requested = Event()

        def handler(tick: Tick) -> TaskResult:
            scheduler.pause()
            pause_requested.set()
            return TaskResult.CONTINUE

        scheduler.submit(Task("pause", handler))
        thread = Thread(target=scheduler.run, daemon=True)
        thread.start()

        self.assertTrue(pause_requested.wait(1))
        scheduler.stop()
        thread.join(1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(runtime.frames, 1)
        self.assertTrue(runtime.stopped)
        self.assertFalse(scheduler.running)
        self.assertFalse(scheduler.paused)

    def test_stop_interrupts_interval_wait(self) -> None:
        runtime = FakeRuntime()
        scheduler = Scheduler(runtime)
        first_tick = Event()

        def handler(tick: Tick) -> TaskResult:
            first_tick.set()
            return TaskResult.CONTINUE

        scheduler.submit(Task("loop", handler))
        thread = Thread(target=scheduler.run, kwargs={"interval": 60_000}, daemon=True)
        thread.start()

        self.assertTrue(first_tick.wait(1))
        scheduler.stop()
        thread.join(1)

        self.assertFalse(thread.is_alive())
        self.assertEqual(runtime.frames, 1)

    def test_invalid_trigger_and_run_intervals_are_rejected(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        task = Task("noop", lambda tick: TaskResult.DONE)

        with self.assertRaises(ValueError):
            scheduler.after(task, delay=-1)
        with self.assertRaises(ValueError):
            scheduler.every(task, interval=0)
        with self.assertRaises(ValueError):
            scheduler.run(interval=-1)

    def test_scheduler_rejects_reentrant_run(self) -> None:
        scheduler = Scheduler(FakeRuntime())

        def handler(tick: Tick) -> TaskResult:
            with self.assertRaises(RuntimeError):
                scheduler.run()
            return TaskResult.DONE

        scheduler.submit(Task("reentrant", handler))
        scheduler.run()

    def test_context_manager_stops_runtime(self) -> None:
        runtime = FakeRuntime()

        with Scheduler(runtime) as scheduler:
            self.assertIs(scheduler.runtime, runtime)

        self.assertTrue(runtime.stopped)


if __name__ == "__main__":
    unittest.main()