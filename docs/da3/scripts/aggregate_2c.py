"""Generate a fail-closed, deduplicated DA3 Step 20 Trivy comparison table."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from summarize_trivy import SummaryError, load_json, validate_metadata, validate_raw_report


SEVERITIES = ("CRITICAL", "HIGH")
CLASSES = ("os-pkgs", "lang-pkgs", "unknown")
ROW_KINDS = {
    "experimental-baseline",
    "prehardening-production",
    "baseline-rescan",
    "hardened",
    "unchanged-exclusion",
}


class ComparisonError(ValueError):
    """A saved scan cannot safely be included in the comparison."""


def result_class(result: dict[str, Any]) -> str:
    value = result.get("Class")
    return value if value in CLASSES else "unknown"


def deduplicated_counts(raw: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Deduplicate within each result-class/severity group by the locked key."""
    validate_raw_report(raw)
    seen = {(package_class, severity): set() for package_class in CLASSES for severity in SEVERITIES}
    for result in raw["Results"]:
        if not isinstance(result, dict):
            raise ComparisonError("raw scan contains a malformed Result")
        package_class = result_class(result)
        for finding in result.get("Vulnerabilities") or []:
            if not isinstance(finding, dict):
                raise ComparisonError("raw scan contains a malformed vulnerability")
            severity = finding.get("Severity")
            if severity not in SEVERITIES:
                continue
            key_values = tuple(finding.get(field) for field in ("VulnerabilityID", "PkgName", "InstalledVersion"))
            if not all(isinstance(value, str) and value for value in key_values):
                raise ComparisonError("high/critical finding lacks the required deduplication key")
            seen[(package_class, severity)].add(key_values)
    return {
        package_class: {severity: len(seen[(package_class, severity)]) for severity in SEVERITIES}
        for package_class in CLASSES
    }


def validate_row_metadata(metadata: dict[str, Any]) -> None:
    database = metadata["database_snapshot"]
    trivy = metadata["trivy"]
    base_images = metadata["base_images"]
    if not re.fullmatch(r"[0-9a-f]{64}", str(metadata.get("trivy_db_sha256", ""))):
        raise ComparisonError("scan metadata lacks a usable Trivy DB SHA-256")
    if not isinstance(database, dict) or not isinstance(trivy, dict) or not isinstance(base_images, list):
        raise ComparisonError("scan metadata has malformed provenance")
    if not all(isinstance(database.get(field), (str, int)) for field in ("schema_version", "version", "updated_at")):
        raise ComparisonError("scan metadata lacks complete DB identity")
    if not all(isinstance(trivy.get(field), str) and trivy[field] for field in ("image", "version")):
        raise ComparisonError("scan metadata lacks complete scanner identity")
    image = metadata.get("image")
    if not isinstance(image, dict) or not isinstance(image.get("size_bytes"), int) or image["size_bytes"] < 0:
        raise ComparisonError("scan metadata lacks a usable image size")
    for base in base_images:
        if not isinstance(base, dict) or not isinstance(base.get("declared_from"), str) or not base["declared_from"]:
            raise ComparisonError("scan metadata has malformed base-image provenance")


def load_row(label: str, row_kind: str, raw_path: Path, metadata_path: Path) -> dict[str, Any]:
    if row_kind not in ROW_KINDS:
        raise ComparisonError("row kind is not an approved comparison category")
    try:
        raw, metadata = load_json(raw_path), load_json(metadata_path)
        validate_raw_report(raw)
        validate_metadata(metadata)
    except SummaryError as exc:
        raise ComparisonError(f"cannot include {label}: {exc}") from exc
    expected_hash = metadata.get("raw_report_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise ComparisonError(f"cannot include {label}: metadata lacks a raw report SHA-256")
    validate_row_metadata(metadata)
    actual_hash = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if expected_hash is not None and expected_hash != actual_hash:
        raise ComparisonError(f"cannot include {label}: raw report hash does not match metadata")
    return {
        "label": label,
        "kind": row_kind,
        "raw_path": raw_path,
        "metadata_path": metadata_path,
        "image": metadata["image"],
        "image_bases": metadata["base_images"],
        "trivy": metadata["trivy"],
        "database": metadata["database_snapshot"],
        "database_hash": metadata["trivy_db_sha256"],
        "scan_arguments": metadata["scan_arguments"],
        "counts": deduplicated_counts(raw),
    }


def comparison_identity(row: dict[str, Any]) -> tuple[str, str, tuple[str, str, tuple[str, ...]]]:
    return (
        json.dumps(row["database"], sort_keys=True, separators=(",", ":")),
        row["database_hash"],
        (row["trivy"]["image"], row["trivy"]["version"], tuple(row["scan_arguments"])),
    )


def require_comparable(rows: list[dict[str, Any]]) -> None:
    if len(rows) < 2:
        raise ComparisonError("at least two completed scan rows are required for a comparison")
    if len({comparison_identity(row) for row in rows}) != 1:
        raise ComparisonError(
            "scan rows do not share an identical vulnerability DB snapshot, pinned scanner identity, and scan arguments"
        )


def base_images(row: dict[str, Any]) -> str:
    return ", ".join(base["declared_from"] for base in row["image_bases"])


def total(row: dict[str, Any], severity: str) -> int:
    return sum(row["counts"][package_class][severity] for package_class in CLASSES)


def size_comparison_rows(rows: list[dict[str, Any]], labels: list[str] | None) -> tuple[dict[str, Any], dict[str, Any]] | None:
    if labels is None:
        return None
    before_label, after_label = labels
    if before_label == after_label:
        raise ComparisonError("image-size comparison labels must be distinct")
    indexed = {row["label"]: row for row in rows}
    if before_label not in indexed or after_label not in indexed:
        raise ComparisonError("image-size comparison labels must be comparison rows")
    before, after = indexed[before_label], indexed[after_label]
    if before["kind"] not in {"prehardening-production", "baseline-rescan"} or after["kind"] != "hardened":
        raise ComparisonError("image-size comparison must pair prehardening-production or baseline-rescan with hardened")
    return before, after


def markdown(rows: list[dict[str, Any]], size_comparison: list[str] | None) -> str:
    if not rows:
        raise ComparisonError("at least one comparison row is required")
    require_comparable(rows)
    compared_rows = size_comparison_rows(rows, size_comparison)
    lines = [
        "# DA3 Step 20 Trivy comparison",
        "",
        "Counts below are deduplicated within each `Results[].Class` and severity group by ",
        "`VulnerabilityID + PkgName + InstalledVersion`. They are distinct from Step 19's retained raw-occurrence summaries.",
        "",
        "All listed rows share an identical vulnerability DB snapshot, pinned scanner identity, and scan arguments.",
        (f"Image-size delta is measured from `{compared_rows[0]['label']}` to `{compared_rows[1]['label']}` only." if compared_rows else
         "No image-size delta is calculated because no valid size-comparison baseline was selected."),
        "",
        "| Label | Row kind | Image / ID | Base image(s) | Size bytes | Size delta bytes | User | Trivy | DB schema/version/updated | DB SHA-256 | CRITICAL | HIGH | OS C/H | Language C/H | Unknown C/H | Raw JSON | Metadata |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        image, database, counts = row["image"], row["database"], row["counts"]
        if compared_rows is None or row["label"] not in {compared_rows[0]["label"], compared_rows[1]["label"]}:
            size_delta = "not applicable"
        else:
            size_delta = str(image["size_bytes"] - compared_rows[0]["image"]["size_bytes"])
        lines.append(
            "| {label} | {kind} | `{reference}` / `{identifier}` | `{bases}` | {size} | {size_delta} | `{user}` | `{version}` | "
            "{schema}/{db_version}/{updated} | `{hash}` | {critical} | {high} | {os_critical}/{os_high} | "
            "{language_critical}/{language_high} | {unknown_critical}/{unknown_high} | `{raw}` | `{metadata}` |".format(
                label=row["label"], kind=row["kind"], reference=image["reference"], identifier=image["id"], bases=base_images(row), size=image["size_bytes"], size_delta=size_delta,
                user=image["configured_user"], version=row["trivy"]["version"],
                schema=database["schema_version"], db_version=database["version"], updated=database["updated_at"],
                hash=row["database_hash"], critical=total(row, "CRITICAL"), high=total(row, "HIGH"),
                os_critical=counts["os-pkgs"]["CRITICAL"], os_high=counts["os-pkgs"]["HIGH"],
                language_critical=counts["lang-pkgs"]["CRITICAL"], language_high=counts["lang-pkgs"]["HIGH"],
                unknown_critical=counts["unknown"]["CRITICAL"], unknown_high=counts["unknown"]["HIGH"],
                raw=row["raw_path"].as_posix(), metadata=row["metadata_path"].as_posix(),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row", action="append", nargs=4, metavar=("LABEL", "KIND", "RAW_JSON", "METADATA_JSON"), required=True)
    parser.add_argument("--size-comparison", nargs=2, metavar=("BEFORE_LABEL", "AFTER_LABEL"), help="valid prehardening/baseline-rescan and hardened row labels used for byte-size deltas")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("comparison stopped: refusing to overwrite an existing output")
    labels = [item[0] for item in args.row]
    if len(set(labels)) != len(labels):
        raise SystemExit("comparison stopped: row labels must be unique")
    try:
        rows = [load_row(label, row_kind, Path(raw), Path(metadata)) for label, row_kind, raw, metadata in args.row]
        text = markdown(rows, args.size_comparison)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        try:
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(args.output)
        finally:
            temporary.unlink(missing_ok=True)
    except (ComparisonError, OSError) as exc:
        raise SystemExit(f"comparison stopped: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
