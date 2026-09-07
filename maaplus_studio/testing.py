"""Explicit positive/negative assertions and reproducible visual reports."""
from __future__ import annotations

import html
import json
import uuid
from datetime import datetime, timezone

from PIL import ImageDraw

from .project import Project, atomic_write, png


def iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    intersection = max(0, min(ax + aw, bx + bw) - max(ax, bx)) * max(0, min(ay + ah, by + bh) - max(ay, by))
    union = aw * ah + bw * bh - intersection
    return intersection / union if union > 0 else 0.0


def evaluate(result: dict, expected: dict):
    if result.get("error"):
        return "error"
    if type(result.get("hit")) is not bool:
        return "error"
    if result["hit"] != expected["hit"]:
        return "failed"
    box = expected.get("box")
    if expected["hit"] and box is not None:
        if result.get("box") is None or iou(result["box"], box) < expected.get("min_iou", 0.5):
            return "failed"
    return "passed"


def overlay(image, results, expectations=None):
    result = image.convert("RGB").copy()
    draw = ImageDraw.Draw(result)
    for entry in results:
        box = entry.get("box")
        if box:
            x, y, w, h = box
            draw.rectangle((x, y, x + w - 1, y + h - 1), outline="#21b86b", width=3)
            draw.text((x + 3, max(0, y - 14)), entry.get("name", "match"), fill="#21b86b")
    for eid, expectation in (expectations or {}).items():
        if expectation.get("box"):
            x, y, w, h = expectation["box"]
            draw.rectangle((x, y, x + w - 1, y + h - 1), outline="#f7a929", width=2)
    return result


def run_suite(project: Project, recognize, report_dir=".debug/studio-report", cancelled=lambda: False):
    project.check_generated()
    assertions = sum(len(c["expect"]) for c in project.data["cases"])
    if not assertions:
        raise ValueError("No labelled test cases. Add positive/negative expectations; unlabelled screenshots are not passes.")
    run_id = uuid.uuid4().hex
    report = {"run_id": run_id, "artifacts": f"runs/{run_id}", "created_at": datetime.now(timezone.utc).isoformat(), "project_revision": project.revision,
              "engine": "MaaPlus Runtime.match / MaaFramework", "passed": 0, "failed": 0, "error": 0, "cases": []}
    output = project.path(report_dir)
    if any(output.is_relative_to(project.path(project.data[k])) or project.path(project.data[k]).is_relative_to(output)
           for k in ("ui_dir", "resource_dir", "fixtures_dir")):
        raise ValueError("Reports must not overlap UI, resources or fixtures")
    rows = []
    for case in project.data["cases"]:
        if cancelled():
            raise InterruptedError("Test run cancelled; any previous report remains unchanged")
        if not case["expect"]:
            continue
        try:
            results = recognize(case["page"], case["screenshot"])
        except Exception as exc:
            results = [{"element": eid, "error": str(exc)} for eid in case["expect"]]
        by_id = {r["element"]: r for r in results}
        checks = []
        for eid, expectation in case["expect"].items():
            actual = by_id.get(eid, {"error": "Engine returned no result for this element"})
            status = evaluate(actual, expectation)
            report[status] += 1
            checks.append({"element": eid, "name": project.element(case["page"], eid)["name"],
                           "status": status, "expected": expectation, "actual": actual})
        record = {"id": case["id"], "page": project.page(case["page"])["name"],
                  "screenshot": case["screenshot"], "checks": checks}
        report["cases"].append(record)
        try:
            annotated = overlay(project.image(case["screenshot"]), results, case["expect"])
            atomic_write(output / "runs" / run_id / f"{case['id']}.png", png(annotated))
        except (OSError, ValueError) as exc:
            record["image_error"] = str(exc)
        detail = html.escape(json.dumps(record, ensure_ascii=False, indent=2))
        rows.append(f"<section><h2>{html.escape(record['page'])}</h2><img src='runs/{run_id}/{case['id']}.png'><pre>{detail}</pre></section>")
    report["warnings"] = project.audit()["warnings"]
    atomic_write(output / "report.json", (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    page = ("<!doctype html><meta charset='utf-8'><title>MaaPlus UI Studio report</title>"
            "<style>body{font:16px system-ui;margin:32px;max-width:1280px}img{max-width:100%}"
            "pre{white-space:pre-wrap;background:#eee;padding:16px}section{margin:32px 0}</style>"
            f"<h1>UI regression · {report['passed']} passed / {report['failed']} failed / {report['error']} errors</h1>"
            "<p>Green: actual match; amber: expected box. Unlabelled elements are not assertions.</p>" + "".join(rows))
    atomic_write(output / "index.html", page.encode())
    return report
