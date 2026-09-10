"""Small, dependency-light command line tools for MaaPlus projects."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from .dev import Inspector, FixtureSet, run_doctor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="maaplus")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create a runnable offline MaaPlus project")
    init.add_argument("directory", nargs="?", default=".")
    init.add_argument("--force", action="store_true")

    inspect = subparsers.add_parser("inspect", help="inspect fixtures with one project locator")
    inspect.add_argument("fixtures", type=Path)
    inspect.add_argument("--locator", required=True, help="module:attribute locator reference")
    inspect.add_argument(
        "--factory",
        default="offline:create_inspector",
        help="module:callable returning Inspector or Tasker (default: offline:create_inspector)",
    )
    inspect.add_argument("--box-tolerance", type=int, default=0)
    inspect.add_argument("--json", dest="json_path", type=Path)

    doctor = subparsers.add_parser("doctor", help="run read-only MaaPlus environment checks")
    doctor.add_argument("--resource", type=Path)

    trace = subparsers.add_parser("trace", help="summarize one isolated trace session")
    trace.add_argument("session", type=Path)

    ui = subparsers.add_parser("ui", help="launch interactive UI Workbench in browser")
    ui.add_argument("--host", default="127.0.0.1", help="host address (default: 127.0.0.1)")
    ui.add_argument("--port", type=int, default=8080, help="port number (default: 8080)")
    ui.add_argument("--no-browser", action="store_true", help="do not open browser automatically")

    args = parser.parse_args(argv)
    if args.command == "init":
        return _init(Path(args.directory), force=args.force)
    if args.command == "inspect":
        return _inspect(args)
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "trace":
        return _trace(args)
    if args.command == "ui":
        return _ui(args)
    return 2


def _inspect(args: argparse.Namespace) -> int:
    try:
        locator = _load_reference(args.locator)
        factory = _load_reference(args.factory)
        value = factory() if callable(factory) else factory
        inspector = value if isinstance(value, Inspector) else Inspector(value)
        results = inspector.inspect_set(
            locator,
            FixtureSet(args.fixtures),
            box_tolerance=args.box_tolerance,
        )
    except Exception as exc:
        print(f"inspect: {type(exc).__name__}: {exc}")
        return 2

    payload = []
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(f"{status} {item.fixture.path}")
        for error in item.errors:
            print(f"  {error}")
        if item.error is not None:
            print(f"  {item.error}")
        payload.append(
            {
                "path": str(item.fixture.path),
                "passed": item.passed,
                "errors": list(item.errors),
                "error": str(item.error) if item.error else None,
                "hit": item.result.hit if item.result else None,
                "box": item.result.box if item.result else None,
                "annotated_path": item.result.annotated_path if item.result else None,
            }
        )
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return 0 if all(item["passed"] for item in payload) else 1


def _doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(resource_dir=args.resource)
    failed = False
    for check in checks:
        marker = "OK" if check.ok else ("WARN" if check.optional else "FAIL")
        print(f"{marker:4} {check.name}: {check.detail}")
        failed = failed or (not check.ok and not check.optional)
    return 0 if not failed else 1


def _trace(args: argparse.Namespace) -> int:
    session = args.session
    trace_path = session / "run.jsonl" if session.is_dir() else session
    if not trace_path.is_file():
        print(f"trace: file not found: {trace_path}")
        return 2
    events = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    run_id = events[0].get("run_id") if events else None
    failures = list((session / "failures").glob("*/summary.md")) if session.is_dir() else []
    images = list((session / "images").glob("*.png")) if session.is_dir() else []
    print(f"run_id: {run_id or '<none>'}")
    print(f"trace: {trace_path}")
    print(f"events: {len(events)}")
    print(f"images: {len(images)}")
    print(f"failure_reports: {len(failures)}")
    return 0


def _ui(args: argparse.Namespace) -> int:
    import importlib.util
    tools_script = Path(__file__).resolve().parent.parent / "tools" / "ui_workbench.py"
    if not tools_script.exists():
        print(f"ui: {tools_script} not found")
        return 2
    spec = importlib.util.spec_from_file_location("ui_workbench", tools_script)
    if spec is None or spec.loader is None:
        print(f"ui: failed to load module spec for {tools_script}")
        return 2
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ui_workbench"] = mod
    spec.loader.exec_module(mod)
    mod.run_server(
        host=args.host,
        port=args.port,
        project_root=Path.cwd(),
        open_browser=not args.no_browser,
    )
    return 0


def _load_reference(reference: str) -> Any:
    try:
        module_name, attribute = reference.split(":", 1)
    except ValueError as exc:
        raise ValueError(f"reference must use module:attribute syntax: {reference!r}") from exc
    value: Any = importlib.import_module(module_name)
    for part in attribute.split("."):
        value = getattr(value, part)
    return value


def _init(directory: Path, *, force: bool) -> int:
    files = {
        "pyproject.toml": """[project]\nname = \"my-maaplus-game\"\nversion = \"0.1.0\"\nrequires-python = \">=3.10\"\ndependencies = [\n    \"maaplus[dev]\",\n]\n\n[project.scripts]\ninspect-fixtures = \"main:main\"\n""",
        "main.py": """from pathlib import Path\n\nfrom ui import UI\nfrom offline import create_inspector\n\n\ndef main() -> int:\n    fixtures = Path(__file__).parent / \"fixtures\"\n    results = create_inspector().inspect_set(UI.READY, fixtures)\n    for result in results:\n        print(\"PASS\" if result.passed else \"FAIL\", result.fixture.path)\n    return 0 if all(result.passed for result in results) else 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n""",
        "bootstrap.py": """# Add live MaaFramework Tasker/Controller/Resource setup here.\n# Keep the offline path in offline.py so fixture tests never touch a device.\n""",
        "offline.py": """from types import SimpleNamespace\n\nimport numpy\n\nfrom maaplus.dev import Inspector\n\n\nclass FixtureTasker:\n    def post_recognition(self, reco_type, locator, image):\n        height, width = image.shape[:2]\n        hit = bool(image.max())\n        detail = SimpleNamespace(\n            hit=hit,\n            box=(0, 0, width, height) if hit else None,\n            raw_detail={\"fixture_demo\": True},\n        )\n        job = SimpleNamespace(\n            succeeded=True,\n            wait=lambda: job,\n            get=lambda: SimpleNamespace(nodes=[SimpleNamespace(recognition=detail)]),\n        )\n        return job\n\n\ndef create_inspector() -> Inspector:\n    return Inspector(FixtureTasker(), output_dir=\".maaplus/inspect\")\n""",
        "ui.py": """from maaplus import Template\n\n\nclass UI:\n    READY = Template(template=[\"ready.png\"])\n""",
        "fixtures/README.md": """# Recognition fixtures\n\nPut BGR-compatible screenshots here. A non-empty screenshot is a hit in the dry-run tasker.\nAdd `expected.json` to assert `hit` and an optional `box`.\n""",
        "fixtures/expected.json": "{}\n",
        "tests/test_smoke.py": """def test_project_imports():\n    import ui\n    import offline\n\n    assert ui.UI.READY\n    assert offline.create_inspector()\n""",
        "README.md": """# MaaPlus project\n\nInstall with `uv sync`, put a screenshot in `fixtures/`, then run:\n\n```bash\nuv run python main.py\nmaaplus inspect fixtures --locator ui:UI.READY --factory offline:create_inspector\nmaaplus doctor\n```\n\n`bootstrap.py` is reserved for the live MaaFramework connection. The generated offline path never\nsends controller input.\n""",
    }
    directory.mkdir(parents=True, exist_ok=True)
    existing = [directory / path for path in files if (directory / path).exists()]
    if existing and not force:
        raise SystemExit(f"Refusing to overwrite existing files: {', '.join(map(str, existing))}")
    for relative, content in files.items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"Created MaaPlus project in {directory.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
