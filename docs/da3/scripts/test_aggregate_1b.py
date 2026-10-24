"""Offline fixture tests for the Step 11 aggregation policy."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SOURCE = Path(__file__).with_name("aggregate_1b.py")
SPEC = importlib.util.spec_from_file_location("da3_aggregate_1b_under_test", SOURCE)
assert SPEC and SPEC.loader
AGGREGATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AGGREGATE)


def row(ordinal: int, instances: int, repetition: int, *, rps: str = "10", mean: str = "100",
        failed: int = 0, non_2xx: int = 0, status: str = "complete",
        diagnostics: str = "complete") -> dict[str, object]:
    return {
        "ordinal": ordinal, "run_id": f"s11-test-o{ordinal}", "topology_instances": instances,
        "topology_repetition": repetition, "concurrency": 20,
        "planned_warmup_requests": 100, "planned_measured_requests": 1000,
        "status": status, "reason": None, "invocation_exit_status": 0,
        "metrics": {
            "warmup_completed_requests": 100, "completed_requests": 1000,
            "requests_per_second": rps, "mean_time_per_request_ms": mean,
            "failed_requests": failed, "non_2xx_responses": non_2xx,
            "return_code": 0, "timed_out": False, "interrupted": False,
            "execution_error": None, "harness_error": None,
        },
        "nginx_diagnostics": {
            "availability": diagnostics,
            "phases": {"measured": {"status_counts": {"200": 1000}}},
        },
        "topology": {"activation": "verified", "restoration": "verified"},
        "raw_files": [f"docs/da3/results/11-raw-{ordinal}.txt"],
        "result_files": [], "diagnostic_files": [],
        "median_eligible": True, "median_exclusion_reason": None,
    }


class AggregateTests(unittest.TestCase):
    def test_complete_six_run_medians_and_formulas(self) -> None:
        rows = [
            row(1, 1, 1, rps="10", mean="100"), row(2, 3, 1, rps="30", mean="40"),
            row(3, 1, 2, rps="12", mean="90"), row(4, 3, 2, rps="32", mean="35"),
            row(5, 1, 3, rps="11", mean="95"), row(6, 3, 3, rps="31", mean="36"),
        ]
        document = AGGREGATE.aggregate(rows)
        self.assertTrue(document["intended_benchmark_complete"])
        self.assertEqual(document["configurations"]["1"]["median_requests_per_second"], "11")
        self.assertEqual(document["configurations"]["3"]["median_mean_time_per_request_ms"], "36")
        self.assertEqual(document["comparisons"]["throughput_speedup_factor"], "2.818181818181818181818181818")
        self.assertEqual(document["comparisons"]["mean_response_time_improvement_factor"], "2.638888888888888888888888889")

    def test_complete_run_with_http_errors_remains_eligible(self) -> None:
        summary = AGGREGATE.row_summary(row(1, 1, 1, failed=2, non_2xx=2))
        self.assertTrue(summary["median_eligible"])
        self.assertEqual(summary["failed_requests"], 2)
        self.assertEqual(summary["non_2xx_responses"], 2)

    def test_missing_diagnostics_do_not_exclude_complete_ab_measurement(self) -> None:
        summary = AGGREGATE.row_summary(row(1, 1, 1, diagnostics="unavailable"))
        self.assertTrue(summary["median_eligible"])
        self.assertEqual(summary["nginx_diagnostics"], "unavailable")

    def test_partial_and_skipped_rows_remain_visible_and_make_benchmark_incomplete(self) -> None:
        rows = [row(1, 1, 1), row(2, 3, 1), row(3, 1, 2, status="partial"),
                row(4, 3, 2), row(5, 1, 3, status="skipped"), row(6, 3, 3)]
        rows[2]["reason"] = "timed out"
        rows[4]["reason"] = "topology restoration not verified"
        document = AGGREGATE.aggregate(rows)
        self.assertFalse(document["intended_benchmark_complete"])
        self.assertEqual(document["configurations"]["1"]["eligible_runs"], 1)
        self.assertEqual(document["rows"][2]["median_exclusion_reason"], "timed out")
        self.assertEqual(document["rows"][4]["median_exclusion_reason"], "topology restoration not verified")

    def test_raw_output_is_used_only_as_partial_fallback(self) -> None:
        with TemporaryDirectory(dir=SOURCE.parent) as directory:
            raw = Path(directory) / "raw.txt"
            raw.write_text("Complete requests: 2\nFailed requests: 1\nRequests per second: 1.5 [#/sec]\n", encoding="utf-8")
            original_root, original_results = AGGREGATE.ROOT, AGGREGATE.RESULTS
            try:
                AGGREGATE.ROOT = Path(directory)
                AGGREGATE.RESULTS = Path(directory)
                partial = row(1, 1, 1, status="partial")
                partial["metrics"] = {}
                partial["raw_files"] = ["raw.txt"]
                summary = AGGREGATE.row_summary(partial)
            finally:
                AGGREGATE.ROOT, AGGREGATE.RESULTS = original_root, original_results
        self.assertEqual(summary["metric_source"], "partial raw output")
        self.assertFalse(summary["median_eligible"])
        self.assertEqual(summary["completed_requests"], 2)

    def test_unknown_existing_output_is_not_overwritten(self) -> None:
        with TemporaryDirectory(dir=SOURCE.parent) as directory:
            path = Path(directory) / "table.md"
            path.write_text("human output", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                AGGREGATE.atomic_text(path, "replacement")

    def test_nonzero_invocation_exit_excludes_visible_metrics(self) -> None:
        summary = AGGREGATE.row_summary(row(1, 1, 1))
        self.assertTrue(summary["median_eligible"])
        failed = row(1, 1, 1)
        failed["invocation_exit_status"] = 7
        summary = AGGREGATE.row_summary(failed)
        self.assertFalse(summary["median_eligible"])
        self.assertEqual(summary["completed_requests"], 1000)

    def test_unverified_restoration_excludes_complete_looking_result(self) -> None:
        failed = row(1, 1, 1)
        failed["topology"] = {"activation": "verified", "restoration": "not verified"}
        summary = AGGREGATE.row_summary(failed)
        self.assertFalse(summary["median_eligible"])
        self.assertEqual(summary["completed_requests"], 1000)

    def test_invalid_manifest_rows_are_refused(self) -> None:
        valid = [
            row(1, 1, 1), row(2, 3, 1), row(3, 1, 2),
            row(4, 3, 2), row(5, 1, 3), row(6, 3, 3),
        ]
        malformed = list(valid)
        malformed[2] = "not a row"  # type: ignore[list-item]
        with self.assertRaises(ValueError):
            AGGREGATE.validate_rows(malformed)
        wrong_order = list(valid)
        wrong_order[1] = row(2, 1, 1)
        with self.assertRaises(ValueError):
            AGGREGATE.validate_rows(wrong_order)

    def test_invalid_top_level_contract_is_refused_before_outputs(self) -> None:
        manifest = {"locked_configuration": {"concurrency": 10}, "rows": []}
        with self.assertRaises(ValueError):
            AGGREGATE.validate_manifest(manifest)

    def test_warmup_failure_and_unknown_activation_are_ineligible(self) -> None:
        failed = row(1, 1, 1)
        failed["warmup_metrics"] = {"completed_requests": 100, "return_code": 0, "timed_out": False,
                                     "interrupted": False, "execution_error": None, "failed_requests": 1,
                                     "non_2xx_responses": 0}
        self.assertFalse(AGGREGATE.row_summary(failed)["median_eligible"])
        failed = row(1, 1, 1)
        failed["topology"] = {"activation": "unknown", "restoration": "verified"}
        self.assertFalse(AGGREGATE.row_summary(failed)["median_eligible"])

    def test_regeneration_preflight_is_all_or_nothing(self) -> None:
        with TemporaryDirectory(dir=SOURCE.parent) as directory:
            base = Path(directory)
            first, second, third = base / "one.md", base / "two.csv", base / "three.json"
            first.write_text(AGGREGATE.MARKER + "\nold", encoding="utf-8")
            second.write_text("human output", encoding="utf-8")
            outputs = {first: AGGREGATE.MARKER + "\nnew", second: AGGREGATE.MARKER + "\nnew", third: "{}\n"}
            with self.assertRaises(RuntimeError):
                AGGREGATE.replace_outputs(outputs)
            self.assertEqual(first.read_text(encoding="utf-8"), AGGREGATE.MARKER + "\nold")
            self.assertFalse(third.exists())

    def test_recognized_outputs_regenerate_together(self) -> None:
        with TemporaryDirectory(dir=SOURCE.parent) as directory:
            base = Path(directory)
            first, second, third = base / "one.md", base / "two.csv", base / "three.json"
            first.write_text(AGGREGATE.MARKER + "\nold", encoding="utf-8")
            second.write_text(AGGREGATE.MARKER + "\nold", encoding="utf-8")
            third.write_text('{"generated_by":"docs/da3/scripts/aggregate_1b.py"}\n', encoding="utf-8")
            AGGREGATE.replace_outputs({first: AGGREGATE.MARKER + "\nnew", second: AGGREGATE.MARKER + "\nnew", third: '{"generated_by":"docs/da3/scripts/aggregate_1b.py","new":true}\n'})
            self.assertIn("new", first.read_text(encoding="utf-8"))
            self.assertIn("new", second.read_text(encoding="utf-8"))
            self.assertIn("new", third.read_text(encoding="utf-8"))

    def test_replacement_failure_restores_prior_generation(self) -> None:
        with TemporaryDirectory(dir=SOURCE.parent) as directory:
            base = Path(directory)
            first, second, third = base / "one.md", base / "two.csv", base / "three.json"
            first.write_text(AGGREGATE.MARKER + "\nold-one", encoding="utf-8")
            second.write_text(AGGREGATE.MARKER + "\nold-two", encoding="utf-8")
            original = Path.replace
            calls = 0
            def fail_second_replace(source: Path, target: Path) -> Path:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("fixture replacement failure")
                return original(source, target)
            with patch.object(Path, "replace", new=fail_second_replace):
                with self.assertRaises(RuntimeError):
                    AGGREGATE.replace_outputs({first: AGGREGATE.MARKER + "\nnew-one", second: AGGREGATE.MARKER + "\nnew-two", third: '{"generated_by":"docs/da3/scripts/aggregate_1b.py"}\n'})
            self.assertEqual(first.read_text(encoding="utf-8"), AGGREGATE.MARKER + "\nold-one")
            self.assertEqual(second.read_text(encoding="utf-8"), AGGREGATE.MARKER + "\nold-two")
            self.assertFalse(third.exists())

    def test_nonfinite_metrics_and_missing_failure_counts_are_ineligible(self) -> None:
        invalid = row(1, 1, 1, rps="NaN")
        self.assertFalse(AGGREGATE.row_summary(invalid)["median_eligible"])
        invalid = row(1, 1, 1)
        invalid["metrics"]["failed_requests"] = None
        self.assertFalse(AGGREGATE.row_summary(invalid)["median_eligible"])

    def test_partial_comparison_is_labelled_in_markdown(self) -> None:
        document = AGGREGATE.aggregate([row(1, 1, 1), row(2, 3, 1), row(3, 1, 2, status="partial"), row(4, 3, 2), row(5, 1, 3), row(6, 3, 3)])
        self.assertIn("PARTIAL / INCOMPLETE", AGGREGATE.markdown(document, Path("manifest.json")))


if __name__ == "__main__":
    unittest.main()
