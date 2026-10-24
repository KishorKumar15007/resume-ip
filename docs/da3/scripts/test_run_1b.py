"""Offline tests for the Step 11 benchmark orchestrator."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SOURCE = Path(__file__).with_name("run_1b.py")
SPEC = importlib.util.spec_from_file_location("da3_run_1b_under_test", SOURCE)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def complete_document(instances: int, repetition: int, *, marker: str, restored: bool = True) -> dict[str, object]:
    return {
        "mode": "single-run", "instances": instances, "rep": repetition,
        "concurrency": 20, "requests": 1000, "benchmark_id": marker, "error": None,
        "topology_activated": True,
        "restored_three_backends": restored,
        "warmup": {
            "completed_requests": 100, "requests_per_second": "10.0",
            "mean_time_per_request_ms": "100.0", "failed_requests": 0,
            "non_2xx_responses": 0, "return_code": 0, "timed_out": False,
            "interrupted": False, "execution_error": None,
        },
        "measurement": {
            "completed_requests": 1000, "requests_per_second": "10.0",
            "mean_time_per_request_ms": "100.0", "failed_requests": 0,
            "non_2xx_responses": 0, "return_code": 0, "timed_out": False,
            "interrupted": False, "execution_error": None,
        },
    }


class RunnerTests(unittest.TestCase):
    def test_generated_ids_are_accepted_by_the_real_harness_parser(self) -> None:
        sequence = RUNNER.new_sequence_id()
        rows = RUNNER.planned_rows(sequence)
        self.assertEqual(len(rows), 6)
        for row in rows:
            marker = str(row["run_id"])
            self.assertEqual(RUNNER.loadtest.benchmark_id(marker), marker)
            self.assertEqual(RUNNER.loadtest.parser().parse_args(["--single-run", "--benchmark-id", marker]).benchmark_id, marker)

    def test_planned_rows_keep_the_locked_order(self) -> None:
        rows = RUNNER.planned_rows("s11-test")
        self.assertEqual([row["topology_instances"] for row in rows], [1, 3, 1, 3, 1, 3])
        self.assertEqual([row["topology_repetition"] for row in rows], [1, 1, 2, 2, 3, 3])
        self.assertTrue(all(row["concurrency"] == 20 for row in rows))

    def test_one_token_and_six_invocations_without_token_persistence(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            calls: list[list[str]] = []

            def fake_run(command: list[str], **_: object) -> object:
                calls.append(command)
                marker = command[-1]
                instances = int(command[command.index("--instances") + 1])
                repetition = int(command[command.index("--rep") + 1])
                paths = RUNNER.artifact_paths(marker, instances, repetition)
                paths["warmup_raw"].write_text("warmup", encoding="utf-8")
                paths["measured_raw"].write_text("measured", encoding="utf-8")
                paths["result_json"].write_text(json.dumps(complete_document(instances, repetition, marker=marker)), encoding="utf-8")
                paths["result_markdown"].write_text("result", encoding="utf-8")
                return type("Result", (), {"returncode": 0})()

            diagnostics = {"availability": "complete", "phases": {"warmup": {}, "measured": {}}}
            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER, "NGINX_LOG", results / "access.log"), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), \
                 patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", return_value=diagnostics):
                code, manifest_path = RUNNER.run_sequence("s11-test")
            manifest_text = manifest_path.read_text(encoding="utf-8")
            document = json.loads(manifest_text)
            self.assertEqual(code, 0, document)
            self.assertEqual(len(calls), 6)
            self.assertEqual([row["status"] for row in document["rows"]], ["complete"] * 6)
            self.assertNotIn("private-token", manifest_text)

    def test_failed_run_is_not_retried_when_restoration_succeeds(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            calls = 0

            def fake_run(command: list[str], **_: object) -> object:
                nonlocal calls
                calls += 1
                marker = command[-1]
                instances = int(command[command.index("--instances") + 1])
                repetition = int(command[command.index("--rep") + 1])
                paths = RUNNER.artifact_paths(marker, instances, repetition)
                document = complete_document(instances, repetition, marker=marker)
                if calls == 1:
                    document["error"] = "measurement incomplete"
                    document["measurement"] = None
                paths["result_json"].write_text(json.dumps(document), encoding="utf-8")
                paths["measured_raw"].write_text("partial", encoding="utf-8")
                return type("Result", (), {"returncode": 1 if calls == 1 else 0})()

            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER, "NGINX_LOG", results / "access.log"), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), \
                 patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", return_value={"availability": "unavailable", "phases": {}}):
                code, manifest_path = RUNNER.run_sequence("s11-failure")
            document = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            self.assertEqual(calls, 6)
            self.assertEqual(document["rows"][0]["status"], "failed")
            self.assertEqual(document["rows"][1]["status"], "complete")

    def test_nonzero_harness_exit_excludes_complete_looking_result(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)

            def fake_run(command: list[str], **_: object) -> object:
                marker = command[-1]
                instances = int(command[command.index("--instances") + 1])
                repetition = int(command[command.index("--rep") + 1])
                RUNNER.artifact_paths(marker, instances, repetition)["result_json"].write_text(
                    json.dumps(complete_document(instances, repetition, marker=marker)), encoding="utf-8"
                )
                return type("Result", (), {"returncode": 9})()

            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER, "NGINX_LOG", results / "access.log"), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), \
                 patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", return_value={"availability": "unavailable", "phases": {}}):
                code, manifest_path = RUNNER.run_sequence("s11-nonzero")
            first = json.loads(manifest_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(code, 1)
            self.assertEqual(first["status"], "failed")
            self.assertEqual(first["metrics"]["completed_requests"], 1000)
            self.assertFalse(first["median_eligible"])

    def test_unverified_restoration_skips_remaining_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)

            def fake_run(command: list[str], **_: object) -> object:
                marker = command[-1]
                instances = int(command[command.index("--instances") + 1])
                repetition = int(command[command.index("--rep") + 1])
                paths = RUNNER.artifact_paths(marker, instances, repetition)
                paths["result_json"].write_text(json.dumps(complete_document(instances, repetition, marker=marker, restored=False)), encoding="utf-8")
                return type("Result", (), {"returncode": 1})()

            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER, "NGINX_LOG", results / "access.log"), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), \
                 patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", return_value={"availability": "unavailable", "phases": {}}):
                code, manifest_path = RUNNER.run_sequence("s11-restore")
            rows = json.loads(manifest_path.read_text(encoding="utf-8"))["rows"]
            self.assertEqual(code, 1)
            self.assertEqual(rows[0]["topology"]["restoration"], "not verified")
            self.assertTrue(all(row["status"] == "skipped" for row in rows[1:]))

    def test_token_failure_prevents_workload_invocation(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), \
                 patch.object(RUNNER, "acquire_token", return_value=None), \
                 patch.object(RUNNER.subprocess, "run") as invoke:
                code, manifest_path = RUNNER.run_sequence("s11-no-token")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            invoke.assert_not_called()
            self.assertTrue(all(row["status"] == "skipped" for row in manifest["rows"]))

    def test_initial_topology_failure_prevents_token_request(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value="not ready"), \
                 patch.object(RUNNER, "acquire_token") as token:
                code, manifest_path = RUNNER.run_sequence("s11-no-topology")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(code, 1)
            token.assert_not_called()
            self.assertEqual(manifest["preflight_topology"], "failed")
            self.assertTrue(all(row["status"] == "skipped" for row in manifest["rows"]))

    def test_interruption_preserves_active_artifacts_and_skips_only_later_rows(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            calls = 0

            def fake_run(command: list[str], **_: object) -> object:
                nonlocal calls
                calls += 1
                if calls == 2:
                    marker = command[-1]
                    instances = int(command[command.index("--instances") + 1])
                    repetition = int(command[command.index("--rep") + 1])
                    paths = RUNNER.artifact_paths(marker, instances, repetition)
                    paths["measured_raw"].write_text("partial", encoding="utf-8")
                    paths["result_json"].write_text(json.dumps(complete_document(instances, repetition, marker=marker)), encoding="utf-8")
                    raise KeyboardInterrupt
                marker = command[-1]
                instances = int(command[command.index("--instances") + 1])
                repetition = int(command[command.index("--rep") + 1])
                paths = RUNNER.artifact_paths(marker, instances, repetition)
                paths["result_json"].write_text(json.dumps(complete_document(instances, repetition, marker=marker)), encoding="utf-8")
                return type("Result", (), {"returncode": 0})()

            with patch.object(RUNNER, "RESULTS", results), \
                 patch.object(RUNNER, "NGINX_LOG", results / "access.log"), \
                 patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), \
                 patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", return_value={"availability": "unavailable", "phases": {}}):
                code, manifest_path = RUNNER.run_sequence("s11-interrupt")
            rows = json.loads(manifest_path.read_text(encoding="utf-8"))["rows"]
            self.assertEqual(code, 130)
            self.assertEqual(rows[0]["status"], "complete")
            self.assertEqual(rows[1]["status"], "interrupted")
            self.assertTrue(rows[1]["raw_files"][0].endswith(".txt"))
            self.assertTrue(rows[1]["result_files"])
            self.assertTrue(all(row["status"] == "skipped" for row in rows[2:]))

    def test_nginx_diagnostics_separate_phases_and_preserve_non_2xx(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            log = Path(directory) / "access.log"
            marker = "s11-log-o1"
            records = [
                {"request": f"GET /postings?bench={marker}&phase=warmup HTTP/1.1", "status": 200,
                 "upstream_status": "200", "upstream_addr": "backend-1:8000", "time": "now", "request_time": "0.1"},
                {"request": f"GET /postings?bench={marker}&phase=measured HTTP/1.1", "status": "503",
                 "upstream_status": "503", "upstream_addr": "backend-2:8000", "time": "now", "request_time": "0.2"},
            ]
            log.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
            with patch.object(RUNNER, "NGINX_LOG", log):
                diagnostics = RUNNER.read_nginx_diagnostics(marker, {"warmup": 1, "measured": 1})
            self.assertEqual(diagnostics["availability"], "complete")
            self.assertEqual(diagnostics["phases"]["warmup"]["status_counts"], {"200": 1})
            self.assertEqual(diagnostics["phases"]["measured"]["status_counts"], {"503": 1})
            self.assertEqual(diagnostics["phases"]["measured"]["non_2xx_excerpt"][0]["upstream_addr"], "backend-2:8000")

    def test_nginx_diagnostics_marks_missing_or_malformed_logs_unavailable_or_incomplete(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            log = Path(directory) / "access.log"
            with patch.object(RUNNER, "NGINX_LOG", log):
                self.assertEqual(RUNNER.read_nginx_diagnostics("s11-log", {"warmup": 1, "measured": 1})["availability"], "unavailable")
            log.write_text('{"request":"GET /postings?bench=s11-log&phase=warmup HTTP/1.1","status":"bad"}\n', encoding="utf-8")
            with patch.object(RUNNER, "NGINX_LOG", log), patch.object(RUNNER, "LOG_SETTLE_SECONDS", 0):
                self.assertEqual(RUNNER.read_nginx_diagnostics("s11-log", {"warmup": 1, "measured": 1})["availability"], "incomplete")

    def test_postprocessing_exception_marks_active_row_failed(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            def fake_run(command: list[str], **_: object) -> object:
                marker = command[-1]; instances = int(command[command.index("--instances") + 1]); repetition = int(command[command.index("--rep") + 1])
                paths = RUNNER.artifact_paths(marker, instances, repetition)
                paths["measured_raw"].write_text("partial", encoding="utf-8")
                paths["result_json"].write_text(json.dumps(complete_document(instances, repetition, marker=marker)), encoding="utf-8")
                return type("Result", (), {"returncode": 0})()
            with patch.object(RUNNER, "RESULTS", results), patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), patch.object(RUNNER, "compose_contract_ok", return_value=True), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", side_effect=RuntimeError("fixture")):
                code, manifest_path = RUNNER.run_sequence("s11-post")
            rows = json.loads(manifest_path.read_text(encoding="utf-8"))["rows"]
            self.assertEqual(code, 1)
            self.assertEqual(rows[0]["status"], "failed")
            self.assertTrue(rows[0]["result_files"])
            self.assertTrue(all(row["status"] == "skipped" for row in rows[1:]))

    def test_interrupt_during_diagnostics_does_not_finalize_active_row(self) -> None:
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            results = Path(directory)
            def fake_run(command: list[str], **_: object) -> object:
                marker = command[-1]; instances = int(command[command.index("--instances") + 1]); repetition = int(command[command.index("--rep") + 1])
                paths = RUNNER.artifact_paths(marker, instances, repetition)
                paths["measured_raw"].write_text("partial", encoding="utf-8")
                paths["result_json"].write_text(json.dumps(complete_document(instances, repetition, marker=marker)), encoding="utf-8")
                return type("Result", (), {"returncode": 0})()
            with patch.object(RUNNER, "RESULTS", results), patch.object(RUNNER.loadtest, "RESULTS", results), \
                 patch.object(RUNNER.loadtest, "activate_topology", return_value=None), patch.object(RUNNER, "compose_contract_ok", return_value=True), \
                 patch.object(RUNNER, "acquire_token", return_value="private-token"), patch.object(RUNNER.subprocess, "run", side_effect=fake_run), \
                 patch.object(RUNNER, "read_nginx_diagnostics", side_effect=KeyboardInterrupt):
                code, manifest_path = RUNNER.run_sequence("s11-diagnostic-interrupt")
            rows = json.loads(manifest_path.read_text(encoding="utf-8"))["rows"]
            self.assertEqual(code, 130)
            self.assertEqual(rows[0]["status"], "interrupted")
            self.assertTrue(rows[0]["result_files"])
            self.assertTrue(all(row["status"] == "skipped" for row in rows[1:]))


if __name__ == "__main__":
    unittest.main()
