# Locators

A Locator is a MaaFramework recognition parameter object. Import recognition types directly from
`maa.pipeline`; MaaPlus passes them to the native tasker without rebuilding them. MaaPlus keeps
`Locator` as a type annotation for the native `JRecognitionParam` union.

## Native recognition parameters

```python
from maa.pipeline import JOCR, JTemplateMatch

START = JTemplateMatch(
    template=["start.png"],
    threshold=[0.85],
    roi=(0, 0, 1280, 720),
)
CONFIRM = JOCR(expected=["确认"])
```

Use any supported native fields directly. Template paths are relative to the resource bundle's
`image/` directory. For several images with the same recognition parameters, use one
`JTemplateMatch(template=["start_a.png", "start_b.png"], threshold=[0.85])`.

Other native types include `JFeatureMatch`, `JColorMatch`, and `JCustomRecognition`.
The calling code is the same for every recognition type:

```python
if result := tick.match(START):
    result.click()
```

## Ordered fallback with JOr

`JOr` tries members in order and returns the first successful recognition. Each member is an
inline recognition dictionary in MaaFramework's pipeline format:

```python
from maa.pipeline import JOr

START = JOr(any_of=[
    {
        "recognition": {
            "type": "TemplateMatch",
            "param": {"template": ["start.png"], "threshold": [0.85]},
        },
    },
    {
        "recognition": {
            "type": "OCR",
            "param": {"expected": ["挑战"]},
        },
    },
])
```

Use ordered fallback when algorithms, ROIs, or other parameters differ. Multiple equivalent
templates can stay in one `JTemplateMatch`.

## Requiring all members with JAnd

`JAnd` requires every member to match. `box_index` selects which top-level member supplies the
result box, including the default target for `MatchResult.click()`:

```python
from maa.pipeline import JAnd

READY_TO_START = JAnd(
    all_of=[
        {
            "recognition": {
                "type": "TemplateMatch",
                "param": {"template": ["battle/title.png"]},
            },
        },
        {
            "recognition": {
                "type": "TemplateMatch",
                "param": {"template": ["battle/start.png"]},
            },
        },
    ],
    box_index=1,
)

if ready := tick.match(READY_TO_START):
    ready.click()  # Uses the battle/start.png result box.
```

Choose a zero-based `box_index` within the member list. Studio checks empty combinations, invalid
indices, missing references, and cycles before saving or validating recognition.

## Nested combinations

Nested members use `"type": "And"` or `"type": "Or"`, with `all_of` or `any_of` inside `param`.
The nested value is an inline dictionary, not a bare parameter object. MaaPlus does not add a
separate combination syntax or change member order.

[MaaPlus Studio](../studio/README.md) lets you select members visually and generates the nested
native dictionaries. It expands cross-module references inline, so generated UI modules do not
depend on each other. Recognition validation and Python generation share the same config compiler.

Keep task transitions and action sequences in handlers and navigation code. Combinations describe
recognition conditions. Custom recognition callbacks and their registration remain application-owned;
see [the complete example](../examples/complete_project/CUSTOM_RECOGNITION.md).

Studio imports current `maa.pipeline` definitions only, including ordinary Python import aliases.
Inline combinations use the structured `recognition: {type, param}` format shown above.
Unsupported imports and definitions are rejected with a source location, and the file stays unchanged.
