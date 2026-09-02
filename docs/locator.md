# Locator composition

MaaPlus keeps recognition declarative: a Locator describes **what should be recognized**, while `Tick` and `Runtime` decide **when and against which screenshot it is recognized**.

Normal MaaFramework recognition parameters are still valid Locators:

```python
from maaplus import OCR, Template

START = Template(
    template=["start.png"],
    threshold=[0.85],
)

CONFIRM = OCR(expected=["确认"])
```

Use them normally through `Tick`:

```python
if start := tick.match(START):
    start.click()
```

## Multiple templates of the same element

If several images use the same TemplateMatch parameters, prefer one `Template` with multiple templates:

```python
START = Template(
    template=[
        "soul/start.png",
        "awakening/start.png",
        "orochi/start.png",
    ],
    threshold=[0.85],
)
```

Do not use `FirstOf` just to split identical TemplateMatch configuration into separate Locators.

## FirstOf

`FirstOf` represents ordered fallback recognition. It is backed by MaaFramework's native `Or` recognition.

```python
from maaplus import FirstOf, OCR, Template

START = FirstOf(
    Template(
        template=["start.png"],
        threshold=[0.85],
    ),
    OCR(expected=["挑战"]),
)
```

The sub-Locators are attempted in order. Recognition stops when the first one succeeds.

Use `FirstOf` when one semantic UI element may need different recognition algorithms, ROIs, thresholds, or other parameters.

## AllOf

`AllOf` represents a semantic condition that requires every sub-Locator to match. It is backed by MaaFramework's native `And` recognition.

```python
from maaplus import AllOf, OCR, Template

BATTLE_PAGE = AllOf(
    Template(template=["battle/icon.png"]),
    OCR(expected=["自动"]),
)
```

This is useful when one image or one text match alone is not enough to identify a page reliably.

### Choosing the result box

An `AllOf` may match several different UI elements, but `MatchResult` still needs one box for operations such as `click()`.

Use `box_index` to select which sub-Locator supplies that box:

```python
READY_TO_START = AllOf(
    Template(template=["battle/title.png"]),
    Template(template=["battle/start.png"]),
    box_index=1,
)

if ready := tick.match(READY_TO_START):
    ready.click()  # clicks the box returned by battle/start.png
```

`box_index` defaults to `0` and must refer to an existing top-level sub-Locator.

## Composition

`FirstOf` and `AllOf` are themselves normal Locators and may be nested:

```python
BATTLE_READY = AllOf(
    FirstOf(
        Template(template=["battle/title_a.png"]),
        Template(template=["battle/title_b.png"]),
    ),
    OCR(expected=["挑战"]),
    box_index=1,
)
```

The calling code remains unchanged:

```python
if result := tick.match(BATTLE_READY):
    result.click()
```

Keep business flow outside Locator composition. `FirstOf` and `AllOf` should describe recognition semantics, not task state transitions or action sequences.
