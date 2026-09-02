# Interaction

MaaPlus separates exact input coordinates from rectangular click areas.

```text
Point click
    Point
      ↓
Runtime.click()

Area click
    Rect
      ↓
ClickResolver
      ↓
    Point
      ↓
Runtime.click()
```

A `ClickResolver` is purely geometric:

```python
from maaplus import ClickResolver, Point, Rect


def bottom_right(area: Rect) -> Point:
    x, y, width, height = area
    return x + width - 1, y + height - 1
```

It does not depend on `MatchResult`, so the same resolver can be reused for recognition boxes and application-defined screen areas.

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

By default this uses the runtime-level click resolver:

```python
InteractionConfig(
    click=ClickConfig(
        resolver=click.random(padding=0.15),
    ),
)
```

A single action can override the resolver without replacing the timing policy:

```python
tick.click_area(
    (200, 150, 880, 500),
    resolver=click.center,
)
```

or:

```python
tick.click_area(
    (200, 150, 880, 500),
    resolver=click.relative(0.8, 0.5),
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
ClickResolver
      ↓
Runtime.click()
```

Therefore the same project-level `click.random(...)` policy applies equally to recognition targets and explicit application areas.

A local resolver also uses the same `Rect -> Point` contract:

```python
if button := tick.match(UI.CONFIRM):
    button.click(resolver=click.relative(0.5, 0.8))
```

## Common strategies

MaaPlus provides reusable rectangle strategies:

```python
click.center
click.random()
click.random(padding=0.15)
click.relative(0.5, 0.5)
click.relative(0.8, 0.5)
```

The important boundary is:

```text
click()       = exact coordinate
click_area()  = rectangular target + selection strategy
result.click() = recognition box + the same selection strategy
```

Timing behavior remains orthogonal to target selection. `duration`, `pre_delay`, `post_delay`, and `action_interval` continue to be controlled by `InteractionConfig` or per-action overrides.
