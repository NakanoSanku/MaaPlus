from __future__ import annotations

import unittest
from types import SimpleNamespace

from maaplus import FlowContext, MatchResult, Runner, Template


def make_match(hit: bool, box=None) -> MatchResult:
    return MatchResult(SimpleNamespace(hit=hit, box=box))


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.clicks: list[tuple[int, int]] = []
        self.hits: dict[object, MatchResult] = {}
        self.stopped = False

    def screenshot(self) -> object:
        self.frames += 1
        return object()

    def recognize(self, locator, frame) -> MatchResult:
        return self.hits.get(locator, make_match(False))

    def click(self, point) -> bool:
        self.clicks.append(point)
        return True

    def stop(self) -> None:
        self.stopped = True


class FlowContextTests(unittest.TestCase):
    def test_match_calls_share_one_frame_until_action(self) -> None:
        runtime = FakeRuntime()
        first = Template("first.png")
        second = Template("second.png")
        runtime.hits[first] = make_match(True, (10, 20, 30, 40))
        runtime.hits[second] = make_match(True, (50, 60, 20, 20))
        ctx = FlowContext(runtime)

        self.assertTrue(ctx.match(first))
        self.assertTrue(ctx.match(second))
        self.assertEqual(runtime.frames, 1)

        self.assertTrue(ctx.match(first).click())
        self.assertEqual(runtime.clicks, [(25, 40)])

        self.assertTrue(ctx.match(second))
        self.assertEqual(runtime.frames, 2)

    def test_click_supports_custom_point_resolver(self) -> None:
        runtime = FakeRuntime()
        locator = Template("button.png")
        runtime.hits[locator] = make_match(True, (10, 20, 30, 40))
        ctx = FlowContext(runtime)

        def bottom_right(result: MatchResult) -> tuple[int, int]:
            x, y, width, height = result.box
            return x + width - 1, y + height - 1

        self.assertTrue(ctx.match(locator).click(bottom_right))
        self.assertEqual(runtime.clicks, [(39, 59)])

    def test_click_on_miss_is_false(self) -> None:
        runtime = FakeRuntime()
        ctx = FlowContext(runtime)

        self.assertFalse(ctx.match(Template("missing.png")).click())
        self.assertEqual(runtime.clicks, [])

    def test_click_without_box_is_false(self) -> None:
        runtime = FakeRuntime()
        locator = Template("no-box.png")
        runtime.hits[locator] = make_match(True)
        ctx = FlowContext(runtime)

        self.assertFalse(ctx.match(locator).click())
        self.assertEqual(runtime.clicks, [])

    def test_match_result_keeps_original_detail(self) -> None:
        detail = SimpleNamespace(hit=True, box=(1, 2, 3, 4), raw_detail={"foo": "bar"})
        result = MatchResult(detail)

        self.assertIs(result.detail, detail)
        self.assertEqual(result.box, (1, 2, 3, 4))


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
