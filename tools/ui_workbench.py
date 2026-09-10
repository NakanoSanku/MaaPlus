"""MaaPlus UI Workbench FastAPI backend bridge and dev server.

Independent from the runtime core; assists UI layer development, visual creation,
device connection, screencap, input, and fixture backtesting.
"""

from __future__ import annotations

import argparse
import ast
import base64
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Device support is intentionally loaded separately from recognition support.
# A missing Pillow/NumPy installation must not make ADB devices disappear.
try:
    from maaplus.dev.controller import create_adb_controller, find_adb_devices

    MAA_DEVICE_AVAILABLE = True
except Exception:
    create_adb_controller = None
    find_adb_devices = None
    MAA_DEVICE_AVAILABLE = False

try:
    from maa.controller import CustomController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maaplus import OCR, Template
    from maaplus.locator import recognition_type
    import numpy as np
    from PIL import Image

    class StandaloneDummyController(CustomController):
        def request_uuid(self) -> str:
            return "standalone_dummy_controller"

    MAA_AVAILABLE = True
except Exception:
    MAA_AVAILABLE = False
    CustomController = None
    StandaloneDummyController = None
    Resource = None
    Tasker = None
    OCR = None
    Template = None
    recognition_type = None
    np = None
    Image = None

logger = logging.getLogger("maaplus.workbench")


class DeviceBridge:
    """Manage device connection, screenshots and input with MaaFramework + raw ADB fallback."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.controller: Any = None
        self.tasker: Any = None
        self.resource: Any = None
        self.connected_device: dict[str, Any] | None = None
        self.last_screencap_bytes: bytes | None = None
        self.last_screencap_np: Any = None
        self.lock = threading.Lock()

    @staticmethod
    def _resolve_adb_path(adb_path: str | Path = "adb") -> str:
        requested = str(adb_path or "adb")
        if Path(requested).is_file():
            return str(Path(requested).resolve())

        env_path = os.environ.get("ADB_PATH")
        if requested == "adb" and env_path and Path(env_path).is_file():
            return str(Path(env_path).resolve())

        found = shutil.which(requested)
        if found:
            return found
        raise RuntimeError(
            "未找到 adb。请将 Android platform-tools 加入 PATH，"
            "或设置 ADB_PATH 环境变量。"
        )

    @classmethod
    def _run_adb(
        cls,
        args: list[str],
        *,
        adb_path: str | Path = "adb",
        timeout: float = 5,
    ) -> subprocess.CompletedProcess[bytes]:
        adb = cls._resolve_adb_path(adb_path)
        return subprocess.run(
            [adb, *args],
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def _discover_raw_adb_devices(self, adb_path: str | Path = "adb") -> list[dict[str, Any]]:
        try:
            result = self._run_adb(["devices", "-l"], adb_path=adb_path, timeout=4)
        except Exception as exc:
            logger.debug("raw adb discovery unavailable: %s", exc)
            return []

        if result.returncode != 0:
            return []

        devices: list[dict[str, Any]] = []
        output = result.stdout.decode("utf-8", errors="replace")
        resolved_adb = self._resolve_adb_path(adb_path)
        for line in output.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            address, state = parts[0], parts[1]
            if state != "device":
                continue
            metadata: dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    metadata[key] = value
            model = metadata.get("model") or metadata.get("device") or address
            devices.append(
                {
                    "address": address,
                    "name": model.replace("_", " "),
                    "adb_path": resolved_adb,
                    "screencap_methods": 0,
                    "input_methods": 0,
                    "config": metadata,
                    "source": "adb",
                    "connected": bool(
                        self.connected_device
                        and self.connected_device.get("address") == address
                    ),
                }
            )
        return devices

    def discover_devices(self) -> list[dict[str, Any]]:
        """Discover devices through MaaFramework first, then raw ``adb devices -l``."""
        devices: list[dict[str, Any]] = []
        seen: set[str] = set()

        if MAA_DEVICE_AVAILABLE and find_adb_devices is not None:
            try:
                for device in find_adb_devices():
                    address = str(device.address)
                    if not address:
                        continue
                    devices.append(
                        {
                            "address": address,
                            "name": device.name or address,
                            "adb_path": str(device.adb_path),
                            "screencap_methods": device.screencap_methods,
                            "input_methods": device.input_methods,
                            "config": device.config,
                            "source": "maaplus",
                            "connected": bool(
                                self.connected_device
                                and self.connected_device.get("address") == address
                            ),
                        }
                    )
                    seen.add(address)
            except Exception as exc:
                logger.warning("MaaFramework device discovery failed: %s", exc)

        for device in self._discover_raw_adb_devices():
            if device["address"] not in seen:
                devices.append(device)
                seen.add(device["address"])

        return devices

    def _verify_raw_adb(self, address: str, adb_path: str | Path) -> str:
        resolved_adb = self._resolve_adb_path(adb_path)
        state = self._run_adb(["-s", address, "get-state"], adb_path=resolved_adb, timeout=4)
        if state.returncode == 0 and state.stdout.decode(errors="replace").strip() == "device":
            return resolved_adb

        # Network emulators/devices may need an explicit adb connect first.
        if ":" in address:
            connect_result = self._run_adb(["connect", address], adb_path=resolved_adb, timeout=6)
            logger.debug(
                "adb connect %s: %s",
                address,
                connect_result.stdout.decode(errors="replace").strip(),
            )
            state = self._run_adb(["-s", address, "get-state"], adb_path=resolved_adb, timeout=4)
            if state.returncode == 0 and state.stdout.decode(errors="replace").strip() == "device":
                return resolved_adb

        detail = (state.stderr or state.stdout).decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"ADB device {address!r} is not in device state")

    def connect(self, address: str, adb_path: str = "adb") -> dict[str, Any]:
        """Connect to a real device, preferring MaaFramework and falling back to verified raw ADB."""
        address = address.strip()
        if not address or address == "offline":
            return {"success": False, "error": "请选择或输入真实 ADB 设备地址"}

        with self.lock:
            self._disconnect_locked()
            maa_error: Exception | None = None

            if MAA_DEVICE_AVAILABLE and create_adb_controller is not None:
                try:
                    controller = create_adb_controller(serial=address, adb_path=adb_path)
                    self.controller = controller
                    self.tasker = None
                    self._ensure_tasker()
                    self.connected_device = {
                        "address": address,
                        "adb_path": adb_path,
                        "mode": "maaplus_adb",
                    }
                    logger.info("Connected to device via MaaFramework: %s", address)
                    return {"success": True, "address": address, "mode": "maaplus_adb"}
                except Exception as exc:
                    maa_error = exc
                    logger.warning("MaaFramework connection failed for %s: %s", address, exc)

            try:
                resolved_adb = self._verify_raw_adb(address, adb_path)
                self.connected_device = {
                    "address": address,
                    "adb_path": resolved_adb,
                    "mode": "adb_fallback",
                }
                logger.info("Connected to device via raw ADB fallback: %s", address)
                return {"success": True, "address": address, "mode": "adb_fallback"}
            except Exception as adb_exc:
                detail = f"ADB 连接失败: {adb_exc}"
                if maa_error is not None:
                    detail = f"MaaFramework 连接失败: {maa_error}; {detail}"
                return {"success": False, "error": detail}

    def _ensure_tasker(self) -> Any:
        if self.tasker is not None:
            return self.tasker
        if not MAA_AVAILABLE or Tasker is None or Resource is None:
            return None

        try:
            if self.resource is None:
                self.resource = Resource()
                resource_dirs = [
                    self.project_root / "resource",
                    self.project_root / "examples" / "complete_project" / "resource",
                ]
                for resource_dir in resource_dirs:
                    if not resource_dir.is_dir():
                        continue
                    try:
                        job = self.resource.post_bundle(str(resource_dir)).wait()
                        if not job.succeeded:
                            self.resource.post_image(str(resource_dir)).wait()
                    except Exception as exc:
                        logger.debug("Resource loading error for %s: %s", resource_dir, exc)

            controller = self.controller
            if controller is None and StandaloneDummyController is not None:
                controller = StandaloneDummyController()
            if controller is not None:
                tasker = Tasker()
                if tasker.bind(self.resource, controller):
                    self.tasker = tasker
                    return tasker
        except Exception as exc:
            logger.warning("Failed to initialize tasker: %s", exc)
        return None

    def disconnect(self) -> dict[str, Any]:
        with self.lock:
            self._disconnect_locked()
            return {"success": True}

    def _disconnect_locked(self) -> None:
        self.controller = None
        self.tasker = None
        self.resource = None
        self.connected_device = None
        self.last_screencap_bytes = None
        self.last_screencap_np = None

    def _remember_raw_screencap(self, raw_bytes: bytes) -> None:
        self.last_screencap_bytes = raw_bytes
        if Image is None or np is None:
            return
        try:
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            rgb = np.array(image)
            self.last_screencap_np = rgb[:, :, ::-1]
        except Exception as exc:
            logger.debug("Unable to decode raw ADB screencap for recognition: %s", exc)

    def screencap(self) -> bytes:
        with self.lock:
            if self.controller is not None:
                job = self.controller.post_screencap().wait()
                if not job.succeeded:
                    raise RuntimeError("Screencap failed on controller")
                image_np = job.get()
                self.last_screencap_np = image_np
                if Image is not None and np is not None:
                    if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                        image = Image.fromarray(image_np[:, :, ::-1])
                    else:
                        image = Image.fromarray(image_np)
                    buffer = io.BytesIO()
                    image.save(buffer, format="JPEG", quality=85)
                    self.last_screencap_bytes = buffer.getvalue()
                    return self.last_screencap_bytes
                raise RuntimeError("Pillow is required to encode MaaFramework screenshots")

            if self.connected_device and self.connected_device.get("address"):
                address = self.connected_device["address"]
                adb_path = self.connected_device.get("adb_path", "adb")
                result = self._run_adb(
                    ["-s", address, "exec-out", "screencap", "-p"],
                    adb_path=adb_path,
                    timeout=6,
                )
                if result.returncode == 0 and result.stdout.startswith(b"\x89PNG"):
                    self._remember_raw_screencap(result.stdout)
                    return result.stdout
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(detail or "ADB screencap failed")

            raise RuntimeError("No device connected")

    def click(self, x: int, y: int) -> bool:
        with self.lock:
            if self.controller is not None:
                return bool(self.controller.post_click(int(x), int(y)).wait().succeeded)
            if self.connected_device and self.connected_device.get("address"):
                result = self._run_adb(
                    ["-s", self.connected_device["address"], "shell", "input", "tap", str(int(x)), str(int(y))],
                    adb_path=self.connected_device.get("adb_path", "adb"),
                    timeout=3,
                )
                return result.returncode == 0
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500) -> bool:
        with self.lock:
            if self.controller is not None:
                return bool(
                    self.controller.post_swipe(
                        int(x1), int(y1), int(x2), int(y2), int(duration_ms)
                    ).wait().succeeded
                )
            if self.connected_device and self.connected_device.get("address"):
                result = self._run_adb(
                    [
                        "-s", self.connected_device["address"], "shell", "input", "swipe",
                        str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms)),
                    ],
                    adb_path=self.connected_device.get("adb_path", "adb"),
                    timeout=5,
                )
                return result.returncode == 0
            return False

    def press_key(self, keycode: int) -> bool:
        with self.lock:
            if self.controller is not None and hasattr(self.controller, "post_press_key"):
                return bool(self.controller.post_press_key(int(keycode)).wait().succeeded)
            if self.connected_device and self.connected_device.get("address"):
                result = self._run_adb(
                    ["-s", self.connected_device["address"], "shell", "input", "keyevent", str(int(keycode))],
                    adb_path=self.connected_device.get("adb_path", "adb"),
                    timeout=3,
                )
                return result.returncode == 0
            return False

    def recognize(self, locator_data: dict[str, Any], image_bytes: bytes | None = None) -> dict[str, Any]:
        """Test recognition using MaaFramework."""
        if not MAA_AVAILABLE or np is None or Image is None or Template is None or OCR is None:
            return {
                "success": False,
                "error": "MaaFramework recognition dependencies are unavailable.",
            }

        target_np = None
        if image_bytes:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            target_np = np.array(image)[:, :, ::-1]
        elif self.last_screencap_np is not None:
            target_np = self.last_screencap_np
        else:
            try:
                self.screencap()
                target_np = self.last_screencap_np
            except Exception as exc:
                return {"success": False, "error": f"No image available: {exc}"}

        if target_np is None:
            return {"success": False, "error": "Failed to acquire target image"}

        locator_type = locator_data.get("type", "Template")
        roi_value = locator_data.get("roi")
        if roi_value and len(roi_value) == 4 and all(value is not None for value in roi_value):
            roi = tuple(map(int, roi_value))
        else:
            roi = (0, 0, 0, 0)

        started = time.perf_counter()
        try:
            if locator_type == "Template":
                templates = locator_data.get("template", [])
                if isinstance(templates, str):
                    templates = [templates]
                threshold = locator_data.get("threshold", 0.85)
                threshold_list = [float(threshold)] if not isinstance(threshold, list) else threshold
                locator = Template(template=templates, threshold=threshold_list, roi=roi)
            elif locator_type == "OCR":
                expected = locator_data.get("expected", [])
                if isinstance(expected, str):
                    expected = [expected]
                locator = OCR(expected=expected, roi=roi)
            else:
                return {"success": False, "error": f"Unsupported locator type: {locator_type}"}

            tasker = self._ensure_tasker()
            if not tasker or recognition_type is None:
                return {"success": False, "error": "MaaFramework Tasker 未能初始化"}

            if locator_type == "Template" and self.resource is not None:
                templates = locator_data.get("template", [])
                if isinstance(templates, str):
                    templates = [templates]
                for template_name in templates:
                    for base in [
                        self.project_root / "resource",
                        self.project_root / "examples" / "complete_project" / "resource",
                        self.project_root,
                    ]:
                        target_file = base / template_name
                        if target_file.exists():
                            try:
                                self.resource.post_image(str(target_file.parent)).wait()
                            except Exception:
                                pass
                            break

            job = tasker.post_recognition(recognition_type(locator), locator, target_np).wait()
            elapsed_ms = (time.perf_counter() - started) * 1000
            if not job.succeeded:
                return {
                    "success": False,
                    "hit": False,
                    "elapsed_ms": round(elapsed_ms, 2),
                    "error": "MaaFramework recognition failed",
                }

            detail = job.get()
            node = next(iter(detail.nodes), None) if detail and detail.nodes else None
            recognition = getattr(node, "recognition", None) if node else None
            hit = bool(getattr(recognition, "hit", False)) if recognition else False
            box = getattr(recognition, "box", None) if recognition else None
            score = getattr(recognition, "score", None) if recognition else None
            return {
                "success": True,
                "hit": hit,
                "box": list(box) if box is not None else None,
                "score": score,
                "elapsed_ms": round(elapsed_ms, 2),
                "raw_detail": getattr(recognition, "raw_detail", None),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def save_template_image(self, rel_path: str, image_b64: str) -> dict[str, Any]:
        try:
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(image_b64)
            resource_dir = self.project_root / "resource"
            if not resource_dir.exists():
                example_resource = self.project_root / "examples" / "complete_project" / "resource"
                resource_dir = example_resource if example_resource.exists() else resource_dir
                resource_dir.mkdir(parents=True, exist_ok=True)
            target_file = resource_dir / rel_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(raw_bytes)
            return {
                "success": True,
                "saved_path": str(target_file.resolve()),
                "relative_path": str(rel_path),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def scan_project_ui(self) -> dict[str, Any]:
        ui_files: list[dict[str, Any]] = []
        search_dirs = [
            self.project_root / "ui",
            self.project_root / "demo" / "ui",
            self.project_root / "examples" / "complete_project" / "demo" / "ui",
        ]
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for pyfile in search_dir.glob("*.py"):
                if pyfile.name == "__init__.py":
                    continue
                try:
                    classes = self._parse_ui_file(pyfile)
                    if classes:
                        ui_files.append(
                            {
                                "file_path": str(pyfile.resolve()),
                                "rel_path": str(pyfile.relative_to(self.project_root)),
                                "classes": classes,
                            }
                        )
                except Exception as exc:
                    logger.debug("Failed parsing %s: %s", pyfile, exc)
        return {"ui_files": ui_files}

    def _parse_ui_file(self, file_path: Path) -> list[dict[str, Any]]:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        results: list[dict[str, Any]] = []
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            class_data: dict[str, Any] = {"name": node.name, "locators": []}
            for item in node.body:
                if not isinstance(item, ast.Assign) or len(item.targets) != 1:
                    continue
                target = item.targets[0]
                if not isinstance(target, ast.Name):
                    continue
                locator_info = self._parse_locator_call(item.value)
                if locator_info:
                    locator_info["name"] = target.id
                    class_data["locators"].append(locator_info)
            if class_data["locators"]:
                class_data["screenshots"] = self._find_class_screenshots(node.name)
                results.append(class_data)
        return results

    def _find_class_screenshots(self, class_name: str) -> list[dict[str, Any]]:
        extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        search_dirs = [
            self.project_root / "assets" / "fixtures" / class_name,
            self.project_root / "tests" / "fixtures" / class_name,
            self.project_root / "fixtures" / class_name,
        ]
        found: list[dict[str, Any]] = []
        for directory in search_dirs:
            if not directory.is_dir():
                continue
            for file in sorted(directory.iterdir()):
                if not file.is_file() or file.suffix.lower() not in extensions:
                    continue
                try:
                    raw = file.read_bytes()
                    found.append(
                        {
                            "id": file.stem,
                            "name": file.name,
                            "path": str(file.relative_to(self.project_root)).replace("\\", "/"),
                            "dataUrl": f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}",
                        }
                    )
                except Exception:
                    pass
            if found:
                break
        return found

    def _parse_locator_call(self, node: ast.AST) -> dict[str, Any] | None:
        if not isinstance(node, ast.Call):
            return None
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        else:
            return None
        if function_name not in {"Template", "OCR", "FirstOf", "AllOf", "JCustomRecognition"}:
            return None
        data: dict[str, Any] = {"type": function_name}
        for keyword in node.keywords:
            try:
                data[keyword.arg] = ast.literal_eval(keyword.value)
            except Exception:
                pass
        return data

    def run_backtest(self, locator_data: dict[str, Any], fixture_dir: str | None = None) -> dict[str, Any]:
        directory = Path(fixture_dir) if fixture_dir else self.project_root / "fixtures"
        if not directory.exists():
            example = self.project_root / "examples" / "fixture_project" / "fixtures"
            if example.exists():
                directory = example
            else:
                return {"success": False, "error": f"Fixture directory not found: {directory}"}

        expected_map: dict[str, Any] = {}
        expected_json = directory / "expected.json"
        if expected_json.exists():
            try:
                expected_map = json.loads(expected_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        results: list[dict[str, Any]] = []
        extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        for image_path in sorted(directory.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in extensions:
                continue
            raw = image_path.read_bytes()
            expected = expected_map.get(image_path.name, {})
            recognition = self.recognize(locator_data, image_bytes=raw)
            hit = recognition.get("hit", False)
            box = recognition.get("box")
            passed = True
            reasons: list[str] = []
            if "hit" in expected and bool(hit) != bool(expected["hit"]):
                passed = False
                reasons.append(f"Expected hit={expected['hit']}, got {hit}")
            if passed and expected.get("box"):
                target_box = expected["box"]
                tolerance = int(expected.get("box_tolerance", 5))
                if not box:
                    passed = False
                    reasons.append("Expected bounding box, got None")
                elif any(abs(a - b) > tolerance for a, b in zip(box, target_box)):
                    passed = False
                    reasons.append(f"Box mismatch: expected {target_box} ±{tolerance}, got {box}")
            results.append(
                {
                    "filename": image_path.name,
                    "thumbnail": f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}",
                    "hit": hit,
                    "box": box,
                    "score": recognition.get("score"),
                    "elapsed_ms": recognition.get("elapsed_ms", 0),
                    "passed": passed,
                    "fail_reasons": reasons,
                    "expected": expected,
                }
            )
        passed_count = sum(1 for result in results if result["passed"])
        return {
            "success": True,
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": round(passed_count / len(results) * 100, 1) if results else 0,
            "results": results,
        }

    def save_bound_screenshot(self, ui_class: str, name: str, image_b64: str) -> dict[str, Any]:
        try:
            target_dir = self.project_root / "assets" / "fixtures" / ui_class
            target_dir.mkdir(parents=True, exist_ok=True)
            clean_name = name.strip() or "screenshot.png"
            if not clean_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                clean_name += ".png"
            target_file = target_dir / clean_name
            raw_b64 = image_b64.split(",", 1)[1] if image_b64.startswith("data:image") else image_b64
            raw = base64.b64decode(raw_b64)
            target_file.write_bytes(raw)
            relative_path = str(target_file.relative_to(self.project_root)).replace("\\", "/")
            return {
                "success": True,
                "id": target_file.stem,
                "name": clean_name,
                "path": relative_path,
                "dataUrl": f"data:image/png;base64,{raw_b64}",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def run_class_backtest(
        self,
        ui_class: str,
        locators: list[dict[str, Any]],
        screenshots: list[dict[str, Any]] | None = None,
        fixture_dir: str | None = None,
    ) -> dict[str, Any]:
        target_images: list[tuple[str, bytes]] = []
        if screenshots:
            for screenshot in screenshots:
                name = screenshot.get("name", "screenshot.png")
                raw = b""
                data_value = screenshot.get("dataUrl") or screenshot.get("data")
                if data_value:
                    if data_value.startswith("data:image"):
                        data_value = data_value.split(",", 1)[1]
                    try:
                        raw = base64.b64decode(data_value)
                    except Exception:
                        pass
                elif screenshot.get("path"):
                    path = self.project_root / screenshot["path"]
                    if path.is_file():
                        raw = path.read_bytes()
                if raw:
                    target_images.append((name, raw))

        if not target_images:
            search_dirs: list[Path] = []
            if fixture_dir:
                search_dirs.append(Path(fixture_dir))
            search_dirs.extend(
                [
                    self.project_root / "assets" / "fixtures" / ui_class,
                    self.project_root / "tests" / "fixtures" / ui_class,
                    self.project_root / "fixtures" / ui_class,
                ]
            )
            extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
            for directory in search_dirs:
                if not directory.is_dir():
                    continue
                for file in sorted(directory.iterdir()):
                    if file.is_file() and file.suffix.lower() in extensions:
                        target_images.append((file.name, file.read_bytes()))
                if target_images:
                    break

        if not target_images:
            return {
                "success": False,
                "error": f"UI 类「{ui_class}」尚未绑定任何样本截图，请先添加或上传截图",
                "ui_class": ui_class,
                "total_screenshots": 0,
                "total_locators": len(locators),
                "total_checks": 0,
                "passed_checks": 0,
                "pass_rate": 0.0,
                "matrix": [],
            }

        matrix: list[dict[str, Any]] = []
        total_checks = 0
        passed_checks = 0
        for image_name, image_bytes in target_images:
            row_results: dict[str, Any] = {}
            row_passed = True
            for locator in locators:
                total_checks += 1
                recognition = self.recognize(locator, image_bytes=image_bytes)
                hit = recognition.get("hit", False)
                if hit:
                    passed_checks += 1
                else:
                    row_passed = False
                row_results[locator.get("name", "unknown")] = {
                    "hit": hit,
                    "score": recognition.get("score"),
                    "box": recognition.get("box"),
                    "elapsed_ms": recognition.get("elapsed_ms", 0),
                    "error": recognition.get("error"),
                }
            matrix.append(
                {
                    "screenshot_name": image_name,
                    "thumbnail": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}",
                    "passed": row_passed,
                    "results": row_results,
                }
            )

        return {
            "success": True,
            "ui_class": ui_class,
            "total_screenshots": len(target_images),
            "total_locators": len(locators),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "pass_rate": round(passed_checks / total_checks * 100, 1) if total_checks else 0.0,
            "matrix": matrix,
        }


class ConnectRequest(BaseModel):
    address: str
    adb_path: str = "adb"


class TapRequest(BaseModel):
    x: int
    y: int


class SwipeRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration: int = 500


class KeyRequest(BaseModel):
    keycode: int = 4


class RecognizeRequest(BaseModel):
    locator: dict[str, Any]
    image: str | None = None


class SaveTemplateRequest(BaseModel):
    path: str = "template.png"
    image: str = ""


class BacktestRequest(BaseModel):
    locator: dict[str, Any]
    fixture_dir: str | None = None


class ClassBacktestRequest(BaseModel):
    ui_class: str
    locators: list[dict[str, Any]]
    screenshots: list[dict[str, Any]] = []
    fixture_dir: str | None = None


class SaveBoundScreenshotRequest(BaseModel):
    ui_class: str
    name: str = "screenshot.png"
    image: str = ""


class SaveUIRequest(BaseModel):
    file_path: str
    code: str


ConnectRequest.model_rebuild()
TapRequest.model_rebuild()
SwipeRequest.model_rebuild()
KeyRequest.model_rebuild()
RecognizeRequest.model_rebuild()
SaveTemplateRequest.model_rebuild()
BacktestRequest.model_rebuild()
ClassBacktestRequest.model_rebuild()
SaveBoundScreenshotRequest.model_rebuild()
SaveUIRequest.model_rebuild()


def create_app(bridge: DeviceBridge | None = None, project_root: Path | None = None) -> FastAPI:
    """Create and configure the UI Workbench application."""
    if project_root is None:
        project_root = Path.cwd()
    if bridge is None:
        bridge = DeviceBridge(project_root)

    app = FastAPI(
        title="MaaPlus UI Workbench",
        description="Developer workbench for MaaPlus UI creation, device control and regression testing.",
        version="1.4.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    @app.get("/workbench", response_class=HTMLResponse)
    async def get_workbench_html():
        html_path = Path(__file__).parent / "ui_workbench.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="ui_workbench.html not found")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    @app.get("/api/status")
    async def get_status():
        return {
            "maa_available": MAA_AVAILABLE,
            "maa_device_available": MAA_DEVICE_AVAILABLE,
            "adb_available": bool(shutil.which("adb") or os.environ.get("ADB_PATH")),
            "project_root": str(bridge.project_root.resolve()),
            "connected_device": bridge.connected_device,
        }

    @app.get("/api/devices")
    async def get_devices():
        return {"devices": bridge.discover_devices()}

    @app.get("/api/screencap")
    async def get_screencap():
        try:
            image_bytes = bridge.screencap()
            return Response(
                content=image_bytes,
                media_type="image/png" if image_bytes.startswith(b"\x89PNG") else "image/jpeg",
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/project_ui")
    async def get_project_ui():
        return bridge.scan_project_ui()

    @app.post("/api/connect")
    async def connect_device(req: ConnectRequest):
        return bridge.connect(req.address, adb_path=req.adb_path)

    @app.post("/api/disconnect")
    async def disconnect_device():
        return bridge.disconnect()

    @app.post("/api/input/tap")
    async def input_tap(req: TapRequest):
        return {"success": bridge.click(req.x, req.y)}

    @app.post("/api/input/swipe")
    async def input_swipe(req: SwipeRequest):
        return {"success": bridge.swipe(req.x1, req.y1, req.x2, req.y2, req.duration)}

    @app.post("/api/input/key")
    async def input_key(req: KeyRequest):
        return {"success": bridge.press_key(req.keycode)}

    @app.post("/api/recognize")
    async def recognize(req: RecognizeRequest):
        image_bytes = None
        if req.image:
            image_b64 = req.image.split(",", 1)[1] if "," in req.image else req.image
            image_bytes = base64.b64decode(image_b64)
        return bridge.recognize(req.locator, image_bytes=image_bytes)

    @app.post("/api/save_template")
    async def save_template(req: SaveTemplateRequest):
        return bridge.save_template_image(req.path, req.image)

    @app.post("/api/backtest")
    async def backtest(req: BacktestRequest):
        return bridge.run_backtest(req.locator, req.fixture_dir)

    @app.post("/api/class_backtest")
    async def class_backtest(req: ClassBacktestRequest):
        return bridge.run_class_backtest(
            ui_class=req.ui_class,
            locators=req.locators,
            screenshots=req.screenshots,
            fixture_dir=req.fixture_dir,
        )

    @app.post("/api/save_bound_screenshot")
    async def save_bound_screenshot(req: SaveBoundScreenshotRequest):
        return bridge.save_bound_screenshot(req.ui_class, req.name, req.image)

    @app.post("/api/save_ui")
    async def save_ui(req: SaveUIRequest):
        try:
            target = bridge.project_root / req.file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(req.code, encoding="utf-8")
            return {"success": True, "path": str(target.resolve())}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    app.state.bridge = bridge
    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    project_root: Path | None = None,
    open_browser: bool = True,
) -> None:
    if project_root is None:
        project_root = Path.cwd()
    app = create_app(project_root=project_root)
    url = f"http://{host}:{port}/"
    print(f"MaaPlus UI Workbench running at: {url}")
    print(f"API docs: {url}docs")
    print(f"Project root: {project_root.resolve()}")
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))
    try:
        server.run()
    except KeyboardInterrupt:
        print("\nShutting down MaaPlus UI Workbench...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MaaPlus UI Workbench FastAPI Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port number (default: 8080)")
    parser.add_argument("--project-root", type=Path, default=Path.cwd(), help="Project root path")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args(argv)
    run_server(
        host=args.host,
        port=args.port,
        project_root=args.project_root,
        open_browser=not args.no_browser,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
