"""Opt-in bounding-box snapshots. Pillow is loaded only when Debug is constructed."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from numbers import Integral
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .geometry import Rect

if TYPE_CHECKING:
    import numpy

    from .locator import Locator
    from .runtime import MatchResult

logger = logging.getLogger(__name__)
_GREEN = (64, 224, 128)
_BLUE = (80, 168, 255)
_RED = (255, 96, 96)
_OUTPUT_NAME = re.compile(r"maaplus-\d{8}T\d{12}Z-[0-9a-f]{32}\.png")


class Debug:
    """Save annotated BGR screenshots as PNGs, retaining the newest ``max_images``.

    Pass an instance to ``App.from_maa(debug=...)`` to capture every recognition, or call
    ``draw(image, *boxes)`` directly. Coordinates are ``(x, y, width, height)``; colors are RGB.
    The screenshot keeps its original origin and size above a separate caption panel.
    Install the optional ``maaplus[debug]`` dependency before constructing this class.
    """

    def __init__(
        self,
        output_dir: str | Path = ".debug",
        *,
        max_images: int | None = 200,
        line_width: int = 2,
        font: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        for name, value in (("max_images", max_images), ("line_width", line_width)):
            if value is None and name == "max_images":
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        try:
            from PIL import ImageFont
        except ImportError as exc:
            raise ImportError(
                'Drawing requires Pillow. Install with uv add "maaplus[debug]", '
                "or run uv sync --extra debug in the MaaPlus repository."
            ) from exc

        self.output_dir = Path(output_dir).resolve()
        self.max_images = max_images
        self.line_width = line_width
        self.metadata = dict(metadata or {})
        self._font = (
            ImageFont.truetype(str(font), size=16) if font else ImageFont.load_default(size=16)
        )
        self._lock = Lock()

    def draw(
        self,
        image: numpy.ndarray,
        *boxes: Rect,
        label: str = "debug",
        color: tuple[int, int, int] = _GREEN,
    ) -> Path | None:
        """Save a fresh image with zero or more boxes; never modify ``image``.

        Boxes extending outside the screenshot are clipped. Width and height must be positive.
        An empty box list saves just the screenshot and caption. Explicit drawing errors raise.
        """
        if len(color) != 3 or any(
            isinstance(c, bool) or not isinstance(c, Integral) or not 0 <= c <= 255
            for c in color
        ):
            raise ValueError("color must contain three RGB integers between 0 and 255")
        rgb = tuple(int(c) for c in color)
        annotations = []
        for index, box in enumerate(boxes, 1):
            rect = _rect(box)
            if rect is None or rect[2] <= 0 or rect[3] <= 0:
                raise ValueError("boxes must be integer (x, y, width, height) with positive size")
            annotations.append((f"BOX {index}", rect, rgb))
        try:
            return self._save(image, label, annotations)
        except OSError:
            logger.warning("could not write debug image label=%s", label, exc_info=True)
            return None

    def _match(
        self, image: numpy.ndarray, locator: Locator, result: MatchResult, label: str
    ) -> Path | None:
        # Diagnostics must not turn a successful recognition into a failed task.
        try:
            roi = _static_roi(locator, image.shape[1], image.shape[0])
            annotations = []
            if roi is not None:
                annotations.append(("ROI", roi, _BLUE if result.hit else _RED))
            if result.hit and result.box is not None:
                annotations.append(("HIT", result.box, _GREEN))
            return self._save(
                image, label, annotations,
                status="HIT" if result.hit else "MISS",
                note="ROI resolved by MaaFramework; not drawn" if roi is None else "",
            )
        except Exception:
            logger.warning("debug image failed label=%s", label, exc_info=True)
            return None

    def _save(
        self,
        image: numpy.ndarray,
        label: str,
        annotations: list[tuple[str, Rect, tuple[int, ...]]],
        *,
        status: str = "DRAW",
        note: str = "",
    ) -> Path:
        import numpy
        from PIL import Image, ImageDraw, PngImagePlugin

        if (
            not isinstance(image, numpy.ndarray)
            or image.dtype != numpy.uint8
            or image.ndim != 3
            or image.shape[2] != 3
            or not image.shape[0]
            or not image.shape[1]
        ):
            raise ValueError("debug drawing requires a non-empty uint8 BGR image (H, W, 3)")
        height, width = image.shape[:2]
        caption = [(f"{status} | {' '.join(label.split())}", (232, 237, 244))]
        caption.extend((f"{name}  {tuple(box)}", color) for name, box, color in annotations)
        if note:
            caption.append((note, (170, 180, 194)))
        # A separate footer leaves screenshot coordinates and the topmost UI visible.
        canvas = Image.new("RGB", (max(width, 480), height + 16 + 24 * len(caption)), (20, 26, 36))
        canvas.paste(Image.fromarray(image[..., ::-1]), (0, 0))
        painter = ImageDraw.Draw(canvas)
        for _, (x, y, w, h), color in annotations:
            left, top = max(0, x), max(0, y)
            right, bottom = min(width, x + w), min(height, y + h)
            if left < right and top < bottom:
                # Pillow's rectangle endpoints are inclusive; Maa's width/height are extents.
                painter.rectangle(
                    (left, top, right - 1, bottom - 1), outline=color,
                    width=min(self.line_width, right - left, bottom - top),
                )
        for row, (text, color) in enumerate(caption):
            # Keep captions on one line; full labels are preserved in PNG metadata.
            while len(text) > 1 and painter.textlength(text, font=self._font) > canvas.width - 24:
                text = text[:-2] + "…"
            painter.text((12, height + 8 + row * 24), text, font=self._font, fill=color)

        metadata = PngImagePlugin.PngInfo()
        annotation_metadata = {
            "label": label, "status": status, "image_size": [width, height], "note": note,
            "boxes": [{"label": name, "box": list(box), "color": list(color)}
                      for name, box, color in annotations],
            **self.metadata,
        }
        metadata.add_itxt("maaplus", json.dumps(annotation_metadata, ensure_ascii=False))

        with self._lock:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            destination = self.output_dir / f"maaplus-{stamp}-{uuid4().hex}.png"
            with NamedTemporaryFile(
                dir=self.output_dir, prefix=".maaplus-", suffix=".tmp", delete=False
            ) as stream:
                temporary = Path(stream.name)
            try:
                canvas.save(temporary, format="PNG", pnginfo=metadata)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
            self._prune()
        logger.debug("debug image saved label=%s status=%s path=%s", label, status, destination)
        return destination

    def _prune(self) -> None:
        if self.max_images is None:
            return
        try:
            images = sorted(
                path for path in self.output_dir.glob("maaplus-*.png")
                if _OUTPUT_NAME.fullmatch(path.name) and path.is_file()
            )
            for path in images[:-self.max_images]:
                path.unlink(missing_ok=True)
        except OSError:
            logger.warning("could not prune debug images in %s", self.output_dir, exc_info=True)


def _rect(value: Any) -> Rect | None:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    if any(isinstance(v, bool) or not isinstance(v, Integral) for v in value):
        return None
    x, y, w, h = (int(v) for v in value)
    return x, y, w, h


def _static_roi(locator: Locator, width: int, height: int) -> Rect | None:
    """Resolve literal Maa ROIs only; references/composite subnodes need native context."""
    roi = _rect(getattr(locator, "roi", None))
    offset = _rect(getattr(locator, "roi_offset", (0, 0, 0, 0)))
    if roi is None or offset is None:
        return None
    x, y, w, h = roi
    if x < 0:
        x += width
    if y < 0:
        y += height
    if w == 0:
        w = width - x
    elif w < 0:
        x += w
        w = -w
    if h == 0:
        h = height - y
    elif h < 0:
        y += h
        h = -h
    dx, dy, dw, dh = offset
    return x + dx, y + dy, w + dw, h + dh
