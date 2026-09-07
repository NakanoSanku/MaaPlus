from __future__ import annotations

import copy
import importlib.util
import json
import os
import time
from pathlib import Path

import pytest
from PIL import Image

from maaplus_studio.__main__ import main
from maaplus_studio.demo import create_demo
from maaplus_studio.engine import WorkerClient, load_locators
from maaplus_studio.project import Project, digest, identifier, rect, relative
from maaplus_studio.testing import evaluate, iou, run_suite


@pytest.fixture
def project(tmp_path):
    p = Project.create(tmp_path)
    page = p.add_page("ChallengeUI", "ui/generated/challenge.py")
    sid = p.add_screenshot(Image.new("RGB", (1280, 720), "navy"))
    p.put_element(page, name="CHALLENGE", shot_id=sid, crop=[10, 20, 40, 30], roi=[0, 0, 200, 100])
    return p


def first(p):
    page = p.data["pages"][0]
    return page, page["elements"][0], p.data["screenshots"][0]


@pytest.mark.parametrize("value", ["../a.py", "/tmp/a.py", "C:/a.py", "a\\b.py", "a/../b.py", "a//b.py", "./x", ""])
def test_unsafe_relative_paths(value):
    with pytest.raises(ValueError):
        relative(value)


@pytest.mark.parametrize("value", ["class", "with space", "a.b", "1x", "Template", "__dict__", ""])
def test_identifiers(value):
    with pytest.raises(ValueError):
        identifier(value)


@pytest.mark.parametrize("value", [[-1, 0, 2, 2], [0, 0, 0, 2], [0, 0, 100, 200], [0.5, 0, 1, 1], [True, 0, 1, 1], [0, 0, 2]])
def test_rect_validation(value):
    with pytest.raises(ValueError):
        rect(value, [100, 100])


def test_roundtrip_and_stable_provenance(project):
    page, element, shot = first(project)
    project.generate()
    reloaded = Project.open(project.root)
    assert reloaded.data == project.data
    assert reloaded.image(shot["id"]).size == (1280, 720)
    assert element["source"] == shot["id"]
    assert digest(reloaded.path(shot["path"]).read_bytes()) == shot["sha256"]
    code = reloaded.output_path(page["file"]).read_text()
    assert element["id"] in code and shot["id"] in code
    assert "roi=(0, 0, 200, 100)" in code


def test_duplicate_capture_preserves_observations(project):
    _, _, shot = first(project)
    sid = project.add_screenshot(project.image(shot["id"]), {"kind": "adb", "name": "second origin"})
    assert sid == shot["id"]
    assert len(project.data["screenshots"]) == 1
    assert shot["observations"][0]["source"]["name"] == "second origin"


def test_dimensions_not_silently_stretched(project):
    with pytest.raises(ValueError, match="Expected"):
        project.add_screenshot(Image.new("RGB", (1920, 1080)))
    assert len(project.data["screenshots"]) == 1


def test_duplicate_name_rolls_back(project):
    page, _, shot = first(project)
    before = copy.deepcopy(project.data)
    with pytest.raises(ValueError, match="Duplicate"):
        project.put_element(page["id"], name="CHALLENGE", shot_id=shot["id"], crop=[1, 1, 2, 2])
    assert project.data == before
    assert Project.open(project.root).data == before


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_thresholds(project, threshold):
    page, _, shot = first(project)
    with pytest.raises(ValueError):
        project.put_element(page["id"], name="BAD", shot_id=shot["id"], crop=[1, 1, 2, 2], threshold=threshold)


def test_crop_larger_than_search_roi(project):
    page, _, shot = first(project)
    with pytest.raises(ValueError, match="larger"):
        project.put_element(page["id"], name="BAD", shot_id=shot["id"], crop=[1, 1, 20, 20], roi=[1, 1, 2, 2])


def test_safe_ast_loader_and_composites(project):
    page, element, shot = first(project)
    text = '\"); __import__("os").system("touch SHOULD_NOT_EXIST"); #'
    ocr_id = project.put_element(page["id"], name="TEXT", kind="OCR", shot_id=shot["id"], crop=[1, 1, 2, 2], expected=[text])
    composite_id = project.put_element(page["id"], name="READY", kind="AllOf", refs=[element["id"], ocr_id], box_index=1)
    fallback_id = project.put_element(page["id"], name="MARKER", kind="FirstOf", refs=[element["id"], ocr_id])
    project.generate()
    constructors = {name: (lambda *args, _name=name, **kwargs: (_name, args, kwargs)) for name in ("Template", "OCR", "FirstOf", "AllOf")}
    values = load_locators(project, page["id"], constructors)
    assert values[ocr_id][2]["expected"] == [text]
    assert values[composite_id][2]["box_index"] == 1
    assert values[fallback_id][1][0] is values[element["id"]]
    assert not Path("SHOULD_NOT_EXIST").exists()


def test_cycles_and_referenced_deletion_blocked(project):
    page, e, _ = first(project)
    cid = project.put_element(page["id"], name="READY", kind="FirstOf", refs=[e["id"]])
    with pytest.raises(ValueError, match="referenced"):
        project.remove_element(page["id"], e["id"])
    with pytest.raises(ValueError, match="earlier"):
        project.put_element(page["id"], name="CHALLENGE", element_id=e["id"], kind="FirstOf", refs=[cid])
    assert project.element(page["id"], e["id"])["kind"] == "Template"


def test_rename_preserves_ids_and_composition(project):
    page, e, shot = first(project)
    cid = project.put_element(page["id"], name="READY", kind="FirstOf", refs=[e["id"]])
    project.put_element(page["id"], name="START", element_id=e["id"], shot_id=shot["id"], crop=e["crop"], roi=e["roi"])
    assert project.element(page["id"], cid)["refs"] == [e["id"]]
    assert "READY = FirstOf(START)" in project.render()[page["file"]]


def test_multiple_pages_one_file(project):
    page, _, _ = first(project)
    project.add_page("HomeUI", page["file"])
    project.generate()
    code = project.output_path(page["file"]).read_text()
    assert "class HomeUI:" in code and "class ChallengeUI:" in code
    with pytest.raises(ValueError, match="Duplicate"):
        project.add_page("HomeUI", page["file"])


def test_unmanaged_file_never_overwritten(project):
    page, _, _ = first(project)
    path = project.output_path(page["file"])
    path.parent.mkdir(parents=True)
    path.write_text("# handwritten\n")
    with pytest.raises(RuntimeError, match="Refusing"):
        project.generate()
    assert path.read_text() == "# handwritten\n"


def test_external_modification_never_overwritten(project):
    page, _, _ = first(project)
    project.generate()
    path = project.output_path(page["file"])
    path.write_text(path.read_text() + "# custom\n")
    with pytest.raises(RuntimeError, match="Refusing"):
        project.generate()
    with pytest.raises(ValueError, match="stale"):
        load_locators(project, page["id"], {})


def test_preflight_all_files_before_writing(project):
    page, _, _ = first(project)
    project.add_page("HomeUI", "ui/generated/home.py")
    conflict = project.path("ui/generated/home.py")
    conflict.parent.mkdir(parents=True)
    conflict.write_text("# manual")
    with pytest.raises(RuntimeError):
        project.generate()
    assert not project.output_path(page["file"]).exists()


def test_generated_files_rollback_on_manifest_failure(project, monkeypatch):
    import maaplus_studio.project as module
    page, _, _ = first(project)
    project.generate()
    previous = project.output_path(page["file"]).read_bytes()
    project.update_page(page["id"], name="RenamedUI", file=page["file"])
    original = module.atomic_write
    def fail_manifest(path, data):
        if path.name == "maaplus-studio.json":
            raise OSError("simulated disk error")
        original(path, data)
    monkeypatch.setattr(module, "atomic_write", fail_manifest)
    with pytest.raises(OSError):
        project.generate()
    assert project.output_path(page["file"]).read_bytes() == previous
    assert not (project.root / ".maaplus-studio.lock").exists()


def test_optimistic_concurrency(project):
    other = Project.open(project.root)
    project.add_page("HomeUI", "ui/generated/home.py")
    with pytest.raises(RuntimeError, match="changed on disk"):
        other.add_page("StaleUI", "ui/generated/stale.py")
    assert len(other.data["pages"]) == 1
    assert len(Project.open(project.root).data["pages"]) == 2


def test_output_and_symlink_boundary(project, tmp_path):
    with pytest.raises(ValueError):
        project.add_page("UnsafeUI", "maaplus_studio/engine.py")
    external = tmp_path.parent / (tmp_path.name + "-outside")
    external.mkdir()
    (project.root / "escape").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        project.path("escape/file.py")


def test_overlap_directories_rejected(tmp_path):
    with pytest.raises(ValueError, match="overlap"):
        Project.create(tmp_path, ui="resource/ui")


def test_tampered_screenshot_and_template_reported(project):
    _, e, shot = first(project)
    project.generate()
    project.path(shot["path"]).write_bytes(b"bad")
    template = project.path(project.data["resource_dir"] + "/image/" + e["template"])
    template.write_bytes(b"also bad")
    issues = project.audit()["errors"]
    assert len(issues) == 2
    assert any("Screenshot" in issue for issue in issues)
    assert any("template" in issue for issue in issues)


def test_stale_generation_reported(project):
    project.generate()
    page, e, shot = first(project)
    project.put_element(page["id"], name="START", element_id=e["id"], shot_id=shot["id"], crop=e["crop"], roi=e["roi"])
    assert any("stale" in issue for issue in project.audit()["errors"])


def test_delete_is_metadata_only(project):
    page, e, shot = first(project)
    project.generate()
    project.expect(page["id"], shot["id"], e["id"], True)
    template = project.path(project.data["resource_dir"] + "/image/" + e["template"])
    project.remove_element(page["id"], e["id"])
    assert template.exists() and project.path(shot["path"]).exists()
    assert project.data["cases"][0]["expect"] == {}
    project.remove_page(page["id"])
    assert any("Unreferenced generated" in w for w in project.audit()["warnings"])
    assert project.data["cases"] == []


def test_diagnostic_coverage_warnings(project):
    page, e, shot = first(project)
    project.generate()
    assert any("No assertions" in w for w in project.audit()["warnings"])
    project.expect(page["id"], shot["id"], e["id"], True)
    warnings = project.audit()["warnings"]
    assert any("negative" in w for w in warnings)
    assert any("Only the crop source" in w for w in warnings)


@pytest.mark.parametrize("actual,expected,status", [
    ({"hit": True, "box": [10, 10, 20, 20]}, {"hit": True, "box": [10, 10, 20, 20]}, "passed"),
    ({"hit": True, "box": [90, 90, 20, 20]}, {"hit": True, "box": [10, 10, 20, 20]}, "failed"),
    ({"hit": False}, {"hit": False}, "passed"),
    ({"hit": True}, {"hit": False}, "failed"),
    ({"error": "native error"}, {"hit": False}, "error"),
    ({}, {"hit": False}, "error"),
    ({"hit": True, "box": None}, {"hit": True, "box": [0, 0, 5, 5]}, "failed"),
])
def test_assertion_semantics(actual, expected, status):
    assert evaluate(actual, expected) == status


def test_iou():
    assert iou([0, 0, 10, 10], [5, 0, 10, 10]) == pytest.approx(1 / 3)
    assert iou([0, 0, 10, 10], [20, 20, 10, 10]) == 0


def test_unlabelled_is_not_a_pass(project):
    project.generate()
    with pytest.raises(ValueError, match="No labelled"):
        run_suite(project, lambda *_: [])


def test_demo_and_report(tmp_path):
    project = create_demo(tmp_path)
    assert project.audit() == {"errors": [], "warnings": []}
    def fake_recognize(page_id, sid):
        case = next(c for c in project.data["cases"] if c["page"] == page_id and c["screenshot"] == sid)
        return [dict(element=eid, name=project.element(page_id, eid)["name"], hit=expect["hit"], box=expect["box"])
                for eid, expect in case["expect"].items()]
    report = run_suite(project, fake_recognize)
    assert report["passed"] == 9 and report["failed"] == report["error"] == 0
    out = project.path(".debug/studio-report")
    assert json.loads((out / "report.json").read_text())["run_id"] == report["run_id"]
    assert len(list((out / report["artifacts"]).glob("*.png"))) == 3
    assert "Green: actual" in (out / "index.html").read_text()


def test_missing_result_is_error(project):
    project.generate()
    page, e, shot = first(project)
    project.expect(page["id"], shot["id"], e["id"], False)
    report = run_suite(project, lambda *_: [])
    assert report["error"] == 1 and report["passed"] == 0


def test_cancellation_does_not_publish_report(project):
    project.generate()
    page, e, shot = first(project)
    project.expect(page["id"], shot["id"], e["id"], True)
    with pytest.raises(InterruptedError):
        run_suite(project, lambda *_: [], cancelled=lambda: True)
    assert not project.path(".debug/studio-report/index.html").exists()


def test_report_output_must_not_overlap_sources(project):
    project.generate()
    page, e, shot = first(project)
    project.expect(page["id"], shot["id"], e["id"], True)
    with pytest.raises(ValueError, match="overlap"):
        run_suite(project, lambda *_: [], report_dir="tests")


def test_cli_exit_codes(tmp_path, capsys):
    assert main(["--project", str(tmp_path), "demo"]) == 0
    assert main(["--project", str(tmp_path), "check", "--strict"]) == 0
    assert main(["--project", str(tmp_path), "init"]) == 2
    assert "already exists" in capsys.readouterr().err


def _echo(connection):
    while True:
        try:
            message = connection.recv()
            connection.send({"ok": True, "value": message["args"]})
        except (EOFError, OSError):
            break


def _hang(connection):
    connection.recv()
    time.sleep(10)


def test_worker_roundtrip_and_shutdown():
    with WorkerClient(timeout=5, _target=_echo) as worker:
        assert worker.request("discover", value=42) == {"value": 42}
        process = worker.process
        assert process.is_alive()
    assert not process.is_alive()


def test_worker_timeout_and_recovery():
    with WorkerClient(timeout=0.2, _target=_hang) as worker:
        with pytest.raises(TimeoutError):
            worker.request("capture")
        assert worker.process is None
        worker.timeout = 5
        worker.target = _echo
        assert worker.request("capture", again=True) == {"again": True}


@pytest.mark.skipif(os.environ.get("MAAPLUS_STUDIO_NATIVE") != "1", reason="Opt-in: needs the real MaaPlus + maafw native library")
def test_native_synthetic_regression(tmp_path):
    project = create_demo(tmp_path)
    with WorkerClient(timeout=90) as worker:
        report = run_suite(project, lambda page_id, sid: worker.request("recognize", root=str(project.root), page_id=page_id, shot_id=sid))
    assert report["passed"] == 9 and report["failed"] == report["error"] == 0, report
