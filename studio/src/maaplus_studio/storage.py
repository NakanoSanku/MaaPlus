from __future__ import annotations

import difflib
import hashlib
import io
import json
import os
import re
import secrets
import threading
import uuid
from pathlib import Path, PureWindowsPath

from PIL import Image

from .generator import generate
from .importer import import_source
from .models import Project, StudioError

CONFIG = "maaplus-studio.json"


def digest(data: bytes | None) -> str:
    return hashlib.sha256(data).hexdigest() if data is not None else "missing"


def source_digest(data: bytes | None) -> str:
    # Git/Windows may change LF to CRLF on checkout without changing Python source.
    return digest(data.replace(b"\r\n", b"\n") if data is not None else None)


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


class ProjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise StudioError("项目路径必须是目录")
        self.lock = threading.RLock()
        self.adoptions: dict[str, str] = {}
        self.imports: dict[str, dict] = {}
        self.previews: dict[str, dict] = {}
        self.cache = self.path(".maaplus/studio")
        self.cache.mkdir(parents=True, exist_ok=True)

    def path(self, relative: str) -> Path:
        relative = relative.replace("\\", "/")
        parts = relative.split("/")
        if (not relative or PureWindowsPath(relative).drive or relative.startswith("/")
                or any(part in {"", ".", ".."} for part in parts)
                or any(":" in part or "\x00" in part or part.rstrip(" .") != part for part in parts)
                or any(re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", part, re.I) for part in parts)
                or any(part.casefold() in {".git", ".venv", "node_modules"} for part in parts)):
            raise StudioError(f"无效的项目内相对路径：{relative}")
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root) or target == self.root:
            raise StudioError("路径超出项目目录")
        return target

    def read(self, relative: str) -> bytes | None:
        path = self.path(relative)
        return path.read_bytes() if path.is_file() else None

    def load(self) -> tuple[Project, str]:
        data = self.read(CONFIG)
        project = Project.model_validate_json(data) if data else Project()
        self.validate_paths(project)
        return project, digest(data)

    def validate_paths(self, project: Project):
        for path in (project.resource_dir, project.output_dir):
            self.path(path)
            if any(part.startswith(".") for part in path.replace("\\", "/").split("/")):
                raise StudioError("资源和代码目录不能放在隐藏目录内")
        for file in project.managed_files:
            self.path(file)

    def _write(self, relative: str, data: bytes | None):
        path = self.path(relative)
        if data is None:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path = self.path(relative)  # Re-check after creating parents, including Windows junctions.
        temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            with temp.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def transaction(self, writes: dict[str, bytes | None], expected: dict[str, str]):
        with self.lock:
            before = {name: self.read(name) for name in writes}
            if any(digest(self.read(name)) != value for name, value in expected.items()):
                raise StudioError("文件在预览后发生变化，请重新预览")
            for name in writes:
                target = self.path(name)
                if target.exists() and not target.is_file():
                    raise StudioError(f"目标不是文件：{name}")
            token = uuid.uuid4().hex
            staged = {}
            backups = {}
            applied = []
            completed = False
            try:
                # Finish all potentially space-consuming writes before replacing originals.
                for name, data in writes.items():
                    if data is not None:
                        staged[name] = name + f".{token}.stage"
                        self._write(staged[name], data)
                if any(digest(self.read(name)) != value for name, value in expected.items()):
                    raise StudioError("文件在预览后发生变化，请重新预览")
                for name, data in writes.items():
                    applied.append(name)
                    if before[name] is not None:
                        backup = name + f".{token}.backup"
                        os.replace(self.path(name), self.path(backup))
                        backups[name] = backup
                    if data is not None:
                        os.replace(self.path(staged[name]), self.path(name))
                completed = True
            except Exception as exc:
                failures = []
                for name in reversed(applied):
                    try:
                        if name in backups:
                            os.replace(self.path(backups[name]), self.path(name))
                        elif before[name] is None:
                            self.path(name).unlink(missing_ok=True)
                    except OSError:
                        failures.append(backups.get(name, name))
                if failures:
                    raise StudioError("保存失败且回滚受阻，恢复文件保留在：" + ", ".join(failures)) from exc
                raise
            finally:
                for relative in staged.values():
                    self.path(relative).unlink(missing_ok=True)
                if completed:
                    for relative in backups.values():
                        self.path(relative).unlink(missing_ok=True)

    def preview(self, project: Project, revision: str, extra: dict[str, bytes | None] | None = None):
        with self.lock:
            saved, current = self.load()
            if revision != current:
                raise StudioError("项目配置已变化，请重新加载后编辑")
            self.validate_paths(project)
            files = generate(project)
            resolved = [str(self.path(name)).casefold() for name in files]
            if len(set(resolved)) != len(resolved):
                raise StudioError("生成模块路径存在大小写或链接冲突")
            writes: dict[str, bytes | None] = {name: value.encode("utf-8") for name, value in files.items()}
            expected = {CONFIG: current}
            old = saved.managed_files
            for name in set(old) | set(files):
                existing = self.read(name)
                actual = digest(existing)
                adopted = self.adoptions.get(name)
                unchanged = actual == adopted if adopted is not None else source_digest(existing) == old.get(name, "missing")
                if not unchanged:
                    raise StudioError(f"文件存在手工修改或尚未导入，禁止覆盖：{name}")
                expected[name] = actual
                if name not in files:
                    writes[name] = None
            if extra:
                for name, data in extra.items():
                    if name in writes or name == CONFIG:
                        raise StudioError("资源路径与生成文件冲突")
                    writes[name] = data
                    expected[name] = digest(self.read(name))
            updated = project.model_copy(deep=True)
            updated.managed_files = {name: digest(value.encode("utf-8")) for name, value in files.items()}
            writes[CONFIG] = json_bytes(updated.model_dump(mode="json"))
            changes = []
            for name, value in writes.items():
                before = self.read(name)
                if before == value:
                    continue
                diff = ""
                if name.endswith((".py", ".json")):
                    diff = "".join(difflib.unified_diff((before or b"").decode("utf-8").splitlines(True),
                                                       (value or b"").decode("utf-8").splitlines(True),
                                                       fromfile=name, tofile=name))
                changes.append({"path": name, "action": "delete" if value is None else "create" if before is None else "update", "diff": diff})
            token = secrets.token_urlsafe(24)
            self.previews.clear()
            self.previews[token] = {"writes": writes, "expected": expected}
            return {"preview_id": token, "changes": changes, "files": files, "project": updated.model_dump(mode="json")}

    def commit(self, token: str):
        with self.lock:
            plan = self.previews.pop(token, None)
            if plan is None:
                raise StudioError("预览已过期，请重新预览")
            self.transaction(plan["writes"], plan["expected"])
            self.adoptions.clear()
            project, revision = self.load()
            return {"project": project.model_dump(mode="json"), "revision": revision}

    def import_file(self, relative: str, project: Project):
        path = self.path(relative)
        output = self.path(project.output_dir)
        if path.suffix != ".py" or not path.is_relative_to(output):
            raise StudioError("导入文件必须位于所选 Python 输出目录内")
        module = ".".join(path.relative_to(output).with_suffix("").parts)
        raw = path.read_bytes()
        groups, locators = import_source(raw.decode("utf-8-sig"), relative, module)
        # Display names belong to the Studio config, not to generated Python.
        previous_groups = {g.class_name: g for g in project.groups if g.module == module}
        previous_labels = {(g.class_name, item.name): item.label for g in previous_groups.values()
                           for item in project.locators if item.group_id == g.id and item.export}
        for group in groups:
            if group.class_name in previous_groups:
                group.label = previous_groups[group.class_name].label
            for item in locators:
                if item.group_id == group.id and item.export:
                    item.label = previous_labels.get((group.class_name, item.name), "")
        existing_ids = {g.id for g in project.groups if g.module == module}
        removed_ids = {item.id for item in project.locators if item.group_id in existing_ids}
        if any(removed_ids.intersection(item.children) for item in project.locators if item.group_id not in existing_ids):
            raise StudioError("该模块已有其他定位项引用，请先处理组合依赖")
        data = project.model_dump(mode="json")
        data["groups"] = [g.model_dump() for g in project.groups if g.module != module] + [g.model_dump() for g in groups]
        data["locators"] = [i.model_dump() for i in project.locators if i.group_id not in existing_ids] + [i.model_dump() for i in locators]
        merged = Project.model_validate(data)
        token = secrets.token_urlsafe(24)
        result = {"import_id": token, "project": merged.model_dump(mode="json"), "groups": len(groups), "locators": sum(i.export for i in locators), "path": relative.replace("\\", "/")}
        self.imports.clear()
        self.imports[token] = {"result": result, "hash": digest(raw)}
        return result

    def accept_import(self, token: str):
        with self.lock:
            imported = self.imports.pop(token, None)
            if imported is None:
                raise StudioError("导入预览已过期，请重新导入")
            result = imported["result"]
            if digest(self.read(result["path"])) != imported["hash"]:
                raise StudioError("源文件在导入预览后变化，请重新导入")
            self.adoptions[result["path"]] = imported["hash"]
            return result

    def list_python(self, project: Project):
        folder = self.path(project.output_dir)
        return [p.relative_to(self.root).as_posix() for p in sorted(folder.rglob("*.py"))
                if p.is_file() and p.resolve().is_relative_to(self.root) and "__pycache__" not in p.parts][:2000] if folder.exists() else []

    def assets(self, project: Project):
        folder = self.path(project.resource_dir + "/image")
        if not folder.exists():
            return []
        return [{"path": p.relative_to(folder).as_posix(), "bytes": p.stat().st_size,
                 "references": self.asset_references(project, p.relative_to(folder).as_posix())}
                for p in sorted(folder.rglob("*")) if p.is_file() and p.resolve().is_relative_to(self.root)
                and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}][:2000]

    def asset_references(self, project: Project, name: str):
        target = self.path(f"{project.resource_dir}/image/{name}")
        groups = {g.id: g.class_name for g in project.groups}
        return [f"{item.label}（{groups[item.group_id]}.{item.name}）" if item.label.strip() else f"{groups[item.group_id]}.{item.name}" for item in project.locators
                if any(self.path(f"{project.resource_dir}/image/{template}") == target for template in item.params.get("template", []))]

    def asset_thumbnail(self, resource_dir: str, name: str) -> bytes:
        folder = self.path(f"{resource_dir}/image")
        path = self.path(f"{resource_dir}/image/{name}")
        if not path.is_relative_to(folder) or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            raise StudioError("只能预览当前资源 image 目录内的图片")
        if not path.is_file():
            raise StudioError(f"图片不存在：{name}")
        if path.stat().st_size > 32 * 1024 * 1024:
            raise StudioError("图片超过 32 MB，无法生成缩略图")
        try:
            with Image.open(path) as image:
                if image.width * image.height > 40_000_000:
                    raise StudioError("图片像素数过大，无法生成缩略图")
                image.thumbnail((240, 160), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                image.convert("RGBA").save(buffer, format="PNG")
                return buffer.getvalue()
        except (OSError, Image.DecompressionBombError) as exc:
            raise StudioError(f"无法预览图片 {name}：{exc}") from exc

    def save_snapshot(self, data: bytes, source: dict | None = None):
        if len(data) > 32 * 1024 * 1024:
            raise StudioError("截图不能超过 32 MB")
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 40_000_000:
                raise StudioError("截图像素数过大")
            image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
        key = uuid.uuid4().hex
        relative = f".maaplus/studio/shots/{key}.png"
        self._write(relative, buffer.getvalue())
        metadata = {"id": key, "width": image.width, "height": image.height, "source": source or {"kind": "import"}}
        self._write(f".maaplus/studio/shots/{key}.json", json_bytes(metadata))
        return metadata

    def snapshot_path(self, key: str):
        if len(key) != 32 or any(char not in "0123456789abcdef" for char in key):
            raise StudioError("截图标识无效")
        path = self.path(f".maaplus/studio/shots/{key}.png")
        if not path.is_file():
            raise StudioError("截图不存在，请重新采集")
        return path

    def crop(self, project: Project, key: str, rect: list[int], name: str):
        if len(rect) != 4 or any(type(v) is not int for v in rect):
            raise StudioError("裁图区域必须为整数 x, y, width, height")
        x, y, width, height = rect
        if min(x, y) < 0 or min(width, height) <= 0:
            raise StudioError("裁图区域无效")
        if not name.lower().endswith(".png"):
            raise StudioError("模板保存为 PNG 文件")
        target = f"{project.resource_dir}/image/{name}"
        if self.path(target).exists():
            raise StudioError("图片已存在，请使用新名称")
        with Image.open(self.snapshot_path(key)) as image:
            if x + width > image.width or y + height > image.height:
                raise StudioError("裁图区域超出截图")
            buffer = io.BytesIO()
            image.crop((x, y, x + width, y + height)).save(buffer, format="PNG")
        self.transaction({target: buffer.getvalue()}, {target: "missing"})
        return {"path": name, "width": width, "height": height}
