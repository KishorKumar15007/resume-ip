"""Offline regression tests for deterministic, safe Trivy summary parsing."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import summarize_trivy as SUMMARY  # noqa: E402


def metadata(status: str = "success") -> dict[str, object]:
    return {"status": status, "exit_status": 0 if status == "success" else 1, "label": "fixture",
        "scan_timestamp": "2026-10-29T00:00:00Z", "image": {"reference": "fixture:image", "id": "sha256:fixture", "size_bytes": 1, "configured_user": "root"},
        "trivy": {"image": "fixture@sha256:pin", "version": "0.76.1"},
        "database_metadata": {"SchemaVersion": 2}, "database_snapshot": {"schema_version": 2, "version": 2, "updated_at": "fixture"},
        "trivy_db_sha256": "a" * 64, "scan_arguments": ["image", "--format", "json"],
        "base_images": [{"declared_from": "python:3.12", "resolved_id": "sha256:base", "platform": {"os": "linux", "architecture": "amd64"}}]}


def finding(identifier: str, package: str, severity: str, package_class: str = "os-pkgs") -> dict[str, str]:
    return {"VulnerabilityID": identifier, "PkgName": package, "InstalledVersion": "1", "FixedVersion": "2", "Severity": severity, "Class": package_class}


class SummaryTests(unittest.TestCase):
    def test_zero_finding_is_distinct_valid_success(self) -> None:
        data = SUMMARY.summary_data({"SchemaVersion": 2, "Results": []}, metadata())
        self.assertEqual(data["by_severity"], {"CRITICAL": 0, "HIGH": 0})

    def test_multiple_targets_and_duplicate_cves_remain_raw_occurrences(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [{"Target": "a", "Vulnerabilities": [finding("CVE-1", "pkg", "CRITICAL"), finding("CVE-2", "pkg", "HIGH")]}, {"Target": "b", "Vulnerabilities": [finding("CVE-1", "pkg", "CRITICAL"), finding("CVE-3", "lang", "HIGH", "lang-pkgs")]}]}
        data = SUMMARY.summary_data(raw, metadata())
        self.assertEqual(data["by_severity"], {"CRITICAL": 2, "HIGH": 2})
        self.assertEqual(data["top_packages"][0]["occurrences"], 3)
        self.assertEqual(data["top_packages"][0]["identifier"], "CVE-1")

    def test_unknown_class_and_special_characters_are_preserved_safely(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [{"Vulnerabilities": [finding("CVE|1", "pkg|line\nnext", "HIGH", "other")] }]}
        self.assertEqual(SUMMARY.summary_data(raw, metadata())["by_class"]["unknown"]["HIGH"], 1)
        text = SUMMARY.markdown(raw, metadata())
        self.assertIn("unknown", text)
        self.assertIn("pkg\\|line next", text)

    def test_result_level_class_is_inherited_by_vulnerabilities(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [{"Class": "os-pkgs", "Vulnerabilities": [finding("CVE-1", "pkg", "HIGH", "")] }]}
        self.assertEqual(SUMMARY.summary_data(raw, metadata())["by_class"]["os-pkgs"]["HIGH"], 1)

    def test_malformed_raw_or_missing_metadata_or_failed_status_is_rejected(self) -> None:
        with self.assertRaises(SUMMARY.SummaryError):
            SUMMARY.summary_data({"Results": []}, metadata())
        broken = metadata(); del broken["scan_arguments"]
        with self.assertRaises(SUMMARY.SummaryError):
            SUMMARY.summary_data({"SchemaVersion": 2, "Results": []}, broken)
        with self.assertRaises(SUMMARY.SummaryError):
            SUMMARY.summary_data({"SchemaVersion": 2, "Results": []}, metadata("failed"))

    def test_deterministic_tie_and_existing_output_protection(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [{"Vulnerabilities": [finding("CVE-B", "z", "HIGH"), finding("CVE-A", "a", "HIGH")]}]}
        self.assertEqual(SUMMARY.summary_data(raw, metadata())["top_packages"][0]["package"], "a")
        old_argv = sys.argv
        try:
            sys.argv = ["summary", "raw.json", "meta.json", "existing.md"]
            with patch.object(Path, "exists", return_value=True):
                with self.assertRaises(SystemExit):
                    SUMMARY.main()
        finally:
            sys.argv = old_argv


if __name__ == "__main__":
    unittest.main()
