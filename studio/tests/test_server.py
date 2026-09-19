from __future__ import annotations

from unittest.mock import Mock

import io
import pytest
import sys

from fastapi.testclient import TestClient
from PIL import Image

from maaplus_studio.server import create_app
from maaplus_studio.storage import ProjectStore
from test_project import project


def client(tmp_path):
    worker = Mock(state={"connected": False})
    app = create_app(tmp_path, token="test-token", worker=worker)
    return TestClient(app, base_url="http://127.0.0.1:54321", headers={"Authorization": "Bearer test-token"}), worker


def test_session_and_same_origin_required(tmp_path):
    test, worker = client(tmp_path)
    assert test.get("/api/project").status_code == 200
    assert test.get("/api/project", headers={"Authorization": ""}).status_code == 401
    assert test.post("/api/capture", json={}, headers={"Origin": "http://malicious.example"}).status_code == 403
    assert test.get("/api/project", headers={"Host": "malicious.example"}).status_code == 403
    worker.request.assert_not_called()


def test_no_device_input_routes(tmp_path):
    test, worker = client(tmp_path)
    for path in ["click", "swipe", "input", "action", "shell", "task"]:
        assert test.post("/api/" + path, json={}).status_code == 404
    worker.request.assert_not_called()


def test_asset_rename_is_previewed_and_updates_generated_references(tmp_path):
    test, _ = client(tmp_path)
    config = project().model_dump(mode="json")
    source = tmp_path / "resource/image/home/button.png"
    source.parent.mkdir(parents=True); source.write_bytes(b"asset")
    preview = test.post("/api/assets/rename", json={"project": config, "revision": "missing", "source": "home/button.png", "target": "home/new.png"})
    assert preview.status_code == 200, preview.text
    assert source.exists()
    assert test.post("/api/commit", json={"preview_id": preview.json()["preview_id"]}).status_code == 200
    assert not source.exists()
    assert (tmp_path / "resource/image/home/new.png").read_bytes() == b"asset"
    assert "home/new.png" in (tmp_path / "ui/home.py").read_text(encoding="utf-8")


def test_referenced_asset_cannot_be_deleted(tmp_path):
    test, _ = client(tmp_path)
    response = test.post("/api/assets/delete", json={"project": project().model_dump(mode="json"), "path": "home/button.png"})
    assert response.status_code == 400
    assert "BUTTON" in response.json()["detail"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path spelling aliases")
def test_resource_dependencies_resolve_windows_case_and_separators(tmp_path):
    test, _ = client(tmp_path)
    config = project().model_dump(mode="json")
    config["locators"][0]["params"]["template"] = ["HOME\\BUTTON.PNG"]
    response = test.post("/api/assets/delete", json={"project": config, "path": "home/button.png"})
    assert response.status_code == 400 and "HomeUI.BUTTON" in response.json()["detail"]


def test_connection_failure_and_inspection_error_are_visible(tmp_path):
    from maaplus_studio.models import StudioError
    test, worker = client(tmp_path)
    worker.request.side_effect = StudioError("窗口已失效")
    response = test.post("/api/connect", json={"kind": "win32", "id": "123"})
    assert response.status_code == 400 and "窗口已失效" in response.json()["detail"]


def test_bundled_web_is_served(tmp_path):
    test, _ = client(tmp_path)
    response = test.get("/")
    assert response.status_code == 200
    assert "MaaPlus Studio" in response.text


def test_incomplete_requests_are_validation_errors(tmp_path):
    test, worker = client(tmp_path)
    for path in ["preview", "commit", "import", "import/accept", "crop", "inspect", "devices", "connect"]:
        assert test.post("/api/" + path, json={}).status_code == 422
    worker.request.assert_not_called()


def test_template_browser_serves_authenticated_thumbnails_without_modifying_images(tmp_path):
    test, worker = client(tmp_path)
    image = tmp_path / "assets/image/按钮/确定.png"
    image.parent.mkdir(parents=True)
    Image.new("RGBA", (400, 200), (200, 10, 30, 128)).save(image)
    original = image.read_bytes()
    (image.parent / "not-an-image.txt").write_text("not an image", encoding="utf-8")
    listing = test.post("/api/assets/browse", json={"resource_dir": "assets"})
    assert listing.status_code == 200
    assert [item["path"] for item in listing.json()["items"]] == ["按钮/确定.png"]
    payload = {"resource_dir": "assets", "path": "按钮/确定.png"}
    assert test.post("/api/assets/thumbnail", json=payload, headers={"Authorization": ""}).status_code == 401
    assert test.post("/api/assets/thumbnail", json=payload, headers={"Origin": "http://other.example"}).status_code == 403
    response = test.post("/api/assets/thumbnail", json=payload)
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    with Image.open(io.BytesIO(response.content)) as thumbnail:
        assert thumbnail.size == (240, 120)
        r, g, b, alpha = thumbnail.getpixel((120, 60))
        assert abs(r - 200) <= 1 and abs(g - 10) <= 1 and abs(b - 30) <= 1 and alpha == 128
    assert image.read_bytes() == original
    worker.request.assert_not_called()


@pytest.mark.parametrize("directory, path", [
    ("../outside", "private.png"), ("resource", "../../private.png"),
    ("resource", "secrets.txt"), ("resource", "missing.png"),
])
def test_template_preview_rejects_invalid_paths(tmp_path, directory, path):
    test, _ = client(tmp_path)
    response = test.post("/api/assets/thumbnail", json={"resource_dir": directory, "path": path})
    assert response.status_code == 400
