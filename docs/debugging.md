# Bounding-box debugging

MaaPlus keeps drawing out of the default runtime. Create `Debug` only when visual diagnostics are
needed:

```python
from maaplus import App, Debug

with App.from_maa(
    tasker=tasker,
    controller=controller,
    resource=resource,
    debug=Debug(".debug", max_images=200),
) as app:
    ...
```

`Debug` uses Pillow 12.3 or newer, which is an optional dependency:

```bash
uv add "maaplus[debug]"
```

The scheduler still captures one immutable screenshot per `Tick`. Recognition runs against that
same array, while drawing creates a separate PIL image, so annotations cannot change a later
recognition result. Each automatic `tick.match(locator)` writes one PNG and attaches its path to
`MatchResult.debug_path`. A successful result draws the returned `box` in green; literal `roi`
coordinates are drawn in blue for a hit and red for a miss. ROI references and composite locators
are left to MaaFramework's native context and are mentioned in the caption instead of being
guessed.

The screenshot remains at its original origin and a caption panel is added below it. This makes
pixel coordinates directly comparable with MaaFramework's `box` values. PNG metadata under the
`maaplus` key contains the complete label, status, image size, colors, and unclipped coordinates.

For a temporary manual marker:

```python
path = tick.draw(
    (320, 180, 96, 48),
    label="expected button",
    color=(255, 190, 40),
)
```

`tick.draw()` returns `None` when debugging is disabled or its output cannot be written. It accepts
Maa's `(x, y, width, height)` rectangles, clips rectangles at the image edge, and raises for
malformed or zero-sized boxes.
Only the newest `max_images` files named by that `Debug` instance are retained. Set
`max_images=None` for an intentionally unbounded capture. Other files in the directory are not
touched.

For screenshot-only recognition and native Maa debug images, use the separate
[`maaplus.dev.Inspector`](development.md) workflow. It never calls controller input methods.

For a live run, prefer `TraceSession.create_debug()` so recognition trace events and failure
reports point into one session directory. A terminal task failure copies recent referenced images
into its retained evidence bundle before normal debug retention can remove them.
