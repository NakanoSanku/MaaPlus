from __future__ import annotations

import unittest

from maaplus import FlowContext, Match, Runner, Template


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.clicks: list[tuple[int, int, int, int]] = []
        self.hits: dict[object, Match] = {}
        self.stopped = False

    def screenshot(self) -> object:
        self.frames += 1
        return object()

    def recognize(self, locator, frame) -> Match:
        return self.hits.get(locator, Match(False))

    def click(self, box) -> bool:
        self.clicks.append(box)
        return True

    def stop(self) -> None:
        self.stopped = True


class FlowContextTests(unittest.TestCase):
    def test_find_calls_share_one_frame_until_action(self) -> None:
        runtime = FakeRuntime()
        first = Template("first.png")
        second = Template("second.png")
        runtime.hits[first] = Match(True, (10, 20, 30, 40), 0.95)
        runtime.hits[second] = Match(True, (50, 60, 20, 20), 0.90)
        ctx = FlowContext(runtime)

        self.assertTrue(ctx.find(first))
        self.assertTrue(ctx.find(second))
        self.assertEqual(runtime.frames, 1)

        self.assertTrue(ctx.find(first).click())
        self.assertEqual(runtime.clicks, [(10, 20, 30, 40)])

        self.assertTrue(ctx.find(second))
        self.assertEqual(runtime.frames, 2)

    def test_click_on_miss_is_false(self) -> None:
        runtime = FakeRuntime()
        ctx = FlowContext(runtime)

        self.assertFalse(ctx.find(Template("missing.png")).click())
        self.assertEqual(runtime.clicks, [])

    def test_click_without_box_is_false(self) -> None:
        runtime = FakeRuntime()
        locator = Template("no-box.png")
        runtime.hits[locator] = Match(True)
        ctx = FlowContext(runtime)

        self.assertFalse(ctx.find(locator).click())
        self.assertEqual(runtime.clicks, [])


class RunnerTests(unittest.TestCase):
    def test_runner_executes_flow_and_can_stop(self) -> None:
        runtime = FakeRuntime()

        def flow(ctx: FlowContext) -> str:
            ctx.screenshot()
            return "ok"

        runner = Runner(runtime)
        self.assertEqual(runner.run(flow), "ok")
        runner.stop()
        self.assertTrue(runtime.stopped)


if __name__ == "__main__":
    unittest.main()
