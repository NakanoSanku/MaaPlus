from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import call, patch

from maaplus import (
    App,
    ClickConfig,
    InteractionConfig,
    Runtime,
    SwipeConfig,
    Tick,
    path,
    point,
    timing,
)


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


class BindTasker:
    running = False

    def __init__(self) -> None:
        self.bound = None

    def bind(self, resource, controller) -> bool:
        self.bound = (resource, controller)
        return True


class TimingTests(unittest.TestCase):
    def test_random_timing_stays_inside_inclusive_range(self) -> None:
        resolver = timing.random(40, 90)
        values = [resolver() for _ in range(100)]

        self.assertTrue(all(40 <= value <= 90 for value in values))

    def test_timing_strategy_is_resolved_for_each_action(self) -> None:
        calls = 0

        def dynamic_duration() -> int:
            nonlocal calls
            calls += 1
            return 0

        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=FakeController(),
            interaction=InteractionConfig(click=ClickConfig(duration=dynamic_duration)),
        )

        runtime.click((10, 20))
        runtime.click((10, 20))

        self.assertEqual(calls, 2)


class PointStrategyTests(unittest.TestCase):
    def test_random_point_respects_padding(self) -> None:
        area = (100, 200, 100, 80)
        resolver = point.random(padding=0.15)

        for _ in range(100):
            x, y = resolver(area)
            self.assertGreaterEqual(x, 115)
            self.assertLessEqual(x, 184)
            self.assertGreaterEqual(y, 212)
            self.assertLessEqual(y, 267)

    def test_relative_point_resolves_expected_point(self) -> None:
        self.assertEqual(point.relative(0.5, 0.5)((10, 20, 11, 21)), (15, 30))

    def test_center_accepts_plain_area(self) -> None:
        self.assertEqual(point.center((10, 20, 30, 40)), (25, 40))

    def test_point_strategy_rejects_empty_area(self) -> None:
        with self.assertRaises(ValueError):
            point.center((10, 20, 0, 40))

    def test_point_resolver_can_build_swipe_endpoints(self) -> None:
        pick = point.relative(0.5, 0.5)
        start = pick((0, 100, 100, 100))
        end = pick((200, 0, 100, 100))

        self.assertEqual(start, (50, 150))
        self.assertEqual(end, (250, 50))
        self.assertEqual(path.direct([start, end]), (start, end))


class RuntimeInteractionTests(unittest.TestCase):
    def test_click_applies_pre_duration_and_post_timing(self) -> None:
        controller = FakeController()
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=controller,
            interaction=InteractionConfig(
                click=ClickConfig(
                    duration=20,
                    pre_delay=10,
                    post_delay=30,
                )
            ),
        )

        with patch("maaplus.runtime.time.sleep") as sleep:
            self.assertTrue(runtime.click((100, 200)))

        self.assertEqual(controller.events, [("down", 100, 200), ("up",)])
        self.assertEqual(sleep.call_args_list, [call(0.01), call(0.02), call(0.03)])

    def test_local_click_timing_overrides_defaults(self) -> None:
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=FakeController(),
            interaction=InteractionConfig(
                click=ClickConfig(duration=100, pre_delay=100, post_delay=100)
            ),
        )

        with patch("maaplus.runtime.time.sleep") as sleep:
            runtime.click((1, 2), duration=0, pre_delay=0, post_delay=0)

        sleep.assert_not_called()

    def test_exact_click_does_not_use_area_resolver(self) -> None:
        def fail_if_called(area):
            raise AssertionError(f"unexpected area resolver call: {area}")

        controller = FakeController()
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=controller,
            interaction=InteractionConfig(
                click=ClickConfig(resolver=fail_if_called, duration=0),
            ),
        )

        runtime.click((12, 34))

        self.assertEqual(controller.events, [("down", 12, 34), ("up",)])

    def test_click_area_uses_default_point_resolver(self) -> None:
        controller = FakeController()
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=controller,
            interaction=InteractionConfig(
                click=ClickConfig(
                    resolver=point.relative(1.0, 1.0),
                    duration=0,
                ),
            ),
        )

        runtime.click_area((10, 20, 30, 40))

        self.assertEqual(controller.events, [("down", 39, 59), ("up",)])

    def test_click_area_can_override_resolver(self) -> None:
        controller = FakeController()
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=controller,
            interaction=InteractionConfig(
                click=ClickConfig(
                    resolver=point.relative(1.0, 1.0),
                    duration=0,
                ),
            ),
        )

        runtime.click_area((10, 20, 30, 40), resolver=point.center)

        self.assertEqual(controller.events, [("down", 25, 40), ("up",)])

    def test_tick_click_area_forwards_to_runtime(self) -> None:
        controller = FakeController()
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=controller,
            interaction=InteractionConfig(click=ClickConfig(duration=0)),
        )
        tick = Tick(runtime=runtime, image=object())

        tick.click_area((10, 20, 30, 40))

        self.assertEqual(controller.events, [("down", 25, 40), ("up",)])

    def test_action_interval_limits_consecutive_inputs(self) -> None:
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=FakeController(),
            interaction=InteractionConfig(
                click=ClickConfig(duration=0),
                action_interval=100,
            ),
        )
        runtime._last_input_end = 1.0

        with (
            patch("maaplus.runtime.time.monotonic", side_effect=[1.02, 1.10]),
            patch("maaplus.runtime.time.sleep") as sleep,
        ):
            runtime.click((1, 2))

        sleep.assert_called_once()
        self.assertAlmostEqual(sleep.call_args.args[0], 0.08)

    def test_swipe_uses_configured_path_interpolation(self) -> None:
        controller = FakeController()
        runtime = Runtime(
            tasker=SimpleNamespace(running=False),
            controller=controller,
            interaction=InteractionConfig(
                swipe=SwipeConfig(
                    duration=0,
                    interpolation=path.linear(samples=5),
                )
            ),
        )

        runtime.swipe([(0, 0), (8, 0)])

        self.assertEqual(
            controller.events,
            [
                ("down", 0, 0),
                ("move", 2, 0),
                ("move", 4, 0),
                ("move", 6, 0),
                ("move", 8, 0),
                ("up",),
            ],
        )

    def test_app_factory_passes_interaction_config_to_runtime(self) -> None:
        tasker = BindTasker()
        controller = FakeController()
        resource = object()
        interaction = InteractionConfig(click=ClickConfig(duration=0))

        app = App.from_maa(
            tasker=tasker,
            controller=controller,
            resource=resource,
            interaction=interaction,
        )

        self.assertIs(app.scheduler.runtime.interaction, interaction)
        self.assertEqual(tasker.bound, (resource, controller))


class PathStrategyTests(unittest.TestCase):
    def test_linear_interpolation_resamples_path(self) -> None:
        interpolator = path.linear(samples=5)
        self.assertEqual(
            tuple(interpolator([(0, 0), (8, 0)])),
            ((0, 0), (2, 0), (4, 0), (6, 0), (8, 0)),
        )

    def test_ease_in_out_preserves_endpoints(self) -> None:
        resolved = tuple(path.ease_in_out(samples=20)([(10, 20), (100, 200)]))
        self.assertEqual(resolved[0], (10, 20))
        self.assertEqual(resolved[-1], (100, 200))


if __name__ == "__main__":
    unittest.main()
