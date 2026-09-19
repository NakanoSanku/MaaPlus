from __future__ import annotations

import ast
import uuid
from .models import KINDS, Locator, Project, StudioError, UIGroup, native_params

CALLS = {cls.__name__: kind for kind, cls in KINDS.items()}


def import_source(source: str, filename: str, module: str) -> tuple[list[UIGroup], list[Locator]]:
    """Read a conservative static subset. Never import or execute the inspected source."""
    try:
        tree = ast.parse(source, filename=filename)
        compile(tree, filename, "exec")  # Syntax validation only; never execute the code object.
    except SyntaxError as exc:
        raise StudioError(f"{filename}:{exc.lineno}: {exc.msg}") from exc
    aliases = {}
    namespaces = set()
    groups = []
    items = []
    expressions = {}

    def fail(node, message):
        raise StudioError(f"{filename}:{getattr(node, 'lineno', 1)}: {message}")

    def docstring(node):
        return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)

    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.level:
                fail(node, "相对模块导入需要人工处理")
            if node.module == "__future__":
                continue
            if node.module != "maa.pipeline" or any(a.name not in CALLS for a in node.names):
                fail(node, "仅支持来自 maa.pipeline 的原生识别类型")
            aliases.update({a.asname or a.name: a.name for a in node.names})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "maa.pipeline":
                    fail(node, "仅支持导入 maa.pipeline 模块")
                namespaces.add(alias.asname or alias.name)
        elif isinstance(node, ast.ClassDef):
            if node.bases or node.keywords or node.decorator_list:
                fail(node, "带继承或装饰器的 UI 类需要人工处理")
            if any(group.class_name == node.name for group in groups):
                fail(node, "UI 类重复定义")
            group = UIGroup(id=uuid.uuid4().hex, module=module, class_name=node.name)
            groups.append(group)
            for statement in node.body:
                if docstring(statement) or isinstance(statement, ast.Pass):
                    continue
                if isinstance(statement, ast.Assign) and len(statement.targets) == 1 and isinstance(statement.targets[0], ast.Name):
                    name, value = statement.targets[0].id, statement.value
                elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is not None:
                    if not isinstance(statement.annotation, (ast.Name, ast.Attribute, ast.Constant)):
                        fail(statement, "复杂或动态类型注解需要人工处理")
                    name, value = statement.target.id, statement.value
                else:
                    fail(statement, "UI 类仅支持静态定位项赋值，文件保持原样")
                key = f"{node.name}.{name}"
                if key in expressions:
                    fail(statement, "定位项重复赋值")
                expressions[key] = (group, name, value)
        elif not docstring(node):
            fail(node, "存在无法转换的模块级代码，文件保持原样")
    if not groups:
        raise StudioError(f"{filename}:1: 未找到静态 UI 类")

    def literal(node):
        try:
            return ast.literal_eval(node)
        except (ValueError, TypeError, SyntaxError) as exc:
            fail(node, "参数不是静态字面量，不能安全转换")

    def constructor(node):
        name = ast.unparse(node)
        if name in aliases:
            return aliases[name]
        for prefix in namespaces:
            if name.startswith(prefix + ".") and name[len(prefix) + 1:] in CALLS:
                return name[len(prefix) + 1:]
        fail(node, f"不支持的识别构造：{name}")

    def inline_native(value, group, node):
        if not isinstance(value, dict) or not isinstance(value.get("recognition"), dict):
            fail(node, "组合成员必须使用 recognition: {type, param} 格式的内联识别")
        recognition = value["recognition"]
        if set(value) != {"recognition"} or set(recognition) - {"type", "param"}:
            fail(node, "内联组合包含无法保留的字段，需要人工处理")
        if not isinstance(recognition.get("param", {}), dict):
            fail(node, "内联识别 param 必须为参数字典")
        kind = recognition.get("type")
        if not isinstance(kind, str) or kind not in KINDS:
            fail(node, "不支持的内联识别类型")
        key = uuid.uuid4().hex
        add_locator(kind, recognition.get("param", {}), group, "_inline_" + key[:10], key, False, node)
        return key

    def add_locator(kind, parameters, group, name, key, export, node):
        params = dict(parameters)
        children = []
        if kind in {"And", "Or"}:
            values = params.pop("all_of" if kind == "And" else "any_of", [])
            if not isinstance(values, (list, tuple)):
                fail(node, "组合成员必须是静态列表")
            children = [inline_native(value, group, node) for value in values]
        try:
            item = Locator(id=key, group_id=group.id, name=name, kind=kind, params=params, children=children, export=export)
            if kind not in {"And", "Or"}:
                native_params(item)
            items.append(item)
        except ValueError as exc:
            fail(node, str(exc))

    for group, name, value in expressions.values():
        if not isinstance(value, ast.Call):
            fail(value, "定位项必须是静态识别构造调用")
        kind = CALLS[constructor(value.func)]
        if value.args:
            fail(value, "原生识别构造请使用具名参数")
        if any(kw.arg is None for kw in value.keywords):
            fail(value, "不支持 **kwargs 展开")
        params = {kw.arg: literal(kw.value) for kw in value.keywords}
        add_locator(kind, params, group, name, uuid.uuid4().hex, True, value)
    try:
        Project(groups=groups, locators=items)
    except ValueError as exc:
        raise StudioError(f"{filename}:1: {exc}") from exc
    return groups, items
