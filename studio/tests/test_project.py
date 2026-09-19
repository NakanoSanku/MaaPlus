from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
from pathlib import Path

import pytest
from PIL import Image
from maa.pipeline import JOCR, JTemplateMatch

from maaplus_studio.generator import generate
from maaplus_studio.importer import import_source
from maaplus_studio.models import Locator, Project, StudioError, UIGroup, compile_locator
from maaplus_studio.storage import CONFIG, ProjectStore, digest


def project():
    return Project(groups=[UIGroup(id="g", module="home", class_name="HomeUI")],
                   locators=[Locator(id="a", group_id="g", name="BUTTON", kind="TemplateMatch", params={"template": ["home/button.png"], "threshold": [0.85]})])


def test_import_complete_example_preserves_native_parameters():
    directory = Path(__file__).parents[2] / "examples/complete_project/demo/ui"
    for file in directory.glob("*.py"):
        if file.name == "__init__.py":
            continue
        groups, locators = import_source(file.read_text(encoding="utf-8"), str(file), file.stem)
        config = Project(groups=groups, locators=locators)
        original, regenerated = {}, {}
        exec(compile(file.read_text(encoding="utf-8"), str(file), "exec"), original)
        source = next(iter(generate(config).values()))
        exec(compile(source, "generated.py", "exec"), regenerated)
        for item in locators:
            cls = next(g.class_name for g in groups if g.id == item.group_id)
            first, second = getattr(original[cls], item.name), getattr(regenerated[cls], item.name)
            assert type(first) is type(second)
            assert dataclasses.asdict(first) == dataclasses.asdict(second)


def test_composition_import_and_generation_share_compiler():
    template = {"recognition": {"type": "TemplateMatch", "param": dataclasses.asdict(JTemplateMatch(template=["a.png"]))}}
    text = {"recognition": {"type": "OCR", "param": dataclasses.asdict(JOCR(expected=["确认"]))}}
    choice = {"recognition": {"type": "Or", "param": {"any_of": [template, text]}}}
    source = (
        "from maa.pipeline import JTemplateMatch, JOr, JAnd\nclass UI:\n"
        "    A = JTemplateMatch(template=['a.png'])\n"
        f"    B = JOr(any_of={[template, text]!r})\n"
        f"    C = JAnd(all_of={[choice, template]!r}, box_index=1)\n"
    )
    original = {}
    exec(source, original)
    groups, items = import_source(source, "ui.py", "home")
    config = Project(groups=groups, locators=items)
    code = next(iter(generate(config).values()))
    assert code == next(iter(generate(config).values()))
    assert "from maaplus" not in code
    assert "JOr(" in code and "JAnd(" in code and "JTemplateMatch(" in code
    scope = {}
    exec(code, scope)
    imported_groups, imported_items = import_source(code, "generated.py", "home")
    imported = Project(groups=imported_groups, locators=imported_items)
    for item in items:
        if item.export:
            generated = getattr(scope["UI"], item.name)
            expected = compile_locator(config, item.id)
            assert type(generated) is type(expected)
            assert dataclasses.asdict(generated) == dataclasses.asdict(expected)
            assert dataclasses.asdict(generated) == dataclasses.asdict(getattr(original["UI"], item.name))
            reimported = next(candidate for candidate in imported_items if candidate.export and candidate.name == item.name)
            assert dataclasses.asdict(compile_locator(imported, reimported.id)) == dataclasses.asdict(expected)


def test_generated_imports_cannot_be_shadowed_by_ui_names():
    config = project()
    config.groups[0].class_name = "JTemplateMatch"
    config.locators[0].name = "JTemplateMatch"
    config.locators.append(Locator(id="b", group_id="g", name="Z", kind="TemplateMatch", params={"template": ["b.png"]}))
    source = next(iter(generate(config).values()))
    scope = {}
    exec(source, scope)
    assert scope["JTemplateMatch"].Z.template == ["b.png"]
    imported_groups, imported_items = import_source(source, "generated.py", "home")
    assert len(imported_items) == 2 and imported_groups[0].class_name == "JTemplateMatch"


def test_native_compositions_expand_across_modules_without_ui_imports():
    config = project()
    config.groups.append(UIGroup(id="other", module="other", class_name="OtherUI"))
    config.locators.extend([
        Locator(id="text", group_id="other", name="TEXT", kind="OCR", params={"expected": ["确认"]}),
        Locator(id="all", group_id="other", name="ALL", kind="And", children=["a", "text"], params={"box_index": 1}),
        Locator(id="any", group_id="g", name="ANY", kind="Or", children=["all", "a"]),
    ])
    config = Project.model_validate(config.model_dump())
    files = generate(config)
    for group in config.groups:
        code = files[f"ui/{group.module}.py"]
        assert "from maaplus" not in code
        assert "from ui" not in code
        scope = {}
        exec(code, scope)
        for item in config.locators:
            if item.group_id == group.id:
                generated = getattr(scope[group.class_name], item.name)
                assert dataclasses.asdict(generated) == dataclasses.asdict(compile_locator(config, item.id))


@pytest.mark.parametrize("box_index", [-1, 2, True])
def test_native_and_config_rejects_invalid_box_index(box_index):
    config = project().model_dump()
    config["locators"].append({"id": "all", "group_id": "g", "name": "ALL", "kind": "And", "children": ["a", "a"], "params": {"box_index": box_index}})
    with pytest.raises(ValueError, match="box_index"):
        Project.model_validate(config)


@pytest.mark.parametrize("source", [
    "from maa.pipeline import JTemplateMatch\nclass UI:\n    A=JTemplateMatch(template=load())\n",
    "from maa.pipeline import JTemplateMatch\nclass UI:\n    def method(self): pass\n",
    "from maa.pipeline import JTemplateMatch\nraise RuntimeError('executed')\n",
    "from maa.pipeline import JTemplateMatch\n@decorator\nclass UI:\n    A=JTemplateMatch(template=['a.png'])\n",
    "from maa.pipeline import JTemplateMatch\nclass UI:\n    A=JTemplateMatch(template=['a.png'])\n    A=JTemplateMatch(template=['b.png'])\n",
    "from maa.pipeline import JOCR\nclass UI:\n    A=JOCR(expected=['a'], expected=['b'])\n",
    "from maa.pipeline import JAnd\nclass UI:\n    A=JAnd(all_of=[{'sub_name': 'alias', 'recognition': {'type': 'OCR', 'param': {}}}])\n",
    "from maa.pipeline import JOCR\nclass UI:\n    A=JOCR(unknown=True)\n",
])
def test_import_rejects_whole_unsupported_file_without_executing(source):
    with pytest.raises(StudioError, match=r"fixture.py:\d+:"):
        import_source(source, "fixture.py", "home")


def test_static_native_and_import():
    source = "from maa.pipeline import JAnd\nclass UI:\n    A = JAnd(all_of=[{'recognition': {'type': 'OCR', 'param': {'expected': ['确认']}}}])\n"
    groups, items = import_source(source, "ui.py", "home")
    assert compile_locator(Project(groups=groups, locators=items), next(i.id for i in items if i.export)).all_of


def test_static_native_or_import():
    source = "from maa.pipeline import JOr\nclass UI:\n    A = JOr(any_of=[{'recognition': {'type': 'OCR', 'param': {'expected': ['确认']}}}])\n"
    groups, items = import_source(source, "ui.py", "home")
    assert compile_locator(Project(groups=groups, locators=items), next(i.id for i in items if i.export)).any_of


@pytest.mark.parametrize("imports, constructor", [
    ("from maa.pipeline import JOCR as Text", "Text"),
    ("import maa.pipeline", "maa.pipeline.JOCR"),
    ("import maa.pipeline as native", "native.JOCR"),
])
def test_native_import_aliases(imports, constructor):
    source = f"{imports}\nclass UI:\n    TEXT = {constructor}(expected=['确认'])\n"
    groups, items = import_source(source, "ui.py", "home")
    result = compile_locator(Project(groups=groups, locators=items), items[0].id)
    assert isinstance(result, JOCR)
    assert result.expected == ["确认"]


def test_inline_native_kind_does_not_override_import_alias():
    source = (
        "from maa.pipeline import JAnd, JOCR as JTemplateMatch\nclass UI:\n"
        "    BOTH = JAnd(all_of=[{'recognition': {'type': 'TemplateMatch', 'param': {'template': ['a.png']}}}])\n"
        "    TEXT = JTemplateMatch(expected=['确认'])\n"
    )
    groups, items = import_source(source, "ui.py", "home")
    text = next(item for item in items if item.name == "TEXT")
    assert isinstance(compile_locator(Project(groups=groups, locators=items), text.id), JOCR)


@pytest.mark.parametrize("source", [
    "from maaplus import Template\nclass UI:\n    A = Template(template=['a.png'])\n",
    "from maaplus import OCR\nclass UI:\n    A = OCR(expected=['确认'])\n",
    "from maaplus import FirstOf\nclass UI:\n    A = FirstOf()\n",
    "from maaplus import AllOf\nclass UI:\n    A = AllOf()\n",
    "import maaplus\nclass UI:\n    A = maaplus.OCR(expected=['确认'])\n",
    "from maa.pipeline import JOr\nclass UI:\n    A = JOr(any_of=[{'recognition': 'OCR', 'expected': ['确认']}])\n",
])
def test_import_rejects_noncurrent_syntax_without_taking_over_file(tmp_path, source):
    path = tmp_path / "ui/home.py"
    path.parent.mkdir()
    path.write_text(source, encoding="utf-8")
    store = ProjectStore(tmp_path)
    with pytest.raises(StudioError, match=r"ui/home.py:\d+:"):
        store.import_file("ui/home.py", Project())
    assert path.read_text(encoding="utf-8") == source
    assert not store.adoptions and not store.imports


def test_module_package_collision_is_rejected():
    with pytest.raises(ValueError, match="同名包冲突"):
        Project(groups=[UIGroup(id="a", module="home", class_name="HomeUI"), UIGroup(id="b", module="home.login", class_name="LoginUI")])


@pytest.mark.parametrize("children", [["absent"], ["a"]])
def test_invalid_composite_references_rejected(children):
    data = project().model_dump()
    data["locators"][0].update(kind="And", params={}, children=children)
    with pytest.raises(ValueError):
        Project.model_validate(data)


@pytest.mark.parametrize("path", ["../escape", "a/../../escape", "D:/escape", "\\\\server\\share", "a/../b", "a:stream", ".git/config", "link/../file", "folder./file", "resource/CON.png", "resource/LPT1.png"])
def test_project_paths_reject_escape(tmp_path, path):
    with pytest.raises(StudioError):
        ProjectStore(tmp_path).path(path)


def test_resolved_symlink_escape_rejected(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside")
    outside.mkdir()
    try:
        (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation requires OS privileges")
    with pytest.raises(StudioError):
        ProjectStore(tmp_path).path("link/escaped.txt")


def test_save_generation_is_idempotent_and_conflicts_are_preserved(tmp_path):
    store = ProjectStore(tmp_path)
    draft = project()
    preview = store.preview(draft, "missing")
    result = store.commit(preview["preview_id"])
    config = Project.model_validate(result["project"])
    assert store.preview(config, result["revision"])["changes"] == []
    target = tmp_path / "ui/home.py"
    target.write_text("# manually edited\n", encoding="utf-8")
    with pytest.raises(StudioError, match="手工修改"):
        store.preview(config, result["revision"])
    assert target.read_text() == "# manually edited\n"


def test_locator_display_name_roundtrip_does_not_change_python_interface(tmp_path):
    config = project()
    assert config.locators[0].label == ""
    original_code = generate(config)
    config.locators[0].label = "开始按钮"
    assert generate(config) == original_code
    store = ProjectStore(tmp_path)
    saved = store.commit(store.preview(config, "missing")["preview_id"])
    loaded, _ = store.load()
    assert loaded.locators[0].label == "开始按钮"
    assert loaded.locators[0].name == "BUTTON"
    imported = store.import_file("ui/home.py", Project.model_validate(saved["project"]))
    assert next(item for item in imported["project"]["locators"] if item["name"] == "BUTTON")["label"] == "开始按钮"


def test_windows_checkout_line_endings_are_not_manual_edits(tmp_path):
    store = ProjectStore(tmp_path)
    saved = store.commit(store.preview(project(), "missing")["preview_id"])
    file = tmp_path / "ui/home.py"
    generated = file.read_bytes()
    file.write_bytes(generated.replace(b"\n", b"\r\n"))
    preview = store.preview(Project.model_validate(saved["project"]), saved["revision"])
    store.commit(preview["preview_id"])
    assert file.read_bytes() == generated


def test_import_requires_conversion_before_overwriting(tmp_path):
    file = tmp_path / "ui/home.py"
    file.parent.mkdir()
    file.write_text("from maa.pipeline import JOCR\nclass HomeUI:\n    TEXT=JOCR(expected=['确认'])\n", encoding="utf-8")
    store = ProjectStore(tmp_path)
    with pytest.raises(StudioError):
        store.preview(project(), "missing")
    converted = store.import_file("ui/home.py", Project())
    assert "from maa.pipeline import JOCR" in file.read_text(encoding="utf-8")
    with pytest.raises(StudioError):
        store.preview(Project.model_validate(converted["project"]), "missing")
    store.accept_import(converted["import_id"])
    preview = store.preview(Project.model_validate(converted["project"]), "missing")
    store.commit(preview["preview_id"])
    assert file.read_text(encoding="utf-8").startswith("# Generated")


def test_explicit_reimport_can_adopt_hand_edited_generated_module(tmp_path):
    store = ProjectStore(tmp_path)
    first = store.preview(project(), "missing")
    saved = store.commit(first["preview_id"])
    file = tmp_path / "ui/home.py"
    file.write_text("from maa.pipeline import JOCR\nclass HomeUI:\n    TEXT=JOCR(expected=['确定'])\n", encoding="utf-8")
    result = store.import_file("ui/home.py", Project.model_validate(saved["project"]))
    store.accept_import(result["import_id"])
    next_preview = store.preview(Project.model_validate(result["project"]), saved["revision"])
    store.commit(next_preview["preview_id"])
    assert "TEXT = JOCR" in file.read_text(encoding="utf-8")


def test_preview_checks_external_edits_again_at_commit(tmp_path):
    store = ProjectStore(tmp_path)
    preview = store.preview(project(), "missing")
    (tmp_path / CONFIG).write_text("{}", encoding="utf-8")
    with pytest.raises(StudioError, match="预览后"):
        store.commit(preview["preview_id"])
    assert not (tmp_path / "ui/home.py").exists()


def test_write_failure_rolls_back_generated_files(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    real = store._write
    def failing(name, data):
        if name.startswith(CONFIG + "."):
            raise OSError("disk full")
        real(name, data)
    monkeypatch.setattr(store, "_write", failing)
    preview = store.preview(project(), "missing")
    with pytest.raises(OSError, match="disk full"):
        store.commit(preview["preview_id"])
    assert not (tmp_path / "ui/home.py").exists()
    assert not (tmp_path / CONFIG).exists()


def test_replacement_failure_restores_existing_files_without_rewriting(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    first = store.commit(store.preview(project(), "missing")["preview_id"])
    original = {name: (tmp_path / name).read_bytes() for name in (CONFIG, "ui/home.py")}
    edited = Project.model_validate(first["project"])
    edited.locators[0].name = "RENAMED"
    preview = store.preview(edited, first["revision"])
    replace = os.replace
    def failing(source, target):
        if Path(source).suffix == ".stage" and Path(target) == tmp_path / CONFIG:
            raise OSError("replacement failed")
        replace(source, target)
    monkeypatch.setattr(os, "replace", failing)
    with pytest.raises(OSError, match="replacement failed"):
        store.commit(preview["preview_id"])
    for name, data in original.items():
        assert (tmp_path / name).read_bytes() == data
    assert not list(tmp_path.rglob("*.stage"))
    assert not list(tmp_path.rglob("*.backup"))


def test_crop_uses_frame_pixels_and_preserves_rgb(tmp_path):
    import io
    image = Image.new("RGB", (20, 16), (200, 10, 30))
    image.putpixel((7, 5), (1, 120, 250))
    buffer = io.BytesIO(); image.save(buffer, format="PNG")
    store = ProjectStore(tmp_path)
    shot = store.save_snapshot(buffer.getvalue())
    store.crop(project(), shot["id"], [7, 5, 6, 4], "crop.png")
    with Image.open(tmp_path / "resource/image/crop.png") as cropped:
        assert cropped.size == (6, 4)
        assert cropped.getpixel((0, 0)) == (1, 120, 250)
    with pytest.raises(StudioError, match="超出截图"):
        store.crop(project(), shot["id"], [19, 15, 5, 5], "invalid.png")
