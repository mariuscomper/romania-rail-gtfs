#!/usr/bin/env python3
"""Validate the station GeoJSON against stops and stop_times."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "data" / "raw" / "gtfs"
GEOJSON = ROOT / "data" / "derived" / "stations.geojson"
DEFAULT_OUTPUT = ROOT / "qa" / "geojson-validation.json"


def read(name: str) -> list[dict[str, str]]:
    with (GTFS / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def run() -> dict[str, Any]:
    errors: list[str] = []
    if not GEOJSON.exists():
        return {"status": "fail", "errors": [f"missing GeoJSON: {GEOJSON}"]}
    try:
        document = json.loads(GEOJSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "fail", "errors": [f"invalid GeoJSON JSON: {exc}"]}

    stops = read("stops.txt")
    stop_times = read("stop_times.txt")
    routes = {row["route_id"]: row for row in read("routes.txt")}
    trips = {row["trip_id"]: row for row in read("trips.txt")}
    agencies = {row["agency_id"]: row["agency_name"] for row in read("agency.txt")}
    calls: Counter[str] = Counter(row["stop_id"] for row in stop_times)
    operator_sets: defaultdict[str, set[str]] = defaultdict(set)
    for row in stop_times:
        trip = trips[row["trip_id"]]
        route = routes[trip["route_id"]]
        operator_sets[row["stop_id"]].add(agencies[route["agency_id"]])

    if document.get("type") != "FeatureCollection":
        errors.append("top-level type is not FeatureCollection")
    features = document.get("features", [])
    if not isinstance(features, list):
        errors.append("features is not a list")
        features = []
    if len(features) != len(stops):
        errors.append(f"feature count {len(features)} differs from stops count {len(stops)}")

    feature_ids: set[str] = set()
    for feature in features:
        properties = feature.get("properties") or {}
        stop_id = properties.get("id")
        if stop_id in feature_ids:
            errors.append(f"duplicate feature id {stop_id}")
        feature_ids.add(stop_id)
        if feature.get("type") != "Feature" or (feature.get("geometry") or {}).get("type") != "Point":
            errors.append(f"feature {stop_id}: geometry is not Point")
            continue
        coordinates = (feature.get("geometry") or {}).get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) != 2:
            errors.append(f"feature {stop_id}: coordinates are not [lon, lat]")
            continue
        try:
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            errors.append(f"feature {stop_id}: coordinates are not numeric")
            continue
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            errors.append(f"feature {stop_id}: coordinate outside WGS84 bounds")
        expected_operators = sorted(operator_sets.get(stop_id, set()))
        if properties.get("name") is None or properties.get("name") == "":
            errors.append(f"feature {stop_id}: missing name")
        if properties.get("calls") != calls.get(stop_id, 0):
            errors.append(f"feature {stop_id}: calls does not match stop_times")
        if sorted(properties.get("operators", [])) != expected_operators:
            errors.append(f"feature {stop_id}: operators do not match GTFS joins")
        if properties.get("operator_count") != len(expected_operators):
            errors.append(f"feature {stop_id}: operator_count mismatch")

    expected_ids = {row["stop_id"] for row in stops}
    if feature_ids != expected_ids:
        errors.append("feature ids do not match stops.txt")
    return {
        "status": "pass" if not errors else "fail",
        "feature_count": len(features),
        "stop_count": len(stops),
        "geometry_types": sorted({(feature.get("geometry") or {}).get("type") for feature in features}),
        "operator_count_range": [
            min((len(operator_sets[row["stop_id"]]) for row in stops), default=0),
            max((len(operator_sets[row["stop_id"]]) for row in stops), default=0),
        ],
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
