"""MaaFramework integration isolated in a killable process; no game input actions."""
from __future__ import annotations

import ast
import dataclasses
import io
import math
import multiprocessing as mp
import threading
import time
from pathlib import Path
from datetime import datetime, timezone

from PIL import Image

from .project import Project, png


def load_locators(project: Project, page_id: str, constructors=None):
    """Read the actual generated Python, using a tiny AST allowlist, never exec/import it."""
    project.check_generated()
    if constructors is None:
        from maaplus import AllOf, FirstOf, OCR, Template
        constructors = dict(Template=Template, OCR=OCR, FirstOf=FirstOf, AllOf=AllOf)
    page = project.page(page_id)
    tree = ast.parse(project.output_path(page["file"]).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == page["name"])
    values = {}
    for statement in cls.body:
        if isinstance(statement, ast.Pass):
            continue
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
            raise ValueError("Only generated locator assignments are allowed")
        call = statement.value
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id not in constructors:
            raise ValueError("Unapproved locator constructor")
        args = []
        for arg in call.args:
            if not isinstance(arg, ast.Name) or arg.id not in values:
                raise ValueError("Composite arguments must reference earlier locator constants")
            args.append(values[arg.id])
        kwargs = {}
        for kw in call.keywords:
            if kw.arg is None:
                raise ValueError("Expanded keyword arguments are not allowed")
            kwargs[kw.arg] = ast.literal_eval(kw.value)
        values[statement.targets[0].id] = constructors[call.func.id](*args, **kwargs)
    return {e["id"]: values[e["name"]] for e in page["elements"]}


def json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if dataclasses.is_dataclass(value):
        return {f.name: json_value(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if hasattr(value, "shape"):
        return {"array_shape": list(value.shape)}
    return str(value)


class MaaBackend:
    """Used exclusively inside the worker process. All native calls are serialized."""
    def __init__(self):
        self.controller = None
        self.device = None

    def configure(self, root):
        from maa.toolkit import Toolkit
        project = Project.open(root)
        log_dir = project.path(".debug/studio")
        log_dir.mkdir(parents=True, exist_ok=True)
        if not Toolkit.init_option(str(log_dir)):
            raise RuntimeError("MaaFramework option initialization failed")
        return project

    def discover(self, root, adb=""):
        from maa.toolkit import Toolkit
        self.configure(root)
        return [dict(name=d.name, adb_path=str(d.adb_path), address=d.address,
                     screencap_methods=int(d.screencap_methods), input_methods=int(d.input_methods),
                     config=d.config) for d in Toolkit.find_adb_devices(adb or None)]

    def connect(self, root, device):
        from maa.controller import AdbController
        project = self.configure(root)
        self.controller = None
        self.device = None
        options = {key: device[key] for key in ("screencap_methods", "input_methods", "config") if key in device}
        controller = AdbController(adb_path=Path(device["adb_path"]), address=device["address"], **options)
        if not controller.set_screenshot_target_short_side(project.data["short_side"]):
            raise RuntimeError("Cannot configure screenshot scaling")
        if not controller.post_connection().wait().succeeded:
            raise RuntimeError(f"Cannot connect to {device['address']}")
        self.controller, self.device = controller, device
        return {"connected": True, "short_side": project.data["short_side"]}

    def capture(self, root):
        project = Project.open(root)
        if self.controller is None:
            raise RuntimeError("Connect an emulator first")
        job = self.controller.post_screencap().wait()
        if not job.succeeded:
            raise RuntimeError("MaaFramework screenshot failed; reconnect the device")
        array = job.get()
        if array is None:
            raise RuntimeError("MaaFramework returned no screenshot")
        image = Image.fromarray(array[:, :, :3][:, :, ::-1].copy())  # BGR -> RGB
        if list(image.size) != project.data["size"]:
            raise ValueError(f"Controller frame {image.size} differs from project {project.data['size']}. Match the runtime resolution; no automatic stretching is performed.")
        return {"png": png(image), "source": {
            "kind": "adb", "captured_at": datetime.now(timezone.utc).isoformat(), "name": self.device["name"], "address": self.device["address"],
            "raw_size": list(self.controller.resolution), "frame_size": list(image.size),
            "short_side": project.data["short_side"],
        }}

    def recognize(self, root, page_id, shot_id):
        import numpy as np
        from maa.controller import DbgController
        from maa.resource import Resource
        from maa.tasker import Tasker
        from maaplus import Runtime

        project = self.configure(root)
        diagnostics = project.audit()
        if diagnostics["errors"]:
            raise ValueError("\n".join(diagnostics["errors"]))
        locators = load_locators(project, page_id)
        image = np.asarray(project.image(shot_id))[:, :, ::-1].copy()
        # Recreate the resource for each test so changed crops cannot be hidden by a native cache.
        resource = Resource()
        if not resource.post_bundle(str(project.path(project.data["resource_dir"]))).wait().succeeded:
            raise RuntimeError("Cannot load resource bundle. OCR also requires resource/model/ocr.")
        controller = DbgController(project.path(project.screenshot(shot_id)["path"]))
        if not controller.set_screenshot_use_raw_size(True) or not controller.post_connection().wait().succeeded:
            raise RuntimeError("Cannot initialize offline screenshot controller")
        tasker = Tasker()
        if not tasker.bind(resource, controller) or not tasker.inited:
            raise RuntimeError("Cannot bind MaaFramework resource/controller")
        runtime = Runtime(tasker=tasker, controller=controller, resource=resource)
        results = []
        for element in project.page(page_id)["elements"]:
            started = time.perf_counter()
            try:
                match = runtime.match(locators[element["id"]], image)
                results.append(dict(element=element["id"], name=element["name"], hit=bool(match),
                                    box=list(match.box) if match.box is not None else None,
                                    detail=json_value(getattr(match.detail, "detail", None)),
                                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2)))
            except Exception as exc:
                results.append(dict(element=element["id"], name=element["name"], error=str(exc),
                                    elapsed_ms=round((time.perf_counter() - started) * 1000, 2)))
        return results


def _serve(connection):
    backend = MaaBackend()
    try:
        while True:
            message = connection.recv()
            if message["action"] == "close":
                break
            try:
                action = message["action"]
                if action not in ("discover", "connect", "capture", "recognize"):
                    raise ValueError("Unknown engine command")
                value = getattr(backend, action)(**message["args"])
                connection.send({"ok": True, "value": value})
            except Exception as exc:
                connection.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        connection.close()


class WorkerClient:
    def __init__(self, timeout=45.0, *, _target=_serve):
        self.timeout = timeout
        self.target = _target
        self.process = self.connection = None
        self.lock = threading.Lock()

    def _start(self):
        context = mp.get_context("spawn")
        parent, child = context.Pipe()
        process = context.Process(target=self.target, args=(child,), daemon=True)
        process.start()
        child.close()
        self.process, self.connection = process, parent

    def request(self, action, **args):
        with self.lock:
            if self.process is None or not self.process.is_alive():
                self.close()
                self._start()
            connection = self.connection
            try:
                connection.send({"action": action, "args": args})
                if not connection.poll(self.timeout):
                    raise TimeoutError("MaaFramework operation timed out; worker stopped. Reconnect the emulator before continuing.")
                response = connection.recv()
            except (TimeoutError, EOFError, BrokenPipeError, OSError):
                self.close()
                raise
            if not response["ok"]:
                raise RuntimeError(response["error"])
            return response["value"]

    def close(self):
        process, connection = self.process, self.connection
        self.process = self.connection = None
        if process is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
        if connection is not None:
            connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
