"""Command-line entry point; GUI libraries and MaaFramework are loaded only when needed."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .project import Project


def main(argv=None):
    parser = argparse.ArgumentParser(prog="maaplus-studio", description="MaaPlus UI authoring and regression workbench")
    parser.add_argument("--project", "-p", type=Path, default=Path.cwd(), help="Project root directory")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="Open the desktop workbench (default)")
    init = commands.add_parser("init", help="Initialize metadata without overwriting existing Python")
    init.add_argument("--ui", default="ui/generated")
    init.add_argument("--resource", default="resource")
    init.add_argument("--fixtures", default="tests/ui")
    init.add_argument("--width", type=int, default=1280)
    init.add_argument("--height", type=int, default=720)
    commands.add_parser("demo", help="Create a self-contained synthetic screenshot project")
    commands.add_parser("generate", help="Generate guarded Python modules")
    check = commands.add_parser("check", help="Check references, integrity, code freshness and test coverage")
    check.add_argument("--strict", action="store_true", help="Return failure for warnings as well as errors")
    test = commands.add_parser("test", help="Run annotated screenshots through MaaPlus Runtime.match")
    test.add_argument("--report", default=".debug/studio-report")
    test.add_argument("--timeout", type=float, default=90, help="Per native request timeout in seconds")
    args = parser.parse_args(argv)
    try:
        if args.command in (None, "gui"):
            from .gui import launch
            project = Project.open(args.project) if (args.project / "maaplus-studio.json").exists() else None
            launch(project)
        elif args.command == "init":
            Project.create(args.project, ui=args.ui, resource=args.resource, fixtures=args.fixtures, size=(args.width, args.height))
            print(args.project / "maaplus-studio.json")
        elif args.command == "demo":
            from .demo import create_demo
            create_demo(args.project)
            print(f"Demo created: {args.project}")
        elif args.command == "generate":
            print("\n".join(Project.open(args.project).generate()))
        elif args.command == "check":
            result = Project.open(args.project).audit()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return int(bool(result["errors"] or (args.strict and result["warnings"])))
        elif args.command == "test":
            from .engine import WorkerClient
            from .testing import run_suite
            if args.timeout <= 0:
                raise ValueError("Timeout must be positive")
            project = Project.open(args.project)
            with WorkerClient(timeout=args.timeout) as worker:
                def recognize(page_id, shot_id):
                    if Project.open(project.root).revision != project.revision:
                        raise RuntimeError("Project changed during the run; rerun against one revision")
                    return worker.request("recognize", root=str(project.root), page_id=page_id, shot_id=shot_id)
                report = run_suite(project, recognize, args.report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return int(bool(report["failed"] or report["error"]))
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"UI Studio: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
