#!/usr/bin/env python3
"""Write SHA-256 sums for source and derived data files."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "MANIFEST.sha256"
EXPLICIT = (
    ROOT / "data" / "derived" / "gtfs-romania-feroviar.zip",
    ROOT / "data" / "derived" / "romania-rail.sqlite",
    ROOT / "data" / "derived" / "stations.geojson",
    ROOT / "data" / "derived" / "metadata.json",
    ROOT / "data" / "derived" / "atlas" / "atlas.json",
    ROOT / "data" / "derived" / "atlas" / "atlas.js",
)


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def main() -> None:
    paths = list((ROOT / "data" / "raw" / "gtfs").glob("*.txt"))
    paths += list((ROOT / "data" / "derived" / "gtfs").glob("*.txt"))
    paths += list(EXPLICIT)
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise SystemExit("Missing files: " + ", ".join(str(path.relative_to(ROOT)) for path in missing))
    unique_paths = sorted(set(paths), key=lambda path: path.relative_to(ROOT).as_posix())
    lines = [
        f"{digest(path)}  {path.relative_to(ROOT).as_posix()}"
        for path in unique_paths
    ]
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(lines)} entries")


if __name__ == "__main__":
    main()
