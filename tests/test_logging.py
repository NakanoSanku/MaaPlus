from __future__ import annotations

import unittest
from types import SimpleNamespace

from maaplus import DONE, YIELD, Runtime, Scheduler, Task, TaskResult, Template, routed


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0

    def screenshot(self):
        self.frames += 1
        return object()

    def stop(self) -> None:
        pass


class FakeNavigator:
    def __init__(self, current: str) -> None:
        self.current = current

    def ensure(self, target: str, tick) -> bool:
        if self.current == target:
            return True
        self.current = target
        return False


class FakeJob:
    def __init__(self, value=None, *, succeeded: bool = True) -> None:
        self.value = value
        self.succeeded = succeeded

    def wait(self):
        return self

    def get(self):
        return self.value


class FakeTasker:
    running = False

    def __init__(self, recognition) -> None:
        self.recognition = recognition

    def post_recognition(self, recognition_type, param, image):
        detail = SimpleNamespace(
            nodes=[SimpleNamespace(recognition=self.recognition)],
        )
        return FakeJob(detail)


class FakeController:
    def post_screencap(self):
        return FakeJob(object())

    def post_touch_down(self, x, y):
        return FakeJob()

    def post_touch_move(self, x, y):
        return FakeJob()

    def post_touch_up(self):
        return FakeJob()


class SchedulerLoggingTests(unittest.TestCase):
    def test_scheduler_logs_preemption_and_resume_lifecycle(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        low_ticks = 0

        high = Task("high", lambda tick: DONE, priority=100)

        def low_handler(tick):
            nonlocal low_ticks
            low_ticks += 1
            if low_ticks == 1:
                scheduler.submit(high)
                return YIELD
            return DONE

        low = Task("low", low_handler, priority=10)

        with self.assertLogs("maaplus.scheduler", level="INFO") as captured:
            scheduler.submit(low)
            scheduler.run()

        output = "\n".join(captured.output)
        self.assertIn("task requested task=low", output)
        self.assertIn("task started task=low priority=10", output)
        self.assertIn("task preempted task=low priority=10 by=high priority=100", output)
        self.assertIn("task completed task=high", output)
        self.assertIn("task resumed task=low priority=10", output)
        self.assertIn("task completed task=low", output)

    def test_handler_result_is_debug_logged(self) -> None:
        scheduler = Scheduler(FakeRuntime())
        task = Task("simple", lambda tick: TaskResult.DONE)

        with self.assertLogs("maaplus.scheduler", level="DEBUG") as captured:
            scheduler.tick(task)

        output = "\n".join(captured.output)
        self.assertIn("handler result task=simple result=DONE", output)
        self.assertIn("handler_ms=", output)
        self.assertIn("tick_ms=", output)


class RuntimeLoggingTests(unittest.TestCase):
    def test_recognition_debug_log_contains_result_and_duration(self) -> None:
        recognition = SimpleNamespace(hit=True, box=(10, 20, 30, 40))
        runtime = Runtime(
            tasker=FakeTasker(recognition),
            controller=FakeController(),
        )
        locator = Template(template=["button.png"])

        with self.assertLogs("maaplus.runtime.recognition", level="DEBUG") as captured:
            result = runtime.match(locator, object())

        self.assertTrue(result)
        output = "\n".join(captured.output)
        self.assertIn("recognition type=TemplateMatch", output)
        self.assertIn("hit=True", output)
        self.assertIn("box=(10, 20, 30, 40)", output)
        self.assertIn("elapsed_ms=", output)

    def test_screenshot_is_debug_logged(self) -> None:
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=FakeController(),
        )

        with self.assertLogs("maaplus.runtime", level="DEBUG") as captured:
            runtime.screenshot()

        self.assertTrue(any("screenshot captured elapsed_ms=" in line for line in captured.output))

    def test_click_log_contains_resolved_interaction_timing(self) -> None:
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=FakeController(),
        )

        with self.assertLogs("maaplus.runtime.controller", level="DEBUG") as captured:
            runtime.click((10, 20), duration=0, pre_delay=0, post_delay=0)

        output = "\n".join(captured.output)
        self.assertIn("click point=(10, 20)", output)
        self.assertIn("duration_ms=0", output)
        self.assertIn("pre_delay_ms=0", output)
        self.assertIn("post_delay_ms=0", output)


class RoutingLoggingTests(unittest.TestCase):
    def test_routing_logs_pending_then_ready(self) -> None:
        navigator = FakeNavigator("explore")
        handler = routed(
            lambda tick: DONE,
            target="draw",
            navigator=navigator,
        )
        tick = SimpleNamespace()

        with self.assertLogs("maaplus.routing", level="DEBUG") as captured:
            self.assertIs(handler(tick), TaskResult.CONTINUE)
            self.assertIs(handler(tick), TaskResult.DONE)

        output = "\n".join(captured.output)
        self.assertIn("context pending target='draw'", output)
        self.assertIn("context ready target='draw'", output)


if __name__ == "__main__":
    unittest.main()
