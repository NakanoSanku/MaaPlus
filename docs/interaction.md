# Interaction

MaaPlus separates geometry strategies from input actions.

```text
Geometry
├── Point / Rect
├── PointResolver        Rect -> Point
└── PathInterpolator     points -> path

Interaction
├── click / click_area
└── swipe
```

The geometry layer does not know whether a point will be clicked, used as a swipe endpoint, stored for later, or consumed by another gesture.

## Point resolvers

A `PointResolver` converts a rectangle into one point:

```python
from maaplus import Point, PointResolver, Rect


def bottom_right(area: Rect) -> Point:
    x, y, width, height = area
    return x + width - 1, y + height - 1
```

Built-in strategies live under `point`:

```python
from maaplus import point

point.center
point.random()
point.random(padding=0.15)
point.relative(0.5, 0.5)
point.relative(0.8, 0.5)
```

They are general geometry helpers rather than click-specific helpers.

For example, the same resolver can produce swipe endpoints:

```python
from maaplus import point

pick = point.random(padding=0.15)

start = pick((100, 500, 300, 200))
end = pick((700, 100, 300, 200))

tick.swipe([start, end])
```

## Path interpolators

A `PathInterpolator` converts a caller-supplied point sequence into the path used by an action:

```python
from maaplus import path

path.direct
path.linear(samples=20)
path.ease_in(samples=20)
path.ease_out(samples=20)
path.ease_in_out(samples=20)
```

Although `SwipeConfig` currently consumes a `PathInterpolator`, the path strategies themselves are not swipe-specific and can be reused by future gesture APIs.

## Exact point clicks

Use `click()` when the coordinate itself is intentional:

```python
tick.click((500, 300))
```

Exact point clicks do not use `ClickConfig.resolver`. They still inherit click duration, pre-delay, post-delay, and global action interval from `InteractionConfig`.

## Rectangular area clicks

Use `click_area()` when the application knows a safe region but does not require one exact coordinate:

```python
tick.click_area((200, 150, 880, 500))
```

By default this uses the runtime-level `PointResolver`:

```python
InteractionConfig(
    click=ClickConfig(
        resolver=point.random(padding=0.15),
    ),
)
```

A single action can override the resolver without replacing the timing policy:

```python
tick.click_area(
    (200, 150, 880, 500),
    resolver=point.center,
)
```

or:

```python
tick.click_area(
    (200, 150, 880, 500),
    resolver=point.relative(0.8, 0.5),
)
```

## Recognition-result clicks

`MatchResult.click()` treats the recognition box as an area and forwards it through the same area-click path:

```python
if button := tick.match(UI.CONFIRM):
    button.click()
```

Conceptually:

```text
MatchResult.box
      ↓
Runtime.click_area()
      ↓
PointResolver
      ↓
    Point
      ↓
Runtime.click()
```

Therefore the same project-level `point.random(...)` policy applies equally to recognition targets and explicit application areas.

A local resolver uses the same `Rect -> Point` contract:

```python
if button := tick.match(UI.CONFIRM):
    button.click(resolver=point.relative(0.5, 0.8))
```

## Interaction configuration

Geometry and timing stay orthogonal:

```python
from maaplus import ClickConfig, InteractionConfig, SwipeConfig, path, point, timing

INTERACTION = InteractionConfig(
    click=ClickConfig(
        resolver=point.random(padding=0.15),
        duration=timing.random(40, 90),
        pre_delay=timing.random(80, 150),
        post_delay=timing.random(250, 450),
    ),
    swipe=SwipeConfig(
        interpolation=path.ease_in_out(samples=20),
        duration=timing.random(300, 500),
    ),
)
```

The important boundary is:

```text
point / path   = reusable geometry
click / swipe  = concrete input actions
timing         = reusable time strategies
```
