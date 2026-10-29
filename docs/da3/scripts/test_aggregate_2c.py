"""Offline tests for the Step 20 Trivy comparison counter."""

from __future__ import annotations

import sys
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_2c as AGGREGATE  # noqa: E402


def finding(identifier: str, package: str, installed: str, severity: str) -> dict[str, str]:
    return {"VulnerabilityID": identifier, "PkgName": package, "InstalledVersion": installed, "Severity": severity}


def successful_metadata(raw_path: Path, *, status: str = "success") -> dict[str, object]:
    return {
        "status": status,
        "exit_status": 0 if status == "success" else 1,
        "label": "fixture",
        "scan_timestamp": "now",
        "image": {"reference": "fixture", "id": "sha256:fixture", "size_bytes": 1, "configured_user": "10001"},
        "trivy": {"image": "trivy@sha256:pin", "version": "0.76.1"},
        "database_metadata": {},
        "database_snapshot": {"schema_version": 2, "version": 2, "updated_at": "now"},
        "trivy_db_sha256": "a" * 64,
        "scan_arguments": ["image"],
        "base_images": [{"declared_from": "python:3.14.2-slim"}],
        "raw_report_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
    }


class AggregateTests(unittest.TestCase):
    def test_duplicate_records_share_the_locked_key_within_group(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [
            {"Class": "os-pkgs", "Vulnerabilities": [finding("CVE-1", "pkg", "1", "HIGH"), finding("CVE-1", "pkg", "1", "HIGH")]},
            {"Class": "lang-pkgs", "Vulnerabilities": [finding("CVE-1", "pkg", "1", "HIGH")]},
        ]}
        counts = AGGREGATE.deduplicated_counts(raw)
        self.assertEqual(counts["os-pkgs"]["HIGH"], 1)
        self.assertEqual(counts["lang-pkgs"]["HIGH"], 1)

    def test_package_and_installed_version_are_part_of_the_key(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [{"Class": "os-pkgs", "Vulnerabilities": [
            finding("CVE-1", "package-a", "1", "CRITICAL"),
            finding("CVE-1", "package-b", "1", "CRITICAL"),
            finding("CVE-1", "package-a", "2", "CRITICAL"),
        ]}]}
        self.assertEqual(AGGREGATE.deduplicated_counts(raw)["os-pkgs"]["CRITICAL"], 3)

    def test_severity_and_unknown_result_class_are_grouped_separately(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [
            {"Class": "other", "Vulnerabilities": [finding("CVE-1", "pkg", "1", "HIGH")]},
            {"Class": "os-pkgs", "Vulnerabilities": [finding("CVE-1", "pkg", "1", "CRITICAL")]},
        ]}
        counts = AGGREGATE.deduplicated_counts(raw)
        self.assertEqual(counts["unknown"]["HIGH"], 1)
        self.assertEqual(counts["os-pkgs"]["CRITICAL"], 1)

    def test_missing_deduplication_key_fails_closed(self) -> None:
        raw = {"SchemaVersion": 2, "Results": [{"Class": "os-pkgs", "Vulnerabilities": [{"Severity": "HIGH"}]}]}
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.deduplicated_counts(raw)

    def test_missing_raw_report_hash_fails_closed(self) -> None:
        raw = {"SchemaVersion": 2, "Results": []}
        metadata = {
            "status": "success", "exit_status": 0, "label": "fixture", "scan_timestamp": "now",
            "image": {"reference": "fixture", "id": "sha256:fixture", "size_bytes": 1, "configured_user": "root"},
            "trivy": {"image": "fixture@sha256:pin", "version": "0.76.1"},
            "database_metadata": {}, "database_snapshot": {"schema_version": 2, "version": 2, "updated_at": "now"},
            "trivy_db_sha256": "a" * 64, "scan_arguments": [], "base_images": [],
        }
        with patch.object(AGGREGATE, "load_json", side_effect=[raw, metadata]):
            with self.assertRaisesRegex(AGGREGATE.ComparisonError, "raw report SHA-256"):
                AGGREGATE.load_row("fixture", "experimental-baseline", Path("raw.json"), Path("metadata.json"))

    def test_db_or_scanner_mismatch_refuses_comparison(self) -> None:
        row = {
            "database": {"schema_version": 2, "version": 2, "updated_at": "one"},
            "database_hash": "a" * 64,
            "trivy": {"image": "trivy@sha256:pin", "version": "0.76.1"},
            "scan_arguments": ["image"],
        }
        changed_database = {**row, "database_hash": "b" * 64}
        changed_scanner = {**row, "trivy": {"image": "other@sha256:pin", "version": "0.76.1"}}
        changed_arguments = {**row, "scan_arguments": ["image", "--different"]}
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.require_comparable([row, changed_database])
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.require_comparable([row, changed_scanner])
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.require_comparable([row, changed_arguments])

    def test_single_row_and_unknown_kind_are_not_accepted_as_a_comparison(self) -> None:
        row = {
            "database": {"schema_version": 2, "version": 2, "updated_at": "one"},
            "database_hash": "a" * 64,
            "trivy": {"image": "trivy@sha256:pin", "version": "0.76.1"},
            "scan_arguments": ["image"],
        }
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.require_comparable([row])
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.load_row("fixture", "unknown-kind", Path("raw.json"), Path("metadata.json"))

    def test_size_comparison_requires_a_valid_before_and_hardened_pair(self) -> None:
        rows = [
            {"label": "before", "kind": "prehardening-production", "image": {"size_bytes": 10}},
            {"label": "after", "kind": "hardened", "image": {"size_bytes": 5}},
            {"label": "frontend", "kind": "unchanged-exclusion", "image": {"size_bytes": 3}},
        ]
        self.assertEqual(AGGREGATE.size_comparison_rows(rows, ["before", "after"]), (rows[0], rows[1]))
        with self.assertRaises(AGGREGATE.ComparisonError):
            AGGREGATE.size_comparison_rows(rows, ["frontend", "after"])

    def test_retained_step19_backend_artifacts_are_accepted(self) -> None:
        repository_root = Path(__file__).resolve().parents[3]
        row = AGGREGATE.load_row(
            "experimental-backend",
            "experimental-baseline",
            repository_root / "docs" / "da3" / "results" / "19-trivy-baseline-r3.json",
            repository_root / "docs" / "da3" / "results" / "19-trivy-baseline-r3.metadata.json",
        )
        self.assertGreater(AGGREGATE.total(row, "CRITICAL"), 0)
        self.assertGreater(AGGREGATE.total(row, "HIGH"), 0)

    def test_missing_or_invalid_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            missing = root / "missing.json"
            metadata = root / "metadata.json"
            metadata.write_text("{}", encoding="utf-8")
            with self.assertRaises(AGGREGATE.ComparisonError):
                AGGREGATE.load_row("fixture", "hardened", missing, metadata)
            raw = root / "raw.json"
            raw.write_text("not-json", encoding="utf-8")
            with self.assertRaises(AGGREGATE.ComparisonError):
                AGGREGATE.load_row("fixture", "hardened", raw, metadata)

    def test_malformed_or_failed_scan_input_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            raw = root / "raw.json"
            raw.write_text(json.dumps({"SchemaVersion": 2, "Results": ["malformed"]}), encoding="utf-8")
            metadata = root / "metadata.json"
            metadata.write_text(json.dumps(successful_metadata(raw)), encoding="utf-8")
            with self.assertRaises(AGGREGATE.ComparisonError):
                AGGREGATE.load_row("fixture", "hardened", raw, metadata)
            raw.write_text(json.dumps({"SchemaVersion": 2, "Results": []}), encoding="utf-8")
            metadata.write_text(json.dumps(successful_metadata(raw, status="failed")), encoding="utf-8")
            with self.assertRaises(AGGREGATE.ComparisonError):
                AGGREGATE.load_row("fixture", "hardened", raw, metadata)

    def test_hash_mismatch_and_incomplete_metadata_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            raw = root / "raw.json"
            raw.write_text(json.dumps({"SchemaVersion": 2, "Results": []}), encoding="utf-8")
            metadata = successful_metadata(raw)
            metadata["raw_report_sha256"] = "b" * 64
            metadata_path = root / "metadata.json"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(AGGREGATE.ComparisonError):
                AGGREGATE.load_row("fixture", "hardened", raw, metadata_path)
            metadata = successful_metadata(raw)
            del metadata["base_images"]
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(AGGREGATE.ComparisonError):
                AGGREGATE.load_row("fixture", "hardened", raw, metadata_path)


if __name__ == "__main__":
    unittest.main()
