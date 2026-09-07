#!/usr/bin/env python3
"""Validate the SQLite materialisation against the GTFS source counts."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "data" / "raw" / "gtfs"
DATABASE = ROOT / "data" / "derived" / "romania-rail.sqlite"
DEFAULT_OUTPUT = ROOT / "qa" / "sqlite-validation.json"
EXPECTED_TABLES = {"agencies", "routes", "trips", "stops", "stop_times", "calendar", "calendar_dates"}
EXPECTED_INDEXES = {
    "idx_stop_times_stop",
    "idx_stop_times_trip",
    "idx_trips_route",
    "idx_trips_service",
    "idx_routes_agency",
    "idx_calendar_dates_service",
}


def source_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for filename in ("agency", "routes", "trips", "stops", "stop_times", "calendar", "calendar_dates"):
        with (GTFS / f"{filename}.txt").open(encoding="utf-8-sig", newline="") as handle:
            counts[filename] = sum(1 for _ in csv.DictReader(handle))
    return counts


def run() -> dict[str, Any]:
    errors: list[str] = []
    if not DATABASE.exists():
        return {"status": "fail", "errors": [f"missing database: {DATABASE}"], "counts": {}}
    counts = source_counts()
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")
    foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_key_errors = [row for row in connection.execute("PRAGMA foreign_key_check")]
    if foreign_keys != 1:
        errors.append("foreign_keys pragma is not enabled for the validation connection")
    if integrity != "ok":
        errors.append(f"integrity_check returned {integrity}")
    if foreign_key_errors:
        errors.append(f"foreign_key_check returned {len(foreign_key_errors)} rows")

    tables = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if not row[0].startswith("sqlite_")
    }
    missing_tables = sorted(EXPECTED_TABLES - tables)
    extra_tables = sorted(tables - EXPECTED_TABLES)
    if missing_tables:
        errors.append(f"missing tables: {', '.join(missing_tables)}")
    actual_counts: dict[str, int] = {}
    table_map = {
        "agencies": "agency",
        "routes": "routes",
        "trips": "trips",
        "stops": "stops",
        "stop_times": "stop_times",
        "calendar": "calendar",
        "calendar_dates": "calendar_dates",
    }
    for table, source_name in table_map.items():
        if table not in tables:
            continue
        actual_counts[table] = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if actual_counts[table] != counts[source_name]:
            errors.append(f"{table}: {actual_counts[table]} rows, source has {counts[source_name]}")

    indexes = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        if not row[0].startswith("sqlite_")
    }
    missing_indexes = sorted(EXPECTED_INDEXES - indexes)
    if missing_indexes:
        errors.append(f"missing indexes: {', '.join(missing_indexes)}")
    joined_stop_times = connection.execute(
        """SELECT COUNT(*) FROM stop_times AS st
           JOIN trips AS t USING (trip_id)
           JOIN routes AS r USING (route_id)
           JOIN agencies AS a USING (agency_id)
           JOIN stops AS s USING (stop_id)"""
    ).fetchone()[0]
    if joined_stop_times != counts["stop_times"]:
        errors.append("the complete GTFS join does not preserve stop_times row count")
    connection.close()
    return {
        "status": "pass" if not errors else "fail",
        "counts": actual_counts,
        "source_counts": counts,
        "tables": sorted(tables),
        "extra_tables": extra_tables,
        "indexes": sorted(indexes),
        "joined_stop_times": joined_stop_times,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
