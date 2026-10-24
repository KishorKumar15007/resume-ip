"""Isolated, no-Docker checks for the Step 10 harness."""
from __future__ import annotations

import importlib.util
import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).with_name("loadtest.py")
SPEC = importlib.util.spec_from_file_location("da3_loadtest_under_test", SOURCE)
assert SPEC and SPEC.loader
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


def metrics(requests: int, *, code: int = 0, complete: bool = True,
            failed: int | None = 0, non_2xx: int | None = 0) -> object:
    return HARNESS.Metrics(
        requests, requests if complete else None, "100.0" if complete else None,
        "10.0" if complete else None, failed, 0, 0, 0, 0, non_2xx, code,
        launched=True,
    )


class HarnessTests(unittest.TestCase):
    def test_complete_non_2xx_warmup_is_reported_as_failure(self) -> None:
        item = metrics(HARNESS.WARMUP, non_2xx=HARNESS.WARMUP)
        self.assertEqual(HARNESS.status(item, HARNESS.WARMUP), "non-2xx responses")

    def test_cli_requires_one_mode(self) -> None:
        self.assertTrue(HARNESS.parser().parse_args(["--calibrate"]).calibrate)
        with self.assertRaises(SystemExit):
            HARNESS.parser().parse_args([])

    def test_missing_non_2xx_is_unknown(self) -> None:
        item = HARNESS.parse_ab("Complete requests: 1\n", 100, 119)
        self.assertIsNone(item.non_2xx_responses)
        self.assertFalse(HARNESS.measured_ok(item))

    def test_successful_summary_without_non_2xx_is_a_zero_count(self) -> None:
        output = (
            "Complete requests:      100\n"
            "Failed requests:        0\n"
            "Requests per second:    4.49 [#/sec] (mean)\n"
            "Time per request:       1114.082 [ms] (mean)\n"
        )
        item = HARNESS.parse_ab(output, HARNESS.WARMUP, 0)
        self.assertEqual(item.non_2xx_responses, 0)
        self.assertTrue(HARNESS.warmup_ok(item))

    def test_missing_non_2xx_stays_unknown_without_a_successful_summary(self) -> None:
        output = (
            "Complete requests:      100\n"
            "Failed requests:        0\n"
            "Requests per second:    4.49 [#/sec] (mean)\n"
            "Time per request:       1114.082 [ms] (mean)\n"
        )
        self.assertIsNone(HARNESS.parse_ab(output, HARNESS.WARMUP, 119).non_2xx_responses)
        self.assertIsNone(HARNESS.parse_ab("Complete requests: 100\nFailed requests: 0\n",
                                            HARNESS.WARMUP, 0).non_2xx_responses)

    def test_incomplete_grid_selects_nothing(self) -> None:
        point = HARNESS.Point(1, 5, 1, measurement=metrics(HARNESS.MEASURED))
        maximum, eligibility, selected = HARNESS.selection([point])
        self.assertEqual(maximum, {})
        self.assertIsNone(selected)
        self.assertTrue(eligibility)

    def test_complete_grid_uses_locked_lowest_eligible_level(self) -> None:
        points = []
        for instances in (1, 3):
            for concurrency in HARNESS.LEVELS:
                item = metrics(HARNESS.MEASURED)
                item.requests_per_second = str(100 - concurrency / 10)
                points.append(HARNESS.Point(instances, concurrency, 1, measurement=item))
        _, _, selected = HARNESS.selection(points)
        self.assertEqual(selected, 5)

    def test_nonzero_exit_is_never_a_valid_measurement(self) -> None:
        points = []
        for instances in (1, 3):
            for concurrency in HARNESS.LEVELS:
                code = 119 if instances == 1 and concurrency == 50 else 0
                points.append(HARNESS.Point(instances, concurrency, 1,
                              measurement=metrics(HARNESS.MEASURED, code=code)))
        _, _, selected = HARNESS.selection(points)
        self.assertIsNone(selected)

    def test_successful_warmups_produce_the_full_matrix(self) -> None:
        def fake_ab(requests: int, _: int, __: Path) -> object:
            return metrics(requests)
        with patch.object(HARNESS, "activate_topology", return_value=None), \
             patch.object(HARNESS, "run_ab", side_effect=fake_ab):
            points, traffic, error, interrupted = HARNESS.run_calibration(9)
        self.assertEqual(len(points), 10)
        self.assertIsNone(error)
        self.assertFalse(interrupted)
        self.assertEqual(traffic["launched_measurement"], 3000)

    def test_failed_warmup_skips_only_that_measurement_when_recovered(self) -> None:
        calls = 0
        def fake_ab(requests: int, _: int, __: Path) -> object:
            nonlocal calls
            calls += 1
            return metrics(requests, code=119) if calls == 1 else metrics(requests)
        with patch.object(HARNESS, "activate_topology", return_value=None), \
             patch.object(HARNESS, "recover_topology", return_value=None), \
             patch.object(HARNESS, "run_ab", side_effect=fake_ab):
            points, traffic, error, interrupted = HARNESS.run_calibration(9)
        self.assertTrue(points[0].measurement_skipped)
        self.assertIsNone(points[0].measurement)
        self.assertIsNone(error)
        self.assertFalse(interrupted)
        self.assertEqual(traffic["skipped_measurement"], 300)

    def test_main_returns_failure_when_restoration_fails(self) -> None:
        completed = [HARNESS.Point(1, 5, 9)]
        with patch.object(sys, "argv", ["loadtest.py", "--calibrate", "--rep", "9"]), \
             patch.dict(HARNESS.os.environ, {"LOADTEST_TOKEN": "test", "DA3_LOADTEST_ENV_FILE": "test"}, clear=False), \
             patch.object(HARNESS, "collision", return_value=None), \
             patch.object(HARNESS, "run_calibration", return_value=(completed, {}, None, False)), \
             patch.object(HARNESS, "restore_three_backends", return_value=False), \
             patch.object(HARNESS, "write_calibration", return_value=None):
            self.assertEqual(HARNESS.main(), 1)

    def test_collision_refuses_existing_file(self) -> None:
        target = Path("existing.json")
        with patch.object(Path, "exists", return_value=True):
            self.assertIn("refusing", HARNESS.collision([target]) or "")

    def test_legacy_single_paths_and_target_are_unchanged(self) -> None:
        warmup, measured, result_json, result_markdown = HARNESS.single_paths(1, 20, 11)
        self.assertEqual(warmup.name, "10-single-i1-c20-rep11-warmup.txt")
        self.assertEqual(measured.name, "10-single-i1-c20-rep11.txt")
        self.assertEqual(result_json.name, "10-single-i1-c20-rep11.json")
        self.assertEqual(result_markdown.name, "10-single-i1-c20-rep11.md")
        self.assertEqual(HARNESS.benchmark_target(None, None), "/postings")

    def test_opt_in_benchmark_marker_has_distinct_paths_and_phases(self) -> None:
        warmup, measured, result_json, result_markdown = HARNESS.single_paths(
            3, 20, 2, "s11-example-o2"
        )
        self.assertEqual(warmup.name, "11-1b-s11-example-o2-i3-c20-r2-warmup.txt")
        self.assertEqual(measured.name, "11-1b-s11-example-o2-i3-c20-r2.txt")
        self.assertEqual(result_json.name, "11-1b-s11-example-o2-i3-c20-r2.json")
        self.assertEqual(result_markdown.name, "11-1b-s11-example-o2-i3-c20-r2.md")
        self.assertEqual(
            HARNESS.benchmark_target("s11-example-o2", "warmup"),
            "/postings?bench=s11-example-o2&phase=warmup",
        )

    def test_marker_based_output_has_step_11_title_and_legacy_title_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            base = Path(directory)
            warmup, measured = metrics(HARNESS.WARMUP), metrics(HARNESS.MEASURED)
            marked_json, marked_md = base / "marked.json", base / "marked.md"
            HARNESS.write_single(1, 20, 1000, 1, warmup, measured, None, True, marked_json, marked_md, "s11-test-o1", True)
            self.assertIn("Step 11 benchmark run", marked_md.read_text(encoding="utf-8"))
            self.assertIn("Run ID: s11-test-o1", marked_md.read_text(encoding="utf-8"))
            legacy_json, legacy_md = base / "legacy.json", base / "legacy.md"
            HARNESS.write_single(1, 20, 1000, 1, warmup, measured, None, True, legacy_json, legacy_md)
            self.assertIn("Step 10 single run", legacy_md.read_text(encoding="utf-8"))

    def test_timeout_writes_partial_output_once(self) -> None:
        self.assertEqual(HARNESS.AB_TIMEOUT_SECONDS, 120)
        class Process:
            returncode = None
            def communicate(self, timeout: int):
                if timeout == HARNESS.AB_TIMEOUT_SECONDS:
                    raise subprocess.TimeoutExpired(["mock"], timeout, output="partial")
                self.returncode = -15
                return "partial-final", None
            def terminate(self) -> None:
                return None
            def kill(self) -> None:
                return None
            def poll(self) -> None:
                return None
        import subprocess
        output = Path("raw.txt")
        written: list[str] = []
        with patch.object(HARNESS.subprocess, "Popen", return_value=Process()), \
             patch.object(HARNESS, "cleanup_invocation",
                          return_value=HARNESS.Cleanup(True, True, True)), \
             patch.object(Path, "write_text", side_effect=lambda text, **_: written.append(text)):
                item = HARNESS.run_ab(100, 5, output)
        self.assertTrue(item.timed_out)
        self.assertEqual(
            item.execution_error,
            f"load-test command exceeded the {HARNESS.AB_TIMEOUT_SECONDS}-second wall-clock limit",
        )
        self.assertEqual(written, ["partial-final"])

    def test_cleanup_scope_uses_run_label(self) -> None:
        calls: list[list[str]] = []
        def fake_run(command: list[str], **_: object) -> object:
            calls.append(command)
            return type("Result", (), {"returncode": 0, "stdout": ""})()
        with patch.object(HARNESS.subprocess, "run", side_effect=fake_run), \
             patch.dict(HARNESS.os.environ, {"COMPOSE_PROJECT_NAME": "resume-ip"}, clear=False):
            self.assertEqual(HARNESS.invocation_containers("only-this-run"), ())
        flattened = " ".join(calls[0])
        self.assertIn("com.resume_ip.da3_loadtest_run=only-this-run", flattened)


if __name__ == "__main__":
    unittest.main()
