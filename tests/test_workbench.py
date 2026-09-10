"""Tests for the MaaPlus UI Workbench dev tool and FastAPI backend bridge."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tools.ui_workbench import DeviceBridge, create_app


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    # Create a minimal project structure with UI and resource directories
    ui_dir = tmp_path / "ui"
    ui_dir.mkdir(parents=True)
    (ui_dir / "__init__.py").write_text("", encoding="utf-8")
    (ui_dir / "sample.py").write_text(
        """from maaplus import Template, OCR

class SampleUI:
    READY = Template(template=["sample/ready.png"], threshold=[0.88], roi=(10, 20, 100, 50))
    CONFIRM = OCR(expected=["确定"], roi=(200, 300, 80, 40))
""",
        encoding="utf-8",
    )
    (tmp_path / "resource").mkdir()
    return tmp_path


@pytest.fixture
def bridge(project_root: Path) -> DeviceBridge:
    return DeviceBridge(project_root)


@pytest.fixture
def client(bridge: DeviceBridge, project_root: Path) -> TestClient:
    app = create_app(bridge=bridge, project_root=project_root)
    return TestClient(app)


def test_html_file_integrity():
    html_path = Path(__file__).resolve().parent.parent / "tools" / "ui_workbench.html"
    assert html_path.exists(), "ui_workbench.html must exist"
    content = html_path.read_text(encoding="utf-8")

    # Verify essential components are present in the single HTML file
    assert "MaaPlus UI Workbench" in content
    assert "screenCanvas" in content
    assert "loupeCanvas" in content
    assert "btnTakeScreenshot" in content
    assert "btnConnectDevice" in content
    assert "btnCropSelection" in content
    assert "btnTestRecognition" in content
    assert "btnRunBacktest" in content
    assert "codePreviewBox" in content


def test_device_discovery(bridge: DeviceBridge):
    devices = bridge.discover_devices()
    assert isinstance(devices, list)
    for dev in devices:
        assert "address" in dev
        assert "name" in dev
        assert "source" in dev


def test_parse_ui_file(bridge: DeviceBridge, project_root: Path):
    sample_py = project_root / "ui" / "sample.py"
    classes = bridge._parse_ui_file(sample_py)
    assert len(classes) == 1
    cls_info = classes[0]
    assert cls_info["name"] == "SampleUI"
    assert len(cls_info["locators"]) == 2

    ready = cls_info["locators"][0]
    assert ready["name"] == "READY"
    assert ready["type"] == "Template"
    assert ready["template"] == ["sample/ready.png"]
    assert ready["threshold"] == [0.88]
    assert ready["roi"] == (10, 20, 100, 50)

    confirm = cls_info["locators"][1]
    assert confirm["name"] == "CONFIRM"
    assert confirm["type"] == "OCR"
    assert confirm["expected"] == ["确定"]


def test_scan_project_ui(bridge: DeviceBridge):
    result = bridge.scan_project_ui()
    assert "ui_files" in result
    assert len(result["ui_files"]) >= 1
    assert result["ui_files"][0]["classes"][0]["name"] == "SampleUI"


def test_save_template_image(bridge: DeviceBridge, project_root: Path):
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buf, format="PNG")
    dummy_png_bytes = buf.getvalue()
    b64_str = base64.b64encode(dummy_png_bytes).decode("ascii")

    res = bridge.save_template_image("icons/btn.png", b64_str)
    assert res["success"] is True

    saved_path = project_root / "resource" / "icons" / "btn.png"
    assert saved_path.exists()
    assert saved_path.read_bytes() == dummy_png_bytes


def test_fastapi_endpoints(client: TestClient, project_root: Path):
    # GET /
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "MaaPlus UI Workbench" in resp.text

    # GET /api/status
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "project_root" in data
    assert "maa_available" in data

    # GET /api/devices
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    assert "devices" in resp.json()

    # GET /api/project_ui
    resp = client.get("/api/project_ui")
    assert resp.status_code == 200
    data = resp.json()
    assert "ui_files" in data
    assert len(data["ui_files"]) >= 1

    # POST /api/save_template
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="green").save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    resp = client.post("/api/save_template", json={"path": "test.png", "image": img_b64})
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # POST /api/recognize
    resp = client.post(
        "/api/recognize",
        json={
            "locator": {"type": "OCR", "expected": ["确认"], "roi": [0, 0, 50, 50]},
            "image": img_b64,
        },
    )
    assert resp.status_code == 200
    rec_data = resp.json()
    assert rec_data["success"] is True
    assert "hit" in rec_data

    # POST /api/save_ui
    resp = client.post(
        "/api/save_ui",
        json={"file_path": "ui/generated.py", "code": "# Test code"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    assert (project_root / "ui" / "generated.py").exists()


def test_recognize_api(bridge: DeviceBridge):
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="blue").save(buf, format="PNG")
    valid_png_bytes = buf.getvalue()

    ocr_loc = {"type": "OCR", "expected": ["测试"], "roi": [0, 0, 10, 10]}
    res = bridge.recognize(ocr_loc, image_bytes=valid_png_bytes)
    assert "success" in res
    assert res["success"] is True
    assert "hit" in res

    tmpl_loc = {
        "type": "Template",
        "template": ["non_existent.png"],
        "threshold": 0.85,
        "roi": [0, 0, 0, 0],
    }
    res_tmpl = bridge.recognize(tmpl_loc, image_bytes=valid_png_bytes)
    assert "success" in res_tmpl
    assert res_tmpl["success"] is True
    assert res_tmpl["hit"] is False


def test_class_backtest_and_bound_screenshots(bridge: DeviceBridge, project_root: Path):
    from fastapi.testclient import TestClient
    from tools.ui_workbench import create_app

    buf = io.BytesIO()
    Image.new("RGB", (60, 60), color="white").save(buf, format="PNG")
    img_b64 = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"

    app = create_app(bridge)
    client = TestClient(app)

    # 1. Save bound screenshot for HomeUI
    resp = client.post(
        "/api/save_bound_screenshot",
        json={
            "ui_class": "HomeUI",
            "name": "home_test_1080p.png",
            "image": img_b64,
        },
    )
    assert resp.status_code == 200
    save_data = resp.json()
    assert save_data["success"] is True
    assert (project_root / "assets" / "fixtures" / "HomeUI" / "home_test_1080p.png").exists()

    # 2. Run class-level backtest
    resp = client.post(
        "/api/class_backtest",
        json={
            "ui_class": "HomeUI",
            "locators": [
                {"name": "start_btn", "type": "OCR", "expected": ["开始"], "roi": [0, 0, 30, 30]},
                {"name": "title_text", "type": "OCR", "expected": ["终端"], "roi": [0, 0, 30, 30]},
            ],
            "screenshots": [
                {"name": "home_test_1080p.png", "dataUrl": img_b64},
            ],
        },
    )
    assert resp.status_code == 200
    res = resp.json()
    assert res["success"] is True
    assert res["ui_class"] == "HomeUI"
    assert res["total_screenshots"] == 1
    assert res["total_locators"] == 2
    assert res["total_checks"] == 2
    assert len(res["matrix"]) == 1
    assert "start_btn" in res["matrix"][0]["results"]
    assert "title_text" in res["matrix"][0]["results"]

    # Cleanup test created file
    created_file = project_root / "assets" / "fixtures" / "HomeUI" / "home_test_1080p.png"
    if created_file.exists():
        created_file.unlink()
    home_dir = project_root / "assets" / "fixtures" / "HomeUI"
    if home_dir.exists():
        home_dir.rmdir()
    fix_dir = project_root / "assets" / "fixtures"
    if fix_dir.exists():
        fix_dir.rmdir()
    assets_dir = project_root / "assets"
    if assets_dir.exists():
        try:
            assets_dir.rmdir()
        except OSError:
            pass

