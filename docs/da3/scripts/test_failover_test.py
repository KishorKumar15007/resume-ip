"""Offline regression tests for DA3 Step 12. No test may invoke Docker or the live API."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).with_name("failover_test.py")
SPEC = importlib.util.spec_from_file_location("da3_failover_under_test", SOURCE)
assert SPEC and SPEC.loader
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


def completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["mocked"], returncode, stdout, stderr)


def metrics(requests: int, *, completed_requests: int | None = None, failed: int | None = 0,
            non_2xx: int | None = 0, return_code: int = 0, timed_out: bool = False,
            interrupted: bool = False, execution_error: str | None = None,
            launched: bool = True) -> HARNESS.loadtest.Metrics:
    return HARNESS.loadtest.Metrics(
        requests=requests,
        completed_requests=completed_requests,
        requests_per_second="20.00",
        mean_time_per_request_ms="50.00",
        failed_requests=failed,
        connect_failures=0,
        receive_failures=0,
        length_failures=0,
        exception_failures=failed,
        non_2xx_responses=non_2xx,
        return_code=return_code,
        launched=launched,
        interrupted=interrupted,
        timed_out=timed_out,
        execution_error=execution_error,
    )


def complete_ab_output(requests: int, failed: int = 0, non_2xx: int = 0) -> list[str]:
    completed_count = requests - failed
    return [
        f"Complete requests: {completed_count}\n",
        f"Failed requests: {failed} (Connect: 0, Receive: 0, Length: 0, Exceptions: {failed})\n",
        f"Requests per second: 20.00 [#/sec] (mean)\n",
        "Time per request: 50.00 [ms] (mean)\n",
        f"Non-2xx responses: {non_2xx}\n",
    ]


class FakeProcess:
    def __init__(self, lines, *, delay_after: str | None = None, delay: float = 0.0):
        self.stdout = self._stream(lines, delay_after, delay)
        self.returncode = None
        self.terminated = False
        self.killed = False

    def _stream(self, lines, delay_after, delay):
        for line in lines:
            yield line
            if delay_after is not None and delay_after in line and delay:
                time.sleep(delay)

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        if self.returncode is None:
            self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


class FailoverTests(unittest.TestCase):
    def setUp(self):
        # Every test starts with external effects forbidden. Individual tests may replace
        # these boundaries with explicit mocks, never with the real implementation.
        self._external_guards = [
            patch.object(HARNESS, "compose", side_effect=AssertionError("unmocked Compose call")),
            patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("unmocked subprocess.run")),
            patch.object(HARNESS.subprocess, "Popen", side_effect=AssertionError("unmocked subprocess.Popen")),
            patch.object(HARNESS, "urlopen", side_effect=AssertionError("unmocked live API call")),
        ]
        for guard in self._external_guards:
            guard.start()

    def tearDown(self):
        for guard in reversed(self._external_guards):
            guard.stop()

    def test_only_approved_profiles_are_accepted(self):
        self.assertEqual(HARNESS.profile("default"), "default")
        self.assertEqual(HARNESS.profile("baseline"), "baseline")
        with self.assertRaises(Exception):
            HARNESS.profile("after")

    def test_default_and_baseline_configs_have_the_locked_directives(self):
        default = (HARNESS.ROOT / "nginx" / "nginx-3-default.conf").read_text(encoding="utf-8")
        baseline = (HARNESS.ROOT / "nginx" / "nginx-3-baseline.conf").read_text(encoding="utf-8")
        self.assertEqual(default.count("server backend-"), 3)
        self.assertNotIn("max_fails=0", default)
        self.assertNotIn("proxy_next_upstream", default)
        self.assertNotIn("proxy_connect_timeout 2s", default)
        self.assertEqual(baseline.count("server backend-"), 3)
        self.assertEqual(baseline.count("max_fails=0"), 3)
        self.assertIn("proxy_next_upstream off;", baseline)
        self.assertIn("proxy_connect_timeout 2s;", baseline)

        canonical = (HARNESS.ROOT / "nginx" / "nginx-3.conf").read_text(encoding="utf-8")
        host_directive = "proxy_set_header Host $http_host;"
        self.assertIn(host_directive, canonical)
        self.assertIn(host_directive, default)
        self.assertIn(host_directive, baseline)
        self.assertNotIn("proxy_set_header Host $host;", default)
        self.assertNotIn("proxy_set_header Host $host;", baseline)

    def test_ab_command_uses_locked_flags_numbers_and_safe_token_reference(self):
        command = HARNESS.ab_command(HARNESS.MEASURED, "s12-test-r1-abcdef1234", "measured")
        shell = command[-1]
        self.assertIn("ab -k -r -n 1000 -c 20", shell)
        self.assertIn("DA3_AB_START:s12-test-r1-abcdef1234:measured", shell)
        self.assertIn("DA3_AB_END:s12-test-r1-abcdef1234:measured:", shell)
        self.assertIn('"Authorization: Bearer $LOADTEST_TOKEN"', shell)
        self.assertNotIn("LOADTEST_TOKEN=private", " ".join(command))
        self.assertAlmostEqual(HARNESS.ESTIMATED_MEASURED_SECONDS, 1000 / 24.88)

    def test_backend_identity_rejects_ambiguous_service_without_docker(self):
        listing = completed("one\ntwo\n")
        with patch.object(HARNESS, "compose", return_value=listing), \
             patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("unexpected Docker command")):
            identity, reason = HARNESS.backend_two_id()
        self.assertIsNone(identity)
        self.assertIn("backend-2", reason or "")

    def test_backend_identity_rejects_wrong_compose_labels(self):
        listing = completed("0123456789ab\n")
        labels = completed(json.dumps({
            "com.docker.compose.service": "backend-1", "com.docker.compose.project": "resume-ip",
        }))
        running = completed("true\n")
        with patch.object(HARNESS, "compose", return_value=listing), \
             patch.object(HARNESS.subprocess, "run", side_effect=[labels, running]), \
             patch.object(HARNESS.loadtest, "project_name", return_value="resume-ip"):
            identity, reason = HARNESS.backend_two_id()
        self.assertIsNone(identity)
        self.assertIn("labels", reason or "")

    def test_profile_verification_checks_the_effective_profile_not_just_mount(self):
        default_text = (HARNESS.ROOT / "nginx" / "nginx-3-default.conf").read_text(encoding="utf-8")
        baseline_text = (HARNESS.ROOT / "nginx" / "nginx-3-baseline.conf").read_text(encoding="utf-8")
        source = completed(str(HARNESS.ROOT / "nginx" / "nginx-3-default.conf"))
        with patch.object(HARNESS, "compose", side_effect=[completed("# configuration file /etc/nginx/conf.d/default.conf:\n" + default_text), completed("abcdef1234567890\n")]), \
             patch.object(HARNESS.subprocess, "run", return_value=source):
            self.assertTrue(HARNESS.nginx_profile_loaded("default"))
        # A file path can say default while the effective content is actually baseline.
        with patch.object(HARNESS, "compose", side_effect=[completed("# configuration file /etc/nginx/conf.d/default.conf:\n" + baseline_text), completed("abcdef1234567890\n")]), \
             patch.object(HARNESS.subprocess, "run", return_value=source):
            self.assertFalse(HARNESS.nginx_profile_loaded("default"))

    def test_canonical_profile_verifier_accepts_canonical_host_header(self):
        canonical_text = (HARNESS.ROOT / "nginx" / "nginx-3.conf").read_text(encoding="utf-8")
        source = completed(str(HARNESS.ROOT / "nginx" / "nginx-3.conf"))
        with patch.object(HARNESS, "compose", side_effect=[
            completed("# configuration file /etc/nginx/conf.d/default.conf:\n" + canonical_text),
            completed("abcdef1234567890\n"),
        ]), patch.object(HARNESS.subprocess, "run", return_value=source):
            self.assertTrue(HARNESS.nginx_profile_loaded("canonical"))

    def test_docker_desktop_mount_alias_matches_windows_source_path(self):
        expected = r"C:\Github\Repos\resume-ip\nginx\nginx-3-default.conf"
        docker_desktop = "/run/desktop/mnt/host/c/Github/Repos/resume-ip/nginx/nginx-3-default.conf"
        host_mnt = "/host_mnt/c/Github/Repos/resume-ip/nginx/nginx-3-default.conf"
        self.assertEqual(HARNESS._normalise_mount_path(expected), HARNESS._normalise_mount_path(docker_desktop))
        self.assertEqual(HARNESS._normalise_mount_path(expected), HARNESS._normalise_mount_path(host_mnt))

    def test_loadtest_token_is_scoped_to_child_environment_not_parent_or_argv(self):
        marker = "s12-run-r1-envscope"
        stream = [f"DA3_AB_START:{marker}:warmup\n", *complete_ab_output(100),
                  f"DA3_AB_END:{marker}:warmup:0\n"]
        process = FakeProcess(stream)
        token = "mock-token-do-not-log"
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS.subprocess, "Popen", return_value=process) as popen, \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            before = HARNESS.os.environ.get("LOADTEST_TOKEN")
            raw_path = Path(directory) / "warmup.txt"
            HARNESS.run_ab(100, marker, "warmup", raw_path, token=token)
            self.assertEqual(HARNESS.os.environ.get("LOADTEST_TOKEN"), before)
            saved = raw_path.read_text(encoding="utf-8")
        argv = popen.call_args.args[0]
        child_env = popen.call_args.kwargs["env"]
        self.assertNotIn(token, " ".join(argv))
        self.assertEqual(child_env["LOADTEST_TOKEN"], token)
        self.assertNotIn(token, saved)

    def test_missing_external_env_file_blocks_preflight_before_any_external_command(self):
        with patch.dict(HARNESS.os.environ, {"DA3_LOADTEST_ENV_FILE": ""}), \
             patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("unexpected subprocess")), \
             patch.object(HARNESS.subprocess, "Popen", side_effect=AssertionError("unexpected child process")):
            reason = HARNESS.preflight_error("default", 1)
        self.assertIn("environment file", reason or "")

    def test_request_accounting_accepts_complete_measured_run_with_expected_failures(self):
        observed = metrics(1000, completed_requests=990, failed=10, non_2xx=4)
        self.assertTrue(HARNESS.metrics_accounted(observed, 1000))
        self.assertFalse(HARNESS.metrics_accounted(metrics(1000, completed_requests=980, failed=10), 1000))
        self.assertFalse(HARNESS.metrics_accounted(metrics(1000, completed_requests=1000, timed_out=True), 1000))
        self.assertFalse(HARNESS.metrics_accounted(metrics(1000, completed_requests=None), 1000))
        self.assertTrue(HARNESS.metrics_accounted(metrics(100, completed_requests=100), 100, warmup=True))
        self.assertFalse(HARNESS.metrics_accounted(metrics(100, completed_requests=100, failed=1), 100, warmup=True))

    def test_diagnostics_usable_rejects_partial_or_unparseable_evidence(self):
        valid = {
            "warmup": {"availability": "readable", "matching_lines": 100},
            "measured": {"availability": "readable", "matching_lines": 1000},
        }
        self.assertTrue(HARNESS.diagnostics_usable(valid))
        malformed = json.loads(json.dumps(valid))
        malformed["measured"]["malformed_lines"] = 1
        self.assertFalse(HARNESS.diagnostics_usable(malformed))
        unparseable = json.loads(json.dumps(valid))
        unparseable["warmup"]["unparseable_statuses"] = 1
        self.assertFalse(HARNESS.diagnostics_usable(unparseable))
        unavailable = json.loads(json.dumps(valid))
        unavailable["measured"]["availability"] = "readable-no-matching-records"
        self.assertFalse(HARNESS.diagnostics_usable(unavailable))

    def test_run_ab_raw_file_excludes_compose_banners_and_sentinels(self):
        marker = "s12-run-r1-abcd123456"
        stream = ["Container loadtest Creating\n", f"DA3_AB_START:{marker}:warmup\n",
                  *complete_ab_output(100), f"DA3_AB_END:{marker}:warmup:0\n", "Container loadtest Exited\n"]
        process = FakeProcess(stream)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS.subprocess, "Popen", return_value=process), \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            raw = Path(directory) / "warmup.txt"
            item, result = HARNESS.run_ab(100, marker, "warmup", raw, token="mock-token")
            saved = raw.read_text(encoding="utf-8")
        self.assertNotIn("Container loadtest", saved)
        self.assertNotIn("DA3_AB_START", saved)
        self.assertNotIn("DA3_AB_END", saved)
        self.assertIn("Complete requests: 100", saved)
        self.assertTrue(item.launched)
        self.assertTrue(result["end_sentinel_seen"])
        self.assertTrue(result["reader_joined"])
        self.assertTrue(result["cleanup_verified"])

    def test_run_ab_launch_failure_still_attempts_label_scoped_cleanup(self):
        marker = "s12-run-r1-launchfail"
        cleanup = SimpleNamespace(verified=True)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS.subprocess, "Popen", side_effect=OSError("private detail")), \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=cleanup) as cleanup_mock:
            item, result = HARNESS.run_ab(100, marker, "warmup", Path(directory) / "warmup.txt", token="mock-token")
        cleanup_mock.assert_called_once_with(marker)
        self.assertFalse(item.launched)
        self.assertIn("could not be prepared or launched", item.execution_error or "")
        self.assertTrue(result["cleanup_verified"])

    def test_run_ab_timeout_preserves_partial_ab_output_and_joins_reader(self):
        marker = "s12-run-r1-timeout"
        stream = ["Container creating\n", f"DA3_AB_START:{marker}:measured\n",
                  "Complete requests: 400\n", "Requests per second: 1.0 [#/sec] (mean)\n",
                  "Time per request: 1000.0 [ms] (mean)\n", "Failed requests: 0\n", "Non-2xx responses: 0\n",
                  f"DA3_AB_END:{marker}:measured:0\n"]
        process = FakeProcess(stream, delay_after="Complete requests", delay=0.15)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS, "FAILOVER_TIMEOUT_SECONDS", 0.04), \
             patch.object(HARNESS.subprocess, "Popen", return_value=process), \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            raw = Path(directory) / "measured.txt"
            item, result = HARNESS.run_ab(1000, marker, "measured", raw, token="mock-token")
            saved = raw.read_text(encoding="utf-8")
        self.assertTrue(item.timed_out)
        self.assertIn("exceeded the 0.04-second", item.execution_error or "")
        self.assertIn("Complete requests: 400", saved)
        self.assertNotIn("Container creating", saved)
        self.assertTrue(result["reader_joined"])

    def test_run_ab_keyboard_interrupt_cancels_pending_kill_and_cleans_up(self):
        marker = "s12-run-r1-interrupted"
        class InterruptAfterStartQueue(HARNESS.queue.Queue):
            def __init__(self):
                super().__init__()
                self.start_seen = False
                self.interruption_sent = False
            def get(self, *args, **kwargs):
                # Allow the start sentinel through so the real timer is scheduled;
                # then simulate Ctrl+C on the next blocking consumer wait. Do not
                # inject KeyboardInterrupt into the final nonblocking queue drain.
                if kwargs.get("timeout") is not None and self.start_seen and not self.interruption_sent:
                    self.interruption_sent = True
                    raise KeyboardInterrupt()
                item = super().get(*args, **kwargs)
                if (item[0] == "line" and item[1]
                        and item[1].strip() == f"DA3_AB_START:{marker}:measured"):
                    self.start_seen = True
                return item
        process = FakeProcess([f"DA3_AB_START:{marker}:measured\n", "Complete requests: 200\n"])
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS, "KILL_OFFSET_SECONDS", 10.0), \
             patch.object(HARNESS.queue, "Queue", InterruptAfterStartQueue), \
             patch.object(HARNESS.subprocess, "Popen", return_value=process), \
             patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("aborted run must not kill a container")), \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            raw = Path(directory) / "measured.txt"
            item, result = HARNESS.run_ab(1000, marker, "measured", raw,
                                          "verified-container-id", token="mock-token")
            saved = raw.read_text(encoding="utf-8")
        self.assertTrue(item.interrupted)
        self.assertTrue(process.terminated)
        self.assertTrue(result["cleanup_verified"])
        self.assertTrue(result["reader_joined"])
        self.assertTrue(result["timer_joined"])
        self.assertIn("did not execute", result["error"] or "")
        self.assertIn("Complete requests: 200", saved)

    def test_run_ab_kill_starts_after_sentinel_and_is_verified(self):
        marker = "s12-run-r1-kill"
        stream = ["Compose Creating\n", f"DA3_AB_START:{marker}:measured\n",
                  "Complete requests: 1000\n", "Failed requests: 0\n",
                  "Requests per second: 20.00 [#/sec] (mean)\n", "Time per request: 50.00 [ms] (mean)\n",
                  "Non-2xx responses: 0\n", f"DA3_AB_END:{marker}:measured:0\n"]
        process = FakeProcess(stream, delay_after="Complete requests", delay=0.08)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS, "KILL_OFFSET_SECONDS", 0.01), \
             patch.object(HARNESS.subprocess, "Popen", return_value=process), \
             patch.object(HARNESS.subprocess, "run", side_effect=[completed(), completed("false\n")]) as run_mock, \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            item, result = HARNESS.run_ab(1000, marker, "measured", Path(directory) / "measured.txt", "verified-container-id", token="mock-token")
        self.assertTrue(item.launched)
        self.assertEqual(run_mock.call_count, 2)
        self.assertTrue(result["start_sentinel_seen"])
        self.assertTrue(result["end_sentinel_seen"])
        self.assertTrue(result["stopped_verified"])
        self.assertEqual(result["return_code"], 0)
        self.assertTrue(result["timer_joined"])
        self.assertTrue(result["reader_joined"])
        self.assertIsNone(result["error"])

    def test_run_ab_early_exit_cancels_timer_and_invalidates_experiment(self):
        marker = "s12-run-r1-early"
        stream = [f"DA3_AB_START:{marker}:measured\n", *complete_ab_output(1000),
                  f"DA3_AB_END:{marker}:measured:0\n"]
        process = FakeProcess(stream)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS, "KILL_OFFSET_SECONDS", 10.0), \
             patch.object(HARNESS.subprocess, "Popen", return_value=process), \
             patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("kill should not have fired")), \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            item, result = HARNESS.run_ab(1000, marker, "measured", Path(directory) / "measured.txt", "verified-container-id", token="mock-token")
        self.assertTrue(result["timer_joined"])
        self.assertIn("did not execute", result["error"] or "")
        self.assertIsNotNone(item.execution_error)

    def test_run_ab_refuses_a_late_timer_callback_after_end_sentinel(self):
        marker = "s12-run-r1-latekill"
        end_sentinel = f"DA3_AB_END:{marker}:measured:0"
        stream = [f"DA3_AB_START:{marker}:measured\n", *complete_ab_output(1000),
                  end_sentinel + "\n"]
        process = FakeProcess(stream, delay_after=end_sentinel, delay=0.06)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(HARNESS, "KILL_OFFSET_SECONDS", 0.01), \
             patch.object(HARNESS.subprocess, "Popen", return_value=process), \
             patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("late kill must not execute")) as run_mock, \
             patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
            item, result = HARNESS.run_ab(1000, marker, "measured", Path(directory) / "measured.txt",
                                          "verified-container-id", token="mock-token")
        run_mock.assert_not_called()
        self.assertTrue(result["end_sentinel_seen"])
        self.assertTrue(result["late_kill_refused"])
        self.assertTrue(result["timer_joined"])
        self.assertIn("late kill was refused", result["error"] or "")
        self.assertIsNotNone(item.execution_error)

    def test_run_ab_nonzero_or_missing_end_sentinel_is_invalid(self):
        for marker, stream in (
            ("s12-nonzero", [f"DA3_AB_START:s12-nonzero:warmup\n", *complete_ab_output(100), f"DA3_AB_END:s12-nonzero:warmup:2\n"]),
            ("s12-noend", [f"DA3_AB_START:s12-noend:warmup\n", *complete_ab_output(100)]),
        ):
            process = FakeProcess(stream)
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory, \
                 patch.object(HARNESS.subprocess, "Popen", return_value=process), \
                 patch.object(HARNESS.loadtest, "cleanup_invocation", return_value=SimpleNamespace(verified=True)):
                item, result = HARNESS.run_ab(100, marker, "warmup", Path(directory) / "warmup.txt", token="mock-token")
            self.assertIsNotNone(item.execution_error)
            self.assertTrue(result["cleanup_verified"])

    def test_access_diagnostics_are_phase_separated_and_count_502_504(self):
        marker = "s12-diagnostics"
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "access.jsonl"
            rows = [
                {"request": f"GET /postings?bench={marker}&phase=warmup HTTP/1.0", "status": "200", "upstream_status": "200"},
                {"request": f"GET /postings?bench={marker}&phase=measured HTTP/1.0", "status": "502", "upstream_status": "502"},
                {"request": f"GET /postings?bench={marker}&phase=measured HTTP/1.0", "status": "504", "upstream_status": "504"},
            ]
            log.write_text("\n".join(json.dumps(row) for row in rows) + f"\nmalformed bench={marker}&phase=measured\n", encoding="utf-8")
            with patch.object(HARNESS, "NGINX_LOG", log):
                report = HARNESS.nginx_diagnostics(marker)
        self.assertEqual(report["warmup"]["status_counts"], {"200": 1})
        self.assertEqual(report["measured"]["502_count"], 1)
        self.assertEqual(report["measured"]["504_count"], 1)
        self.assertEqual(report["measured"]["malformed_lines"], 1)
        self.assertEqual(report["warmup"]["malformed_lines"], 0)

    def test_error_excerpt_requires_marker_phase_and_actual_error_severity(self):
        marker = "s12-errorcapture"
        logs = "\n".join([
            f'2026-10-24T10:00:00Z stderr F 2026/10/24 [error] 1#1: connect failed, request: "GET /postings?bench={marker}&phase=measured HTTP/1.1"',
            f'2026-10-24T10:00:01Z stdout F {{"request":"GET /postings?bench={marker}&phase=measured HTTP/1.0","status":502}}',
            '2026-10-24T10:00:02Z stderr F 2026/10/24 [error] 1#1: unrelated upstream failed',
        ])
        labels = completed(json.dumps({
            "com.docker.compose.service": "nginx", "com.docker.compose.project": HARNESS.loadtest.project_name(),
        }))
        with patch.object(HARNESS, "compose", return_value=completed("abcdef1234567890\n")), \
             patch.object(HARNESS.subprocess, "run", side_effect=[labels, completed("true\n"), completed(logs)]) as run_mock:
            text, state = HARNESS.nginx_error_excerpt(marker, "2026-10-24T09:59:00+00:00", "2026-10-24T10:01:00+00:00")
        self.assertEqual(state["availability"], "captured")
        self.assertIn("[error]", text)
        self.assertIn("phase=measured", text)
        self.assertNotIn('"status":502', text)
        self.assertNotIn("unrelated upstream", text)
        command = run_mock.call_args_list[-1].args[0]
        self.assertIn("--since", command)
        self.assertIn("--until", command)

    def test_token_failure_does_not_mutate_runtime_or_restore_canonical(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory, \
             patch.object(HARNESS, "RESULTS", Path(directory)), \
             patch.object(HARNESS, "preflight_error", return_value=None), \
             patch.object(HARNESS, "acquire_token", return_value=None), \
             patch.object(HARNESS, "activate") as activate, \
             patch.object(HARNESS, "restore_canonical") as restore, \
             patch.object(HARNESS, "nginx_error_excerpt", side_effect=AssertionError("must not capture runtime logs")), \
             patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("unexpected Docker/API subprocess")), \
             patch.object(HARNESS.subprocess, "Popen", side_effect=AssertionError("unexpected child process")), \
             patch.object(HARNESS, "urlopen", side_effect=AssertionError("unexpected live API")):
            code, document = HARNESS.execute("default", 1)
        self.assertEqual(code, 1)
        self.assertEqual(document["canonical_restoration"], "not needed")
        self.assertEqual(document["completion"], "incomplete")
        self.assertEqual(document["traffic"]["skipped_warmup"], HARNESS.WARMUP)
        self.assertEqual(document["traffic"]["skipped_measured"], HARNESS.MEASURED)
        self.assertEqual(document["traffic"]["skipped"], HARNESS.WARMUP + HARNESS.MEASURED)
        activate.assert_not_called()
        restore.assert_not_called()

    def _run_mocked_complete_experiment(self, directory: str, *, restore_ok: bool = True,
                                       timer_joined: bool = True):
        marker_state = {"order": []}
        def fake_run_ab(requests, marker, phase, raw, kill_id=None, *, token):
            Path(raw).write_text("mock AB evidence\n", encoding="utf-8")
            if phase == "warmup":
                return metrics(requests, completed_requests=requests), {}
            marker_state["order"].append("measured")
            return metrics(requests, completed_requests=995, failed=5, non_2xx=3), {
                "error": None, "cleanup_verified": True, "start_sentinel_seen": True,
                "end_sentinel_seen": True, "ab_exit_status": "0", "timer_joined": timer_joined,
                "reader_joined": True, "actual_elapsed_seconds": 12.06, "return_code": 0,
                "stopped_verified": True,
            }
        diagnostics = {
            "warmup": {"availability": "readable", "matching_lines": 100, "status_counts": {"200": 100}},
            "measured": {"availability": "readable", "matching_lines": 1000, "status_counts": {"200": 995, "502": 5}, "502_count": 5, "504_count": 0},
        }
        def capture_error(*args):
            marker_state["order"].append("error-log")
            return "No matching Nginx errors.\n", {"availability": "captured-no-matching-lines"}
        def restore():
            marker_state["order"].append("restore")
            return restore_ok
        patches = [
            patch.object(HARNESS, "RESULTS", Path(directory)),
            patch.object(HARNESS, "preflight_error", return_value=None),
            patch.object(HARNESS, "acquire_token", return_value="private-token-not-to-log"),
            patch.object(HARNESS, "activate", return_value=None),
            patch.object(HARNESS, "run_ab", side_effect=fake_run_ab),
            patch.object(HARNESS, "backend_two_id", return_value=("0123456789abcdef", None)),
            patch.object(HARNESS, "nginx_diagnostics", return_value=diagnostics),
            patch.object(HARNESS, "nginx_error_excerpt", side_effect=capture_error),
            patch.object(HARNESS, "recover_backend_two", return_value=None),
            patch.object(HARNESS, "restore_canonical", side_effect=restore),
            patch.object(HARNESS.subprocess, "run", side_effect=AssertionError("unexpected Docker/API subprocess")),
            patch.object(HARNESS.subprocess, "Popen", side_effect=AssertionError("unexpected child process")),
            patch.object(HARNESS, "urlopen", side_effect=AssertionError("unexpected live API")),
        ]
        return patches, marker_state

    def test_complete_experiment_accepts_observed_measurement_failures_and_logs_before_restore(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            patches, state = self._run_mocked_complete_experiment(directory)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
                code, document = HARNESS.execute("baseline", 1)
            self.assertEqual(code, 0)
            self.assertEqual(document["completion"], "complete")
            self.assertEqual(document["measured"]["failed_requests"], 5)
            self.assertEqual(document["measured"]["non_2xx_responses"], 3)
            self.assertLess(state["order"].index("error-log"), state["order"].index("restore"))
            self.assertTrue(Path(directory, Path(document["artifacts"]["result_json"]).name).exists())

    def test_failed_canonical_restoration_invalidates_experiment_and_exit(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            patches, _ = self._run_mocked_complete_experiment(directory, restore_ok=False)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8], patches[9], patches[10], patches[11], patches[12]:
                code, document = HARNESS.execute("baseline", 1)
        self.assertEqual(code, 1)
        self.assertEqual(document["completion"], "incomplete")
        self.assertFalse(document["canonical_restoration"])
        self.assertIn("restoration", document["error"] or "")

    def test_unjoined_kill_callback_blocks_backend_recovery_and_restoration(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            patches, _ = self._run_mocked_complete_experiment(directory, timer_joined=False)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], \
                 patches[8] as recover_mock, patches[9] as restore_mock, patches[10], patches[11], patches[12]:
                code, document = HARNESS.execute("baseline", 1)
        self.assertEqual(code, 1)
        self.assertTrue(document["runtime_state_uncertain"])
        self.assertIn("not attempted", document["canonical_restoration"])
        recover_mock.assert_not_called()
        restore_mock.assert_not_called()

    def test_diagnostic_exception_does_not_skip_recovery_or_restoration(self):
        with tempfile.TemporaryDirectory(dir=SOURCE.parent) as directory:
            patches, _ = self._run_mocked_complete_experiment(directory)
            patches[6] = patch.object(HARNESS, "nginx_diagnostics", side_effect=RuntimeError("mocked diagnostic failure"))
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], \
                 patches[8] as recover_mock, patches[9] as restore_mock, patches[10], patches[11], patches[12]:
                code, document = HARNESS.execute("baseline", 1)
        self.assertEqual(code, 1)
        self.assertEqual(document["recovery"], "verified")
        self.assertTrue(document["canonical_restoration"])
        recover_mock.assert_called_once()
        restore_mock.assert_called_once()
        self.assertEqual(document["completion"], "incomplete")

    def test_collision_checks_atomic_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "result.json"
            temp = target.with_suffix(".json.tmp")
            temp.write_text("existing", encoding="utf-8")
            self.assertIn("result.json.tmp", HARNESS.collision({"result_json": target}) or "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
