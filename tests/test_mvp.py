from __future__ import annotations

import unittest

from maaplus import Flow, FlowContext, LocatorNotFound, MatchResult, Runner, Template


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.clicks: list[tuple[int, int, int, int]] = []
        self.hits: dict[object, MatchResult] = {}
        self.stopped = False

    def screenshot(self) -> object:
        self.frames += 1
        return object()

    def recognize(self, locator, frame) -> MatchResult:
        return self.hits.get(locator, MatchResult(locator=locator, hit=False))

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
        runtime.hits[first] = MatchResult(first, True, (10, 20, 30, 40), 0.95)
        runtime.hits[second] = MatchResult(second, True, (50, 60, 20, 20), 0.90)
        ctx = FlowContext(runtime)

        self.assertTrue(ctx.find(first))
        self.assertTrue(ctx.find(second))
        self.assertEqual(runtime.frames, 1)

        self.assertTrue(ctx.find(first).click())
        self.assertEqual(runtime.clicks, [(10, 20, 30, 40)])

        self.assertTrue(ctx.find(second))
        self.assertEqual(runtime.frames, 2)

    def test_optional_click_on_miss_is_false(self) -> None:
        runtime = FakeRuntime()
        locator = Template("missing.png")
        ctx = FlowContext(runtime)

        self.assertFalse(ctx.find(locator).click())
        self.assertEqual(runtime.clicks, [])

    def test_require_raises_on_miss(self) -> None:
        runtime = FakeRuntime()
        locator = Template("required.png")
        ctx = FlowContext(runtime)

        with self.assertRaises(LocatorNotFound):
            ctx.find(locator).require()


class RunnerTests(unittest.TestCase):
    def test_runner_executes_flow_and_can_stop(self) -> None:
        runtime = FakeRuntime()

        class ExampleFlow(Flow):
            def run(self, ctx: FlowContext) -> str:
                ctx.screenshot()
                return "ok"

        runner = Runner(runtime)
        self.assertEqual(runner.run(ExampleFlow()), "ok")
        runner.stop()
        self.assertTrue(runtime.stopped)


if __name__ == "__main__":
    unittest.main()
