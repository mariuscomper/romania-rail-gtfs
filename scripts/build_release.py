#!/usr/bin/env python3
"""Build the standard GTFS, SQLite and GeoJSON release artifacts."""
from __future__ import annotations

import csv
import json
import shutil
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "gtfs"
DERIVED = ROOT / "data" / "derived"
GTFS_OUT = DERIVED / "gtfs"
SOURCE_PATH = ROOT / "data" / "source.json"

GTFS_FILES = (
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stops.txt",
    "stop_times.txt",
    "calendar.txt",
    "calendar_dates.txt",
)


def read_csv(name: str) -> list[dict[str, str]]:
    with (RAW / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def iso_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def build_gtfs_zip() -> None:
    """Copy the unpacked release and create a byte-stable zip archive."""
    GTFS_OUT.mkdir(parents=True, exist_ok=True)
    zip_path = DERIVED / "gtfs-romania-feroviar.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in GTFS_FILES:
            source = RAW / name
            shutil.copyfile(source, GTFS_OUT / name)
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())


def build_sqlite(tables: dict[str, list[dict[str, str]]]) -> None:
    path = DERIVED / "romania-rail.sqlite"
    if path.exists():
        path.unlink()

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE agencies (
            agency_id TEXT PRIMARY KEY,
            agency_name TEXT NOT NULL,
            agency_url TEXT,
            agency_timezone TEXT
        );
        CREATE TABLE routes (
            route_id TEXT PRIMARY KEY,
            agency_id TEXT NOT NULL,
            route_short_name TEXT,
            route_long_name TEXT,
            route_type TEXT NOT NULL,
            FOREIGN KEY (agency_id) REFERENCES agencies(agency_id)
        );
        CREATE TABLE trips (
            trip_id TEXT PRIMARY KEY,
            route_id TEXT NOT NULL,
            service_id TEXT NOT NULL,
            trip_short_name TEXT,
            FOREIGN KEY (route_id) REFERENCES routes(route_id)
        );
        CREATE TABLE stops (
            stop_id TEXT PRIMARY KEY,
            stop_name TEXT NOT NULL,
            stop_lat REAL,
            stop_lon REAL
        );
        CREATE TABLE stop_times (
            trip_id TEXT NOT NULL,
            arrival_time TEXT,
            departure_time TEXT,
            stop_id TEXT NOT NULL,
            stop_sequence INTEGER NOT NULL,
            FOREIGN KEY (trip_id) REFERENCES trips(trip_id),
            FOREIGN KEY (stop_id) REFERENCES stops(stop_id)
        );
        CREATE TABLE calendar (
            service_id TEXT PRIMARY KEY,
            monday INTEGER NOT NULL,
            tuesday INTEGER NOT NULL,
            wednesday INTEGER NOT NULL,
            thursday INTEGER NOT NULL,
            friday INTEGER NOT NULL,
            saturday INTEGER NOT NULL,
            sunday INTEGER NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL
        );
        CREATE TABLE calendar_dates (
            service_id TEXT NOT NULL,
            date TEXT NOT NULL,
            exception_type INTEGER NOT NULL
        );
        CREATE INDEX idx_stop_times_stop ON stop_times(stop_id);
        CREATE INDEX idx_stop_times_trip ON stop_times(trip_id);
        CREATE INDEX idx_trips_route ON trips(route_id);
        CREATE INDEX idx_trips_service ON trips(service_id);
        CREATE INDEX idx_routes_agency ON routes(agency_id);
        CREATE INDEX idx_calendar_dates_service ON calendar_dates(service_id);
        PRAGMA user_version = 1;
        """
    )
    connection.executemany(
        "INSERT INTO agencies VALUES (?, ?, ?, ?)",
        [
            (row["agency_id"], row["agency_name"], row.get("agency_url"), row.get("agency_timezone"))
            for row in tables["agency.txt"]
        ],
    )
    connection.executemany(
        "INSERT INTO routes VALUES (?, ?, ?, ?, ?)",
        [
            (
                row["route_id"],
                row["agency_id"],
                row.get("route_short_name"),
                row.get("route_long_name"),
                row["route_type"],
            )
            for row in tables["routes.txt"]
        ],
    )
    connection.executemany(
        "INSERT INTO trips VALUES (?, ?, ?, ?)",
        [
            (row["trip_id"], row["route_id"], row["service_id"], row.get("trip_short_name"))
            for row in tables["trips.txt"]
        ],
    )
    connection.executemany(
        "INSERT INTO stops VALUES (?, ?, ?, ?)",
        [
            (row["stop_id"], row["stop_name"], float(row["stop_lat"]), float(row["stop_lon"]))
            for row in tables["stops.txt"]
        ],
    )
    connection.executemany(
        "INSERT INTO stop_times VALUES (?, ?, ?, ?, ?)",
        [
            (
                row["trip_id"],
                row.get("arrival_time"),
                row.get("departure_time"),
                row["stop_id"],
                int(row["stop_sequence"]),
            )
            for row in tables["stop_times.txt"]
        ],
    )
    connection.executemany(
        "INSERT INTO calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["service_id"],
                int(row["monday"]),
                int(row["tuesday"]),
                int(row["wednesday"]),
                int(row["thursday"]),
                int(row["friday"]),
                int(row["saturday"]),
                int(row["sunday"]),
                row["start_date"],
                row["end_date"],
            )
            for row in tables["calendar.txt"]
        ],
    )
    connection.executemany(
        "INSERT INTO calendar_dates VALUES (?, ?, ?)",
        [
            (row["service_id"], row["date"], int(row["exception_type"]))
            for row in tables["calendar_dates.txt"]
        ],
    )
    connection.commit()
    connection.close()


def build_geojson(tables: dict[str, list[dict[str, str]]]) -> None:
    agencies = {row["agency_id"]: row["agency_name"] for row in tables["agency.txt"]}
    route_agency = {row["route_id"]: row["agency_id"] for row in tables["routes.txt"]}
    trip_agency = {
        row["trip_id"]: route_agency[row["route_id"]] for row in tables["trips.txt"]
    }
    station_calls: Counter[str] = Counter()
    station_agencies: defaultdict[str, set[str]] = defaultdict(set)
    for row in tables["stop_times.txt"]:
        station_calls[row["stop_id"]] += 1
        station_agencies[row["stop_id"]].add(trip_agency[row["trip_id"]])

    features = []
    for row in tables["stops.txt"]:
        stop_id = row["stop_id"]
        operators = [
            agencies[agency_id]
            for agency_id in sorted(station_agencies[stop_id])
            if agency_id in agencies
        ]
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(row["stop_lon"]), float(row["stop_lat"])],
                },
                "properties": {
                    "id": stop_id,
                    "name": row["stop_name"],
                    "calls": station_calls[stop_id],
                    "operators": operators,
                    "operator_count": len(operators),
                },
            }
        )

    write_json(
        DERIVED / "stations.geojson",
        {"type": "FeatureCollection", "features": features},
    )


def build_metadata(tables: dict[str, list[dict[str, str]]], source: dict[str, Any]) -> None:
    agencies = {row["agency_id"]: row for row in tables["agency.txt"]}
    routes = {row["route_id"]: row for row in tables["routes.txt"]}
    trips = tables["trips.txt"]
    trip_by_id = {row["trip_id"]: row for row in trips}
    trip_by_agency = Counter(routes[row["route_id"]]["agency_id"] for row in trips)
    route_by_agency = Counter(row["agency_id"] for row in tables["routes.txt"])
    route_type_trip_counts = Counter(routes[row["route_id"]]["route_type"] for row in trips)
    coordinates = [
        (float(row["stop_lat"]), float(row["stop_lon"])) for row in tables["stops.txt"]
    ]

    station_agencies: defaultdict[str, set[str]] = defaultdict(set)
    for stop_time in tables["stop_times.txt"]:
        trip = trip_by_id[stop_time["trip_id"]]
        station_agencies[stop_time["stop_id"]].add(routes[trip["route_id"]]["agency_id"])

    calendar_dates = tables["calendar.txt"]
    valid_from = min(row["start_date"] for row in calendar_dates)
    valid_to = max(row["end_date"] for row in calendar_dates)
    operator_rows = []
    for agency_id, row in sorted(
        agencies.items(), key=lambda item: (item[0] != "6100826", -trip_by_agency[item[0]])
    ):
        operator_rows.append(
            {
                "agency_id": agency_id,
                "agency_name": row["agency_name"],
                "trips": trip_by_agency[agency_id],
                "routes": route_by_agency[agency_id],
            }
        )

    metadata = {
        "schema_version": 1,
        "snapshot": source["snapshot"],
        "publisher": source["publisher"],
        "scope": source["scope"],
        "counts": {
            "agencies": len(agencies),
            "routes": len(routes),
            "trips": len(trips),
            "stops": len(tables["stops.txt"]),
            "stop_times": len(tables["stop_times.txt"]),
            "calendar": len(tables["calendar.txt"]),
            "calendar_dates": len(tables["calendar_dates.txt"]),
            "stops_with_coordinates": len(coordinates),
            "multi_operator_stops": sum(
                1 for operators in station_agencies.values() if len(operators) > 1
            ),
            "route_type_200_trips": route_type_trip_counts["200"],
        },
        "valid_date_range": [iso_date(valid_from), iso_date(valid_to)],
        "route_type_trip_counts": dict(sorted(route_type_trip_counts.items())),
        "operators": operator_rows,
        "artifacts": {
            "gtfs_directory": "data/derived/gtfs/",
            "gtfs_zip": "data/derived/gtfs-romania-feroviar.zip",
            "sqlite": "data/derived/romania-rail.sqlite",
            "geojson": "data/derived/stations.geojson",
            "atlas": "data/derived/atlas/atlas.json",
        },
    }
    write_json(DERIVED / "metadata.json", metadata)


def main() -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    tables = {name: read_csv(name) for name in GTFS_FILES}
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    build_gtfs_zip()
    build_sqlite(tables)
    build_geojson(tables)
    build_metadata(tables, source)
    print(f"Built GTFS release in {DERIVED}")
    print(f"  GTFS zip: {DERIVED / 'gtfs-romania-feroviar.zip'}")
    print(f"  SQLite:   {DERIVED / 'romania-rail.sqlite'}")
    print(f"  GeoJSON:  {DERIVED / 'stations.geojson'}")
    print(f"  Metadata: {DERIVED / 'metadata.json'}")


if __name__ == "__main__":
    main()
