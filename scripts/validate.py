#!/usr/bin/env python3
"""Run every repository validator and write one release-level QA report."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "qa"
CHECKS = (
    ("release", "validate_release.py", "release-validation.json"),
    ("gtfs", "validate_gtfs.py", "gtfs-validation.json"),
    ("sqlite", "validate_sqlite.py", "sqlite-validation.json"),
    ("geojson", "validate_geojson.py", "geojson-validation.json"),
    ("atlas", "validate_atlas.py", "atlas-validation-report.json"),
)


def main() -> int:
    QA.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    for name, script, report_name in CHECKS:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        report_path = QA / report_name
        if report_path.exists():
            try:
                detail = json.loads(report_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                detail = {"status": "fail", "errors": [f"invalid validator report: {exc}"]}
        else:
            detail = {"status": "fail", "errors": [f"validator did not write {report_name}"]}
        results[name] = {
            "status": detail.get("status", "fail"),
            "report": f"qa/{report_name}",
            "returncode": completed.returncode,
            "detail": detail,
        }
        if completed.stdout.strip():
            print(f"[{name}] {completed.stdout.strip()}")
        if completed.stderr.strip():
            print(f"[{name}:stderr] {completed.stderr.strip()}", file=sys.stderr)

    failed = [name for name, result in results.items() if result["status"] != "pass" or result["returncode"] != 0]
    report = {
        "schema_version": 1,
        "status": "pass" if not failed else "fail",
        "checks": results,
        "failed_checks": failed,
    }
    (QA / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": report["status"], "failed_checks": failed}, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
