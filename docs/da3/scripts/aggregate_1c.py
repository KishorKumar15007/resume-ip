"""Generate a validated DA3 1c before/after table from saved artifacts."""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import statistics
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[2]
RESULTS = ROOT / "docs" / "da3" / "results"
sys.path.insert(0, str(SCRIPTS))
import loadtest  # noqa: E402
_PROBE_SPEC = importlib.util.spec_from_file_location("aggregate_probe", SCRIPTS / "availability_probe.py")
assert _PROBE_SPEC and _PROBE_SPEC.loader
PROBE = importlib.util.module_from_spec(_PROBE_SPEC); _PROBE_SPEC.loader.exec_module(PROBE)
BASELINE = tuple(RESULTS / name for name in (
    "12-1c-s12-baseline-r1-2e36ea414f.json", "12-1c-s12-baseline-r2-b786793df6.json",
    "12-1c-s12-baseline-r3-db7ba83bd0.json"))


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"unreadable result artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"invalid result artifact: {path.name}")
    return value


def validate_phase(value: dict[str, Any], phase: str, expected_requests: int) -> None:
    metrics = value.get(phase)
    diagnostics = value.get("nginx_diagnostics", {}).get(phase)
    raw = ROOT / str(value.get("artifacts", {}).get(f"{phase}_raw", ""))
    protocol = value.get("protocol", {})
    if (not isinstance(metrics, dict) or not isinstance(diagnostics, dict) or not raw.is_file()
            or metrics.get("requests") != expected_requests or protocol.get("concurrency") != 20
            or protocol.get("ab_flags") != ["-k", "-r"]):
        raise ValueError(f"invalid {phase} protocol or artifact")
    parsed = loadtest.parse_ab(raw.read_text(encoding="utf-8"), expected_requests, int(metrics.get("return_code", 0)))
    for key in ("completed_requests", "failed_requests", "non_2xx_responses", "requests_per_second", "mean_time_per_request_ms"):
        if getattr(parsed, key) != metrics.get(key):
            raise ValueError(f"raw AB/result mismatch for {phase}.{key}")
    counts = diagnostics.get("status_counts")
    if (diagnostics.get("availability") != "readable" or not isinstance(counts, dict)
            or diagnostics.get("matching_lines") != metrics.get("completed_requests")
            or diagnostics.get("malformed_lines") != 0 or diagnostics.get("unparseable_statuses") != 0):
        raise ValueError(f"invalid {phase} diagnostics")
    try:
        if any(not 100 <= int(status) <= 599 or not isinstance(count, int) or count < 0 for status, count in counts.items()):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError(f"invalid {phase} status counts") from None
    if sum(counts.values()) != diagnostics["matching_lines"] or diagnostics.get("502_count") != counts.get("502", 0) or diagnostics.get("504_count") != counts.get("504", 0):
        raise ValueError(f"inconsistent {phase} diagnostic totals")


def row(path: Path, expected: str, supplied_probe: Path | None = None) -> dict[str, Any]:
    value = load(path)
    metrics, diagnostics = value.get("measured"), value.get("nginx_diagnostics", {}).get("measured")
    if value.get("config") != expected or value.get("completion") != "complete" or value.get("error"):
        raise ValueError(f"incomplete or wrong configuration: {path.name}")
    if not isinstance(metrics, dict) or not isinstance(diagnostics, dict):
        raise ValueError(f"missing measurement/diagnostics: {path.name}")
    validate_phase(value, "warmup", 100)
    validate_phase(value, "measured", 1000)
    completed, failed, non_2xx = (metrics.get(key) for key in ("completed_requests", "failed_requests", "non_2xx_responses"))
    if (not isinstance(completed, int) or completed <= 0 or not isinstance(failed, int)
            or not isinstance(non_2xx, int) or failed < 0 or non_2xx < 0):
        raise ValueError(f"invalid request accounting: {path.name}")
    if (diagnostics.get("availability") != "readable" or diagnostics.get("matching_lines") != completed
            or diagnostics.get("malformed_lines") != 0 or diagnostics.get("unparseable_statuses") != 0
            or not isinstance(diagnostics.get("status_counts"), dict)):
        raise ValueError(f"invalid diagnostics: {path.name}")
    probe = value.get("availability_probe", {}).get("summary") if expected == "resilient" else None
    if expected == "resilient":
        probe_csv = ROOT / str(value.get("artifacts", {}).get("probe_csv", ""))
        if supplied_probe is not None and supplied_probe.resolve() != probe_csv.resolve():
            raise ValueError(f"explicit probe path does not match result artifact: {path.name}")
        if not isinstance(probe, dict) or not probe_csv.is_file():
            raise ValueError(f"missing resilient probe summary or CSV: {path.name}")
        observed_probe = PROBE.summarise(probe_csv)
        if observed_probe != probe:
            raise ValueError(f"probe CSV/summary mismatch: {path.name}")
    return {"path": path, "rep": value.get("rep"), "completed": completed, "failed": failed,
            "non_2xx": non_2xx, "metrics": metrics, "diagnostics": diagnostics,
            "kill": value.get("kill", {}), "recovery": value.get("recovery"),
            "restoration": value.get("canonical_restoration"), "probe": probe}


def config_diff(output: Path) -> None:
    before = (ROOT / "nginx" / "nginx-3-baseline.conf").read_text(encoding="utf-8").splitlines(True)
    after = (ROOT / "nginx" / "nginx-3-resilient.conf").read_text(encoding="utf-8").splitlines(True)
    content = "".join(difflib.unified_diff(before, after, "nginx-3-baseline.conf", "nginx-3-resilient.conf"))
    if output.exists():
        if output.read_text(encoding="utf-8") != content:
            raise FileExistsError("refusing to overwrite a different configuration diff")
        return
    output.write_text(content, encoding="utf-8")


def render(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> str:
    rows = ["# DA3 1c before/after failover comparison", "", "Failure rate = AB failed requests / AB complete requests × 100.", "",
            "| Set | Rep | Complete | Failed | Connect/Receive/Length/Exceptions | Non-2xx | 5xx (502/504) | RPS | Failure rate | Kill s | Recovery / restoration | Probe total / failed / longest gap s |",
            "|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|"]
    for label, collection in (("baseline", before), ("resilient", after)):
        for item in collection:
            metric, diag, probe = item["metrics"], item["diagnostics"], item["probe"] or {}
            breakdown = "/".join(str(metric.get(key)) for key in ("connect_failures", "receive_failures", "length_failures", "exception_failures"))
            probe_text = "n/a" if not probe else f"{probe.get('total_samples')} / {probe.get('failed_probes')} / {probe.get('longest_observed_gap_seconds')}"
            all_5xx = sum(count for status, count in diag.get("status_counts", {}).items() if 500 <= int(status) <= 599)
            rows.append(f"| {label} | {item['rep']} | {item['completed']} | {item['failed']} | {breakdown} | {item['non_2xx']} | {all_5xx} ({diag.get('502_count', 0)}/{diag.get('504_count', 0)}) | {metric.get('requests_per_second')} | {item['failed'] / item['completed'] * 100:.4f}% | {item['kill'].get('actual_elapsed_seconds')} | {item['recovery']} / {item['restoration']} | {probe_text} |")
    for label, collection in (("baseline", before), ("resilient", after)):
        fivexx = [sum(count for status, count in x['diagnostics'].get('status_counts', {}).items() if 500 <= int(status) <= 599) for x in collection]
        rows.append(f"| {label} median | — | {statistics.median(x['completed'] for x in collection)} | {statistics.median(x['failed'] for x in collection)} | — | {statistics.median(x['non_2xx'] for x in collection)} | {statistics.median(fivexx)} | {statistics.median(float(x['metrics']['requests_per_second']) for x in collection):.2f} | {statistics.median(x['failed'] / x['completed'] * 100 for x in collection):.4f}% | — | — | — |")
    return "\n".join(rows) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diff-only", action="store_true")
    parser.add_argument("--after", type=Path, nargs=3)
    parser.add_argument("--probes", type=Path, nargs=3)
    parser.add_argument("--output", type=Path, default=RESULTS / "13-1c-table.md")
    parser.add_argument("--diff-output", type=Path, default=RESULTS / "13-nginx-config.diff")
    args = parser.parse_args()
    config_diff(args.diff_output)
    if args.diff_only:
        return 0
    if not args.after or not args.probes:
        parser.error("--after and --probes each require exactly three explicit files")
    before = [row(path, "baseline") for path in BASELINE]
    after = [row(path, "resilient", probe) for path, probe in zip(args.after, args.probes)]
    reps = [item["rep"] for item in after]
    if len(set(reps)) != 3:
        raise ValueError("resilient repetition IDs must be unique")
    content = render(before, after)
    if args.output.exists():
        raise FileExistsError("refusing to overwrite existing comparison table")
    args.output.write_text(content, encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
