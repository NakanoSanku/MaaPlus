from __future__ import annotations

import dataclasses
import json
import keyword
import re
from typing import Any, Literal

from maa import pipeline
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

KINDS = {
    "TemplateMatch": pipeline.JTemplateMatch,
    "OCR": pipeline.JOCR,
    "FeatureMatch": pipeline.JFeatureMatch,
    "ColorMatch": pipeline.JColorMatch,
    "Custom": pipeline.JCustomRecognition,
    "And": pipeline.JAnd,
    "Or": pipeline.JOr,
}


class StudioError(ValueError):
    pass


def identifier(value: str) -> bool:
    return bool(value) and value.isidentifier() and not keyword.iskeyword(value)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UIGroup(Model):
    id: str = Field(min_length=1)
    module: str
    class_name: str
    label: str = ""


class Locator(Model):
    id: str = Field(min_length=1)
    group_id: str
    name: str
    label: str = ""
    kind: Literal["TemplateMatch", "OCR", "FeatureMatch", "ColorMatch", "Custom", "And", "Or"]
    params: dict[str, Any] = Field(default_factory=dict)
    children: list[str] = Field(default_factory=list)
    export: bool = True


class Project(Model):
    version: Literal[1] = 1
    resource_dir: str = "resource"
    output_dir: str = "ui"
    resource_hook: str = ""
    groups: list[UIGroup] = Field(default_factory=list)
    locators: list[Locator] = Field(default_factory=list)
    managed_files: dict[str, str] = Field(default_factory=dict)

    @field_validator("resource_dir", "output_dir")
    @classmethod
    def normalize_directory(cls, value: str):
        return value.replace("\\", "/").rstrip("/")

    @model_validator(mode="after")
    def validate_definitions(self):
        group_ids = {g.id for g in self.groups}
        if len(group_ids) != len(self.groups):
            raise ValueError("UI 分组标识重复")
        names = set()
        modules = {g.module.casefold() for g in self.groups}
        for module in modules:
            parts = module.split(".")
            if any(".".join(parts[:index]) in modules for index in range(1, len(parts))):
                raise ValueError(f"模块与同名包冲突：{module}")
        for group in self.groups:
            if not all(identifier(part) for part in group.module.split(".")):
                raise ValueError(f"无效模块名称：{group.module}")
            if not identifier(group.class_name):
                raise ValueError(f"无效类名：{group.class_name}")
            key = (group.module.casefold(), group.class_name)
            if key in names:
                raise ValueError(f"UI 类重复：{group.module}.{group.class_name}")
            names.add(key)
        ids = {item.id for item in self.locators}
        if len(ids) != len(self.locators):
            raise ValueError("定位项标识重复")
        names = set()
        for item in self.locators:
            if item.group_id not in group_ids or not identifier(item.name):
                raise ValueError(f"定位项名称或所属分组无效：{item.name}")
            if item.name.startswith("__") and item.name.endswith("__"):
                raise ValueError(f"定位项不能使用 Python 保留属性：{item.name}")
            if item.export and (item.group_id, item.name) in names:
                raise ValueError(f"定位项名称重复：{item.name}")
            if item.export:
                names.add((item.group_id, item.name))
            if item.kind in {"And", "Or"}:
                if not item.children or any(child not in ids for child in item.children):
                    raise ValueError(f"{item.name}：组合成员为空或引用的定位项不存在")
                allowed = {"box_index"} if item.kind == "And" else set()
                if set(item.params) - allowed:
                    raise ValueError(f"{item.name}：组合通过 children 管理成员")
                index = item.params.get("box_index", 0)
                if type(index) is not int or not 0 <= index < len(item.children):
                    raise ValueError(f"{item.name}：box_index 超出成员范围")
            else:
                if item.children:
                    raise ValueError(f"{item.name}：该识别类型没有组合成员")
                native_params(item)
        visiting: set[str] = set()
        visited: set[str] = set()
        mapping = {item.id: item for item in self.locators}

        def visit(key: str, depth: int = 0):
            if key in visiting or depth > 40:
                raise ValueError("组合引用存在循环或超过 40 层")
            if key in visited:
                return
            visiting.add(key)
            for child in mapping[key].children:
                visit(child, depth + 1)
            visiting.remove(key)
            visited.add(key)

        for key in mapping:
            visit(key)
        if self.resource_hook and not re.fullmatch(r"[\w.]+:[\w.]+", self.resource_hook):
            raise ValueError("资源扩展使用 module:callable 格式")
        return self


def native_params(item: Locator):
    try:
        json.dumps(item.params, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise StudioError(f"{item.name}：参数必须为有效 JSON，不支持非有限数字或 Python 专有对象") from exc
    cls = KINDS[item.kind]
    allowed = {field.name for field in dataclasses.fields(cls)}
    unknown = set(item.params) - allowed
    if unknown:
        raise StudioError(f"{item.name}：未知原生参数 {', '.join(sorted(unknown))}")
    try:
        value = TypeAdapter(cls).validate_python(item.params)
    except ValueError as exc:
        raise StudioError(f"{item.name}：{exc}") from exc
    roi = getattr(value, "roi", None)
    if isinstance(roi, tuple) and any(x < 0 for x in roi):
        raise StudioError(f"{item.name}：ROI 坐标和尺寸不能为负")
    for path in getattr(value, "template", []):
        if not path or path.startswith(("/", "\\")) or ":" in path or ".." in path.replace("\\", "/").split("/"):
            raise StudioError(f"{item.name}：模板必须使用资源目录内的相对路径")
    return value


def compile_locator(project: Project, locator_id: str):
    mapping = {item.id: item for item in project.locators}

    def build(key: str):
        if key not in mapping:
            raise StudioError("定位项不存在")
        item = mapping[key]
        if item.kind in {"And", "Or"}:
            members = [{"recognition": {"type": mapping[child].kind, "param": dataclasses.asdict(build(child))}}
                       for child in item.children]
            if item.kind == "And":
                return pipeline.JAnd(all_of=members, box_index=item.params.get("box_index", 0))
            return pipeline.JOr(any_of=members)
        return native_params(item)

    return build(locator_id)


def schema_catalog():
    return {name: TypeAdapter(cls).json_schema() for name, cls in KINDS.items()}
