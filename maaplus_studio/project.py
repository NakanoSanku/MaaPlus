"""Versioned project metadata, immutable image assets and guarded code generation."""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import keyword
import math
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from PIL import Image

MANIFEST = "maaplus-studio.json"
SCHEMA = 1
KINDS = ("Template", "OCR", "FirstOf", "AllOf")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", value) or keyword.iskeyword(value):
        raise ValueError(f"Invalid Python identifier: {value!r}")
    if value in {*KINDS, "__module__", "__qualname__"}:
        raise ValueError(f"Reserved identifier: {value}")
    return value


def relative(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError(f"Use a project-relative POSIX path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("", ".", "..") for p in value.split("/")):
        raise ValueError(f"Unsafe relative path: {value!r}")
    return value


def rect(value, size) -> list[int]:
    if not isinstance(value, (list, tuple)) or len(value) != 4 or any(type(v) is not int for v in value):
        raise ValueError("Rectangle must contain four integers: x, y, width, height")
    x, y, w, h = value
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > size[0] or y + h > size[1]:
        raise ValueError(f"Rectangle {value} is outside screenshot {size}")
    return list(value)


def png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.convert("RGB").save(output, "PNG")
    return output.getvalue()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".studio-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Project:
    def __init__(self, root: Path, data: dict, revision: str | None = None):
        self.root = Path(root).resolve()
        self.data = data
        self.revision = revision
        self.validate()

    @classmethod
    def create(cls, root, *, ui="ui/generated", resource="resource", fixtures="tests/ui", size=(1280, 720)):
        root = Path(root).resolve()
        if (root / MANIFEST).exists():
            raise FileExistsError(f"Project already exists: {root / MANIFEST}")
        project = cls(root, {
            "schema": SCHEMA, "ui_dir": ui, "resource_dir": resource, "fixtures_dir": fixtures,
            "size": list(size), "short_side": min(size), "pages": [], "screenshots": [],
            "cases": [], "generated": {},
        })
        project.save()
        (project.path(resource) / "image").mkdir(parents=True, exist_ok=True)
        (project.path(resource) / "pipeline").mkdir(parents=True, exist_ok=True)
        return project

    @classmethod
    def open(cls, root):
        root = Path(root)
        if root.is_file():
            root = root.parent
        raw = (root / MANIFEST).read_bytes()
        return cls(root, json.loads(raw), digest(raw))

    def path(self, value: str) -> Path:
        result = (self.root / relative(value)).resolve()
        if not result.is_relative_to(self.root) or result == self.root:
            raise ValueError(f"Path escapes project (possibly a symlink): {value}")
        return result

    def output_path(self, value: str) -> Path:
        path = self.path(value)
        base = self.path(self.data["ui_dir"])
        if not path.is_relative_to(base) or path.suffix != ".py" or path.name == "__init__.py":
            raise ValueError(f"Generated files must be .py files below {self.data['ui_dir']}, not __init__.py")
        return path

    def page(self, page_id):
        return next(p for p in self.data["pages"] if p["id"] == page_id)

    def screenshot(self, shot_id):
        return next(s for s in self.data["screenshots"] if s["id"] == shot_id)

    def element(self, page_id, element_id):
        return next(e for e in self.page(page_id)["elements"] if e["id"] == element_id)

    @contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / ".maaplus-studio.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("Another Studio is writing. If it crashed, close it before removing .maaplus-studio.lock") from exc
        try:
            os.close(fd)
            manifest = self.root / MANIFEST
            current = digest(manifest.read_bytes()) if manifest.exists() else None
            if current != self.revision:
                raise RuntimeError("Project changed on disk. Reopen it before editing; no files were overwritten.")
            yield
        finally:
            lock.unlink(missing_ok=True)

    def _save(self):
        self.validate()
        raw = (json.dumps(self.data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        atomic_write(self.root / MANIFEST, raw)
        self.revision = digest(raw)

    def save(self):
        with self.locked():
            self._save()

    @contextmanager
    def edit(self):
        before = copy.deepcopy(self.data)
        try:
            with self.locked():
                yield
                self._save()
        except BaseException:
            self.data = before
            raise

    def validate(self):
        d = self.data
        if d.get("schema") != SCHEMA:
            raise ValueError("Unsupported project schema; use a compatible Studio version")
        size = d["size"]
        if len(size) != 2 or any(type(n) is not int or not 1 <= n <= 16384 for n in size):
            raise ValueError("Project resolution must contain two positive integers <= 16384")
        if d["short_side"] != min(size):
            raise ValueError("short_side must equal the shorter project dimension")
        roots = [self.path(d[k]) for k in ("ui_dir", "resource_dir", "fixtures_dir")]
        if any(a.is_relative_to(b) or b.is_relative_to(a) for i, a in enumerate(roots) for b in roots[i + 1:]):
            raise ValueError("UI, resource and fixture directories must not overlap")
        seen_ids, shot_ids, names = set(), set(), set()
        paths = {}
        for collection in (d["pages"], d["screenshots"], d["cases"]):
            for item in collection:
                uid = item["id"]
                if not re.fullmatch(r"[a-f0-9]{32,64}", uid) or uid in seen_ids:
                    raise ValueError("Invalid or duplicate stable ID")
                seen_ids.add(uid)
        for shot in d["screenshots"]:
            shot_ids.add(shot["id"])
            if shot["size"] != size or not self.path(shot["path"]).is_relative_to(roots[2]):
                raise ValueError("Screenshot size or fixture path does not match this project")
        page_ids = {p["id"] for p in d["pages"]}
        for page in d["pages"]:
            identifier(page["name"])
            output = self.output_path(page["file"])
            key = (page["file"].casefold(), page["name"])
            if key in names:
                raise ValueError("Duplicate page class in the same output module")
            names.add(key)
            folded = str(output).casefold()
            if folded in paths and paths[folded] != page["file"]:
                raise ValueError("Case-only output path collision")
            paths[folded] = page["file"]
            element_ids, element_names = set(), set()
            for element in page["elements"]:
                identifier(element["name"])
                if element["name"] in element_names or element["id"] in seen_ids:
                    raise ValueError("Duplicate element name or stable ID")
                if not re.fullmatch(r"[a-f0-9]{32}", element["id"]):
                    raise ValueError("Invalid element ID")
                seen_ids.add(element["id"])
                element_names.add(element["name"])
                if element["kind"] not in KINDS:
                    raise ValueError("Unknown locator kind")
                if element["kind"] in ("FirstOf", "AllOf"):
                    refs = element["refs"]
                    if not refs or any(r not in element_ids for r in refs):
                        raise ValueError("Composite references must refer to earlier elements on the same page")
                    if element["kind"] == "AllOf" and not 0 <= element.get("box_index", 0) < len(refs):
                        raise ValueError("AllOf box_index is outside its references")
                else:
                    if element["source"] not in shot_ids:
                        raise ValueError("Element source screenshot is missing")
                    rect(element["crop"], size)
                    rect(element["roi"], size)
                    threshold = element["threshold"]
                    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
                        raise ValueError("Threshold must be between 0 and 1")
                    if element["kind"] == "Template":
                        if element["crop"][2] > element["roi"][2] or element["crop"][3] > element["roi"][3]:
                            raise ValueError("Template crop is larger than the recognition ROI")
                        if not re.fullmatch(r"[a-f0-9]{64}", element["template_sha256"]):
                            raise ValueError("Invalid template hash")
                        template = self.path(d["resource_dir"] + "/image/" + relative(element["template"]))
                        if not template.is_relative_to(roots[1] / "image"):
                            raise ValueError("Invalid template path")
                    elif not isinstance(element["expected"], list) or not element["expected"] or any(not isinstance(t, str) or not t for t in element["expected"]):
                        raise ValueError("OCR requires at least one non-empty expected text/regex")
                element_ids.add(element["id"])
        for case in d["cases"]:
            if case["page"] not in page_ids or case["screenshot"] not in shot_ids:
                raise ValueError("Test references a missing page or screenshot")
            ids = {e["id"] for e in self.page(case["page"])["elements"]}
            for eid, expectation in case["expect"].items():
                if eid not in ids or type(expectation["hit"]) is not bool:
                    raise ValueError("Invalid test expectation")
                if expectation.get("box") is not None:
                    rect(expectation["box"], size)
                iou = expectation.get("min_iou", 0.5)
                if type(iou) not in (int, float) or not math.isfinite(iou) or not 0 <= iou <= 1:
                    raise ValueError("IoU threshold must be in [0, 1]")
        for name, sha in d["generated"].items():
            self.output_path(name)
            if not re.fullmatch(r"[a-f0-9]{64}", sha):
                raise ValueError("Invalid generated file hash")

    def add_page(self, name, file):
        page = {"id": uuid.uuid4().hex, "name": identifier(name), "file": relative(file), "elements": []}
        with self.edit():
            self.data["pages"].append(page)
        return page["id"]

    def update_page(self, page_id, *, name, file):
        with self.edit():
            page = self.page(page_id)
            page.update(name=identifier(name), file=relative(file))

    def remove_page(self, page_id):
        with self.edit():
            self.data["pages"][:] = [p for p in self.data["pages"] if p["id"] != page_id]
            self.data["cases"][:] = [c for c in self.data["cases"] if c["page"] != page_id]

    def add_screenshot(self, image: Image.Image, source: dict | None = None):
        if list(image.size) != self.data["size"]:
            raise ValueError(f"Expected {self.data['size']}, got {list(image.size)}. Capture with the same runtime scaling; Studio will not stretch images.")
        raw = png(image)
        sid = digest(raw)
        existing = next((s for s in self.data["screenshots"] if s["id"] == sid), None)
        if existing is not None:
            self.image(sid)  # Do not accept an externally modified deduplicated image.
            with self.edit():
                existing.setdefault("observations", []).append({
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "source": source or {"kind": "import"},
                })
            return sid
        path = f"{self.data['fixtures_dir']}/screenshots/{sid}.png"
        with self.edit():
            target = self.path(path)
            if target.exists() and target.read_bytes() != raw:
                raise RuntimeError("Immutable screenshot collision")
            atomic_write(target, raw)
            self.data["screenshots"].append({
                "id": sid, "path": path, "sha256": sid, "size": list(image.size),
                "captured_at": datetime.now(timezone.utc).isoformat(), "source": source or {"kind": "import"},
            })
        return sid

    def image(self, shot_id):
        shot = self.screenshot(shot_id)
        raw = self.path(shot["path"]).read_bytes()
        if digest(raw) != shot["sha256"]:
            raise ValueError(f"Screenshot was modified outside Studio: {shot['path']}")
        with Image.open(io.BytesIO(raw)) as image:
            if list(image.size) != self.data["size"]:
                raise ValueError("Screenshot resolution changed")
            return image.convert("RGB")

    def put_element(self, page_id, *, name, kind="Template", shot_id=None, crop=None, roi=None,
                    threshold=0.85, expected=None, element_id=None, refs=None, box_index=0):
        eid = element_id or uuid.uuid4().hex
        element = {"id": eid, "name": identifier(name), "kind": kind}
        if kind in ("FirstOf", "AllOf"):
            element.update(refs=refs or [], box_index=box_index)
        else:
            crop = rect(crop, self.data["size"])
            element.update(source=shot_id, crop=crop, roi=rect(roi or crop, self.data["size"]), threshold=float(threshold))
            if kind == "Template":
                x, y, w, h = crop
                raw = png(self.image(shot_id).crop((x, y, x + w, y + h)))
                element.update(template=f"studio/{eid}/{digest(raw)}.png", template_sha256=digest(raw))
            else:
                element["expected"] = expected or []
        with self.edit():
            elements = self.page(page_id)["elements"]
            index = next((i for i, e in enumerate(elements) if e["id"] == eid), None)
            if index is None:
                elements.append(element)
            else:
                elements[index] = element
            self.validate()
            if kind == "Template":
                target = self.path(self.data["resource_dir"] + "/image/" + element["template"])
                if target.exists() and target.read_bytes() != raw:
                    raise RuntimeError("Immutable template collision")
                atomic_write(target, raw)
        return eid

    def remove_element(self, page_id, element_id):
        with self.edit():
            elements = self.page(page_id)["elements"]
            if any(element_id in e.get("refs", []) for e in elements):
                raise ValueError("This element is referenced by a composite; update that composite first")
            elements[:] = [e for e in elements if e["id"] != element_id]
            for case in self.data["cases"]:
                if case["page"] == page_id:
                    case["expect"].pop(element_id, None)
        # Immutable crops remain on disk. audit() reports unused files; never delete implicitly.

    def expect(self, page_id, shot_id, element_id, hit: bool, box=None):
        with self.edit():
            case = next((c for c in self.data["cases"] if c["page"] == page_id and c["screenshot"] == shot_id), None)
            if case is None:
                case = {"id": uuid.uuid4().hex, "page": page_id, "screenshot": shot_id, "expect": {}}
                self.data["cases"].append(case)
            case["expect"][element_id] = {"hit": hit, "box": box if hit else None, "min_iou": 0.5}

    def render(self) -> dict[str, str]:
        self.validate()
        files = {}
        for page in self.data["pages"]:
            lines = files.setdefault(page["file"], [
                "# Generated by MaaPlus UI Studio. Edit maaplus-studio.json via Studio.",
                "# Keep handwritten compositions in a separate module; this file is guarded by SHA-256.",
                "from maaplus import AllOf, FirstOf, OCR, Template", "",
            ])
            lines.extend([f"# studio-page: {page['id']}", f"class {page['name']}:"])
            if not page["elements"]:
                lines.append("    pass")
            names = {}
            for element in page["elements"]:
                kind = element["kind"]
                lines.append(f"    # studio-element: {element['id']}")
                if kind in ("FirstOf", "AllOf"):
                    args = ", ".join(names[r] for r in element["refs"])
                    if kind == "AllOf":
                        args += f", box_index={element.get('box_index', 0)}"
                else:
                    lines.append(f"    # source: {element['source']} crop={element['crop']}")
                    args = (f"template={[element['template']]!r}, threshold={[element['threshold']]!r}"
                            if kind == "Template" else f"expected={element['expected']!r}, threshold={element['threshold']!r}")
                    args += f", roi={tuple(element['roi'])!r}"
                lines.append(f"    {element['name']} = {kind}({args})")
                names[element["id"]] = element["name"]
            lines.append("")
        rendered = {path: "\n".join(lines) + "\n" for path, lines in files.items()}
        for path, code in rendered.items():
            ast.parse(code, filename=path)
        return rendered

    def generate(self):
        rendered = self.render()
        old_data = copy.deepcopy(self.data)
        changes = []
        with self.locked():
            for name, code in rendered.items():
                path = self.output_path(name)
                previous = path.read_bytes() if path.exists() else None
                if previous is not None and digest(previous) != self.data["generated"].get(name):
                    raise RuntimeError(f"Refusing to overwrite handwritten/externally edited file: {name}. Choose a new output file.")
                changes.append((name, path, previous, code.encode()))
            written = []
            try:
                for name, path, previous, raw in changes:
                    if previous is not None:
                        backup = self.path(f".studio-backups/{digest(previous)}.py")
                        atomic_write(backup, previous)
                    atomic_write(path, raw)
                    written.append((path, previous))
                    self.data["generated"][name] = digest(raw)
                self._save()
            except BaseException:
                for path, previous in reversed(written):
                    if previous is None:
                        path.unlink(missing_ok=True)
                    else:
                        atomic_write(path, previous)
                self.data = old_data
                raise
        return list(rendered)

    def check_generated(self):
        for name, code in self.render().items():
            path = self.output_path(name)
            if not path.exists() or path.read_bytes() != code.encode():
                raise ValueError(f"Generated Python is missing, modified or stale: {name}; generate it before testing")

    def audit(self):
        """Read-only diagnostics. Orphan reports are deliberately not an automatic garbage collector."""
        errors, warnings = [], []
        for shot in self.data["screenshots"]:
            try:
                self.image(shot["id"])
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
        used = set()
        for page in self.data["pages"]:
            for e in page["elements"]:
                if e["kind"] == "Template":
                    path = self.path(self.data["resource_dir"] + "/image/" + e["template"])
                    used.add(path)
                    if not path.is_file() or digest(path.read_bytes()) != e["template_sha256"]:
                        errors.append(f"Missing/modified template: {e['template']}")
                labels = [c for c in self.data["cases"] if c["page"] == page["id"] and e["id"] in c["expect"]]
                if not labels:
                    warnings.append(f"No assertions: {page['name']}.{e['name']}")
                elif not any(not c["expect"][e["id"]]["hit"] for c in labels):
                    warnings.append(f"No negative sample: {page['name']}.{e['name']}")
                if labels and all(c["screenshot"] == e.get("source") for c in labels):
                    warnings.append(f"Only the crop source was tested: {page['name']}.{e['name']}")
        directory = self.path(self.data["resource_dir"]) / "image" / "studio"
        if directory.exists():
            for file in sorted(directory.rglob("*.png")):
                if file.resolve() not in used:
                    warnings.append(f"Unreferenced crop (retained): {file.relative_to(self.root).as_posix()}")
        active_files = self.render()
        for name in self.data["generated"]:
            if name not in active_files:
                warnings.append(f"Unreferenced generated file (retained): {name}")
        try:
            self.check_generated()
        except ValueError as exc:
            errors.append(str(exc))
        return {"errors": errors, "warnings": warnings}
