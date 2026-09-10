# Custom recognition example

This example keeps the custom-recognition implementation in application code. MaaFramework's
Python callback API is enough; no custom recognizer belongs in the MaaPlus core package. A custom
recognizer is a normal Python class:

```python
from maa.custom_recognition import CustomRecognition
from maa.pipeline import JCustomRecognition


class BrightPixel(CustomRecognition):
    def analyze(self, context, argv):
        # argv.image is a BGR numpy array and argv.roi is (x, y, width, height).
        # Return None when the target is absent.
        if (argv.image[argv.roi[1], argv.roi[0]] == [0, 0, 255]).all():
            return CustomRecognition.AnalyzeResult(
                box=(argv.roi[0], argv.roi[1], 1, 1),
                detail={"algorithm": "bright_pixel"},
            )
        return None
```

Register it while loading the application's `Resource`:

```python
from maa.resource import Resource

resource = Resource()
resource.register_custom_recognition("BrightPixel", BrightPixel())

BRIGHT_PIXEL = JCustomRecognition(
    custom_recognition="BrightPixel",
    roi=(100, 200, 300, 200),
)
```

The name must be identical in both places. `custom_recognition_param` is passed as a JSON string
in `argv.custom_recognition_param`; use it for thresholds or other per-node configuration. A
successful result should return `AnalyzeResult` with a rectangular `box`, which means the existing
MaaPlus code can use `tick.match(BRIGHT_PIXEL).click()`.

## Multi-point color matching

For fixed-color UI markers, this example includes a NumPy implementation in
`demo/custom_recognition.py`:

```python
from demo.custom_recognition import ColorPoint, MultiPointColorRecognition

recognizers = {
    "MultiPointColor": MultiPointColorRecognition(
        points=(
            ColorPoint((0, 0), (255, 214, 80)),
            ColorPoint((12, 0), (255, 214, 80)),
            ColorPoint((0, 12), (255, 214, 80)),
        ),
        tolerance=12,
    ),
}
```

`ColorPoint` colors are RGB. MaaFramework screenshots are BGR, and the example converts
the channels before comparing. The first point is the anchor; all points must match within the
per-channel tolerance. The result box encloses the points, so it can be clicked directly.

Use a small stable set of points from the target UI. Avoid sampling animated, anti-aliased, or
gradient edges. Restrict `roi` whenever possible to reduce false positives and recognition cost.

## Lifecycle and failure rules

- Register custom recognizers before submitting tasks. `Resource` retains the Python callback
  objects for its lifetime.
- Return `None` for a normal miss; raise an exception for invalid configuration or a broken image.
- Put JSON-serializable values in `AnalyzeResult.detail`; MaaFramework records that detail with the
  recognition result.
- Keep recognition callbacks short and deterministic. Controller actions belong in task handlers;
  a recognizer should normally inspect the provided screenshot and return a box.
