from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from maaplus_studio.models import Locator, Project, StudioError, UIGroup
from maaplus_studio.worker import NativeWorker
from test_project import project


def wait_forever(pipe, root):
    import time
    pipe.recv()
    time.sleep(60)


def echo(pipe, root):
    while True:
        try:
            message = pipe.recv()
            pipe.send({"ok": True, "value": message["payload"]})
        except EOFError:
            return


def test_worker_timeout_terminates_and_next_request_recovers(tmp_path):
    worker = NativeWorker(tmp_path, target=wait_forever)
    with pytest.raises(StudioError, match="超时"):
        worker.request("inspect", {}, timeout=0.5)
    assert worker.process is None
    worker.target = echo
    try:
        assert worker.request("test", {"recovered": True}) == {"recovered": True}
    finally:
        worker.close()


def test_real_native_template_hit_miss_and_resource_reload(tmp_path):
    image_dir = tmp_path / "resource/image/home"
    image_dir.mkdir(parents=True)
    pattern = np.random.default_rng(12).integers(0, 255, (22, 28, 3), dtype=np.uint8)
    frame = np.zeros((100, 150, 3), dtype=np.uint8)
    frame[35:57, 62:90] = pattern
    Image.fromarray(pattern).save(image_dir / "button.png")
    screenshot = tmp_path / "frame.png"
    Image.fromarray(frame).save(screenshot)
    config = project().model_dump(mode="json")
    config["locators"][0]["params"]["threshold"] = [0.98]
    payload = {"project": config, "locator_id": "a", "snapshot_id": "snapshot", "image_path": str(screenshot)}
    worker = NativeWorker(tmp_path)
    try:
        result = worker.request("inspect", payload)
        assert result["hit"] is True, result
        assert list(result["box"]) == [62, 35, 28, 22]
        replacement = np.random.default_rng(32).integers(0, 255, pattern.shape, dtype=np.uint8)
        Image.fromarray(replacement).save(image_dir / "button.png")
        result = worker.request("inspect", payload)
        assert result["hit"] is False, result
    finally:
        worker.close()


@pytest.mark.parametrize("kind, params, expected", [
    ("OCR", {"expected": ["确认"]}, "OCR 模型缺失"),
    ("OCR", {"expected": ["确认"], "model": "english"}, "model/ocr/english"),
    ("Custom", {"custom_recognition": "not_registered"}, "尚未注册"),
])
def test_missing_models_and_callbacks_are_errors(tmp_path, kind, params, expected):
    (tmp_path / "resource/image").mkdir(parents=True)
    screenshot = tmp_path / "frame.png"
    Image.new("RGB", (80, 80)).save(screenshot)
    config = project().model_dump(mode="json")
    config["locators"][0].update(kind=kind, params=params)
    worker = NativeWorker(tmp_path)
    try:
        with pytest.raises(StudioError, match=expected):
            worker.request("inspect", {"project": config, "locator_id": "a", "snapshot_id": "s", "image_path": str(screenshot)})
    finally:
        worker.close()


def test_real_feature_color_and_combinations(tmp_path):
    directory = tmp_path / "resource/image"
    directory.mkdir(parents=True)
    pattern = np.random.default_rng(18).integers(0, 255, (150, 150, 3), dtype=np.uint8)
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    frame[20:170, 40:190] = pattern
    frame[185:200, 220:240] = (200, 10, 30)  # RGB, deliberately asymmetric channels.
    Image.fromarray(pattern).save(directory / "feature.png")
    screenshot = tmp_path / "frame.png"
    Image.fromarray(frame).save(screenshot)
    config = Project(groups=[UIGroup(id="g", module="home", class_name="UI")], locators=[
        Locator(id="f", group_id="g", name="FEATURE", kind="FeatureMatch", params={"template": ["feature.png"], "count": 4}),
        Locator(id="c", group_id="g", name="COLOR", kind="ColorMatch", params={"method": 4, "lower": [[200, 10, 30]], "upper": [[200, 10, 30]], "count": 100}),
        Locator(id="miss", group_id="g", name="MISS", kind="ColorMatch", params={"method": 4, "lower": [[30, 10, 200]], "upper": [[30, 10, 200]], "count": 100}),
        Locator(id="all", group_id="g", name="ALL", kind="And", children=["f", "c"], params={"box_index": 1}),
        Locator(id="any", group_id="g", name="ANY", kind="Or", children=["miss", "c"]),
        Locator(id="nested", group_id="g", name="NESTED", kind="Or", children=["miss", "all"]),
        Locator(id="all_miss", group_id="g", name="ALL_MISS", kind="And", children=["c", "miss"]),
    ])
    worker = NativeWorker(tmp_path)
    try:
        for key, hit in [("f", True), ("c", True), ("miss", False), ("all", True), ("any", True), ("nested", True), ("all_miss", False)]:
            result = worker.request("inspect", {"project": config.model_dump(mode="json"), "locator_id": key, "snapshot_id": "s", "image_path": str(screenshot)})
            assert result["hit"] is hit, (key, result)
            if key in {"c", "all", "any", "nested"}:
                assert list(result["box"]) == [220, 185, 20, 15]
    finally:
        worker.close()


def test_explicit_hook_registers_real_custom_recognition(tmp_path):
    (tmp_path / "resource/image").mkdir(parents=True)
    example = Path(__file__).parents[2] / "examples/complete_project/demo/custom_recognition.py"
    (tmp_path / "recognition.py").write_bytes(example.read_bytes())
    (tmp_path / "studio_hook.py").write_text(
        "from recognition import create_custom_recognitions\n"
        "def register(resource):\n"
        "    for name, callback in create_custom_recognitions().items():\n"
        "        assert resource.register_custom_recognition(name, callback)\n", encoding="utf-8")
    frame = Image.new("RGB", (80, 80))
    for point in [(20, 25), (32, 25), (20, 37)]:
        frame.putpixel(point, (255, 214, 80))
    screenshot = tmp_path / "frame.png"
    frame.save(screenshot)
    config = Project(resource_hook="studio_hook:register", groups=[UIGroup(id="g", module="home", class_name="UI")],
                     locators=[Locator(id="custom", group_id="g", name="MARKER", kind="Custom", params={"custom_recognition": "MultiPointColor", "custom_recognition_param": {"tolerance": 0}})])
    worker = NativeWorker(tmp_path)
    try:
        result = worker.request("inspect", {"project": config.model_dump(mode="json"), "locator_id": "custom", "snapshot_id": "s", "image_path": str(screenshot)})
        assert result["hit"] is True, result
        assert list(result["box"]) == [20, 25, 13, 13]
    finally:
        worker.close()
