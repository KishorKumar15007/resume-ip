"""Create a deterministic, fail-closed Markdown summary of saved Trivy JSON."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1}
KNOWN_CLASSES = {"os-pkgs": "OS packages", "lang-pkgs": "language packages"}


class SummaryError(ValueError):
    """A raw scan or its metadata cannot truthfully be summarised."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SummaryError(f"cannot read JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise SummaryError(f"JSON root must be an object: {path.name}")
    return value


def markdown_value(value: object) -> str:
    """Keep untrusted scanner strings inside one safe Markdown table cell."""
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def validate_raw_report(raw: dict[str, Any]) -> None:
    if not isinstance(raw.get("SchemaVersion"), int):
        raise SummaryError("raw scan lacks an integer SchemaVersion")
    results = raw.get("Results")
    if not isinstance(results, list):
        raise SummaryError("raw scan has no Results list")
    for result in results:
        if not isinstance(result, dict):
            raise SummaryError("raw scan contains a malformed Result")
        vulnerabilities = result.get("Vulnerabilities", [])
        if vulnerabilities is not None and not isinstance(vulnerabilities, list):
            raise SummaryError("raw scan contains malformed Vulnerabilities")


def validate_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("status") != "success" or metadata.get("exit_status") != 0:
        raise SummaryError("scan metadata is not a successful completed scan")
    image = metadata.get("image")
    trivy = metadata.get("trivy")
    required = ("label", "scan_timestamp", "database_metadata", "database_snapshot", "trivy_db_sha256", "scan_arguments", "base_images")
    if any(key not in metadata for key in required) or not isinstance(image, dict) or not isinstance(trivy, dict):
        raise SummaryError("scan metadata lacks required provenance")
    if any(not image.get(key) for key in ("reference", "id", "size_bytes", "configured_user")):
        raise SummaryError("scan metadata has incomplete image provenance")
    if not trivy.get("image") or not trivy.get("version") or not isinstance(metadata["scan_arguments"], list):
        raise SummaryError("scan metadata has incomplete Trivy provenance")
    db = metadata["database_snapshot"]
    if not isinstance(db, dict) or any(db.get(key) is None for key in ("schema_version", "version", "updated_at")):
        raise SummaryError("scan metadata has incomplete database provenance")


def vulnerability_occurrences(raw: dict[str, Any]) -> list[dict[str, str]]:
    validate_raw_report(raw)
    occurrences: list[dict[str, str]] = []
    for result in raw["Results"]:
        assert isinstance(result, dict)
        vulnerabilities = result.get("Vulnerabilities") or []
        target = result.get("Target", "unknown")
        result_class = str(result.get("Class") or "unknown")
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict):
                raise SummaryError("raw scan contains a malformed vulnerability")
            severity = vulnerability.get("Severity")
            if severity not in SEVERITY_ORDER:
                continue
            package = vulnerability.get("PkgName")
            identifier = vulnerability.get("VulnerabilityID")
            if not isinstance(package, str) or not package or not isinstance(identifier, str) or not identifier:
                raise SummaryError("high/critical finding lacks package or vulnerability identifier")
            package_class = str(vulnerability.get("Class") or result_class)
            if package_class not in KNOWN_CLASSES:
                package_class = "unknown"
            occurrences.append({
                "target": str(target), "class": package_class,
                "package": package, "installed": str(vulnerability.get("InstalledVersion") or "unknown"),
                "fixed": str(vulnerability.get("FixedVersion") or "not available"),
                "identifier": identifier, "severity": severity,
            })
    return occurrences


def summary_data(raw: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    validate_metadata(metadata)
    occurrences = vulnerability_occurrences(raw)  # raw occurrences: never deduplicated.
    by_severity = {severity: 0 for severity in SEVERITY_ORDER}
    by_class = {key: {severity: 0 for severity in SEVERITY_ORDER} for key in (*KNOWN_CLASSES, "unknown")}
    packages: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for item in occurrences:
        by_severity[item["severity"]] += 1
        by_class.setdefault(item["class"], {severity: 0 for severity in SEVERITY_ORDER})[item["severity"]] += 1
        packages[(item["class"], item["package"], item["installed"], item["fixed"])].append(item)
    ranked: list[dict[str, Any]] = []
    for key, findings in packages.items():
        representative = min(findings, key=lambda item: (SEVERITY_ORDER[item["severity"]], item["identifier"], item["target"]))
        ranked.append({"class": key[0], "package": key[1], "installed": key[2], "fixed": key[3],
                       "identifier": representative["identifier"], "severity": representative["severity"],
                       "occurrences": len(findings), "critical": sum(x["severity"] == "CRITICAL" for x in findings),
                       "high": sum(x["severity"] == "HIGH" for x in findings)})
    ranked.sort(key=lambda item: (-item["occurrences"], -item["critical"], -item["high"], SEVERITY_ORDER[item["severity"]],
                                  item["class"], item["package"], item["installed"], item["fixed"], item["identifier"]))
    return {"by_severity": by_severity, "by_class": by_class, "top_packages": ranked[:5]}


def markdown(raw: dict[str, Any], metadata: dict[str, Any]) -> str:
    data = summary_data(raw, metadata)
    image, trivy, db = metadata["image"], metadata["trivy"], metadata["database_snapshot"]
    lines = [f"# Trivy scan: {markdown_value(metadata['label'])}", "", "- Status: **success**",
        f"- Scan timestamp: `{markdown_value(metadata['scan_timestamp'])}`",
        f"- Image reference / ID: `{markdown_value(image['reference'])}` / `{markdown_value(image['id'])}`",
        f"- Image size / configured user: `{markdown_value(image['size_bytes'])}` bytes / `{markdown_value(image['configured_user'])}`",
        f"- Trivy image / version: `{markdown_value(trivy['image'])}` / `{markdown_value(trivy['version'])}`",
        f"- DB schema / version / updated: `{markdown_value(db['schema_version'])}` / `{markdown_value(db['version'])}` / `{markdown_value(db['updated_at'])}`",
        f"- DB content SHA-256: `{markdown_value(metadata['trivy_db_sha256'])}`",
        f"- Scan arguments: `{markdown_value(' '.join(metadata['scan_arguments']))}`", "- Base-image provenance is Docker-inspected at scan time:"]
    for base in metadata["base_images"]:
        lines.append(f"  - `{markdown_value(base['declared_from'])}` -> `{markdown_value(base['resolved_id'])}` ({markdown_value(base['platform'])}; {markdown_value(base.get('resolution_status', 'unknown'))})")
    lines += ["", "## Raw vulnerability occurrences", "", "| Severity | Count |", "| --- | ---: |",
              f"| CRITICAL | {data['by_severity']['CRITICAL']} |", f"| HIGH | {data['by_severity']['HIGH']} |", "",
              "| Package class | CRITICAL | HIGH |", "| --- | ---: | ---: |"]
    for package_class in (*KNOWN_CLASSES, "unknown"):
        counts = data["by_class"].get(package_class, {"CRITICAL": 0, "HIGH": 0})
        lines.append(f"| {KNOWN_CLASSES.get(package_class, package_class)} | {counts['CRITICAL']} | {counts['HIGH']} |")
    lines += ["", "## Five most affected package groups", "", "Ties: occurrence count, CRITICAL count, HIGH count, severity, class, package, installed, fixed, ID.", "",
              "| Class | Package | Installed | Fixed | Representative ID | Severity | Occurrences |", "| --- | --- | --- | --- | --- | --- | ---: |"]
    for item in data["top_packages"]:
        lines.append("| " + " | ".join(markdown_value(item[key]) for key in ("class", "package", "installed", "fixed", "identifier", "severity")) + f" | {item['occurrences']} |")
    if not data["top_packages"]:
        lines.append("| none | none | none | none | none | none | 0 |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refusing to overwrite an existing summary")
    try:
        text = markdown(load_json(args.raw), load_json(args.metadata))
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(args.output)
    except SummaryError as exc:
        raise SystemExit(f"summary stopped: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
