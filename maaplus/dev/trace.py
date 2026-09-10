"""Structured traces and bounded evidence sessions for MaaPlus development."""

from __future__ import annotations

import json
import re
import shutil
import traceback as traceback_module
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, BaseException):
        return {"type": type(value).__name__, "message": str(value)}
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    return repr(value)


class JsonlTrace:
    """Append flushed, JSON-serializable events to one UTF-8 JSONL file."""

    def __init__(self, path: str | Path, *, run_id: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self._stream = self.path.open("a", encoding="utf-8")
        self._lock = Lock()
        self._sequence = 0
        self._closed = False

    def write(self, event: str, **fields: Any) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("trace is closed")
            self._sequence += 1
            record = {
                "schema": 1,
                "run_id": self.run_id,
                "sequence": self._sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **fields,
            }
            self._stream.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
            self._stream.flush()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._stream.close()
                self._closed = True

    def __enter__(self) -> JsonlTrace:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class TraceSession:
    """Own one isolated trace, image directory, and failure-artifact directory."""

    def __init__(self, root: str | Path = ".maaplus/runs", *, run_id: str | None = None) -> None:
        self.run_id = run_id or uuid4().hex
        self.directory = Path(root).resolve() / self.run_id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.assets_dir = self.directory / "images"
        self.failures_dir = self.directory / "failures"
        self.trace = JsonlTrace(self.directory / "run.jsonl", run_id=self.run_id)
        self._sink: TaskerTraceSink | None = None
        self._tasker: Any | None = None
        self._sink_id: int | None = None
        self._closed = False

    @property
    def path(self) -> Path:
        return self.trace.path

    def write(self, event: str, **fields: Any) -> None:
        self.trace.write(event, **fields)

    def create_debug(self, **kwargs: Any) -> Any:
        """Create a Debug writer rooted in this session's retained evidence directory."""
        from ..debug import Debug

        kwargs.setdefault("output_dir", self.assets_dir)
        kwargs.setdefault("max_images", 200)
        metadata = dict(kwargs.get("metadata", {}))
        metadata.setdefault("run_id", self.run_id)
        kwargs["metadata"] = metadata
        return Debug(**kwargs)

    def attach(self, tasker: Any) -> int | None:
        """Attach Maa notifications and close the sink automatically with the session."""
        if self._sink_id is not None:
            return self._sink_id
        self._tasker = tasker
        self._sink = TaskerTraceSink(self)
        self._sink_id = self._sink.add_to(tasker)
        return self._sink_id

    def failure_report(self, task_name: str, error: BaseException, *, attempts: int) -> Path:
        """Write a Markdown, JSON, and traceback bundle for one terminal task failure."""
        safe_name = re.sub(r"[^\w.-]+", "-", task_name).strip(".-") or "task"
        report_dir = self.failures_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{safe_name}"
        report_dir.mkdir(parents=True, exist_ok=True)
        traceback_text = "".join(
            traceback_module.format_exception(type(error), error, error.__traceback__)
        )
        debug_paths: list[str] = []
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines()[-100:]:
                record = json.loads(line)
                for key in ("debug_path", "annotated_path", "raw_path"):
                    path = record.get(key)
                    if path and str(path) not in debug_paths:
                        debug_paths.append(str(path))
                for path in record.get("draw_paths", ()) or ():
                    if str(path) not in debug_paths:
                        debug_paths.append(str(path))
        except (OSError, json.JSONDecodeError):
            pass
        retained_paths: list[str] = []
        for source in debug_paths:
            source_path = Path(source)
            if not source_path.is_file():
                continue
            destination = report_dir / "images" / source_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, destination)
            retained_paths.append(str(destination))
            self.write(
                "evidence.retained",
                source_path=source_path,
                path=destination,
                retained=True,
            )
        payload = {
            "schema": 1,
            "run_id": self.run_id,
            "task": task_name,
            "attempts": attempts,
            "error": {"type": type(error).__name__, "message": str(error)},
            "trace_path": str(self.path),
            "debug_paths": retained_paths,
        }
        (report_dir / "summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (report_dir / "traceback.txt").write_text(traceback_text, encoding="utf-8")
        lines = [
            f"# Task failure: {task_name}",
            "",
            f"- Run: `{self.run_id}`",
            f"- Attempts: `{attempts}`",
            f"- Error: `{type(error).__name__}: {error}`",
            f"- Trace: `{self.path}`",
        ]
        if retained_paths:
            lines.extend(["", "## Evidence", "", *[f"- `{path}`" for path in retained_paths]])
        (report_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return report_dir / "summary.md"

    def close(self) -> None:
        if self._closed:
            return
        if self._sink_id is not None and self._tasker is not None:
            try:
                self._sink.remove_from(self._tasker, self._sink_id)
            finally:
                self._sink_id = None
        images = [
            {"path": str(path), "retained": self.failures_dir in path.parents}
            for path in sorted(self.directory.rglob("*.png"))
        ]
        (self.directory / "index.json").write_text(
            json.dumps({"run_id": self.run_id, "trace_path": str(self.path), "images": images}, indent=2),
            encoding="utf-8",
        )
        (self.directory / "index.md").write_text(
            "\n".join([
                f"# Trace session {self.run_id}",
                "",
                f"Trace: `{self.path}`",
                "",
                *[f"- {'retained' if item['retained'] else 'recent'}: `{item['path']}`" for item in images],
            ]) + "\n",
            encoding="utf-8",
        )
        self.trace.close()
        self._closed = True

    def __enter__(self) -> TraceSession:
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        self.close()


class TaskerTraceSink:
    """MaaFramework Tasker event sink that forwards raw notifications to a trace."""

    def __init__(self, trace: Any) -> None:
        from maa.tasker import TaskerEventSink

        self._trace = trace
        self._sink = _make_sink(TaskerEventSink, trace)

    @property
    def sink(self) -> Any:
        return self._sink

    def add_to(self, tasker: Any) -> int | None:
        return tasker.add_sink(self._sink)

    def remove_from(self, tasker: Any, sink_id: int) -> None:
        tasker.remove_sink(sink_id)


def _make_sink(base: type[Any], trace: Any) -> Any:
    class Sink(base):
        def on_raw_notification(self, tasker: Any, msg: str, details: dict[str, Any]) -> None:
            trace.write("maa.notification", message=msg, details=details)

        def on_tasker_task(self, tasker: Any, noti_type: Any, detail: Any) -> None:
            trace.write(
                "maa.tasker",
                notification_type=noti_type,
                task_id=detail.task_id,
                entry=detail.entry,
                uuid=detail.uuid,
                hash=detail.hash,
            )

    return Sink()
