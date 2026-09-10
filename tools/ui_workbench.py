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
import re
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
from pydantic import BaseModel, Field
import uvicorn

# Optional MaaFramework imports
try:
    from maa.controller import AdbController, CustomController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit
    from maaplus import OCR, Template
    from maaplus.dev import (
        FixtureSet,
        Inspector,
        create_adb_controller,
        find_adb_devices,
    )
    from maaplus.locator import recognition_type
    import numpy as np
    from PIL import Image

    class StandaloneDummyController(CustomController):
        def request_uuid(self) -> str:
            return "standalone_dummy_controller"

    MAA_AVAILABLE = True
except ImportError:
    MAA_AVAILABLE = False
    Toolkit = None
    AdbController = None
    CustomController = None
    StandaloneDummyController = None
    Resource = None
    Tasker = None
    Inspector = None
    np = None
    Image = None

logger = logging.getLogger("maaplus.workbench")

class DeviceBridge:
    """Manages device connection, screencap, and input actions using MaaPlus capabilities."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.controller: Any = None
        self.tasker: Any = None
        self.resource: Any = None
        self.connected_device: dict[str, Any] | None = None
        self.last_screencap_bytes: bytes | None = None
        self.last_screencap_np: Any = None
        self.lock = threading.Lock()

    def discover_devices(self) -> list[dict[str, Any]]:
        """Discover connected devices directly using MaaPlus's device discovery."""
        if not MAA_AVAILABLE:
            return []

        try:
            from maaplus.dev import find_adb_devices

            devs = find_adb_devices()
            return [
                {
                    "address": d.address,
                    "name": d.name,
                    "adb_path": str(d.adb_path),
                    "screencap_methods": d.screencap_methods,
                    "input_methods": d.input_methods,
                    "config": d.config,
                    "source": "maaplus",
                    "connected": bool(
                        self.connected_device
                        and self.connected_device.get("address") == d.address
                    ),
                }
                for d in devs
            ]
        except Exception as e:
            logger.warning("maaplus.dev.find_adb_devices error: %s", e)
            return []

    def connect(self, address: str, adb_path: str = "adb") -> dict[str, Any]:
        """Connect to device directly using MaaPlus's create_adb_controller."""
        with self.lock:
            self._disconnect_locked()

            if not MAA_AVAILABLE:
                self.connected_device = {
                    "address": address,
                    "adb_path": adb_path,
                    "mode": "standalone_mock",
                }
                return {"success": True, "address": address, "mode": "standalone_mock"}

            try:
                from maaplus.dev import create_adb_controller

                controller = create_adb_controller(serial=address, adb_path=adb_path)
                self.controller = controller
                self.tasker = None
                self._ensure_tasker()

                self.connected_device = {
                    "address": address,
                    "adb_path": adb_path,
                    "mode": "maaplus_adb",
                }
                logger.info("Connected to device via maaplus.dev: %s", address)
                return {"success": True, "address": address, "mode": "maaplus_adb"}
            except Exception as exc:
                logger.exception("Failed to connect device %s via maaplus: %s", address, exc)
                return {"success": False, "error": str(exc)}

    def _ensure_tasker(self) -> Any:
        if self.tasker is not None:
            return self.tasker

        if not MAA_AVAILABLE or Tasker is None or Resource is None:
            return None

        try:
            if self.resource is None:
                self.resource = Resource()
                res_dirs = [
                    self.project_root / "resource",
                    self.project_root / "examples" / "complete_project" / "resource",
                ]
                for rdir in res_dirs:
                    if rdir.exists() and rdir.is_dir():
                        try:
                            job = self.resource.post_bundle(str(rdir)).wait()
                            if not job.succeeded:
                                self.resource.post_image(str(rdir)).wait()
                        except Exception as err:
                            logger.debug("Resource loading error for %s: %s", rdir, err)

            ctrl = self.controller
            if ctrl is None and StandaloneDummyController is not None:
                ctrl = StandaloneDummyController()

            if ctrl is not None:
                tasker = Tasker()
                if tasker.bind(self.resource, ctrl):
                    self.tasker = tasker
                    return self.tasker
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

    def screencap(self) -> bytes:
        with self.lock:
            if self.controller is not None:
                job = self.controller.post_screencap().wait()
                if not job.succeeded:
                    raise RuntimeError("Screencap failed on controller")
                img_np = job.get()
                self.last_screencap_np = img_np
                if Image is not None and np is not None:
                    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
                        rgb = img_np[:, :, ::-1]
                        pil_img = Image.fromarray(rgb)
                    else:
                        pil_img = Image.fromarray(img_np)
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=85)
                    self.last_screencap_bytes = buf.getvalue()
                    return self.last_screencap_bytes
                raise RuntimeError("PIL not available to encode screencap")

            if self.connected_device and self.connected_device.get("address"):
                addr = self.connected_device["address"]
                adb = self.connected_device.get("adb_path", "adb")
                res = subprocess.run(
                    [adb, "-s", addr, "exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                if res.returncode == 0 and res.stdout.startswith(b"\x89PNG"):
                    self.last_screencap_bytes = res.stdout
                    return self.last_screencap_bytes

            raise RuntimeError("No device connected or unable to screencap")

    def click(self, x: int, y: int) -> bool:
        with self.lock:
            if self.controller is not None:
                job = self.controller.post_click(int(x), int(y)).wait()
                return bool(job.succeeded)
            if self.connected_device and self.connected_device.get("address"):
                addr = self.connected_device["address"]
                adb = self.connected_device.get("adb_path", "adb")
                res = subprocess.run(
                    [adb, "-s", addr, "shell", "input", "tap", str(int(x)), str(int(y))],
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
                return res.returncode == 0
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 500) -> bool:
        with self.lock:
            if self.controller is not None:
                job = self.controller.post_swipe(
                    int(x1), int(y1), int(x2), int(y2), int(duration_ms)
                ).wait()
                return bool(job.succeeded)
            if self.connected_device and self.connected_device.get("address"):
                addr = self.connected_device["address"]
                adb = self.connected_device.get("adb_path", "adb")
                res = subprocess.run(
                    [
                        adb,
                        "-s",
                        addr,
                        "shell",
                        "input",
                        "swipe",
                        str(int(x1)),
                        str(int(y1)),
                        str(int(x2)),
                        str(int(y2)),
                        str(int(duration_ms)),
                    ],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                return res.returncode == 0
            return False

    def press_key(self, keycode: int) -> bool:
        with self.lock:
            if self.controller is not None and hasattr(self.controller, "post_press_key"):
                job = self.controller.post_press_key(int(keycode)).wait()
                return bool(job.succeeded)
            if self.connected_device and self.connected_device.get("address"):
                addr = self.connected_device["address"]
                adb = self.connected_device.get("adb_path", "adb")
                res = subprocess.run(
                    [adb, "-s", addr, "shell", "input", "keyevent", str(int(keycode))],
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
                return res.returncode == 0
            return False

    def recognize(self, locator_data: dict[str, Any], image_bytes: bytes | None = None) -> dict[str, Any]:
        """Test recognition using MaaFramework."""
        if not MAA_AVAILABLE or np is None or Image is None:
            return {
                "success": False,
                "error": "MaaFramework or Pillow not installed. Running in offline preview mode.",
            }

        target_np = None
        if image_bytes:
            pil_img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            rgb_np = np.array(pil_img)
            target_np = rgb_np[:, :, ::-1]
        elif self.last_screencap_np is not None:
            target_np = self.last_screencap_np
        else:
            try:
                self.screencap()
                target_np = self.last_screencap_np
            except Exception as e:
                return {"success": False, "error": f"No image available: {e}"}

        if target_np is None:
            return {"success": False, "error": "Failed to acquire target image"}

        loc_type = locator_data.get("type", "Template")
        roi = locator_data.get("roi")
        if roi and len(roi) == 4 and all(v is not None for v in roi):
            roi = tuple(map(int, roi))
        else:
            roi = (0, 0, 0, 0)

        started = time.perf_counter()

        try:
            if loc_type == "Template":
                template_paths = locator_data.get("template", [])
                if isinstance(template_paths, str):
                    template_paths = [template_paths]
                threshold = locator_data.get("threshold", 0.85)
                threshold_list = (
                    [float(threshold)] if not isinstance(threshold, list) else threshold
                )
                locator = Template(
                    template=template_paths,
                    threshold=threshold_list,
                    roi=roi,
                )
            elif loc_type == "OCR":
                expected = locator_data.get("expected", [])
                if isinstance(expected, str):
                    expected = [expected]
                locator = OCR(
                    expected=expected,
                    roi=roi,
                )
            else:
                return {"success": False, "error": f"Unsupported locator type: {loc_type}"}

            tasker = self._ensure_tasker()
            if not tasker:
                return {
                    "success": False,
                    "error": "MaaFramework Tasker 未能初始化（请确保已安装 maafw）",
                }

            if loc_type == "Template" and self.resource is not None:
                template_paths = locator_data.get("template", [])
                if isinstance(template_paths, str):
                    template_paths = [template_paths]
                for t_name in template_paths:
                    for base in [
                        self.project_root / "resource",
                        self.project_root / "examples" / "complete_project" / "resource",
                        self.project_root,
                    ]:
                        target_file = base / t_name
                        if target_file.exists():
                            try:
                                self.resource.post_image(str(target_file.parent)).wait()
                            except Exception:
                                pass
                            break

            r_type = recognition_type(locator)
            job = tasker.post_recognition(r_type, locator, target_np).wait()
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
            reco = getattr(node, "recognition", None) if node else None

            hit = bool(getattr(reco, "hit", False)) if reco else False
            box = getattr(reco, "box", None) if reco else None
            score = getattr(reco, "score", None) if reco else None
            if box is not None:
                box = list(box)

            return {
                "success": True,
                "hit": hit,
                "box": box,
                "score": score,
                "elapsed_ms": round(elapsed_ms, 2),
                "raw_detail": getattr(reco, "raw_detail", None),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def save_template_image(self, rel_path: str, image_b64: str) -> dict[str, Any]:
        """Save cropped image data to project resource folder."""
        try:
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(image_b64)

            res_dir = self.project_root / "resource"
            if not res_dir.exists():
                comp_res = self.project_root / "examples" / "complete_project" / "resource"
                if comp_res.exists():
                    res_dir = comp_res
                else:
                    res_dir.mkdir(parents=True, exist_ok=True)

            target_file = res_dir / rel_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(raw_bytes)

            return {
                "success": True,
                "saved_path": str(target_file.resolve()),
                "relative_path": str(rel_path),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def scan_project_ui(self) -> dict[str, Any]:
        """Scan Python files in project for UI classes and locators."""
        ui_files: list[dict[str, Any]] = []
        search_dirs = [
            self.project_root / "ui",
            self.project_root / "demo" / "ui",
            self.project_root / "examples" / "complete_project" / "demo" / "ui",
        ]

        for sdir in search_dirs:
            if not sdir.exists():
                continue
            for pyfile in sdir.glob("*.py"):
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
                except Exception as e:
                    logger.debug("Failed parsing %s: %s", pyfile, e)

        return {"ui_files": ui_files}

    def _parse_ui_file(self, file_path: Path) -> list[dict[str, Any]]:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
        results = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls_data = {
                    "name": node.name,
                    "locators": [],
                }
                for item in node.body:
                    if isinstance(item, ast.Assign) and len(item.targets) == 1:
                        target = item.targets[0]
                        if isinstance(target, ast.Name):
                            loc_name = target.id
                            loc_info = self._parse_locator_call(item.value)
                            if loc_info:
                                loc_info["name"] = loc_name
                                cls_data["locators"].append(loc_info)
                if cls_data["locators"]:
                    cls_data["screenshots"] = self._find_class_screenshots(node.name)
                    results.append(cls_data)

        return results

    def _find_class_screenshots(self, class_name: str) -> list[dict[str, Any]]:
        """Discover screenshots bound to a specific UI class on disk."""
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        search_dirs = [
            self.project_root / "assets" / "fixtures" / class_name,
            self.project_root / "tests" / "fixtures" / class_name,
            self.project_root / "fixtures" / class_name,
        ]
        found = []
        for d in search_dirs:
            if d.exists() and d.is_dir():
                for f in sorted(d.iterdir()):
                    if f.is_file() and f.suffix.lower() in image_extensions:
                        try:
                            raw = f.read_bytes()
                            b64 = f"data:image/png;base64,{base64.b64encode(raw).decode('ascii')}"
                            rel = str(f.relative_to(self.project_root)).replace("\\", "/")
                            found.append({
                                "id": f.stem,
                                "name": f.name,
                                "path": rel,
                                "dataUrl": b64,
                            })
                        except Exception:
                            pass
                if found:
                    break
        return found

    def _parse_locator_call(self, node: ast.AST) -> dict[str, Any] | None:
        if not isinstance(node, ast.Call):
            return None
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name not in {"Template", "OCR", "FirstOf", "AllOf", "JCustomRecognition"}:
            return None

        data: dict[str, Any] = {"type": func_name}
        for kw in node.keywords:
            try:
                val = ast.literal_eval(kw.value)
                data[kw.arg] = val
            except Exception:
                pass
        return data

    def run_backtest(self, locator_data: dict[str, Any], fixture_dir: str | None = None) -> dict[str, Any]:
        """Backtest a locator against fixture screenshots."""
        dir_path = Path(fixture_dir) if fixture_dir else (self.project_root / "fixtures")
        if not dir_path.exists():
            ex_fix = self.project_root / "examples" / "fixture_project" / "fixtures"
            if ex_fix.exists():
                dir_path = ex_fix
            else:
                return {"success": False, "error": f"Fixture directory not found: {dir_path}"}

        results = []
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        expected_map = {}
        expected_json = dir_path / "expected.json"
        if expected_json.exists():
            try:
                expected_map = json.loads(expected_json.read_text(encoding="utf-8"))
            except Exception:
                pass

        for img_path in sorted(dir_path.iterdir()):
            if img_path.is_file() and img_path.suffix.lower() in image_extensions:
                raw_bytes = img_path.read_bytes()
                exp = expected_map.get(img_path.name, {})
                rec = self.recognize(locator_data, image_bytes=raw_bytes)
                hit = rec.get("hit", False)
                box = rec.get("box")
                score = rec.get("score")

                passed = True
                fail_reasons = []
                if "hit" in exp and bool(hit) != bool(exp["hit"]):
                    passed = False
                    fail_reasons.append(f"Expected hit={exp['hit']}, got {hit}")

                if passed and "box" in exp and exp["box"]:
                    target_box = exp["box"]
                    tol = int(exp.get("box_tolerance", 5))
                    if not box:
                        passed = False
                        fail_reasons.append("Expected bounding box, got None")
                    elif any(abs(a - b) > tol for a, b in zip(box, target_box)):
                        passed = False
                        fail_reasons.append(f"Box mismatch: expected {target_box} ±{tol}, got {box}")

                b64_thumb = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode('ascii')}"

                results.append(
                    {
                        "filename": img_path.name,
                        "thumbnail": b64_thumb,
                        "hit": hit,
                        "box": box,
                        "score": score,
                        "elapsed_ms": rec.get("elapsed_ms", 0),
                        "passed": passed,
                        "fail_reasons": fail_reasons,
                        "expected": exp,
                    }
                )

        pass_count = sum(1 for r in results if r["passed"])
        return {
            "success": True,
            "total": len(results),
            "passed": pass_count,
            "failed": len(results) - pass_count,
            "pass_rate": round(pass_count / len(results) * 100, 1) if results else 0,
            "results": results,
        }

    def save_bound_screenshot(self, ui_class: str, name: str, image_b64: str) -> dict[str, Any]:
        """Save a screenshot bound to a UI class under assets/fixtures/{ui_class}/{name}."""
        try:
            target_dir = self.project_root / "assets" / "fixtures" / ui_class
            target_dir.mkdir(parents=True, exist_ok=True)
            clean_name = name.strip() or "screenshot.png"
            if not clean_name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
                clean_name += ".png"
            target_file = target_dir / clean_name

            raw_b64 = image_b64
            if raw_b64.startswith("data:image"):
                raw_b64 = raw_b64.split(",", 1)[1]
            raw_bytes = base64.b64decode(raw_b64)
            target_file.write_bytes(raw_bytes)
            rel_path = str(target_file.relative_to(self.project_root)).replace("\\", "/")
            return {
                "success": True,
                "id": target_file.stem,
                "name": clean_name,
                "path": rel_path,
                "dataUrl": f"data:image/png;base64,{raw_b64}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_class_backtest(
        self,
        ui_class: str,
        locators: list[dict[str, Any]],
        screenshots: list[dict[str, Any]] | None = None,
        fixture_dir: str | None = None,
    ) -> dict[str, Any]:
        """Backtest all locators of a specific UI class against its bound screenshots."""
        target_images: list[tuple[str, bytes]] = []
        if screenshots:
            for s in screenshots:
                s_name = s.get("name", "screenshot.png")
                raw = b""
                data_val = s.get("dataUrl") or s.get("data")
                if data_val:
                    if data_val.startswith("data:image"):
                        data_val = data_val.split(",", 1)[1]
                    try:
                        raw = base64.b64decode(data_val)
                    except Exception:
                        pass
                elif s.get("path"):
                    p = self.project_root / s["path"]
                    if p.exists() and p.is_file():
                        raw = p.read_bytes()
                if raw:
                    target_images.append((s_name, raw))

        if not target_images:
            # Fallback to search disk fixtures
            search_dirs = []
            if fixture_dir:
                search_dirs.append(Path(fixture_dir))
            search_dirs.extend([
                self.project_root / "assets" / "fixtures" / ui_class,
                self.project_root / "tests" / "fixtures" / ui_class,
                self.project_root / "fixtures" / ui_class,
            ])
            image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
            for d in search_dirs:
                if d.exists() and d.is_dir():
                    for f in sorted(d.iterdir()):
                        if f.is_file() and f.suffix.lower() in image_extensions:
                            target_images.append((f.name, f.read_bytes()))
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

        matrix = []
        total_checks = 0
        passed_checks = 0

        for img_name, img_bytes in target_images:
            row_results: dict[str, Any] = {}
            row_all_passed = True

            for loc in locators:
                total_checks += 1
                rec = self.recognize(loc, image_bytes=img_bytes)
                hit = rec.get("hit", False)
                if hit:
                    passed_checks += 1
                else:
                    row_all_passed = False
                loc_name = loc.get("name", "unknown")
                row_results[loc_name] = {
                    "hit": hit,
                    "score": rec.get("score"),
                    "box": rec.get("box"),
                    "elapsed_ms": rec.get("elapsed_ms", 0),
                    "error": rec.get("error"),
                }

            b64_thumb = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('ascii')}"
            matrix.append({
                "screenshot_name": img_name,
                "thumbnail": b64_thumb,
                "passed": row_all_passed,
                "results": row_results,
            })

        pass_rate = round(passed_checks / total_checks * 100, 1) if total_checks else 0.0
        return {
            "success": True,
            "ui_class": ui_class,
            "total_screenshots": len(target_images),
            "total_locators": len(locators),
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "pass_rate": pass_rate,
            "matrix": matrix,
        }


# --- Request Models ---

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


# --- FastAPI Application Factory ---

def create_app(bridge: DeviceBridge | None = None, project_root: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application for UI Workbench."""
    if project_root is None:
        project_root = Path.cwd()
    if bridge is None:
        bridge = DeviceBridge(project_root)

    app = FastAPI(
        title="MaaPlus UI Workbench",
        description="Developer workbench for MaaPlus UI layer creation, inspection, device control, and fixture backtesting.",
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
            "project_root": str(bridge.project_root.resolve()),
            "connected_device": bridge.connected_device,
        }

    @app.get("/api/devices")
    async def get_devices():
        devices = bridge.discover_devices()
        return {"devices": devices}

    @app.get("/api/screencap")
    async def get_screencap():
        try:
            img_bytes = bridge.screencap()
            return Response(
                content=img_bytes,
                media_type="image/jpeg",
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
        ok = bridge.click(req.x, req.y)
        return {"success": ok}

    @app.post("/api/input/swipe")
    async def input_swipe(req: SwipeRequest):
        ok = bridge.swipe(req.x1, req.y1, req.x2, req.y2, req.duration)
        return {"success": ok}

    @app.post("/api/input/key")
    async def input_key(req: KeyRequest):
        ok = bridge.press_key(req.keycode)
        return {"success": ok}

    @app.post("/api/recognize")
    async def recognize(req: RecognizeRequest):
        img_bytes = None
        if req.image:
            img_b64 = req.image
            if "," in img_b64:
                img_b64 = img_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(img_b64)
        return bridge.recognize(req.locator, image_bytes=img_bytes)

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
        except Exception as e:
            return {"success": False, "error": str(e)}

    app.state.bridge = bridge
    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    project_root: Path | None = None,
    open_browser: bool = True,
) -> None:
    """Launch the UI Workbench backend server using uvicorn and open the web browser."""
    if project_root is None:
        project_root = Path.cwd()

    app = create_app(project_root=project_root)
    url = f"http://{host}:{port}/"
    print(f"MaaPlus UI Workbench (FastAPI) running at: {url}")
    print(f"API Docs available at: {url}docs")
    print(f"Serving project root: {project_root.resolve()}")
    print("Press Ctrl+C to stop.")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
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
