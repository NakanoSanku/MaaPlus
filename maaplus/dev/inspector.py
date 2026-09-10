"""Recognition-only inspection against screenshots or fixture files."""

from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy

from ..debug import Debug
from ..geometry import Rect
from ..locator import Locator, recognition_type
from ..runtime import MatchResult
from .fixtures import Fixture, FixtureSet, assert_expected

ImageFormat = Literal["bgr", "rgb"]


class InspectionError(RuntimeError):
    """Recognition inspection failed with fixture and Maa context."""

    def __init__(
        self,
        message: str,
        *,
        source_path: Path | None = None,
        recognition_type: str | None = None,
        job_status: Any | None = None,
        trace_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.source_path = source_path
        self.recognition_type = recognition_type
        self.job_status = job_status
        self.trace_path = trace_path


class InspectionTimeoutError(InspectionError, TimeoutError):
    """Recognition inspection exceeded its cooperative wait deadline."""


@dataclass(frozen=True, slots=True)
class InspectionResult:
    """Recognition evidence without click or other controller methods."""

    detail: Any
    locator: Locator
    source_path: Path | None
    image_sha256: str
    elapsed_ms: float
    annotated_path: Path | None = None
    raw_path: Path | None = None
    draw_paths: tuple[Path, ...] = ()
    trace_path: Path | None = None

    @property
    def hit(self) -> bool:
        return bool(self.detail.hit)

    @property
    def box(self) -> Rect | None:
        box = getattr(self.detail, "box", None)
        return None if box is None else tuple(box)  # type: ignore[return-value]

    @property
    def raw_detail(self) -> Any:
        return _safe_attr(self.detail, "raw_detail")


@dataclass(frozen=True, slots=True)
class FixtureInspection:
    """One fixture result and its default assertion outcome."""

    fixture: Fixture
    result: InspectionResult | None
    passed: bool
    errors: tuple[str, ...] = ()
    error: InspectionError | None = None


class Inspector:
    """Run MaaFramework recognition without granting access to controller input."""

    def __init__(
        self,
        tasker: Any,
        *,
        debug: Debug | None = None,
        output_dir: str | Path | None = ".maaplus/inspect",
        trace: Any | None = None,
        timeout: int | None = 10_000,
    ) -> None:
        if timeout is not None and (not isinstance(timeout, int) or timeout <= 0):
            raise ValueError("inspection timeout must be a positive integer in milliseconds")
        self.tasker = tasker
        self.debug = debug or (Debug(output_dir) if output_dir is not None else None)
        self.trace = trace
        self.timeout = timeout

    @classmethod
    def from_maa(
        cls,
        *,
        tasker: Any | None = None,
        controller: Any | None = None,
        resource: Any | None = None,
        bind: bool = True,
        **kwargs: Any,
    ) -> Inspector:
        """Create an inspector from Maa objects while keeping setup out of fixture code."""
        if tasker is None:
            from maa.tasker import Tasker

            tasker = Tasker()
        if bind and controller is not None and resource is not None:
            if not tasker.bind(resource, controller):
                raise RuntimeError("Failed to bind MaaFramework resource/controller to tasker")
        if getattr(tasker, "inited", True) is False:
            raise RuntimeError("MaaFramework tasker is not initialized")
        return cls(tasker, **kwargs)

    def inspect(
        self,
        locator: Locator,
        image: numpy.ndarray | str | Path,
        *,
        label: str | None = None,
        image_format: ImageFormat | None = None,
    ) -> InspectionResult:
        source_path: Path | None = None
        if isinstance(image, (str, Path)):
            source_path = Path(image)
            image = _load_image(source_path)
        elif image_format is None:
            raise ValueError("image_format is required for ndarray inspection: 'bgr' or 'rgb'")
        if not isinstance(image, numpy.ndarray):
            raise TypeError("inspection image must be a numpy array or image path")
        image = _normalize_image(image, image_format or "bgr")

        image_hash = hashlib.sha256(numpy.ascontiguousarray(image).tobytes()).hexdigest()
        started = time.perf_counter()
        reco_type = recognition_type(locator)
        type_name = getattr(reco_type, "name", str(reco_type))
        try:
            job = _wait_for_job(
                self.tasker.post_recognition(reco_type, locator, image),
                timeout=self.timeout,
            )
        except InspectionTimeoutError as exc:
            raise InspectionTimeoutError(
                f"recognition timed out for {source_path or '<array>'} after {self.timeout} ms",
                source_path=source_path,
                recognition_type=type_name,
                trace_path=_trace_path(self.trace),
            ) from exc
        except Exception as exc:
            raise InspectionError(
                f"recognition job failed for {source_path or '<array>'}: {exc}",
                source_path=source_path,
                recognition_type=type_name,
                trace_path=_trace_path(self.trace),
            ) from exc
        if not getattr(job, "succeeded", False):
            raise InspectionError(
                f"Maa recognition failed for {source_path or '<array>'} "
                f"(status={getattr(job, 'status', None)!r})",
                source_path=source_path,
                recognition_type=type_name,
                job_status=getattr(job, "status", None),
                trace_path=_trace_path(self.trace),
            )
        try:
            task_detail = job.get()
        except Exception as exc:
            raise InspectionError(
                f"Maa recognition result failed for {source_path or '<array>'}: {exc}",
                source_path=source_path,
                recognition_type=type_name,
                job_status=getattr(job, "status", None),
                trace_path=_trace_path(self.trace),
            ) from exc
        if task_detail is None:
            raise InspectionError(
                f"Maa recognition returned no task detail for {source_path or '<array>'}",
                source_path=source_path,
                recognition_type=type_name,
                trace_path=_trace_path(self.trace),
            )
        detail = next(
            (node.recognition for node in reversed(task_detail.nodes) if node.recognition is not None),
            None,
        )
        if detail is None:
            raise InspectionError(
                f"Maa recognition returned no detail for {source_path or '<array>'}",
                source_path=source_path,
                recognition_type=type_name,
                trace_path=_trace_path(self.trace),
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        name = label or getattr(locator, "custom_recognition", type_name)
        annotated_path = None
        if self.debug is not None:
            annotated_path = self.debug._match(image, locator, MatchResult(detail), str(name))
        raw_path = self._save_native_image(_safe_attr(detail, "raw_image"), "raw", str(name))
        draw_paths = tuple(
            path
            for index, native_image in enumerate(self._draw_images(detail))
            if (path := self._save_native_image(native_image, f"draw-{index}", str(name))) is not None
        )
        result = InspectionResult(
            detail=detail,
            locator=locator,
            source_path=source_path,
            image_sha256=image_hash,
            elapsed_ms=elapsed_ms,
            annotated_path=annotated_path,
            raw_path=raw_path,
            draw_paths=draw_paths,
            trace_path=_trace_path(self.trace),
        )
        if self.trace is not None:
            self.trace.write(
                "inspection",
                label=str(name),
                source_path=source_path,
                image_sha256=image_hash,
                recognition_type=type_name,
                hit=result.hit,
                box=result.box,
                elapsed_ms=round(elapsed_ms, 3),
                annotated_path=annotated_path,
                raw_path=raw_path,
                draw_paths=draw_paths,
                detail=_safe_attr(detail, "raw_detail"),
            )
        return result

    def inspect_set(
        self,
        locator: Locator,
        fixtures: FixtureSet | str | Path,
        *,
        box_tolerance: int = 0,
        label: str | None = None,
    ) -> list[FixtureInspection]:
        """Inspect every image and apply its optional default expected record."""
        fixture_set = fixtures if isinstance(fixtures, FixtureSet) else FixtureSet(fixtures)
        results: list[FixtureInspection] = []
        for fixture in fixture_set:
            try:
                result = self.inspect(locator, fixture.path, label=label)
                try:
                    assert_expected(result, fixture.expected, box_tolerance=box_tolerance)
                except AssertionError as exc:
                    results.append(FixtureInspection(fixture, result, False, (str(exc),)))
                else:
                    results.append(FixtureInspection(fixture, result, True))
            except InspectionError as exc:
                results.append(FixtureInspection(fixture, None, False, error=exc))
        return results

    def _save_native_image(self, detail: Any, suffix: str, label: str) -> Path | None:
        if self.debug is None:
            return None
        if isinstance(detail, numpy.ndarray):
            return self.debug.draw(detail, label=f"{label}-{suffix}")
        image = _optional_array(detail)
        return None if image is None else self.debug.draw(image, label=f"{label}-{suffix}")

    @staticmethod
    def _draw_images(detail: Any) -> tuple[Any, ...]:
        images = _safe_attr(detail, "draw_images")
        return tuple(images or ())


def _wait_for_job(job: Any, *, timeout: int | None) -> Any:
    if timeout is None:
        return job.wait()
    completed = threading.Event()
    error: list[BaseException] = []

    def wait() -> None:
        try:
            job.wait()
        except BaseException as exc:  # pragma: no cover - native binding edge
            error.append(exc)
        finally:
            completed.set()

    thread = threading.Thread(target=wait, daemon=True)
    thread.start()
    if not completed.wait(timeout / 1000):
        raise InspectionTimeoutError(
            f"recognition exceeded timeout {timeout} ms",
            recognition_type=None,
        )
    if error:
        raise error[0]
    return job


def _normalize_image(image: numpy.ndarray, image_format: ImageFormat) -> numpy.ndarray:
    if image_format not in {"bgr", "rgb"}:
        raise ValueError("image_format must be 'bgr' or 'rgb'")
    if image.dtype != numpy.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("inspection image must be a uint8 array with shape (height, width, 3)")
    return image[..., ::-1].copy() if image_format == "rgb" else image


def _optional_array(value: Any) -> numpy.ndarray | None:
    try:
        if value is None:
            return None
        array = numpy.asarray(value)
        return array if array.ndim == 3 and array.shape[2] == 3 else None
    except Exception:
        return None


def _safe_attr(value: Any, name: str) -> Any:
    try:
        return getattr(value, name, None)
    except Exception:
        return None


def _trace_path(trace: Any) -> Path | None:
    path = _safe_attr(trace, "path")
    return Path(path) if path is not None else None


def _load_image(path: Path) -> numpy.ndarray:
    from PIL import Image

    with Image.open(path) as image:
        return numpy.asarray(image.convert("RGB"))[..., ::-1].copy()
