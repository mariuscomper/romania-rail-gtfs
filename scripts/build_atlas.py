#!/usr/bin/env python3
"""Build the compact corridor atlas used by Romania Rail GTFS.

Input:  GTFS text files in ../data/raw/gtfs
Output: ../data/derived/atlas/atlas.json

The source GTFS is generated from the official annual Romanian passenger
railway timetable. The visualisation excludes route_type=200 replacement
buses and plots scheduled, not observed, train movements.
"""
from __future__ import annotations

import csv
import datetime as dt
import heapq
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "gtfs"
CONFIG = ROOT / "config" / "corridors.json"
SOURCE = ROOT / "data" / "source.json"
OUT = ROOT / "data" / "derived" / "atlas" / "atlas.json"
JS_OUT = ROOT / "data" / "derived" / "atlas" / "atlas.js"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def fix_diacritics(value: str) -> str:
    return (
        value.replace("ş", "ș")
        .replace("ţ", "ț")
        .replace("Ş", "Ș")
        .replace("Ţ", "Ț")
    )


def canonical_key(value: str) -> str:
    """Stable, diacritic-insensitive key, with the two Bucharest North groups merged."""
    value = fix_diacritics(value).strip()
    decomposed = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
    value = re.sub(r"\s+", " ", value).strip()
    if re.fullmatch(r"bucuresti nord gr\.[ab]", value):
        return "bucuresti nord"
    return value


def iso_date(raw: str) -> str:
    raw = str(raw).strip()
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def parse_time(raw: str | None) -> float | None:
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    hour, minute, second = (int(part) for part in raw.split(":"))
    return hour * 60 + minute + second / 60.0


def fmt_time(minutes: float | None) -> str | None:
    if minutes is None:
        return None
    total_seconds = int(round(minutes * 60))
    hour, rem = divmod(total_seconds, 3600)
    minute, second = divmod(rem, 60)
    if second:
        return f"{hour:02d}:{minute:02d}:{second:02d}"
    return f"{hour:02d}:{minute:02d}"


def read_csv(name: str) -> list[dict[str, str]]:
    with (RAW / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def longest_monotonic_run(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the contiguous mapped run with the greatest corridor span."""
    if len(items) < 2:
        return []

    # Remove repeated corridor indices caused by equivalent station records.
    compact: list[dict[str, Any]] = []
    for item in items:
        if compact and compact[-1]["corridor_index"] == item["corridor_index"]:
            # Keep the later event data but preserve the first arrival where possible.
            previous = compact[-1]
            if previous.get("arrival") is None and item.get("arrival") is not None:
                previous["arrival"] = item["arrival"]
            if item.get("departure") is not None:
                previous["departure"] = item["departure"]
            continue
        compact.append(dict(item))

    if len(compact) < 2:
        return []

    candidates: list[list[dict[str, Any]]] = []
    for direction in (1, -1):
        start = 0
        for pos in range(1, len(compact)):
            diff = compact[pos]["corridor_index"] - compact[pos - 1]["corridor_index"]
            if direction * diff <= 0:
                if pos - start >= 2:
                    candidates.append(compact[start:pos])
                start = pos
        if len(compact) - start >= 2:
            candidates.append(compact[start:])

    if not candidates:
        return []
    return max(
        candidates,
        key=lambda run: (
            abs(run[-1]["corridor_index"] - run[0]["corridor_index"]),
            len(run),
        ),
    )


def main() -> None:
    stops_rows = read_csv("stops.txt")
    routes_rows = read_csv("routes.txt")
    trips_rows = read_csv("trips.txt")
    stop_times_rows = read_csv("stop_times.txt")
    agencies_rows = read_csv("agency.txt")
    calendar_rows = read_csv("calendar.txt")
    calendar_dates_rows = read_csv("calendar_dates.txt")
    corridor_specs = json.loads(CONFIG.read_text(encoding="utf-8"))
    source_snapshot = json.loads(SOURCE.read_text(encoding="utf-8"))["snapshot"]

    agencies = {row["agency_id"]: row for row in agencies_rows}
    routes = {row["route_id"]: row for row in routes_rows}
    trips = {row["trip_id"]: row for row in trips_rows}

    stop_by_id: dict[str, dict[str, Any]] = {}
    ids_by_key: dict[str, list[str]] = defaultdict(list)
    key_coords_acc: dict[str, list[tuple[float, float]]] = defaultdict(list)
    key_names: dict[str, Counter[str]] = defaultdict(Counter)

    for row in stops_rows:
        name = fix_diacritics(row["stop_name"])
        key = canonical_key(name)
        lat, lon = float(row["stop_lat"]), float(row["stop_lon"])
        stop = {"id": row["stop_id"], "name": name, "key": key, "lat": lat, "lon": lon}
        stop_by_id[row["stop_id"]] = stop
        ids_by_key[key].append(row["stop_id"])
        key_coords_acc[key].append((lat, lon))
        key_names[key][name] += 1

    coords: dict[str, tuple[float, float]] = {}
    display_name: dict[str, str] = {}
    for key, values in key_coords_acc.items():
        coords[key] = (
            sum(value[0] for value in values) / len(values),
            sum(value[1] for value in values) / len(values),
        )
        display_name[key] = key_names[key].most_common(1)[0][0]
    display_name["bucuresti nord"] = "București Nord"

    # Build ordered stop-time events and make time values monotonically increasing.
    raw_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stop_times_rows:
        raw_events[row["trip_id"]].append(
            {
                "sequence": int(row["stop_sequence"]),
                "stop_id": row["stop_id"],
                "arrival_raw": parse_time(row.get("arrival_time")),
                "departure_raw": parse_time(row.get("departure_time")),
            }
        )

    trip_events: dict[str, list[dict[str, Any]]] = {}
    trip_keys: dict[str, list[str]] = {}
    for trip_id, rows in raw_events.items():
        rows.sort(key=lambda value: value["sequence"])
        previous = -1.0
        events: list[dict[str, Any]] = []
        keys: list[str] = []
        for row in rows:
            arrival = row["arrival_raw"]
            departure = row["departure_raw"]
            if arrival is not None:
                while arrival + 1e-6 < previous:
                    arrival += 1440
                previous = max(previous, arrival)
            if departure is not None:
                while departure + 1e-6 < previous:
                    departure += 1440
                previous = max(previous, departure)
            stop = stop_by_id[row["stop_id"]]
            event = {
                "sequence": row["sequence"],
                "stop_id": stop["id"],
                "key": stop["key"],
                "name": stop["name"],
                "arrival": arrival,
                "departure": departure,
            }
            events.append(event)
            if not keys or keys[-1] != stop["key"]:
                keys.append(stop["key"])
        trip_events[trip_id] = events
        trip_keys[trip_id] = keys

    # National graph from consecutive scheduled calling points. Long express jumps
    # remain available but receive a quadratic cost, so granular local-stop paths win.
    edge_frequency: Counter[tuple[str, str]] = Counter()
    for trip_id, keys in trip_keys.items():
        trip = trips[trip_id]
        route = routes[trip["route_id"]]
        if int(route["route_type"]) == 200:
            continue
        for a, b in zip(keys, keys[1:]):
            if a == b:
                continue
            edge_frequency[tuple(sorted((a, b)))] += 1

    adjacency: dict[str, list[tuple[str, float, float, int]]] = defaultdict(list)
    for (a, b), frequency in edge_frequency.items():
        distance = haversine(coords[a], coords[b])
        weight = distance + 0.18 * distance * distance
        weight /= 1 + 0.08 * math.log1p(frequency)
        adjacency[a].append((b, weight, distance, frequency))
        adjacency[b].append((a, weight, distance, frequency))

    def max_direct_segment(start_key: str, end_key: str) -> list[str]:
        best: tuple[int, float, list[str]] | None = None
        for trip_id, keys in trip_keys.items():
            trip = trips[trip_id]
            route = routes[trip["route_id"]]
            if int(route["route_type"]) == 200:
                continue
            if start_key not in keys or end_key not in keys:
                continue
            a, b = keys.index(start_key), keys.index(end_key)
            if a == b:
                continue
            segment = keys[a : b + 1] if a < b else list(reversed(keys[b : a + 1]))
            geo_length = sum(haversine(coords[x], coords[y]) for x, y in zip(segment, segment[1:]))
            candidate = (len(segment), -geo_length, segment)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
        if best is None:
            raise ValueError(f"No direct scheduled rail trip joins {start_key!r} and {end_key!r}")
        return best[2]

    def corridor_path(start_key: str, end_key: str) -> list[str]:
        seed = max_direct_segment(start_key, end_key)
        # Stay close to the seed route to avoid parallel lines and network branches.
        allowed: set[str] = set()
        for key, point in coords.items():
            if any(haversine(point, coords[seed_key]) <= 25 for seed_key in seed):
                allowed.add(key)
        allowed.update((start_key, end_key))

        distance: dict[str, float] = {start_key: 0.0}
        previous: dict[str, str] = {}
        heap: list[tuple[float, str]] = [(0.0, start_key)]
        while heap:
            current_distance, current = heapq.heappop(heap)
            if current_distance != distance.get(current):
                continue
            if current == end_key:
                break
            for neighbour, weight, _, _ in adjacency.get(current, []):
                if neighbour not in allowed:
                    continue
                candidate = current_distance + weight
                if candidate < distance.get(neighbour, math.inf):
                    distance[neighbour] = candidate
                    previous[neighbour] = current
                    heapq.heappush(heap, (candidate, neighbour))

        if end_key not in distance:
            return seed
        path: list[str] = []
        cursor = end_key
        while True:
            path.append(cursor)
            if cursor == start_key:
                break
            cursor = previous[cursor]
        path.reverse()
        return path

    # Calendar data: compact base pattern plus explicit additions/removals.
    service_exceptions: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"add": [], "remove": []})
    for row in calendar_dates_rows:
        bucket = "add" if row["exception_type"] == "1" else "remove"
        service_exceptions[row["service_id"]][bucket].append(iso_date(row["date"]))

    services: dict[str, dict[str, Any]] = {}
    for row in calendar_rows:
        service_id = row["service_id"]
        services[service_id] = {
            "week": "".join(row[day] for day in WEEKDAYS),
            "start": iso_date(row["start_date"]),
            "end": iso_date(row["end_date"]),
            "add": sorted(service_exceptions[service_id]["add"]),
            "remove": sorted(service_exceptions[service_id]["remove"]),
        }

    corridors: list[dict[str, Any]] = []
    for spec in corridor_specs:
        start_key = canonical_key(spec["start"])
        end_key = canonical_key(spec["end"])
        path = corridor_path(start_key, end_key)
        station_index = {key: index for index, key in enumerate(path)}

        cumulative = 0.0
        stations: list[dict[str, Any]] = []
        major_keys = {canonical_key(value) for value in spec.get("major", [])}
        for index, key in enumerate(path):
            if index:
                cumulative += haversine(coords[path[index - 1]], coords[key])
            stations.append(
                {
                    "key": key,
                    "name": display_name[key],
                    "km": round(cumulative, 2),
                    "lat": round(coords[key][0], 6),
                    "lon": round(coords[key][1], 6),
                    "major": key in major_keys or key in (start_key, end_key),
                    "calls": 0,
                }
            )

        segment_rows: list[dict[str, Any]] = []
        calls = Counter()
        for trip_id, events in trip_events.items():
            trip = trips[trip_id]
            route = routes[trip["route_id"]]
            if int(route["route_type"]) == 200:
                continue

            mapped: list[dict[str, Any]] = []
            for event in events:
                key = event["key"]
                if key in station_index:
                    mapped.append({**event, "corridor_index": station_index[key]})
            run = longest_monotonic_run(mapped)
            if len(run) < 2:
                continue

            first_index = run[0]["corridor_index"]
            last_index = run[-1]["corridor_index"]
            if first_index == last_index:
                continue

            points: list[dict[str, Any]] = []
            calling_stops: list[dict[str, Any]] = []
            for event in run:
                position = stations[event["corridor_index"]]["km"]
                arrival = event["arrival"]
                departure = event["departure"]
                if arrival is not None:
                    points.append({"t": round(arrival, 3), "km": position, "kind": "a"})
                if departure is not None and (arrival is None or abs(departure - arrival) > 1e-6):
                    points.append({"t": round(departure, 3), "km": position, "kind": "d"})
                if arrival is None and departure is None:
                    continue
                calls[event["key"]] += 1
                calling_stops.append(
                    {
                        "name": stations[event["corridor_index"]]["name"],
                        "km": position,
                        "arrival": fmt_time(arrival),
                        "departure": fmt_time(departure),
                    }
                )

            # Remove exact duplicate points while preserving dwell segments.
            clean_points: list[dict[str, Any]] = []
            for point in sorted(points, key=lambda value: value["t"]):
                if clean_points and point["t"] == clean_points[-1]["t"] and point["km"] == clean_points[-1]["km"]:
                    continue
                clean_points.append(point)
            if len(clean_points) < 2 or clean_points[-1]["t"] <= clean_points[0]["t"]:
                continue

            all_events = events
            origin = all_events[0]["name"]
            destination = all_events[-1]["name"]
            agency = agencies[route["agency_id"]]
            span = abs(clean_points[-1]["km"] - clean_points[0]["km"])
            duration = clean_points[-1]["t"] - clean_points[0]["t"]
            segment_rows.append(
                {
                    "id": trip_id,
                    "service": trip["service_id"],
                    "number": trip_id,
                    "category": trip["trip_short_name"],
                    "operatorId": route["agency_id"],
                    "operator": agency["agency_name"],
                    "route": fix_diacritics(route["route_long_name"]),
                    "origin": origin,
                    "destination": destination,
                    "direction": "forward" if last_index > first_index else "reverse",
                    "start": round(clean_points[0]["t"], 3),
                    "end": round(clean_points[-1]["t"], 3),
                    "duration": round(duration, 2),
                    "distance": round(span, 2),
                    "avgSpeed": round(span / (duration / 60), 1) if duration > 0 else None,
                    "points": clean_points,
                    "stops": calling_stops,
                }
            )

        for station in stations:
            station["calls"] = calls[station["key"]]
        segment_rows.sort(key=lambda value: (value["start"], value["number"]))

        max_gap = max(
            (stations[i + 1]["km"] - stations[i]["km"] for i in range(len(stations) - 1)),
            default=0,
        )
        corridors.append(
            {
                **{key: value for key, value in spec.items() if key != "major"},
                "distanceKm": stations[-1]["km"],
                "stationCount": len(stations),
                "trainDefinitionCount": len(segment_rows),
                "maxStationGapKm": round(max_gap, 1),
                "stations": stations,
                "trains": segment_rows,
            }
        )
        print(
            f"{spec['id']}: {len(stations)} corridor points, "
            f"{len(segment_rows)} train definitions, {stations[-1]['km']:.1f} km approx."
        )

    start_date = min(service["start"] for service in services.values())
    end_date = max(service["end"] for service in services.values())
    requested_date = source_snapshot.get("default_view_date", start_date)
    default_date = min(max(requested_date, start_date), end_date)
    rail_trip_count = sum(1 for trip in trips.values() if int(routes[trip["route_id"]]["route_type"]) != 200)
    bus_trip_count = len(trips) - rail_trip_count

    payload = {
        "meta": {
            "title": "Romania Rail GTFS / Atlasul timp–distanță",
            "generated": source_snapshot.get("build_generated_at", start_date + "T00:00:00+00:00"),
            "validFrom": start_date,
            "validTo": end_date,
            "defaultDate": default_date,
            "stopCount": len(stops_rows),
            "tripDefinitionCount": len(trips_rows),
            "railTripDefinitionCount": rail_trip_count,
            "replacementBusDefinitionCount": bus_trip_count,
            "operatorCount": len(agencies_rows),
            "corridorCount": len(corridors),
            "distanceMethod": "Cumulative great-circle distance between scheduled calling points on a graph-derived corridor path.",
            "scheduleStatus": "planned",
            "sourceGtfsRepository": source_snapshot["upstream_repository"],
            "sourceGtfsCommit": source_snapshot["upstream_commit"],
        },
        "operators": {
            agency_id: {
                "name": row["agency_name"],
                "url": row["agency_url"],
            }
            for agency_id, row in agencies.items()
        },
        "categories": ["IC", "IR", "IR-N", "R-E", "R", "R-M"],
        "services": services,
        "corridors": corridors,
        "sources": [
            {
                "name": "Informatică Feroviară / data.gov.ro",
                "url": "https://data.gov.ro/organization/9b0bc5fc-2062-4aef-b916-b48b7c459af7?organization=sc-informatica-feroviara-sa",
                "note": "Official annual planned operator datasets; consult each dataset for its licence.",
            },
            {
                "name": "Romanian Railways GTFS exporter — Vasile Coțovanu",
                "url": "https://github.com/vasile/data.gov.ro-gtfs-exporter",
                "note": "GTFS conversion and station coordinates; MIT-licensed code.",
            },
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(compact, encoding="utf-8")
    JS_OUT.write_text("window.ATLAS_DATA=" + compact + ";\n", encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.1f} KiB)")
    print(f"Wrote {JS_OUT} ({JS_OUT.stat().st_size / 1024:.1f} KiB)")


if __name__ == "__main__":
    main()
