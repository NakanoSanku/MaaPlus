from __future__ import annotations

import unittest
from types import SimpleNamespace

from maaplus import MatchResult, Runner, Runtime, Template


def make_match(hit: bool, box=None, click=None) -> MatchResult:
    return MatchResult(SimpleNamespace(hit=hit, box=box), click)


class FakeRuntime:
    def __init__(self) -> None:
        self.frames = 0
        self.matches: list[tuple[object, object]] = []
        self.clicks: list[tuple[tuple[int, int], int]] = []
        self.hits: dict[object, tuple[bool, object]] = {}
        self.stopped = False

    def screenshot(self) -> object:
        self.frames += 1
        return object()

    def match(self, locator, image) -> MatchResult:
        self.matches.append((locator, image))
        hit, box = self.hits.get(locator, (False, None))
        return make_match(hit, box, self.click)

    def click(self, point, duration=50) -> bool:
        self.clicks.append((point, duration))
        return True

    def swipe(self, points, duration) -> bool:
        return True

    def stop(self) -> None:
        self.stopped = True


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


class FlowSnapshotTests(unittest.TestCase):
    def test_one_flow_run_uses_one_screenshot(self) -> None:
        runtime = FakeRuntime()
        first = Template("first.png")
        second = Template("second.png")
        runtime.hits[first] = (True, (10, 20, 30, 40))
        runtime.hits[second] = (True, (50, 60, 20, 20))
        runner = Runner(runtime)

        def flow(rt, image):
            first_result = rt.match(first, image)
            second_result = rt.match(second, image)
            self.assertTrue(first_result)
            self.assertTrue(second_result)

            first_result.click()

            # Actions do not replace the current flow snapshot.
            rt.match(second, image)
            return image

        first_image = runner.run(flow)
        self.assertEqual(runtime.frames, 1)
        self.assertTrue(all(image is first_image for _, image in runtime.matches))
        self.assertEqual(runtime.clicks, [((25, 40), 50)])

        runtime.matches.clear()
        second_image = runner.run(flow)
        self.assertEqual(runtime.frames, 2)
        self.assertIsNot(first_image, second_image)
        self.assertTrue(all(image is second_image for _, image in runtime.matches))

    def test_custom_click_resolver_and_duration(self) -> None:
        runtime = FakeRuntime()
        locator = Template("button.png")
        runtime.hits[locator] = (True, (10, 20, 30, 40))
        image = runtime.screenshot()

        def bottom_right(result: MatchResult) -> tuple[int, int]:
            x, y, width, height = result.box
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


class RunnerTests(unittest.TestCase):
    def test_runner_can_stop_runtime(self) -> None:
        runtime = FakeRuntime()
        runner = Runner(runtime)

        runner.stop()
        self.assertTrue(runtime.stopped)


if __name__ == "__main__":
    unittest.main()
