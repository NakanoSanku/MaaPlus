from __future__ import annotations

from dataclasses import dataclass, field

from .click import ClickResolver, center
from .swipe import SwipeInterpolator, direct
from .timing import Timing


@dataclass(frozen=True, slots=True)
class ClickConfig:
    """Default behavior for click actions."""

    resolver: ClickResolver = center
    duration: Timing = 50
    pre_delay: Timing = 0
    post_delay: Timing = 0


@dataclass(frozen=True, slots=True)
class SwipeConfig:
    """Default behavior for swipe actions."""

    duration: Timing = 300
    pre_delay: Timing = 0
    post_delay: Timing = 0
    interpolation: SwipeInterpolator = direct


@dataclass(frozen=True, slots=True)
class InteractionConfig:
    """Runtime-level input behavior shared by all task handlers."""

    click: ClickConfig = field(default_factory=ClickConfig)
    swipe: SwipeConfig = field(default_factory=SwipeConfig)
    action_interval: Timing = 0
