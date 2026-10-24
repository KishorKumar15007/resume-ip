"""Run the locked DA3 Step 11 one-versus-three-backend benchmark sequence."""

from __future__ import annotations

import json
import math
import os
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import loadtest


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "docs" / "da3" / "results"
NGINX_LOG = RESULTS / "nginx-logs" / "da3-access.log"
TOKEN_HELPER = Path(__file__).with_name("get_token.py")
LOADTEST = Path(__file__).with_name("loadtest.py")
COMPOSE = ROOT / "compose.da3.yml"
CONCURRENCY = 20
WARMUP_REQUESTS = 100
MEASURED_REQUESTS = 1000
ORDER = (1, 3, 1, 3, 1, 3)
LOG_SETTLE_SECONDS = 10
GENERATED_BY = "docs/da3/scripts/run_1b.py"


def new_sequence_id() -> str:
    now = datetime.now(UTC)
    return "s11-" + now.strftime("%Y%m%d") + "t" + now.strftime("%H%M%S") + "z-" + secrets.token_hex(4)


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def atomic_json(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def artifact_paths(marker: str, instances: int, repetition: int) -> dict[str, Path]:
    warmup, measured, result_json, result_markdown = loadtest.single_paths(
        instances, CONCURRENCY, repetition, marker
    )
    return {
        "warmup_raw": warmup,
        "measured_raw": measured,
        "result_json": result_json,
        "result_markdown": result_markdown,
        "nginx_diagnostics": RESULTS / ("11-1b-nginx-" + marker + ".json"),
        "nginx_non_2xx": RESULTS / ("11-1b-nginx-" + marker + "-non2xx.json"),
    }


def planned_rows(sequence_id: str) -> list[dict[str, object]]:
    repetitions = {1: 0, 3: 0}
    rows: list[dict[str, object]] = []
    for ordinal, instances in enumerate(ORDER, 1):
        repetitions[instances] += 1
        marker = sequence_id + "-o" + str(ordinal)
        rows.append(
            {
                "ordinal": ordinal,
                "run_id": marker,
                "topology_instances": instances,
                "topology_repetition": repetitions[instances],
                "concurrency": CONCURRENCY,
                "planned_warmup_requests": WARMUP_REQUESTS,
                "planned_measured_requests": MEASURED_REQUESTS,
                "status": "planned",
                "finalized": False,
                "reason": None,
                "invocation_exit_status": None,
                "started_at": None,
                "finished_at": None,
                "metrics": {},
                "nginx_diagnostics": {},
                "topology": {"activation": "not attempted", "restoration": "not attempted"},
                "raw_files": [],
                "result_files": [],
                "diagnostic_files": [],
                "median_eligible": False,
                "median_exclusion_reason": "not run",
                "no_raw_output": True,
                "expected_artifacts": [
                    relative(path) for path in artifact_paths(marker, instances, repetitions[instances]).values()
                ],
            }
        )
    return rows


def new_manifest(sequence_id: str) -> dict[str, object]:
    return {
        "generated_by": GENERATED_BY,
        "sequence_id": sequence_id,
        "created_at": datetime.now(UTC).isoformat(),
        "locked_configuration": {
            "endpoint": "GET /postings through Nginx",
            "keep_alive": True,
            "concurrency": CONCURRENCY,
            "warmup_requests": WARMUP_REQUESTS,
            "measured_requests": MEASURED_REQUESTS,
            "order": list(ORDER),
            "backend_cpus": 0.5,
            "uvicorn_workers": 1,
        },
        "token_acquisition": "not attempted",
        "preflight_topology": "not attempted",
        "rows": planned_rows(sequence_id),
    }


def manifest_path(sequence_id: str) -> Path:
    return RESULTS / ("11-1b-manifest-" + sequence_id + ".json")


def collision_error(manifest: dict[str, object], path: Path) -> str | None:
    paths = [path]
    rows = manifest["rows"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        paths.extend(
            artifact_paths(
                str(row["run_id"]), int(row["topology_instances"]), int(row["topology_repetition"])
            ).values()
        )
    existing = [item.name for item in paths if item.exists()]
    return None if not existing else "refusing to overwrite existing benchmark artifact(s): " + ", ".join(existing)


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    manifest["updated_at"] = datetime.now(UTC).isoformat()
    atomic_json(path, manifest)


def compose_contract_ok() -> bool:
    try:
        source = COMPOSE.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'cpus: "${BACKEND_CPUS:-0.5}"' in source and "--workers 1" in source


def acquire_token() -> str | None:
    try:
        result = subprocess.run(
            [sys.executable, str(TOKEN_HELPER)], cwd=ROOT, check=False,
            capture_output=True, text=True,
        )
    except OSError:
        return None
    token = result.stdout.strip()
    if result.returncode != 0 or not token or any(character.isspace() for character in token):
        return None
    return token


def load_json(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def metrics_from_result(document: dict[str, object] | None) -> dict[str, object]:
    if document is None:
        return {}
    measurement = document.get("measurement")
    warmup = document.get("warmup")
    return {
        "warmup_completed_requests": warmup.get("completed_requests") if isinstance(warmup, dict) else None,
        "completed_requests": measurement.get("completed_requests") if isinstance(measurement, dict) else None,
        "requests_per_second": measurement.get("requests_per_second") if isinstance(measurement, dict) else None,
        "mean_time_per_request_ms": measurement.get("mean_time_per_request_ms") if isinstance(measurement, dict) else None,
        "failed_requests": measurement.get("failed_requests") if isinstance(measurement, dict) else None,
        "non_2xx_responses": measurement.get("non_2xx_responses") if isinstance(measurement, dict) else None,
        "return_code": measurement.get("return_code") if isinstance(measurement, dict) else None,
        "timed_out": measurement.get("timed_out") if isinstance(measurement, dict) else None,
        "interrupted": measurement.get("interrupted") if isinstance(measurement, dict) else None,
        "execution_error": measurement.get("execution_error") if isinstance(measurement, dict) else None,
        "harness_error": document.get("error"),
    }


def warmup_metrics_from_result(document: dict[str, object] | None) -> dict[str, object]:
    warmup = document.get("warmup") if document is not None else None
    return dict(warmup) if isinstance(warmup, dict) else {}


def exact_int(value: object, expected: int | None = None) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and (expected is None or value == expected)


def positive_decimal(value: object) -> bool:
    try:
        number = float(value) if isinstance(value, str) else float("nan")
        return math.isfinite(number) and number > 0
    except ValueError:
        return False


def phase_ok(phase: object, expected: int, *, warmup: bool) -> bool:
    if not isinstance(phase, dict) or not exact_int(phase.get("completed_requests"), expected):
        return False
    if not positive_decimal(phase.get("requests_per_second")) or not positive_decimal(phase.get("mean_time_per_request_ms")):
        return False
    if not exact_int(phase.get("failed_requests")) or not exact_int(phase.get("non_2xx_responses")):
        return False
    if phase.get("return_code") != 0 or phase.get("timed_out") is not False or phase.get("interrupted") is not False or phase.get("execution_error") is not None:
        return False
    return not warmup or (phase["failed_requests"] == 0 and phase["non_2xx_responses"] == 0)


def classify(document: dict[str, object] | None, paths: dict[str, Path], invocation_exit_status: int | None,
             marker: str, instances: int, repetition: int) -> tuple[str, str | None, bool, str | None]:
    if document is None:
        if paths["warmup_raw"].exists() or paths["measured_raw"].exists():
            return "partial", "normal result JSON is unavailable", False, "normal result JSON is unavailable"
        return "failed", "no normal result or raw output exists", False, "measurement was not established"
    measurement = document.get("measurement")
    identity_ok = (document.get("mode") == "single-run" and document.get("benchmark_id") == marker
                   and exact_int(document.get("instances"), instances) and exact_int(document.get("rep"), repetition)
                   and exact_int(document.get("concurrency"), CONCURRENCY) and exact_int(document.get("requests"), MEASURED_REQUESTS))
    complete = (identity_ok and document.get("topology_activated") is True and document.get("restored_three_backends") is True
                and phase_ok(document.get("warmup"), WARMUP_REQUESTS, warmup=True)
                and phase_ok(measurement, MEASURED_REQUESTS, warmup=False)
                and document.get("error") is None)
    if invocation_exit_status != 0:
        reason = "benchmark harness exited with status " + str(invocation_exit_status)
        return "failed", reason, False, reason
    if complete:
        return "complete", None, True, None
    reason = str(document.get("error") or (measurement.get("execution_error") if isinstance(measurement, dict) else None) or "measurement is incomplete or identity does not match")
    return "partial", reason, False, reason


def normalize_status(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        status = value
    elif isinstance(value, str) and value.strip().isdigit():
        status = int(value.strip())
    else:
        return None
    return status if 100 <= status <= 599 else None


def read_nginx_diagnostics(marker: str, expected: dict[str, int | None]) -> dict[str, object]:
    deadline = time.monotonic() + LOG_SETTLE_SECONDS
    while True:
        if not NGINX_LOG.is_file():
            return {"availability": "unavailable", "reason": "Nginx access log is unavailable", "phases": {}}
        try:
            lines = NGINX_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return {"availability": "unavailable", "reason": "Nginx access log could not be read", "phases": {}}
        phases: dict[str, dict[str, object]] = {
            phase: {
                "matching_records": 0, "malformed_records": 0, "status_counts": {},
                "upstream_status_counts": {}, "upstream_address_counts": {}, "non_2xx_excerpt": [],
            }
            for phase in ("warmup", "measured")
        }
        malformed_records = 0
        for line in lines:
            if marker not in line:
                continue
            try:
                record = json.loads(line)
                request = record.get("request") if isinstance(record, dict) else None
                request_parts = request.split(" ") if isinstance(request, str) else []
                parsed = urlsplit(request_parts[1]) if len(request_parts) == 3 and request_parts[0] == "GET" else None
                query = parse_qs(parsed.query, keep_blank_values=True) if parsed and parsed.path == "/postings" else {}
                phase_values = query.get("phase")
                if query.get("bench") != [marker] or phase_values is None or len(phase_values) != 1:
                    continue
                phase = phase_values[0]
                if phase not in phases:
                    continue
                status = normalize_status(record.get("status"))
                if status is None:
                    phases[phase]["malformed_records"] = int(phases[phase]["malformed_records"]) + 1
                    continue
                phases[phase]["matching_records"] = int(phases[phase]["matching_records"]) + 1
                counts = phases[phase]["status_counts"]
                assert isinstance(counts, dict)
                counts[str(status)] = int(counts.get(str(status), 0)) + 1
                for field, count_key in (("upstream_status", "upstream_status_counts"), ("upstream_addr", "upstream_address_counts")):
                    raw_value = record.get(field)
                    if isinstance(raw_value, str) and raw_value:
                        upstream_counts = phases[phase][count_key]
                        assert isinstance(upstream_counts, dict)
                        upstream_counts[raw_value] = int(upstream_counts.get(raw_value, 0)) + 1
                if not 200 <= status < 300:
                    excerpt = phases[phase]["non_2xx_excerpt"]
                    assert isinstance(excerpt, list)
                    if len(excerpt) < 20:
                        excerpt.append({
                            "time": record.get("time"), "status": status,
                            "upstream_status": record.get("upstream_status"),
                            "upstream_addr": record.get("upstream_addr"),
                            "request_time": record.get("request_time"),
                        })
            except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
                malformed_records += 1
        expected_known = all(expected[phase] is not None for phase in phases)
        complete = expected_known and malformed_records == 0 and all(
            int(phases[phase]["malformed_records"]) == 0
            and
            int(phases[phase]["matching_records"]) == expected[phase]
            for phase in phases
        )
        if complete or not expected_known or time.monotonic() >= deadline:
            for phase, payload in phases.items():
                payload["expected_completed_requests"] = expected[phase]
                payload["reconciliation_difference"] = (
                    int(payload["matching_records"]) - expected[phase]
                    if expected[phase] is not None else None
                )
            return {
                "availability": "complete" if complete else "incomplete",
                "malformed_records": malformed_records,
                "phases": phases,
            }
        time.sleep(0.25)


def update_row_artifacts(row: dict[str, object], paths: dict[str, Path]) -> None:
    raw = [relative(path) for key, path in paths.items() if key.endswith("raw") and path.exists()]
    results = [relative(path) for key, path in paths.items() if key.startswith("result") and path.exists()]
    diagnostics = [relative(path) for key, path in paths.items() if key.startswith("nginx") and path.exists()]
    row["raw_files"], row["result_files"], row["diagnostic_files"] = raw, results, diagnostics
    row["no_raw_output"] = not raw


def skip_remaining(rows: list[dict[str, object]], reason: str) -> None:
    for row in rows:
        if row["status"] == "planned":
            row["status"] = "skipped"
            row["reason"] = reason
            row["median_eligible"] = False
            row["median_exclusion_reason"] = reason
            row["topology"] = {"activation": "not attempted", "restoration": "not attempted"}
            row["no_raw_output"] = True


def mark_interrupted_row(row: dict[str, object], paths: dict[str, Path], reason: str) -> None:
    """Preserve the active run separately from later rows that were never started."""
    document = load_json(paths["result_json"])
    row["status"] = "interrupted"
    row["reason"] = reason
    row["metrics"] = metrics_from_result(document)
    row["warmup_metrics"] = warmup_metrics_from_result(document)
    row["median_eligible"] = False
    row["median_exclusion_reason"] = reason
    restored = document.get("restored_three_backends") if document is not None else None
    row["topology"] = {
        "activation": "verified" if document is not None and document.get("warmup") is not None else "unknown",
        "restoration": "verified" if restored is True else "not verified",
    }
    update_row_artifacts(row, paths)
    row["finished_at"] = datetime.now(UTC).isoformat()
    row["finalized"] = True


def mark_postprocessing_failure(row: dict[str, object], paths: dict[str, Path]) -> None:
    reason = "benchmark post-processing could not be completed"
    row["status"], row["reason"] = "failed", reason
    document = load_json(paths["result_json"])
    row["metrics"] = metrics_from_result(document)
    row["warmup_metrics"] = warmup_metrics_from_result(document)
    row["median_eligible"], row["median_exclusion_reason"] = False, reason
    update_row_artifacts(row, paths)
    row["finished_at"] = datetime.now(UTC).isoformat()
    row["finalized"] = True


def run_sequence(sequence_id: str | None = None) -> tuple[int, Path]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    sequence_id = sequence_id or new_sequence_id()
    manifest = new_manifest(sequence_id)
    path = manifest_path(sequence_id)
    problem = collision_error(manifest, path)
    if problem:
        print(problem, file=sys.stderr)
        return 1, path
    write_manifest(path, manifest)
    print("Benchmark manifest: " + relative(path))
    manifest["static_compose_contract"] = "verified" if compose_contract_ok() else "not verified"
    if manifest["static_compose_contract"] != "verified":
        rows = manifest["rows"]
        assert isinstance(rows, list)
        skip_remaining(rows, "locked backend CPU or Uvicorn-worker configuration was not verified")
        write_manifest(path, manifest)
        return 1, path
    preflight_problem = loadtest.activate_topology(3)
    if preflight_problem is not None:
        manifest["preflight_topology"] = "failed"
        rows = manifest["rows"]
        assert isinstance(rows, list)
        skip_remaining(rows, "initial three-backend topology could not be verified")
        write_manifest(path, manifest)
        print("initial benchmark topology could not be verified; no token was requested", file=sys.stderr)
        return 1, path
    manifest["preflight_topology"] = "verified"
    write_manifest(path, manifest)
    token = acquire_token()
    if token is None:
        manifest["token_acquisition"] = "failed (sanitized)"
        rows = manifest["rows"]
        assert isinstance(rows, list)
        skip_remaining(rows, "fresh token acquisition failed")
        write_manifest(path, manifest)
        print("fresh token acquisition failed; no benchmark was started", file=sys.stderr)
        return 1, path
    manifest["token_acquisition"] = "succeeded (token not persisted)"
    write_manifest(path, manifest)
    rows = manifest["rows"]
    assert isinstance(rows, list)
    outcome = 0
    active_row: dict[str, object] | None = None
    active_paths: dict[str, Path] | None = None
    try:
        for row in rows:
            assert isinstance(row, dict)
            marker = str(row["run_id"])
            instances = int(row["topology_instances"])
            repetition = int(row["topology_repetition"])
            paths = artifact_paths(marker, instances, repetition)
            active_row, active_paths = row, paths
            print(
                "Starting run {}/6: {} backend(s), C20; warm-up then measured requests".format(
                    row["ordinal"], instances
                )
            )
            row["status"] = "running"
            row["finalized"] = False
            row["started_at"] = datetime.now(UTC).isoformat()
            row["median_eligible"] = False
            row["median_exclusion_reason"] = "benchmark invocation is running"
            write_manifest(path, manifest)
            environment = os.environ.copy()
            environment["LOADTEST_TOKEN"] = token
            try:
                invocation = subprocess.run(
                    [sys.executable, str(LOADTEST), "--single-run", "--instances", str(instances),
                     "--concurrency", str(CONCURRENCY), "--requests", str(MEASURED_REQUESTS),
                     "--rep", str(repetition), "--benchmark-id", marker],
                    cwd=ROOT, check=False, capture_output=True, text=True, env=environment,
                )
                row["invocation_exit_status"] = invocation.returncode
            except OSError:
                row["invocation_exit_status"] = 127
                row["status"] = "failed"
                row["reason"] = "benchmark harness could not be launched"
                row["median_eligible"] = False
                row["median_exclusion_reason"] = "benchmark harness could not be launched"
                row["topology"] = {"activation": "unknown", "restoration": "unknown"}
                update_row_artifacts(row, paths)
                row["finished_at"] = datetime.now(UTC).isoformat()
                write_manifest(path, manifest)
                skip_remaining(rows, "benchmark harness launch or topology state could not be verified")
                write_manifest(path, manifest)
                return 1, path
            document = load_json(paths["result_json"])
            status, reason, eligible, exclusion = classify(
                document, paths, row["invocation_exit_status"], marker, instances, repetition
            )
            row["status"], row["reason"] = status, reason
            row["metrics"] = metrics_from_result(document)
            row["warmup_metrics"] = warmup_metrics_from_result(document)
            row["median_eligible"], row["median_exclusion_reason"] = eligible, exclusion
            restored = document.get("restored_three_backends") if document is not None else None
            activated = "verified" if document is not None and document.get("topology_activated") is True else "unknown"
            row["topology"] = {
                "activation": activated,
                "restoration": "verified" if restored is True else "not verified",
            }
            if restored is not True:
                status = "failed"
                reason = "three-backend restoration or topology state was not verified"
                eligible, exclusion = False, reason
                row["status"], row["reason"] = status, reason
                row["median_eligible"], row["median_exclusion_reason"] = eligible, exclusion
            expected = {
                "warmup": row["metrics"].get("warmup_completed_requests") if isinstance(row["metrics"], dict) else None,
                "measured": row["metrics"].get("completed_requests") if isinstance(row["metrics"], dict) else None,
            }
            diagnostics = read_nginx_diagnostics(marker, expected)
            atomic_json(paths["nginx_diagnostics"], diagnostics)
            excerpts = {
                phase: payload.get("non_2xx_excerpt")
                for phase, payload in diagnostics.get("phases", {}).items()
                if isinstance(payload, dict) and payload.get("non_2xx_excerpt")
            } if isinstance(diagnostics.get("phases"), dict) else {}
            if excerpts:
                atomic_json(paths["nginx_non_2xx"], {
                    "generated_by": GENERATED_BY,
                    "run_id": marker,
                    "excerpts": excerpts,
                })
            row["nginx_diagnostics"] = diagnostics
            update_row_artifacts(row, paths)
            row["finished_at"] = datetime.now(UTC).isoformat()
            write_manifest(path, manifest)
            row["finalized"] = True
            write_manifest(path, manifest)
            if restored is not True:
                outcome = 1
                skip_remaining(rows, "three-backend restoration or topology state was not verified")
                write_manifest(path, manifest)
                break
            if status != "complete":
                outcome = 1
    except KeyboardInterrupt:
        outcome = 130
        if active_row is not None and active_paths is not None and active_row.get("finalized") is not True:
            mark_interrupted_row(active_row, active_paths, "benchmark sequence interrupted during active run")
        skip_remaining(rows, "benchmark sequence interrupted")
        write_manifest(path, manifest)
    except Exception:
        outcome = 1
        if active_row is not None and active_paths is not None and active_row.get("finalized") is not True:
            mark_postprocessing_failure(active_row, active_paths)
        skip_remaining(rows, "benchmark post-processing could not be completed")
        try:
            write_manifest(path, manifest)
        except OSError:
            print("benchmark manifest persistence could not be verified", file=sys.stderr)
    return outcome, path


def main() -> int:
    code, _ = run_sequence()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
