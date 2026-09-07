#!/usr/bin/env python3
"""Structural and calendar validation for the generated corridor atlas."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "data" / "derived" / "atlas" / "atlas.json"
ATLAS_JS = ROOT / "data" / "derived" / "atlas" / "atlas.js"
RAW = ROOT / "data" / "raw" / "gtfs"
OUTPUTS = ROOT / "qa"


def read_csv_count(name: str) -> int:
    with (RAW / name).open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def previous_day(value: str) -> str:
    date = dt.date.fromisoformat(value) - dt.timedelta(days=1)
    return date.isoformat()


def service_active(service: dict[str, Any], value: str) -> bool:
    additions = set(service.get("add", []))
    removals = set(service.get("remove", []))
    if value in additions:
        return True
    if value in removals:
        return False
    if not service["start"] <= value <= service["end"]:
        return False
    return service["week"][dt.date.fromisoformat(value).weekday()] == "1"


def daily_count(payload: dict[str, Any], corridor: dict[str, Any], value: str) -> int:
    total = 0
    for service_date, shift in ((value, 0), (previous_day(value), -1440)):
        for train in corridor["trains"]:
            service = payload["services"][train["service"]]
            if not service_active(service, service_date):
                continue
            if train["end"] + shift < 0 or train["start"] + shift > 1440:
                continue
            total += 1
    return total


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    payload = json.loads(ATLAS.read_text(encoding="utf-8"))
    meta = payload["meta"]

    # Source/file consistency.
    expected_counts = {
        "stops.txt": meta["stopCount"],
        "trips.txt": meta["tripDefinitionCount"],
    }
    for filename, expected in expected_counts.items():
        actual = read_csv_count(filename)
        if actual != expected:
            fail(errors, f"{filename}: {actual} rows, metadata says {expected}")

    js_text = ATLAS_JS.read_text(encoding="utf-8")
    prefix = "window.ATLAS_DATA="
    if not js_text.startswith(prefix) or not js_text.rstrip().endswith(";"):
        fail(errors, "atlas.js wrapper is malformed")
    else:
        wrapped = js_text[len(prefix):].strip()
        wrapped = wrapped[:-1] if wrapped.endswith(";") else wrapped
        try:
            if json.loads(wrapped) != payload:
                fail(errors, "atlas.js and atlas.json contain different payloads")
        except json.JSONDecodeError as exc:
            fail(errors, f"atlas.js payload is invalid JSON: {exc}")

    if not meta["validFrom"] <= meta["defaultDate"] <= meta["validTo"]:
        fail(errors, "default date lies outside timetable validity")
    if meta["corridorCount"] != len(payload["corridors"]):
        fail(errors, "corridor count metadata mismatch")
    if meta["operatorCount"] != len(payload["operators"]):
        fail(errors, "operator count metadata mismatch")

    corridor_ids: set[str] = set()
    total_train_segments = 0
    max_gap = {"corridor": None, "km": -math.inf}
    category_counts: Counter[str] = Counter()
    operator_counts: Counter[str] = Counter()
    summaries: list[dict[str, Any]] = []

    for corridor in payload["corridors"]:
        cid = corridor["id"]
        if cid in corridor_ids:
            fail(errors, f"duplicate corridor id {cid}")
        corridor_ids.add(cid)
        stations = corridor["stations"]
        trains = corridor["trains"]
        total_train_segments += len(trains)
        if len(stations) != corridor["stationCount"]:
            fail(errors, f"{cid}: stationCount mismatch")
        if len(trains) != corridor["trainDefinitionCount"]:
            fail(errors, f"{cid}: trainDefinitionCount mismatch")
        if len(stations) < 2:
            fail(errors, f"{cid}: fewer than two stations")
            continue
        kms = [station["km"] for station in stations]
        if abs(kms[0]) > 1e-6:
            fail(errors, f"{cid}: first station is not at km 0")
        if any(b <= a for a, b in zip(kms, kms[1:])):
            fail(errors, f"{cid}: station kilometre positions are not strictly increasing")
        if abs(kms[-1] - corridor["distanceKm"]) > 0.15:
            fail(errors, f"{cid}: end distance mismatch")
        calculated_gap = max(b - a for a, b in zip(kms, kms[1:]))
        if abs(calculated_gap - corridor["maxStationGapKm"]) > 0.15:
            fail(errors, f"{cid}: max station gap mismatch")
        if calculated_gap > max_gap["km"]:
            max_gap = {"corridor": cid, "km": calculated_gap}

        station_names = {station["name"] for station in stations}
        for train in trains:
            category_counts[train["category"]] += 1
            operator_counts[train["operatorId"]] += 1
            if train["category"] not in payload["categories"]:
                fail(errors, f"{cid}/{train['id']}: unknown category {train['category']}")
            if train["operatorId"] not in payload["operators"]:
                fail(errors, f"{cid}/{train['id']}: unknown operator")
            if train["service"] not in payload["services"]:
                fail(errors, f"{cid}/{train['id']}: unknown service calendar")
            points = train["points"]
            if len(points) < 2:
                fail(errors, f"{cid}/{train['id']}: fewer than two path points")
                continue
            times = [point["t"] for point in points]
            if any(b < a for a, b in zip(times, times[1:])):
                fail(errors, f"{cid}/{train['id']}: non-monotonic times")
            if abs(times[0] - train["start"]) > 0.01 or abs(times[-1] - train["end"]) > 0.01:
                fail(errors, f"{cid}/{train['id']}: start/end mismatch")
            if any(point["km"] < -0.01 or point["km"] > corridor["distanceKm"] + 0.01 for point in points):
                fail(errors, f"{cid}/{train['id']}: point outside corridor extent")
            if train["duration"] <= 0:
                fail(errors, f"{cid}/{train['id']}: non-positive duration")
            if not train["stops"]:
                fail(errors, f"{cid}/{train['id']}: no calling points")
            elif any(stop["name"] not in station_names for stop in train["stops"]):
                fail(errors, f"{cid}/{train['id']}: stop not present on corridor axis")

        summaries.append({
            "id": cid,
            "corridor_ro": corridor["label_ro"],
            "corridor_en": corridor["label_en"],
            "approx_distance_km": corridor["distanceKm"],
            "axis_points": corridor["stationCount"],
            "timetable_definitions": corridor["trainDefinitionCount"],
            "movements_on_default_date": daily_count(payload, corridor, meta["defaultDate"]),
            "max_gap_between_published_calling_points_km": corridor["maxStationGapKm"],
        })

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    with (OUTPUTS / "corridor-summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summaries)

    report = {
        "validated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "atlas_sha256": hashlib.sha256(ATLAS.read_bytes()).hexdigest(),
        "validity": [meta["validFrom"], meta["validTo"]],
        "default_date": meta["defaultDate"],
        "corridors": len(payload["corridors"]),
        "operators": len(payload["operators"]),
        "services": len(payload["services"]),
        "corridor_train_segments": total_train_segments,
        "category_segment_counts": dict(category_counts),
        "operator_segment_counts": dict(operator_counts),
        "largest_axis_gap": max_gap,
        "errors": errors,
        "status": "pass" if not errors else "fail",
    }
    (OUTPUTS / "atlas-validation-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        print(f"Validation failed with {len(errors)} error(s).", file=sys.stderr)
        return 1
    print(f"Validation passed. Wrote {OUTPUTS / 'corridor-summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
