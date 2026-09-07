#!/usr/bin/env python3
"""Validate the pinned GTFS tables without third-party dependencies."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GTFS = ROOT / "data" / "raw" / "gtfs"
DEFAULT_OUTPUT = ROOT / "qa" / "gtfs-validation.json"

GTFS_COLUMNS = {
    "agency.txt": ("agency_id", "agency_name", "agency_url", "agency_timezone"),
    "routes.txt": ("route_id", "agency_id", "route_short_name", "route_long_name", "route_type"),
    "trips.txt": ("route_id", "service_id", "trip_id", "trip_short_name"),
    "stops.txt": ("stop_id", "stop_name", "stop_lat", "stop_lon"),
    "stop_times.txt": ("trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"),
    "calendar.txt": (
        "service_id",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "start_date",
        "end_date",
    ),
    "calendar_dates.txt": ("service_id", "date", "exception_type"),
}
KEY_COLUMNS = {
    "agency.txt": "agency_id",
    "routes.txt": "route_id",
    "trips.txt": "trip_id",
    "stops.txt": "stop_id",
    "calendar.txt": "service_id",
}


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y%m%d").date()


def parse_time(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError("expected HH:MM:SS")
    hour, minute, second = (int(part) for part in parts)
    if hour < 0 or minute not in range(60) or second not in range(60):
        raise ValueError("invalid time component")
    return hour * 3600 + minute * 60 + second


def read_table(path: Path, name: str, errors: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        errors.append(f"missing required file: {name}")
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            missing = [field for field in GTFS_COLUMNS[name] if field not in fields]
            if missing:
                errors.append(f"{name}: missing columns {', '.join(missing)}")
            rows = []
            for line_number, row in enumerate(reader, start=2):
                if None in row:
                    errors.append(f"{name}:{line_number}: too many CSV fields")
                rows.append({key: (value or "") for key, value in row.items() if key is not None})
            return rows
    except UnicodeDecodeError as exc:
        errors.append(f"{name}: not valid UTF-8 ({exc})")
    except csv.Error as exc:
        errors.append(f"{name}: invalid CSV ({exc})")
    return []


def duplicate_keys(rows: list[dict[str, str]], key: str) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for row in rows:
        value = row.get(key, "")
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def run(gtfs_dir: Path = DEFAULT_GTFS) -> dict[str, Any]:
    errors: list[str] = []
    tables = {
        name: read_table(gtfs_dir / name, name, errors) for name in GTFS_COLUMNS
    }
    counts = {name.removesuffix(".txt"): len(rows) for name, rows in tables.items()}

    for name, key in KEY_COLUMNS.items():
        duplicates = duplicate_keys(tables[name], key)
        if duplicates:
            errors.append(f"{name}: duplicate {key} values: {', '.join(duplicates[:10])}")
        if any(not row.get(key, "").strip() for row in tables[name]):
            errors.append(f"{name}: blank {key} value")

    agencies = {row.get("agency_id", "") for row in tables["agency.txt"]}
    routes = {row.get("route_id", "") for row in tables["routes.txt"]}
    trips = {row.get("trip_id", "") for row in tables["trips.txt"]}
    stops = {row.get("stop_id", "") for row in tables["stops.txt"]}
    calendar = {row.get("service_id", "") for row in tables["calendar.txt"]}
    exception_services = {row.get("service_id", "") for row in tables["calendar_dates.txt"]}
    known_services = calendar | exception_services

    for row in tables["routes.txt"]:
        if row.get("agency_id") not in agencies:
            errors.append(f"routes.txt: unknown agency_id {row.get('agency_id')}")
        try:
            int(row.get("route_type", ""))
        except ValueError:
            errors.append(f"routes.txt: non-numeric route_type {row.get('route_type')}")
    for row in tables["trips.txt"]:
        if row.get("route_id") not in routes:
            errors.append(f"trips.txt: unknown route_id {row.get('route_id')}")
        if row.get("service_id") not in known_services:
            errors.append(f"trips.txt: unknown service_id {row.get('service_id')}")

    stop_times_by_trip: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    station_calls: defaultdict[str, int] = defaultdict(int)
    for row in tables["stop_times.txt"]:
        trip_id = row.get("trip_id", "")
        stop_id = row.get("stop_id", "")
        if trip_id not in trips:
            errors.append(f"stop_times.txt: unknown trip_id {trip_id}")
        if stop_id not in stops:
            errors.append(f"stop_times.txt: unknown stop_id {stop_id}")
        stop_times_by_trip[trip_id].append(row)
        station_calls[stop_id] += 1

    overnight_rollovers = 0
    boundary_time_fallbacks = 0
    for trip_id, rows in stop_times_by_trip.items():
        previous_sequence = -1
        previous_time: int | None = None
        seen_sequences: set[int] = set()
        for row_index, row in enumerate(rows):
            try:
                sequence = int(row.get("stop_sequence", ""))
                if sequence <= 0:
                    raise ValueError("must be positive")
            except ValueError as exc:
                errors.append(f"stop_times.txt/{trip_id}: invalid stop_sequence ({exc})")
                continue
            if sequence in seen_sequences:
                errors.append(f"stop_times.txt/{trip_id}: duplicate stop_sequence {sequence}")
            if sequence <= previous_sequence:
                errors.append(f"stop_times.txt/{trip_id}: stop_sequence is not increasing")
            seen_sequences.add(sequence)
            previous_sequence = sequence
            arrival_raw = row.get("arrival_time", "").strip()
            departure_raw = row.get("departure_time", "").strip()
            if not arrival_raw and not departure_raw:
                errors.append(f"stop_times.txt/{trip_id}/{sequence}: both times are blank")
                continue
            try:
                if arrival_raw:
                    arrival = parse_time(arrival_raw)
                else:
                    if row_index != 0:
                        errors.append(f"stop_times.txt/{trip_id}/{sequence}: arrival is blank away from trip boundary")
                    arrival = parse_time(departure_raw)
                    boundary_time_fallbacks += 1
                if departure_raw:
                    departure = parse_time(departure_raw)
                else:
                    if row_index != len(rows) - 1:
                        errors.append(f"stop_times.txt/{trip_id}/{sequence}: departure is blank away from trip boundary")
                    departure = parse_time(arrival_raw)
                    boundary_time_fallbacks += 1
            except (TypeError, ValueError) as exc:
                errors.append(f"stop_times.txt/{trip_id}/{sequence}: invalid time ({exc})")
                continue
            while previous_time is not None and arrival < previous_time:
                arrival += 24 * 60 * 60
                departure += 24 * 60 * 60
                overnight_rollovers += 1
            if arrival > departure:
                errors.append(f"stop_times.txt/{trip_id}/{sequence}: arrival after departure")
            if previous_time is not None and arrival < previous_time:
                errors.append(f"stop_times.txt/{trip_id}/{sequence}: time moves backwards")
            previous_time = max(arrival, departure)

    coordinate_count = 0
    for row in tables["stops.txt"]:
        try:
            latitude = float(row.get("stop_lat", ""))
            longitude = float(row.get("stop_lon", ""))
        except ValueError as exc:
            errors.append(f"stops.txt/{row.get('stop_id')}: invalid coordinate ({exc})")
            continue
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            errors.append(f"stops.txt/{row.get('stop_id')}: coordinate outside WGS84 bounds")
        if not 43.5 <= latitude <= 48.5 or not 20 <= longitude <= 30:
            errors.append(f"stops.txt/{row.get('stop_id')}: coordinate outside Romania check bounds")
        coordinate_count += 1

    calendar_start: dt.date | None = None
    calendar_end: dt.date | None = None
    for row in tables["calendar.txt"]:
        for field in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
            if row.get(field) not in {"0", "1"}:
                errors.append(f"calendar.txt/{row.get('service_id')}: {field} must be 0 or 1")
        try:
            start = parse_date(row.get("start_date", ""))
            end = parse_date(row.get("end_date", ""))
            if start > end:
                errors.append(f"calendar.txt/{row.get('service_id')}: start_date after end_date")
            calendar_start = start if calendar_start is None else min(calendar_start, start)
            calendar_end = end if calendar_end is None else max(calendar_end, end)
        except ValueError as exc:
            errors.append(f"calendar.txt/{row.get('service_id')}: invalid date ({exc})")
    exception_pairs: set[tuple[str, str]] = set()
    for row in tables["calendar_dates.txt"]:
        pair = (row.get("service_id", ""), row.get("date", ""))
        if pair in exception_pairs:
            errors.append(f"calendar_dates.txt: duplicate service/date {pair[0]} {pair[1]}")
        exception_pairs.add(pair)
        if row.get("exception_type") not in {"1", "2"}:
            errors.append(f"calendar_dates.txt/{pair[0]}: exception_type must be 1 or 2")
        if pair[0] not in known_services:
            errors.append(f"calendar_dates.txt: unknown service_id {pair[0]}")
        try:
            parse_date(pair[1])
        except ValueError as exc:
            errors.append(f"calendar_dates.txt/{pair[0]}: invalid date ({exc})")

    route_type_counts: defaultdict[str, int] = defaultdict(int)
    route_by_id = {row.get("route_id"): row for row in tables["routes.txt"]}
    for row in tables["trips.txt"]:
        route_type_counts[route_by_id.get(row.get("route_id"), {}).get("route_type", "unknown")] += 1

    checks = {
        "required_files_and_columns": "pass" if not any("missing" in error for error in errors) else "fail",
        "unique_keys": "pass" if not any("duplicate" in error or "blank" in error for error in errors) else "fail",
        "referential_integrity": "pass" if not any("unknown" in error for error in errors) else "fail",
        "times_and_sequences": "pass" if not any("stop_times.txt" in error for error in errors) else "fail",
        "coordinates": "pass" if coordinate_count == len(tables["stops.txt"]) and not any("stops.txt" in error for error in errors) else "fail",
        "calendar": "pass" if not any("calendar" in error for error in errors) else "fail",
    }
    report = {
        "status": "pass" if not errors else "fail",
        "gtfs_directory": str(gtfs_dir.relative_to(ROOT)) if gtfs_dir.is_relative_to(ROOT) else str(gtfs_dir),
        "counts": counts,
        "coordinate_coverage": {
            "with_coordinates": coordinate_count,
            "percent": round(100 * coordinate_count / len(tables["stops.txt"]), 2) if tables["stops.txt"] else 0,
        },
        "route_type_trip_counts": dict(sorted(route_type_counts.items())),
        "overnight_rollovers_normalized": overnight_rollovers,
        "boundary_time_fallbacks": boundary_time_fallbacks,
        "valid_date_range": [
            calendar_start.isoformat() if calendar_start else None,
            calendar_end.isoformat() if calendar_end else None,
        ],
        "checks": checks,
        "errors": errors,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gtfs-dir", type=Path, default=DEFAULT_GTFS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.gtfs_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
