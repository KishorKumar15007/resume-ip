"""Fail-closed Trivy baseline scanner for DA3 Steps 19 and 20.

It snapshots both documented DB metadata and the actual ``trivy.db`` bytes
once, then uses that exact named-volume state read-only for comparison scans.
Runtime use is owner-operated; the accompanying tests mock Docker completely.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from summarize_trivy import SummaryError, load_json, markdown, validate_raw_report


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = REPOSITORY_ROOT / "docs" / "da3" / "results"
TRIVY_IMAGE = "aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c"
TRIVY_VERSION = "0.76.1"
CACHE_VOLUME = "resume-ip-trivy-db-v1"
CACHE_ROOT = "/root/.cache/trivy"
DB_METADATA_PATH = f"{CACHE_ROOT}/db/metadata.json"
DB_FILE_PATH = f"{CACHE_ROOT}/db/trivy.db"
SNAPSHOT_PATH = RESULTS_DIR / "19-trivy-db-snapshot.json"
SAFETY_MARGIN_BYTES = 1024 * 1024 * 1024
SCAN_ARGUMENTS = [
    "image", "--input", "/scan/image.tar", "--scanners", "vuln",
    "--pkg-types", "os,library", "--severity", "CRITICAL,HIGH",
    "--format", "json", "--skip-db-update", "--skip-java-db-update",
    "--skip-check-update", "--skip-version-check", "--offline-scan",
    "--no-progress",
]
FROM_PATTERN = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)(?:\s+AS\s+(\S+))?", re.I)


class ScanError(RuntimeError):
    """A short, sanitised owner-actionable scanning error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(text: str) -> str:
    text = " ".join(text.strip().split())
    text = re.sub(r"\b[\w+.-]+://[^\s]+", "[redacted-url]", text)
    return text[-1200:] or "no diagnostic output"


def command(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(args, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise ScanError(f"cannot start required command: {args[0]} ({type(exc).__name__})") from exc
    if check and result.returncode:
        raise ScanError(f"command failed ({args[0]}, exit {result.returncode}): {sanitize(result.stderr or result.stdout)}")
    return result


def docker_mount_arg(source: Path, target: str, *, readonly: bool) -> str:
    """One Docker --mount argument; list subprocess args preserve Windows spaces."""
    return f"type=bind,source={source.resolve()},target={target}{',readonly' if readonly else ''}"


def db_subpath_mount_arg() -> str:
    """Expose only the immutable DB subdirectory; fanal cache stays ephemeral."""
    return f"type=volume,source={CACHE_VOLUME},target={CACHE_ROOT}/db,volume-subpath=db,readonly"


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def inspect_image(reference: str, *, allow_missing: bool = False) -> dict[str, Any]:
    result = command(["docker", "image", "inspect", reference, "--format", "{{json .}}"], check=False)
    if result.returncode:
        if allow_missing and "No such image" in (result.stderr or result.stdout):
            return {"reference": reference, "id": "unavailable", "size_bytes": "unavailable",
                    "configured_user": "unavailable", "os": "unknown", "architecture": "unknown",
                    "repo_digests": [], "resolution_status": "not-locally-inspectable-after-build"}
        raise ScanError(f"command failed (docker, exit {result.returncode}): {sanitize(result.stderr or result.stdout)}")
    try:
        image = json.loads(result.stdout)
        config = image.get("Config") or {}
        return {
            "reference": reference, "id": image["Id"], "size_bytes": image["Size"],
            "configured_user": config.get("User") or "default/root",
            "os": image.get("Os") or "unknown", "architecture": image.get("Architecture") or "unknown",
            "repo_digests": image.get("RepoDigests") or [],
            "resolution_status": "docker-inspected",
        }
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ScanError("docker image inspection returned malformed metadata") from exc


def required_space(image_size: int) -> int:
    return image_size * 2 + SAFETY_MARGIN_BYTES


def ensure_disk_space(image: dict[str, Any], temporary_directory: Path) -> None:
    size = image.get("size_bytes")
    if not isinstance(size, int) or size < 0:
        raise ScanError("docker did not provide a usable image size for disk-space preflight")
    needed = required_space(size)
    available = shutil.disk_usage(temporary_directory).free
    if available < needed:
        raise ScanError(
            f"temporary-filesystem preflight failed: need {needed} bytes (2x image size plus 1 GiB), have {available}; "
            "this safeguard does not measure Docker Desktop internal storage"
        )


def metadata_identity(metadata: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(key).lower(): value for key, value in metadata.items()}
    identity = {
        # Trivy 0.76.1 stores its DB schema number in Version.  Keep support
        # for an explicit schema key if a compatible producer supplies one.
        "schema_version": lowered.get("schemaversion") or lowered.get("schema_version") or lowered.get("version"),
        "version": lowered.get("version"),
        "updated_at": lowered.get("updatedat") or lowered.get("updated_at"),
        "next_update": lowered.get("nextupdate") or lowered.get("next_update"),
        "downloaded_at": lowered.get("downloadedat") or lowered.get("downloaded_at"),
    }
    if not all(identity[key] is not None for key in ("schema_version", "version", "updated_at")):
        raise ScanError("Trivy vulnerability DB metadata lacks schema, version, or update identity")
    if identity["schema_version"] != 2 or identity["version"] != 2:
        raise ScanError("Trivy DB schema version is incompatible with pinned Trivy 0.76.1")
    identity["identity_sha256"] = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return identity


def volume_identity() -> dict[str, str]:
    result = command(["docker", "volume", "inspect", CACHE_VOLUME, "--format", "{{json .}}"])
    try:
        volume = json.loads(result.stdout)
        return {"name": str(volume["Name"]), "driver": str(volume["Driver"])}
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ScanError("Trivy cache volume inspection returned malformed metadata") from exc


def volume_exists() -> bool:
    return command(["docker", "volume", "inspect", CACHE_VOLUME], check=False).returncode == 0


def read_db_state() -> dict[str, Any]:
    """Read Trivy 0.76.1 cache files through a read-only, networkless container."""
    script = (
        f"test -r {DB_METADATA_PATH} && test -r {DB_FILE_PATH}; "
        f"cat {DB_METADATA_PATH}; printf '\\n__TRIVY_DB_SHA256__='; sha256sum {DB_FILE_PATH}"
    )
    result = command([
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--mount", f"type=volume,source={CACHE_VOLUME},target={CACHE_ROOT},readonly",
        "--entrypoint", "/bin/sh", TRIVY_IMAGE, "-ceu", script,
    ])
    marker = "\n__TRIVY_DB_SHA256__="
    if marker not in result.stdout:
        raise ScanError("Trivy DB inspection did not return the required metadata and digest")
    raw_metadata, digest_line = result.stdout.rsplit(marker, 1)
    digest = digest_line.strip().split(maxsplit=1)[0] if digest_line.strip() else ""
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ScanError("Trivy DB inspection returned an invalid trivy.db SHA-256 digest")
    try:
        metadata = json.loads(raw_metadata)
    except json.JSONDecodeError as exc:
        raise ScanError("Trivy vulnerability DB metadata is missing or malformed") from exc
    if not isinstance(metadata, dict):
        raise ScanError("Trivy vulnerability DB metadata must be a JSON object")
    return {"metadata": metadata, "identity": metadata_identity(metadata), "trivy_db_sha256": digest,
            "cache_volume": volume_identity()}


def trivy_version() -> str:
    result = command(["docker", "run", "--rm", "--network", "none", TRIVY_IMAGE, "version", "--format", "json"])
    try:
        data = json.loads(result.stdout)
        version = data.get("Version") or data.get("version")
    except json.JSONDecodeError as exc:
        raise ScanError("pinned Trivy did not return machine-readable version metadata") from exc
    if not isinstance(version, str) or not version:
        raise ScanError("pinned Trivy version metadata is incomplete")
    if version != TRIVY_VERSION:
        raise ScanError("pinned Trivy image did not report the expected version")
    return version


def parse_dockerfile_bases(dockerfile: Path) -> list[str]:
    try:
        lines = dockerfile.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ScanError("cannot read requested Dockerfile for base-image provenance") from exc
    aliases: set[str] = set()
    bases: list[str] = []
    for line in lines:
        match = FROM_PATTERN.match(line)
        if not match:
            continue
        source, alias = match.groups()
        if source.lower() not in aliases:
            bases.append(source)
        if alias:
            aliases.add(alias.lower())
    if not bases:
        raise ScanError("requested Dockerfile has no external FROM image to inspect")
    return bases


def base_image_provenance(dockerfile: Path) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    for declared in parse_dockerfile_bases(dockerfile):
        inspected = inspect_image(declared, allow_missing=True)
        provenance.append({"declared_from": declared, "resolved_id": inspected["id"],
                           "resolved_repo_digests": inspected["repo_digests"],
                           "platform": {"os": inspected["os"], "architecture": inspected["architecture"]},
                           "resolution_status": inspected["resolution_status"]})
    return provenance


def output_paths(label: str) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", label):
        raise ScanError("label may contain only letters, digits, hyphens, and underscores")
    raw = RESULTS_DIR / f"19-trivy-{label}.json"
    metadata = RESULTS_DIR / f"19-trivy-{label}.metadata.json"
    summary = RESULTS_DIR / f"19-trivy-{label}.md"
    if any(path.exists() for path in (raw, metadata, summary)):
        raise ScanError(f"refusing to overwrite existing result for label: {label}")
    return raw, metadata, summary


def load_snapshot() -> dict[str, Any]:
    try:
        snapshot = load_json(SNAPSHOT_PATH)
    except SummaryError as exc:
        raise ScanError("recorded Trivy DB snapshot is absent or malformed") from exc
    required = ("created_at", "trivy_image", "trivy_version", "cache_volume", "database_metadata", "database_snapshot", "trivy_db_sha256")
    if snapshot.get("status") != "success" or any(key not in snapshot for key in required):
        raise ScanError("recorded Trivy DB snapshot is incomplete")
    if snapshot["trivy_image"] != TRIVY_IMAGE or not re.fullmatch(r"[0-9a-f]{64}", str(snapshot["trivy_db_sha256"])):
        raise ScanError("recorded Trivy DB snapshot is incompatible with this pinned scanner")
    if not isinstance(snapshot["database_snapshot"], dict) or not isinstance(snapshot["cache_volume"], dict):
        raise ScanError("recorded Trivy DB snapshot has invalid structure")
    return snapshot


def verify_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    current = read_db_state()
    if (current["cache_volume"] != snapshot["cache_volume"] or current["identity"] != snapshot["database_snapshot"]
            or current["trivy_db_sha256"] != snapshot["trivy_db_sha256"]):
        raise ScanError("current Trivy DB differs from the recorded comparison snapshot")
    return current


def write_snapshot(state: dict[str, Any], *, source: str) -> None:
    """Persist only an already validated DB state; never modify the volume."""
    atomic_json(SNAPSHOT_PATH, {"status": "success", "created_at": utc_now(), "trivy_image": TRIVY_IMAGE,
                 "trivy_version": trivy_version(), "cache_volume": state["cache_volume"],
                 "database_metadata": state["metadata"], "database_snapshot": state["identity"],
                 "trivy_db_sha256": state["trivy_db_sha256"], "snapshot_source": source,
                 "reuse_rule": "Steps 19 and 20 must use this unchanged metadata identity and trivy.db SHA-256; a mismatch invalidates comparison."})


def initialize_db_snapshot() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if SNAPSHOT_PATH.exists():
        raise ScanError("refusing to overwrite existing Trivy DB snapshot")
    if volume_exists():
        try:
            read_db_state()
        except ScanError as exc:
            raise ScanError("named Trivy cache volume already exists but is invalid; inspect it manually, do not reuse it") from exc
        raise ScanError("named Trivy cache volume already exists; inspect and explicitly replace it outside this script")
    command(["docker", "volume", "create", CACHE_VOLUME])
    command(["docker", "run", "--rm", "--mount", f"type=volume,source={CACHE_VOLUME},target={CACHE_ROOT}", TRIVY_IMAGE,
             "image", "--download-db-only", "--skip-java-db-update", "--skip-check-update", "--skip-version-check", "--no-progress"])
    write_snapshot(read_db_state(), source="downloaded-by-initialization")
    return 0


def adopt_existing_db_snapshot() -> int:
    """Explicitly snapshot a valid pre-existing DB without changing its bytes."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if SNAPSHOT_PATH.exists():
        raise ScanError("refusing to overwrite existing Trivy DB snapshot")
    if not volume_exists():
        raise ScanError("cannot adopt a missing named Trivy cache volume")
    # read_db_state validates the documented files, metadata identity, SHA-256,
    # and volume identity; write_snapshot verifies the pinned scanner version.
    write_snapshot(read_db_state(), source="explicitly-adopted-existing-volume")
    return 0


def failure_metadata(path: Path, metadata: dict[str, Any], error: Exception | str) -> None:
    metadata["status"] = "failed"
    metadata["error"] = sanitize(str(error))
    if not path.exists():
        atomic_json(path, metadata)


def scan_image(reference: str, label: str, dockerfile: Path) -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_path, metadata_path, summary_path = output_paths(label)
    image = inspect_image(reference)
    ensure_disk_space(image, Path(tempfile.gettempdir()))
    snapshot = load_snapshot()
    before = verify_snapshot(snapshot)
    metadata: dict[str, Any] = {"status": "failed", "label": label, "scan_timestamp": utc_now(), "image": image,
        "base_images": base_image_provenance(dockerfile), "trivy": {"image": TRIVY_IMAGE, "version": trivy_version()},
        "database_metadata": before["metadata"], "database_snapshot": before["identity"],
        "trivy_db_sha256": before["trivy_db_sha256"], "cache_volume": before["cache_volume"],
        "scan_arguments": SCAN_ARGUMENTS, "exit_status": None}
    tar_path: Path | None = None
    try:
        handle = tempfile.NamedTemporaryFile(prefix="resume-ip-trivy-", suffix=".tar", dir=tempfile.gettempdir(), delete=False)
        tar_path = Path(handle.name)
        handle.close()
        saved = command(["docker", "save", "--output", str(tar_path), reference], check=False)
        if saved.returncode:
            metadata["exit_status"] = saved.returncode
            raise ScanError("docker save failed; no Trivy scan was started")
        scan = command(["docker", "run", "--rm", "--network", "none", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--tmpfs", f"{CACHE_ROOT}:rw,noexec,nosuid,size=256m",
            "--mount", db_subpath_mount_arg(),
            "--mount", docker_mount_arg(tar_path, "/scan/image.tar", readonly=True),
            "--mount", docker_mount_arg(RESULTS_DIR, "/out", readonly=False), TRIVY_IMAGE, *SCAN_ARGUMENTS,
            "--output", f"/out/{raw_path.name}"], check=False)
        metadata["exit_status"] = scan.returncode
        if scan.returncode:
            diagnostic = sanitize(scan.stderr or scan.stdout)
            metadata["trivy_diagnostic"] = diagnostic
            raise ScanError(f"Trivy scan failed: {diagnostic}")
        if not raw_path.is_file() or raw_path.stat().st_size == 0:
            raise ScanError("Trivy scan returned success without a readable current raw JSON report")
        raw = load_json(raw_path)
        validate_raw_report(raw)
        after = verify_snapshot(snapshot)
        metadata.update({"status": "success", "raw_report_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                         "database_metadata_after": after["metadata"]})
        summary = markdown(raw, metadata)
        temporary_summary = summary_path.with_suffix(".md.tmp")
        try:
            temporary_summary.write_text(summary, encoding="utf-8")
            atomic_json(metadata_path, metadata)
            temporary_summary.replace(summary_path)
        except OSError as exc:
            summary_path.unlink(missing_ok=True)
            metadata["status"] = "failed"
            try:
                atomic_json(metadata_path, {**metadata, "error": sanitize(str(exc))})
            except OSError:
                pass
            raise ScanError("cannot publish complete Trivy summary artifacts") from exc
        finally:
            temporary_summary.unlink(missing_ok=True)
    except (ScanError, SummaryError, OSError) as exc:
        try:
            failure_metadata(metadata_path, metadata, exc)
        except OSError:
            pass
        summary_path.unlink(missing_ok=True)
        raise ScanError(str(exc)) from exc
    finally:
        if tar_path is not None:
            try:
                tar_path.unlink(missing_ok=True)
            except OSError:
                pass  # Forced termination cannot be protected; handled runs clean up.
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?")
    parser.add_argument("label", nargs="?")
    parser.add_argument("--dockerfile", type=Path)
    parser.add_argument("--initialize-db-snapshot", action="store_true")
    parser.add_argument("--adopt-existing-db-snapshot", action="store_true")
    args = parser.parse_args()
    try:
        if args.initialize_db_snapshot or args.adopt_existing_db_snapshot:
            if args.initialize_db_snapshot and args.adopt_existing_db_snapshot:
                raise ScanError("choose either DB initialization or explicit existing-volume adoption")
            if args.image or args.label or args.dockerfile:
                raise ScanError("DB snapshot operations accept no image, label, or Dockerfile")
            if args.adopt_existing_db_snapshot:
                return adopt_existing_db_snapshot()
            return initialize_db_snapshot()
        if not args.image or not args.label or args.dockerfile is None:
            raise ScanError("image, label, and --dockerfile are required for a scan")
        return scan_image(args.image, args.label, args.dockerfile)
    except ScanError as exc:
        print(f"Trivy scan stopped: {sanitize(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
