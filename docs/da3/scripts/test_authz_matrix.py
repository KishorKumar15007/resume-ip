"""Offline contracts for the DA3 Step 18 authorization-matrix harness."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("authz_matrix.py")
SPEC = importlib.util.spec_from_file_location("authz_matrix_under_test", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Unable to load authorization matrix harness")
HARNESS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = HARNESS
SPEC.loader.exec_module(HARNESS)


class AuthorizationMatrixOfflineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_results, self.old_evidence = HARNESS.RESULTS_DIRECTORY, HARNESS.EVIDENCE_DIRECTORY
        self.temporary = tempfile.TemporaryDirectory(dir=SCRIPT.parent)
        root = Path(self.temporary.name)
        HARNESS.RESULTS_DIRECTORY, HARNESS.EVIDENCE_DIRECTORY = root / "results", root / "evidence"

    def tearDown(self) -> None:
        HARNESS.RESULTS_DIRECTORY, HARNESS.EVIDENCE_DIRECTORY = self.old_results, self.old_evidence
        self.temporary.cleanup()

    def test_loopback_and_run_id_guards(self) -> None:
        self.assertEqual(HARNESS.parse_base_url("http://localhost:8080/"), "http://localhost:8080")
        for value in ("https://example.com", "http://localhost:8001", "http://localhost:8080/path", "http://user@localhost:8080"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    HARNESS.parse_base_url(value)
        self.assertEqual(HARNESS.parse_run_id("s18-20261029-a1b2"), "s18-20261029-a1b2")
        for value in ("S18", "ab", "s18_bad", "s18/unsafe"):
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    HARNESS.parse_run_id(value)

    def test_tampered_manifest_and_reused_run_fail_closed(self) -> None:
        manifest = HARNESS.build_manifest("s18-example")
        HARNESS.save_manifest("s18-example", manifest)
        with self.assertRaises(HARNESS.MatrixError):
            HARNESS.assert_unused_run("s18-example")
        manifest["fixture"]["posting_title"] = "different"
        HARNESS.save_manifest("s18-example", manifest)
        with self.assertRaises(HARNESS.MatrixError):
            HARNESS.read_manifest("s18-example")

    def test_attempt_outputs_are_preserved_and_markdown_matches_json(self) -> None:
        row = HARNESS.MatrixResult("PUT /synthetic", "No token", "HTTP 401; WWW-Authenticate: Bearer", "HTTP 401; WWW-Authenticate: Bearer", True)
        HARNESS.write_attempt_results("s18-example", 1, [row], "matrix-predelete")
        with self.assertRaises(HARNESS.MatrixError):
            HARNESS.write_attempt_results("s18-example", 1, [row], "matrix-predelete")
        payload = json.loads(HARNESS.attempt_json_path("s18-example", 1, "matrix-predelete").read_text(encoding="utf-8"))
        markdown = HARNESS.attempt_markdown_path("s18-example", 1, "matrix-predelete").read_text(encoding="utf-8")
        self.assertEqual(payload["overall"], "INCOMPLETE")
        self.assertIn(payload["steps"][0]["request"], markdown)
        self.assertIn(payload["steps"][0]["actual"], markdown)

    def test_canonical_requires_passing_final_owner_delete_and_preserves_prior(self) -> None:
        passing = HARNESS.MatrixResult("DELETE /postings/x", "Recruiter A owner access token", "HTTP 204", "HTTP 204", True)
        HARNESS.promote_canonical("s18-prior", 1, [passing])
        prior = HARNESS.canonical_json_path().read_text(encoding="utf-8")
        failed = HARNESS.MatrixResult("DELETE /postings/x", "Recruiter A owner access token", "HTTP 204", "HTTP 500", False)
        self.assertEqual(HARNESS.overall_for([failed], "final-delete-failed"), "FAIL")
        with self.assertRaises(HARNESS.MatrixError):
            HARNESS.promote_canonical("s18-failed", 1, [failed])
        self.assertEqual(HARNESS.canonical_json_path().read_text(encoding="utf-8"), prior)

    def test_invalid_auth_header_and_transport_error_are_failures(self) -> None:
        self.assertEqual(HARNESS.response_actual(SimpleNamespace(status_code=401, headers={}), True), "HTTP 401; WWW-Authenticate: missing")
        results: list[HARNESS.MatrixResult] = []
        with patch.object(HARNESS.requests, "request", side_effect=HARNESS.requests.RequestException("offline")):
            HARNESS.request_case(results, base_url="http://localhost:8080", method="PUT", path="/postings/x", token_type="Malformed token", token="abc", expected_status=401, require_bearer_header=True)
        self.assertFalse(results[0].passed)
        self.assertIn("request error", results[0].actual)

    def test_capture_gate_requires_each_valid_png(self) -> None:
        HARNESS.EVIDENCE_DIRECTORY.mkdir(parents=True)
        for name in HARNESS.CAPTURE_FILENAMES[:-1]:
            (HARNESS.EVIDENCE_DIRECTORY / name).write_bytes(HARNESS.PNG_SIGNATURE + b"test")
        with self.assertRaises(HARNESS.MatrixError):
            HARNESS.verify_capture_files()
        (HARNESS.EVIDENCE_DIRECTORY / HARNESS.CAPTURE_FILENAMES[-1]).write_bytes(HARNESS.PNG_SIGNATURE + b"test")
        HARNESS.verify_capture_files()

    def test_lifecycle_has_no_interactive_finalization(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("hold" + "-for-captures", source)
        self.assertIn("MFA-scope token", source)
        self.assertIn("verify_capture_files()", source)

    def test_preparation_reserves_exact_ids_for_recovery_and_cleanup_order(self) -> None:
        manifest = HARNESS.build_manifest("s18-recover")
        self.assertEqual(manifest["phase"], "preparing")
        self.assertEqual(manifest["ids"], HARNESS.fixture_ids("s18-recover"))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertLess(source.rindex("submission = session.get"), source.rindex("posting = session.get"))
        self.assertIn("session.rollback()", source)

    def test_database_diagnostic_identifies_operation_and_redacts_sensitive_text(self) -> None:
        cause = RuntimeError("connection failed password=redact-me token=redact-me")
        diagnostic = HARNESS.DatabaseDiagnosticError("checking reserved fixture IDs", cause)
        self.assertIn("checking reserved fixture IDs", str(diagnostic))
        output = HARNESS.diagnostic_text("underlying database error", cause)
        self.assertIn("RuntimeError", output)
        self.assertIn("password=[redacted]", output)
        self.assertIn("token=[redacted]", output)
        self.assertNotIn("redact-me", output)


if __name__ == "__main__":
    unittest.main()
