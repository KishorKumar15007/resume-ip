"""Offline aggregation for a saved DA3 Step 11 benchmark manifest."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "docs" / "da3" / "results"
MARKER = "generated-by: docs/da3/scripts/aggregate_1b.py"
MARKDOWN_PATH = RESULTS / "11-1b-table.md"
CSV_PATH = RESULTS / "11-1b-table.csv"
SUMMARY_PATH = RESULTS / "11-1b-summary.json"


def positive_path(value: str) -> Path:
    path = Path(value).resolve()
    try:
        path.relative_to(RESULTS.resolve())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--manifest must be inside docs/da3/results") from exc
    if not path.is_file():
        raise argparse.ArgumentTypeError("--manifest must name an existing file")
    return path


def read_json(path: Path) -> dict[str, object] | None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def result_path(value: object) -> Path | None:
    if not isinstance(value, str):
        return None
    path = (ROOT / value).resolve()
    try:
        path.relative_to(RESULTS.resolve())
    except ValueError:
        return None
    return path


def raw_metrics(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        return {}
    try:
        output = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    def integer(pattern: str) -> int | None:
        match = re.search(pattern, output, re.MULTILINE)
        return int(match.group(1)) if match else None

    def decimal(pattern: str) -> str | None:
        match = re.search(pattern, output, re.MULTILINE)
        return match.group(1) if match else None

    return {
        "completed_requests": integer(r"^Complete requests:\s*(\d+)\s*$"),
        "requests_per_second": decimal(r"^Requests per second:\s*([0-9.]+)\s+\[#/sec\]"),
        "mean_time_per_request_ms": decimal(r"^Time per request:\s*([0-9.]+)\s+\[ms\]\s+\(mean\)"),
        "failed_requests": integer(r"^Failed requests:\s*(\d+)"),
        "non_2xx_responses": integer(r"^Non-2xx responses:\s*(\d+)\s*$"),
    }


def normal_metrics(row: dict[str, object]) -> dict[str, object]:
    values = row.get("metrics")
    return dict(values) if isinstance(values, dict) else {}


def diagnostic_summary(row: dict[str, object]) -> tuple[str, object]:
    diagnostics = row.get("nginx_diagnostics")
    if not isinstance(diagnostics, dict):
        return "UNKNOWN", {}
    availability = diagnostics.get("availability")
    phases = diagnostics.get("phases")
    measured = phases.get("measured") if isinstance(phases, dict) else None
    counts = measured.get("status_counts") if isinstance(measured, dict) else {}
    return str(availability or "UNKNOWN"), counts if isinstance(counts, dict) else {}


def decimal(value: object) -> Decimal | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = Decimal(value)
        return parsed if parsed.is_finite() and parsed > 0 else None
    except (InvalidOperation, ValueError):
        return None


def exact_int(value: object, expected: int | None = None) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and (expected is None or value == expected)


def valid_count(value: object) -> bool:
    return exact_int(value) and value >= 0


def eligible(row: dict[str, object], metrics: dict[str, object]) -> tuple[bool, str | None]:
    if row.get("status") != "complete":
        return False, str(row.get("median_exclusion_reason") or row.get("reason") or "measurement is incomplete")
    if row.get("invocation_exit_status") != 0:
        return False, "benchmark harness invocation exit status is nonzero or unavailable"
    topology = row.get("topology")
    if not isinstance(topology, dict) or topology.get("activation") != "verified" or topology.get("restoration") != "verified":
        return False, "three-backend restoration or topology state was not verified"
    if metrics.get("completed_requests") != row.get("planned_measured_requests"):
        return False, "completed request count is not the planned measurement"
    if decimal(metrics.get("requests_per_second")) is None or decimal(metrics.get("mean_time_per_request_ms")) is None:
        return False, "required Apache Bench metrics are unparseable"
    if metrics.get("return_code") != 0:
        return False, "Apache Bench exit status is nonzero"
    if metrics.get("timed_out") is not False or metrics.get("interrupted") is not False:
        return False, "measurement timed out or was interrupted"
    if metrics.get("execution_error") is not None or metrics.get("harness_error") is not None:
        return False, "harness reported an error"
    if not valid_count(metrics.get("failed_requests")) or not valid_count(metrics.get("non_2xx_responses")):
        return False, "failure counts are missing or invalid"
    warmup = row.get("warmup_metrics")
    if isinstance(warmup, dict):
        if (not exact_int(warmup.get("completed_requests"), 100) or warmup.get("return_code") != 0
                or warmup.get("timed_out") is not False or warmup.get("interrupted") is not False
                or warmup.get("execution_error") is not None or warmup.get("failed_requests") != 0
                or warmup.get("non_2xx_responses") != 0):
            return False, "warm-up does not satisfy the locked success criteria"
    return True, None


def row_summary(row: dict[str, object]) -> dict[str, object]:
    metrics = normal_metrics(row)
    raw_files = row.get("raw_files")
    raw_measurement = None
    if isinstance(raw_files, list):
        candidates = [result_path(item) for item in raw_files if isinstance(item, str) and not item.endswith("-warmup.txt")]
        raw_measurement = next((item for item in candidates if item is not None), None)
    result_identity_ok = True
    result_files = row.get("result_files")
    if isinstance(result_files, list):
        json_paths = [result_path(item) for item in result_files if isinstance(item, str) and item.endswith(".json")]
        if json_paths:
            document = read_json(json_paths[0])
            result_identity_ok = bool(document and document.get("mode") == "single-run"
                                      and document.get("benchmark_id") == row.get("run_id")
                                      and document.get("instances") == row.get("topology_instances")
                                      and document.get("rep") == row.get("topology_repetition")
                                      and document.get("concurrency") == 20
                                      and document.get("requests") == 1000
                                      and document.get("restored_three_backends") is True)
    if raw_measurement is not None and raw_measurement.is_file():
        raw = raw_metrics(raw_measurement)
        required = ("completed_requests", "requests_per_second", "mean_time_per_request_ms", "failed_requests", "non_2xx_responses")
        if all(raw.get(key) is not None for key in required):
            if metrics and any(metrics.get(key) != raw.get(key) for key in required):
                metrics["raw_mismatch"] = True
            metrics.update(raw)
            metrics["source"] = "measured raw Apache Bench output"
        else:
            metrics.update(raw)
            metrics["raw_missing_or_malformed"] = True
            metrics["source"] = "partial raw output"
    elif not metrics:
        metrics = raw_metrics(raw_measurement)
        metrics["source"] = "partial raw output" if metrics else "no parseable result"
    else:
        metrics["source"] = "normal result JSON"
    # Apache Bench may omit "Non-2xx responses" when the count is zero.
    # Infer zero only when raw AB metrics and the saved harness result agree.
    saved_metrics = normal_metrics(row)
    if (
        metrics.get("non_2xx_responses") is None
        and metrics.get("completed_requests") == row.get("planned_measured_requests")
        and metrics.get("failed_requests") == 0
        and decimal(metrics.get("requests_per_second")) is not None
        and decimal(metrics.get("mean_time_per_request_ms")) is not None
        and saved_metrics.get("completed_requests") == row.get("planned_measured_requests")
        and saved_metrics.get("failed_requests") == 0
        and saved_metrics.get("non_2xx_responses") == 0
        and saved_metrics.get("return_code") == 0
        and saved_metrics.get("timed_out") is False
        and saved_metrics.get("interrupted") is False
        and saved_metrics.get("execution_error") is None
        and saved_metrics.get("harness_error") is None
       ):
        metrics["non_2xx_responses"] = 0

        # The only missing raw field was Non-2xx, which AB omits at zero.
        # Clear the partial-output flag only when the other raw metrics match
        # the saved harness metrics.
        if (
            metrics.get("raw_missing_or_malformed")
            and saved_metrics.get("completed_requests")
                == metrics.get("completed_requests")
            and saved_metrics.get("requests_per_second")
                == metrics.get("requests_per_second")
            and saved_metrics.get("mean_time_per_request_ms")
                == metrics.get("mean_time_per_request_ms")
            and saved_metrics.get("failed_requests") == 0
            and metrics.get("failed_requests") == 0
        ):
            metrics.pop("raw_missing_or_malformed", None)
            metrics["source"] = (
                "measured raw Apache Bench output "
                "(zero non-2xx corroborated by saved result JSON)"
            )
    is_eligible, exclusion = eligible(row, metrics)
    if metrics.get("raw_mismatch"):
        is_eligible, exclusion = False, "measured raw Apache Bench values contradict result JSON"
    if not result_identity_ok:
        is_eligible, exclusion = False, "normal result JSON identity or configuration does not match the manifest"
    if any(isinstance(item, str) and item.startswith("docs/da3/results/11-1b-") for item in raw_files or []) and metrics.get("raw_missing_or_malformed"):
        is_eligible, exclusion = False, "required measured raw Apache Bench output is missing or malformed"
    diagnostic_state, status_counts = diagnostic_summary(row)
    return {
        "ordinal": row.get("ordinal"),
        "run_id": row.get("run_id"),
        "topology_instances": row.get("topology_instances"),
        "topology_repetition": row.get("topology_repetition"),
        "concurrency": row.get("concurrency"),
        "warmup_requests": row.get("planned_warmup_requests"),
        "measured_requests": row.get("planned_measured_requests"),
        "status": row.get("status"),
        "reason": row.get("reason"),
        "invocation_exit_status": row.get("invocation_exit_status"),
        "completed_requests": metrics.get("completed_requests"),
        "requests_per_second": metrics.get("requests_per_second"),
        "mean_time_per_request_ms": metrics.get("mean_time_per_request_ms"),
        "failed_requests": metrics.get("failed_requests"),
        "non_2xx_responses": metrics.get("non_2xx_responses"),
        "metric_source": metrics.get("source"),
        "nginx_diagnostics": diagnostic_state,
        "nginx_status_counts": status_counts,
        "raw_files": row.get("raw_files", []),
        "result_files": row.get("result_files", []),
        "diagnostic_files": row.get("diagnostic_files", []),
        "median_eligible": is_eligible,
        "median_exclusion_reason": exclusion,
    }


def median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    return ordered[midpoint] if len(ordered) % 2 else (ordered[midpoint - 1] + ordered[midpoint]) / 2


def aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    summaries = [row_summary(row) for row in rows]
    configurations: dict[str, dict[str, object]] = {}
    for instances in (1, 3):
        selected = [row for row in summaries if row["topology_instances"] == instances and row["median_eligible"]]
        rps = [value for row in selected if (value := decimal(row["requests_per_second"])) is not None]
        latency = [value for row in selected if (value := decimal(row["mean_time_per_request_ms"])) is not None]
        configurations[str(instances)] = {
            "eligible_runs": len(selected), "required_runs": 3,
            "median_requests_per_second": str(median(rps)) if len(rps) == len(selected) else None,
            "median_mean_time_per_request_ms": str(median(latency)) if len(latency) == len(selected) else None,
            "complete_three_repetition_benchmark": len(selected) == 3,
        }
    one, three = configurations["1"], configurations["3"]
    one_rps, three_rps = decimal(one["median_requests_per_second"]), decimal(three["median_requests_per_second"])
    one_ms, three_ms = decimal(one["median_mean_time_per_request_ms"]), decimal(three["median_mean_time_per_request_ms"])
    comparisons: dict[str, str | None] = {
        "throughput_improvement_percent": None,
        "throughput_speedup_factor": None,
        "mean_response_time_reduction_percent": None,
        "mean_response_time_improvement_factor": None,
    }
    if one_rps is not None and three_rps is not None and one_rps != 0:
        comparisons["throughput_improvement_percent"] = str((three_rps / one_rps - 1) * 100)
        comparisons["throughput_speedup_factor"] = str(three_rps / one_rps)
    if one_ms is not None and three_ms is not None and one_ms != 0:
        comparisons["mean_response_time_reduction_percent"] = str((1 - three_ms / one_ms) * 100)
    if one_ms is not None and three_ms is not None and three_ms != 0:
        comparisons["mean_response_time_improvement_factor"] = str(one_ms / three_ms)
    return {
        "rows": summaries,
        "configurations": configurations,
        "comparisons": comparisons,
        "intended_benchmark_complete": bool(one["complete_three_repetition_benchmark"] and three["complete_three_repetition_benchmark"]),
        "formulas": {
            "throughput_improvement_percent": "(median_3_backend_rps / median_1_backend_rps - 1) * 100",
            "throughput_speedup_factor": "median_3_backend_rps / median_1_backend_rps",
            "mean_response_time_reduction_percent": "(1 - median_3_backend_mean_ms / median_1_backend_mean_ms) * 100",
            "mean_response_time_improvement_factor": "median_1_backend_mean_ms / median_3_backend_mean_ms (greater than 1 means improvement)",
        },
    }


def recognized(path: Path) -> bool:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if content.startswith(MARKER):
        return True
    if path.suffix == ".json":
        document = read_json(path)
        return document is not None and document.get("generated_by") == "docs/da3/scripts/aggregate_1b.py"
    return False


def atomic_text(path: Path, text: str) -> None:
    if path.exists() and not recognized(path):
        raise RuntimeError("refusing to overwrite unrecognized derived output: " + path.name)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    temporary.replace(path)


def validate_rows(rows: object) -> list[dict[str, object]]:
    if not isinstance(rows, list) or len(rows) != 6 or not all(isinstance(row, dict) for row in rows):
        raise ValueError("manifest must contain exactly six dictionary benchmark rows")
    expected = ((1, 1), (3, 1), (1, 2), (3, 2), (1, 3), (3, 3))
    sequence_id = None
    for ordinal, (row, (instances, repetition)) in enumerate(zip(rows, expected), 1):
        if (row.get("ordinal"), row.get("topology_instances"), row.get("topology_repetition")) != (ordinal, instances, repetition):
            raise ValueError("manifest rows do not match the locked ordinal and topology order")
        if not all(exact_int(row.get(field), value) for field, value in (
            ("concurrency", 20), ("planned_warmup_requests", 100), ("planned_measured_requests", 1000),
        )):
            raise ValueError("manifest row has an invalid locked workload value")
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id or not run_id.endswith("-o" + str(ordinal)):
            raise ValueError("manifest row has an invalid run ID")
        prefix = run_id.rsplit("-o", 1)[0]
        if sequence_id is None:
            sequence_id = prefix
        elif prefix != sequence_id:
            raise ValueError("manifest run IDs do not share one benchmark sequence")
    run_ids = [row["run_id"] for row in rows]
    if len(set(run_ids)) != 6:
        raise ValueError("manifest run IDs must be unique")
    return rows


def expected_artifacts(row: dict[str, object]) -> set[str]:
    stem = "11-1b-{}-i{}-c20-r{}".format(row["run_id"], row["topology_instances"], row["topology_repetition"])
    return {
        "docs/da3/results/" + stem + "-warmup.txt",
        "docs/da3/results/" + stem + ".txt",
        "docs/da3/results/" + stem + ".json",
        "docs/da3/results/" + stem + ".md",
        "docs/da3/results/11-1b-nginx-" + str(row["run_id"]) + ".json",
        "docs/da3/results/11-1b-nginx-" + str(row["run_id"]) + "-non2xx.json",
    }


def validate_manifest(manifest: dict[str, object]) -> list[dict[str, object]]:
    locked = manifest.get("locked_configuration")
    required = {
        "endpoint": "GET /postings through Nginx", "keep_alive": True, "concurrency": 20,
        "warmup_requests": 100, "measured_requests": 1000, "order": [1, 3, 1, 3, 1, 3],
        "backend_cpus": 0.5, "uvicorn_workers": 1,
    }
    if not isinstance(locked, dict) or any(locked.get(key) != value for key, value in required.items()):
        raise ValueError("manifest locked configuration does not match the Step 11 contract")
    rows = validate_rows(manifest.get("rows"))
    sequence_id = manifest.get("sequence_id")
    if not isinstance(sequence_id, str) or not sequence_id:
        raise ValueError("manifest sequence ID is invalid")
    for row in rows:
        if row["run_id"] != sequence_id + "-o" + str(row["ordinal"]):
            raise ValueError("manifest run ID does not match its sequence and ordinal")
        allowed = expected_artifacts(row)
        for field in ("raw_files", "result_files", "diagnostic_files"):
            references = row.get(field, [])
            if not isinstance(references, list) or any(not isinstance(item, str) or item not in allowed for item in references):
                raise ValueError("manifest contains a cross-run or invalid artifact reference")
        expected_raw = "docs/da3/results/11-1b-{}-i{}-c20-r{}.txt".format(
            row["run_id"], row["topology_instances"], row["topology_repetition"]
        )
        if row.get("status") == "complete" and (expected_raw not in row.get("raw_files", []) or not (ROOT / expected_raw).is_file()):
            raise ValueError("complete manifest row is missing its expected measured raw output")
        expected_result = expected_raw.removesuffix(".txt") + ".json"
        if row.get("status") == "complete" and (expected_result not in row.get("result_files", []) or not (ROOT / expected_result).is_file()):
            raise ValueError("complete manifest row is missing its expected normal result JSON")
    return rows


def preflight_destinations(destinations: tuple[Path, ...]) -> None:
    for path in destinations:
        if path.exists() and not recognized(path):
            raise RuntimeError("refusing to overwrite unrecognized derived output: " + path.name)


def replace_outputs(outputs: dict[Path, str]) -> None:
    """Stage every output and roll back if replacing any destination fails."""
    destinations = tuple(outputs)
    preflight_destinations(destinations)
    temporary_paths: list[Path] = []
    backups: dict[Path, Path | None] = {}
    replaced: list[Path] = []
    completed = False
    recovery_failed = False
    try:
        for path, text in outputs.items():
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", delete=False,
                                             dir=path.parent, prefix=path.name + ".", suffix=".tmp") as handle:
                handle.write(text)
                temporary_paths.append(Path(handle.name))
        for path, temporary in zip(destinations, temporary_paths):
            if path.exists():
                backup = path.with_name(path.name + ".backup")
                if backup.exists():
                    raise RuntimeError("stale recovery backup exists: " + backup.name)
                path.replace(backup)
                backups[path] = backup
            else:
                backups[path] = None
            temporary.replace(path)
            replaced.append(path)
        completed = True
    except Exception as exc:
        for path in reversed(destinations):
            backup = backups.get(path)
            try:
                if path in replaced and path.exists():
                    path.unlink()
                if backup is not None and backup.exists():
                    backup.replace(path)
            except OSError:
                recovery_failed = True
        if recovery_failed:
            raise RuntimeError("output replacement failed and recovery could not be verified") from exc
        raise RuntimeError("output replacement failed; previous generation was restored") from exc
    finally:
        for temporary in temporary_paths:
            if temporary.exists():
                temporary.unlink()
        if completed:
            for backup in backups.values():
                if backup is not None and backup.exists():
                    backup.unlink()


def markdown(document: dict[str, object], manifest: Path) -> str:
    rows = document["rows"]
    assert isinstance(rows, list)
    lines = [MARKER, "", "# DA3 Step 11: one versus three backend instances", "",
             "| Ordinal | Topology | Rep | Status | RPS | Mean ms | Failed | Non-2xx | Nginx statuses | Median |",
             "| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |"]
    for row in rows:
        assert isinstance(row, dict)
        counts = row["nginx_status_counts"]
        count_text = ", ".join(str(key) + ":" + str(value) for key, value in sorted(counts.items())) if isinstance(counts, dict) and counts else "UNKNOWN"
        median_text = "yes" if row["median_eligible"] else "no: " + str(row["median_exclusion_reason"] or "unknown")
        lines.append("| {ordinal} | {topology_instances} | {topology_repetition} | {status} | {rps} | {mean} | {failed} | {non2xx} | {diagnostic}: {counts} | {median} |".format(
            ordinal=row["ordinal"], topology_instances=row["topology_instances"], topology_repetition=row["topology_repetition"],
            status=row["status"], rps=row["requests_per_second"],
            mean=row["mean_time_per_request_ms"], failed=row["failed_requests"], non2xx=row["non_2xx_responses"],
            diagnostic=row["nginx_diagnostics"], counts=count_text, median=median_text,
        ))
    lines.extend(["", "## Artifact references", "", "| Ordinal | Raw | Result | Diagnostics |", "| ---: | --- | --- | --- |"])
    for row in rows:
        assert isinstance(row, dict)
        lines.append("| {ordinal} | {raw} | {result} | {diagnostic} |".format(
            ordinal=row["ordinal"], raw="<br>".join(row["raw_files"]) or "none",
            result="<br>".join(row["result_files"]) or "none",
            diagnostic="<br>".join(row["diagnostic_files"]) or "none",
        ))
    configurations = document["configurations"]
    assert isinstance(configurations, dict)
    lines.extend(["", "## Medians", "", "| Topology | Eligible runs | Median RPS | Median mean ms | Three-repetition state |", "| ---: | --- | ---: | ---: | --- |"])
    for instances in ("1", "3"):
        item = configurations[instances]
        assert isinstance(item, dict)
        state = "complete" if item["complete_three_repetition_benchmark"] else "INCOMPLETE"
        lines.append(f"| {instances} | {item['eligible_runs']} of 3 | {item['median_requests_per_second']} | {item['median_mean_time_per_request_ms']} | {state} |")
    comparisons = document["comparisons"]
    assert isinstance(comparisons, dict)
    comparison_state = "COMPLETE" if document["intended_benchmark_complete"] else "PARTIAL / INCOMPLETE"
    lines.extend(["", "## Comparisons (" + comparison_state + ")", "", "| Metric | Value |", "| --- | ---: |"])
    for key, value in comparisons.items():
        lines.append(f"| {key} | {value if value is not None else 'unavailable'} |")
    lines.extend(["", "Formulas use full available Decimal precision:"])
    formulas = document["formulas"]
    assert isinstance(formulas, dict)
    lines.extend("- `" + str(value) + "`" for value in formulas.values())
    lines.extend(["", "Source manifest: `" + manifest.name + "`", ""])
    return "\n".join(lines)


def csv_text(document: dict[str, object]) -> str:
    import io
    output = io.StringIO(newline="")
    output.write(MARKER + "\n")
    writer = csv.writer(output)
    writer.writerow(["ordinal", "topology_instances", "topology_repetition", "concurrency", "warmup_requests", "measured_requests", "status", "reason", "invocation_exit_status", "requests_per_second", "mean_time_per_request_ms", "failed_requests", "non_2xx_responses", "nginx_diagnostics", "nginx_status_counts", "median_eligible", "median_exclusion_reason", "raw_files"])
    rows = document["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        writer.writerow([
            row[key] for key in ("ordinal", "topology_instances", "topology_repetition", "concurrency", "warmup_requests", "measured_requests", "status", "reason", "invocation_exit_status", "requests_per_second", "mean_time_per_request_ms", "failed_requests", "non_2xx_responses", "nginx_diagnostics")
        ] + [json.dumps(row["nginx_status_counts"], sort_keys=True), row["median_eligible"], row["median_exclusion_reason"], json.dumps(row["raw_files"])])
    return output.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=positive_path)
    args = parser.parse_args()
    manifest = read_json(args.manifest)
    if manifest is None or manifest.get("generated_by") != "docs/da3/scripts/run_1b.py":
        print("manifest is unavailable or unrecognized", file=sys.stderr)
        return 1
    try:
        validated_rows = validate_manifest(manifest)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    document = aggregate(validated_rows)
    document["generated_by"] = "docs/da3/scripts/aggregate_1b.py"
    document["source_manifest"] = args.manifest.name
    try:
        replace_outputs({
            MARKDOWN_PATH: markdown(document, args.manifest),
            CSV_PATH: csv_text(document),
            SUMMARY_PATH: json.dumps(document, indent=2, sort_keys=True) + "\n",
        })
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
