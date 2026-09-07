#!/usr/bin/env python3
"""Check that derived GTFS files and the zip are byte-identical to the source."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "gtfs"
DERIVED = ROOT / "data" / "derived"
DEFAULT_OUTPUT = ROOT / "qa" / "release-validation.json"
SOURCE = ROOT / "data" / "source.json"
GTFS_FILES = (
    "agency.txt",
    "routes.txt",
    "trips.txt",
    "stops.txt",
    "stop_times.txt",
    "calendar.txt",
    "calendar_dates.txt",
)


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run() -> dict[str, Any]:
    errors: list[str] = []
    source_snapshot = json.loads(SOURCE.read_text(encoding="utf-8"))["snapshot"]
    expected_hashes = source_snapshot.get("sha256", {})
    raw_hashes: dict[str, str] = {}
    for name in GTFS_FILES:
        if not (RAW / name).exists():
            errors.append(f"missing raw file: {name}")
        if not (DERIVED / "gtfs" / name).exists():
            errors.append(f"missing derived file: {name}")
        if (RAW / name).exists() and (DERIVED / "gtfs" / name).exists():
            raw_hashes[name] = digest_bytes((RAW / name).read_bytes())
            if raw_hashes[name] != expected_hashes.get(name):
                errors.append(f"raw file does not match pinned SHA-256: {name}")
            if (RAW / name).read_bytes() != (DERIVED / "gtfs" / name).read_bytes():
                errors.append(f"derived file differs from raw input: {name}")

    zip_path = DERIVED / "gtfs-romania-feroviar.zip"
    zip_names: list[str] = []
    member_hashes: dict[str, str] = {}
    if not zip_path.exists():
        errors.append("missing GTFS zip")
    else:
        try:
            with zipfile.ZipFile(zip_path) as archive:
                zip_names = archive.namelist()
                if sorted(zip_names) != sorted(GTFS_FILES):
                    errors.append(f"zip members differ: {zip_names}")
                for name in GTFS_FILES:
                    if name in zip_names and (RAW / name).exists():
                        member_hashes[name] = digest_bytes(archive.read(name))
                        if archive.read(name) != (RAW / name).read_bytes():
                            errors.append(f"zip member differs from raw input: {name}")
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"invalid GTFS zip: {exc}")

    return {
        "status": "pass" if not errors else "fail",
        "raw_files": list(GTFS_FILES),
        "upstream_commit": source_snapshot.get("upstream_commit"),
        "raw_sha256": raw_hashes,
        "zip_members": zip_names,
        "zip_member_sha256": member_hashes,
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
