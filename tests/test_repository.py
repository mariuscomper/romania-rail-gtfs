from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepositorySmokeTests(unittest.TestCase):
    def test_derived_artifacts_exist(self) -> None:
        for relative in (
            "data/derived/gtfs-romania-feroviar.zip",
            "data/derived/romania-rail.sqlite",
            "data/derived/stations.geojson",
            "data/derived/atlas/atlas.json",
            "data/derived/atlas/atlas.js",
            "MANIFEST.sha256",
        ):
            self.assertTrue((ROOT / relative).exists(), relative)

    def test_metadata_has_expected_snapshot_shape(self) -> None:
        metadata = json.loads((ROOT / "data/derived/metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["counts"]["agencies"], 7)
        self.assertEqual(metadata["counts"]["trips"], 2103)
        self.assertEqual(metadata["counts"]["stops"], 1695)
        self.assertEqual(metadata["valid_date_range"], ["2025-12-14", "2026-12-12"])

    def test_sqlite_supports_station_query(self) -> None:
        connection = sqlite3.connect(ROOT / "data/derived/romania-rail.sqlite")
        row = connection.execute(
            """SELECT COUNT(DISTINCT r.agency_id)
                 FROM stop_times AS st
                 JOIN trips AS t USING (trip_id)
                 JOIN routes AS r USING (route_id)
                WHERE st.stop_id = '10017'"""
        ).fetchone()
        connection.close()
        self.assertEqual(row[0], 7)

    def test_full_validator(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/validate.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads((ROOT / "qa/report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "pass")


if __name__ == "__main__":
    unittest.main()
