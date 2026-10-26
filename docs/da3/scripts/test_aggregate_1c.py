"""Offline integrity contracts for Step 13 aggregation."""
from __future__ import annotations
import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("aggregate_1c.py")
SPEC = importlib.util.spec_from_file_location("aggregate_under_test", SOURCE)
assert SPEC and SPEC.loader
AGGREGATE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(AGGREGATE)

class AggregateTests(unittest.TestCase):
    def test_diff_names_the_selected_before_and_after_profiles(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "diff.txt"; AGGREGATE.config_diff(output)
            text = output.read_text(encoding="utf-8")
        self.assertIn("nginx-3-baseline.conf", text)
        self.assertIn("nginx-3-resilient.conf", text)

    def test_renderer_keeps_nonzero_observation_visible(self):
        sample = {"rep": 4, "completed": 1000, "failed": 1, "non_2xx": 1,
                  "metrics": {"connect_failures": 0, "receive_failures": 0, "length_failures": 1, "exception_failures": 0, "requests_per_second": "12.00"},
                  "diagnostics": {"502_count": 1, "504_count": 0}, "kill": {}, "recovery": "verified", "restoration": True,
                  "probe": {"total_samples": 10, "failed_probes": 0, "longest_observed_gap_seconds": .2}}
        text = AGGREGATE.render([sample] * 3, [sample] * 3)
        self.assertIn("| resilient | 4 | 1000 | 1 |", text)

if __name__ == "__main__": unittest.main()
