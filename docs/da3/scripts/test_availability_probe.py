"""Offline contracts for the Step 13 CSV probe."""
from __future__ import annotations
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("availability_probe.py")
SPEC = importlib.util.spec_from_file_location("probe_under_test", SOURCE)
assert SPEC and SPEC.loader
PROBE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(PROBE)

class ProbeTests(unittest.TestCase):
    def test_summary_counts_failures_and_start_timestamp_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=PROBE.FIELDS); writer.writeheader()
                writer.writerows((
                    {"timestamp_utc":"2026-10-26T00:00:00+00:00", "status":"200", "latency_ms":"1", "outcome":"http-200"},
                    {"timestamp_utc":"2026-10-26T00:00:00.200000+00:00", "status":"", "latency_ms":"1000", "outcome":"timeout"},
                    {"timestamp_utc":"2026-10-26T00:00:00.500000+00:00", "status":"503", "latency_ms":"3", "outcome":"http-non-200"},
                ))
            summary = PROBE.summarise(path)
        self.assertEqual(summary["failed_probes"], 2)
        self.assertAlmostEqual(float(summary["longest_observed_gap_seconds"]), .3)

    def test_empty_or_non_monotonic_csv_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.csv"; path.write_text("timestamp_utc,status,latency_ms,outcome\n", encoding="utf-8")
            with self.assertRaises(ValueError): PROBE.summarise(path)

    def test_unknown_or_contradictory_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "probe.csv"
            path.write_text("timestamp_utc,status,latency_ms,outcome\n2026-10-26T00:00:00+00:00,200,1,timeout\n", encoding="utf-8")
            with self.assertRaises(ValueError): PROBE.summarise(path)
            path.write_text("timestamp_utc,status,latency_ms,outcome\n2026-10-26T00:00:00+00:00,200,1,unknown\n", encoding="utf-8")
            with self.assertRaises(ValueError): PROBE.summarise(path)

if __name__ == "__main__": unittest.main()
