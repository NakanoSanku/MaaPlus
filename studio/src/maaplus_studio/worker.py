from __future__ import annotations

import importlib
import io
import multiprocessing
import sys
import threading
from pathlib import Path
from typing import Any

from .models import Project, StudioError, compile_locator


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


class NativeSession:
    """Lives exclusively in the child process. Its interface exposes no input operations."""

    def __init__(self, root: str):
        from maa.toolkit import Toolkit
        self.root = Path(root)
        Toolkit.init_option(self.root / ".maaplus/studio/native")
        self.controller = None
        self.source = None

    def handle(self, operation: str, payload: dict):
        from maa.controller import AdbController, Win32Controller
        from maa.define import MaaWin32InputMethodEnum, MaaWin32ScreencapMethodEnum
        from maa.toolkit import Toolkit

        if operation == "devices":
            kind = payload["kind"]
            if kind == "adb":
                return [{"id": item.address, "name": item.name, "address": item.address, "adb_path": str(item.adb_path)}
                        for item in Toolkit.find_adb_devices(payload.get("adb_path") or None)]
            return [{"id": str(item.hwnd.value if hasattr(item.hwnd, "value") else item.hwnd),
                     "name": item.window_name, "class_name": item.class_name}
                    for item in Toolkit.find_desktop_windows() if item.window_name or item.class_name]
        if operation == "disconnect":
            self.controller = None
            self.source = None
            return {"connected": False}
        if operation == "connect":
            self.controller = None
            self.source = None
            kind = payload["kind"]
            if kind == "adb":
                matches = [d for d in Toolkit.find_adb_devices(payload.get("adb_path") or None) if d.address == payload["id"]]
                if len(matches) != 1:
                    raise StudioError("设备不存在或不唯一，请重新发现并选择")
                device = matches[0]
                controller = AdbController(adb_path=device.adb_path, address=device.address,
                    screencap_methods=device.screencap_methods, input_methods=device.input_methods, config=device.config)
                label = device.name or device.address
            else:
                matches = [w for w in Toolkit.find_desktop_windows()
                           if str(w.hwnd.value if hasattr(w.hwnd, "value") else w.hwnd) == payload["id"]]
                if len(matches) != 1:
                    raise StudioError("窗口已失效，请重新发现并选择")
                method = payload.get("method", "FramePool")
                if method not in {"FramePool", "PrintWindow", "ScreenDC", "GDI", "DXGI_DesktopDup_Window"}:
                    raise StudioError("不支持的截图方式")
                controller = Win32Controller(matches[0].hwnd,
                    screencap_method=getattr(MaaWin32ScreencapMethodEnum, method),
                    mouse_method=MaaWin32InputMethodEnum.PostMessage,
                    keyboard_method=MaaWin32InputMethodEnum.PostMessage)
                label = matches[0].window_name or matches[0].class_name
            if not controller.post_connection().wait().succeeded:
                raise StudioError("原生控制器连接失败，请检查目标状态和截图方式")
            scale = payload.get("scale", "default")
            if scale == "raw":
                ok = controller.set_screenshot_use_raw_size(True)
            elif scale in {"short", "long"}:
                size = payload.get("size", 720)
                if type(size) is not int or not 64 <= size <= 8192:
                    raise StudioError("截图目标尺寸应为 64–8192")
                setter = controller.set_screenshot_target_short_side if scale == "short" else controller.set_screenshot_target_long_side
                ok = setter(size)
            else:
                ok = scale == "default"
            if not ok:
                raise StudioError("无法应用截图尺寸设置")
            self.controller = controller
            self.source = {"kind": kind, "name": label, "scale": scale, "size": payload.get("size"), "method": payload.get("method")}
            return {"connected": True, **self.source}
        if operation == "capture":
            if self.controller is None:
                raise StudioError("请先连接设备或窗口")
            job = self.controller.post_screencap().wait()
            if not job.succeeded:
                raise StudioError("截图失败，目标可能已断开或窗口已关闭")
            image = job.get()
            if image is None or image.ndim != 3 or image.shape[2] != 3 or image.size == 0:
                raise StudioError("控制器返回了无效截图")
            from PIL import Image
            buffer = io.BytesIO()
            Image.fromarray(image[..., ::-1]).save(buffer, format="PNG")
            return {"image": buffer.getvalue(), "source": self.source}
        if operation == "inspect":
            return self.inspect(payload)
        raise StudioError("未知原生操作")

    def inspect(self, payload: dict):
        from maa.resource import Resource
        from maa.tasker import Tasker
        from maaplus.dev import Inspector

        project = Project.model_validate(payload["project"])
        bundle = self.root / project.resource_dir
        if not bundle.is_dir():
            raise StudioError(f"资源目录不存在：{project.resource_dir}")
        resource = Resource()
        if not resource.post_bundle(bundle).wait().succeeded:
            raise StudioError("MaaFramework 资源加载失败")
        if project.resource_hook:
            module_name, attribute = project.resource_hook.split(":", 1)
            sys.path.insert(0, str(self.root))
            try:
                importlib.invalidate_caches()
                module = importlib.import_module(module_name)
                module = importlib.reload(module)
                hook = module
                for part in attribute.split("."):
                    hook = getattr(hook, part)
                if not callable(hook):
                    raise StudioError("资源扩展不是可调用函数")
                hook(resource)
            finally:
                sys.path.pop(0)
        mapping = {item.id: item for item in project.locators}

        def prerequisites(key: str):
            item = mapping[key]
            for child in item.children:
                prerequisites(child)
            if item.kind == "Custom":
                name = item.params.get("custom_recognition")
                if name not in getattr(resource, "_custom_recognition_holder", {}):
                    raise StudioError(f"自定义识别 {name!r} 尚未注册，请配置资源扩展函数")
            if item.kind == "OCR":
                required = ["rec.onnx", "keys.txt"] + ([] if item.params.get("only_rec") else ["det.onnx"])
                model = item.params.get("model", "")
                directory = (bundle / "model/ocr" / model).resolve()
                if not directory.is_relative_to(bundle.resolve()):
                    raise StudioError("OCR 模型路径必须位于资源目录内")
                missing = [name for name in required if not (directory / name).is_file()]
                if missing:
                    raise StudioError("OCR 模型缺失：" + directory.relative_to(bundle.resolve()).as_posix() + "/" + ", ".join(missing))
            for name in item.params.get("template", []):
                target = (bundle / "image" / name).resolve()
                if not target.is_relative_to(self.root) or not target.is_file():
                    raise StudioError(f"模板不存在或超出项目：{name}")

        prerequisites(payload["locator_id"])
        # Offline images are independently bound; validation never depends on the live device.
        from .offline import image_controller
        controller = image_controller(Path(payload["image_path"]))
        if not controller.post_connection().wait().succeeded:
            raise StudioError("离线图像控制器初始化失败")
        tasker = Tasker()
        inspector = Inspector.from_maa(tasker=tasker, controller=controller, resource=resource,
                                      output_dir=None, timeout=None)
        result = inspector.inspect(compile_locator(project, payload["locator_id"]), Path(payload["image_path"]))
        return {"hit": result.hit, "box": result.box, "elapsed_ms": result.elapsed_ms,
                "raw_detail": _json_value(result.raw_detail), "snapshot_id": payload["snapshot_id"],
                "locator_id": payload["locator_id"]}


def _serve(connection, root):
    try:
        session = NativeSession(root)
        while True:
            message = connection.recv()
            try:
                value = session.handle(message["operation"], message["payload"])
                connection.send({"ok": True, "value": value})
            except Exception as exc:
                connection.send({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        try:
            connection.send({"ok": False, "error": f"原生运行时初始化失败：{exc}"})
        except (EOFError, BrokenPipeError):
            pass
    finally:
        connection.close()


class NativeWorker:
    def __init__(self, root: Path, *, target=_serve):
        self.root = root
        self.target = target
        self.lock = threading.RLock()
        self.process = None
        self.pipe = None
        self.state: dict[str, Any] = {"connected": False}

    def close(self):
        with self.lock:
            if self.process is not None:
                if self.process.is_alive():
                    self.process.terminate()
                self.process.join(3)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(3)
                self.process.close()
            if self.pipe is not None:
                self.pipe.close()
            self.process = self.pipe = None
            self.state = {"connected": False}

    def request(self, operation: str, payload: dict, *, timeout: float = 30):
        with self.lock:
            if self.process is None or not self.process.is_alive():
                self.close()
                context = multiprocessing.get_context("spawn")
                self.pipe, child = context.Pipe()
                self.process = context.Process(target=self.target, args=(child, str(self.root)), daemon=True)
                self.process.start()
                child.close()
            try:
                self.pipe.send({"operation": operation, "payload": payload})
                if not self.pipe.poll(timeout):
                    self.close()
                    raise StudioError("原生操作超时，工作进程已重置；可重新连接或再次验证")
                response = self.pipe.recv()
            except (EOFError, BrokenPipeError, OSError) as exc:
                self.close()
                raise StudioError("原生工作进程已退出，请重试") from exc
            if not response["ok"]:
                if operation in {"connect", "capture"}:
                    self.close()
                raise StudioError(response["error"])
            if operation in {"connect", "disconnect"}:
                self.state = response["value"]
            return response["value"]
