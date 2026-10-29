"""Offline tests for DA3 Step 19 Trivy safety guards; Docker is mocked."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import trivy_scan as SCAN  # noqa: E402


def state(digest: str = "a" * 64, updated: str = "2026-10-01T00:00:00Z") -> dict[str, object]:
    metadata = {"SchemaVersion": 2, "Version": 2, "UpdatedAt": updated}
    return {"metadata": metadata, "identity": SCAN.metadata_identity(metadata), "trivy_db_sha256": digest,
            "cache_volume": {"name": SCAN.CACHE_VOLUME, "driver": "local"}}


class ScanSafetyTests(unittest.TestCase):
    def test_pin_is_tag_and_digest(self) -> None:
        self.assertIn(":0.76.1@sha256:", SCAN.TRIVY_IMAGE)
        self.assertNotIn(":latest", SCAN.TRIVY_IMAGE)
        digest = SCAN.TRIVY_IMAGE.rsplit("@sha256:", 1)[1]
        self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_diagnostic_sanitization_redacts_url_shaped_values(self) -> None:
        self.assertNotIn("user:password", SCAN.sanitize("failed https://user:password@example.test/path"))
        self.assertIn("[redacted-url]", SCAN.sanitize("failed https://user:password@example.test/path"))

    def test_space_requirement_has_two_copies_and_margin(self) -> None:
        self.assertEqual(SCAN.required_space(100), 200 + SCAN.SAFETY_MARGIN_BYTES)

    @patch("trivy_scan.shutil.disk_usage")
    def test_insufficient_space_fails_before_export(self, disk_usage) -> None:
        disk_usage.return_value = type("Usage", (), {"free": 1})()
        with self.assertRaises(SCAN.ScanError):
            SCAN.ensure_disk_space({"size_bytes": 100}, Path.cwd())

    def test_mount_argument_preserves_windows_space_path_as_one_argument(self) -> None:
        mounted = SCAN.docker_mount_arg(Path("C:/path with spaces/image.tar"), "/scan/image.tar", readonly=True)
        self.assertIn("source=", mounted)
        self.assertIn("path with spaces", mounted)
        self.assertTrue(mounted.endswith(",readonly"))

    def test_db_mount_exposes_only_read_only_db_subpath(self) -> None:
        mount = SCAN.db_subpath_mount_arg()
        self.assertIn("volume-subpath=db", mount)
        self.assertIn("target=/root/.cache/trivy/db", mount)
        self.assertTrue(mount.endswith(",readonly"))

    def test_dockerfile_base_parser_excludes_named_internal_stages(self) -> None:
        dockerfile = Path("fixture.Dockerfile")
        with patch.object(Path, "read_text", return_value="FROM python:3.12 AS runtime\nFROM runtime AS api\n"):
            self.assertEqual(SCAN.parse_dockerfile_bases(dockerfile), ["python:3.12"])

    def test_missing_declared_base_is_recorded_honestly_not_fabricated(self) -> None:
        result = type("Result", (), {"returncode": 1, "stderr": "No such image: python:3.12", "stdout": ""})()
        with patch.object(SCAN, "command", return_value=result):
            base = SCAN.inspect_image("python:3.12", allow_missing=True)
        self.assertEqual(base["id"], "unavailable")
        self.assertEqual(base["resolution_status"], "not-locally-inspectable-after-build")

    def test_missing_metadata_field_is_rejected(self) -> None:
        with self.assertRaises(SCAN.ScanError):
            SCAN.metadata_identity({"SchemaVersion": 2, "Version": 2})

    def test_trivy_0761_metadata_uses_version_as_schema_version(self) -> None:
        metadata = {
            "DownloadedAt": "2026-10-29T07:56:34.956359505Z",
            "NextUpdate": "2026-10-30T01:22:22.544155326Z",
            "UpdatedAt": "2026-10-29T01:22:22.544155871Z",
            "Version": 2,
        }
        identity = SCAN.metadata_identity(metadata)
        self.assertEqual(identity["schema_version"], 2)
        self.assertEqual(identity["version"], 2)
        self.assertEqual(identity["updated_at"], metadata["UpdatedAt"])
        self.assertEqual(identity["downloaded_at"], metadata["DownloadedAt"])

    def test_changed_metadata_or_db_digest_fails_snapshot_verification(self) -> None:
        snapshot = {"cache_volume": state()["cache_volume"], "database_snapshot": state()["identity"], "trivy_db_sha256": "a" * 64}
        with patch.object(SCAN, "read_db_state", return_value=state("b" * 64)):
            with self.assertRaises(SCAN.ScanError):
                SCAN.verify_snapshot(snapshot)
        changed = state(updated="2026-10-02T00:00:00Z")
        with patch.object(SCAN, "read_db_state", return_value=changed):
            with self.assertRaises(SCAN.ScanError):
                SCAN.verify_snapshot(snapshot)

    def test_corrupt_or_missing_snapshot_is_rejected(self) -> None:
        with patch.object(SCAN, "load_json", side_effect=SCAN.SummaryError("bad")):
            with self.assertRaises(SCAN.ScanError):
                SCAN.load_snapshot()
        with patch.object(SCAN, "load_json", return_value={"status": "success"}):
            with self.assertRaises(SCAN.ScanError):
                SCAN.load_snapshot()

    def test_existing_volume_refuses_baseline_even_when_valid(self) -> None:
        with patch.object(Path, "mkdir"), patch.object(SCAN, "SNAPSHOT_PATH", Path("missing-snapshot.json")), patch.object(SCAN, "volume_exists", return_value=True), patch.object(SCAN, "read_db_state", return_value=state()):
            with self.assertRaisesRegex(SCAN.ScanError, "already exists"):
                SCAN.initialize_db_snapshot()

    def test_explicit_adoption_writes_only_validated_existing_state(self) -> None:
        adopted = state()
        with patch.object(Path, "mkdir"), patch.object(SCAN, "SNAPSHOT_PATH", Path("missing-snapshot.json")), patch.object(SCAN, "volume_exists", return_value=True), patch.object(SCAN, "read_db_state", return_value=adopted), patch.object(SCAN, "write_snapshot") as write_snapshot:
            SCAN.adopt_existing_db_snapshot()
        write_snapshot.assert_called_once_with(adopted, source="explicitly-adopted-existing-volume")

    def test_scan_refuses_without_valid_snapshot_before_export(self) -> None:
        with patch.object(Path, "mkdir"), patch.object(SCAN, "SNAPSHOT_PATH", Path("missing-snapshot.json")), patch.object(SCAN, "inspect_image", return_value={"reference": "x", "id": "sha256:x", "size_bytes": 1, "configured_user": "root", "os": "linux", "architecture": "amd64"}), patch.object(SCAN, "ensure_disk_space"), patch.object(SCAN, "command") as command:
            with self.assertRaises(SCAN.ScanError):
                SCAN.scan_image("x", "label", Path(__file__))
            command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
