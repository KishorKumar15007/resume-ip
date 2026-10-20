"""Measure authenticated Nginx distribution across the three DA3 backends."""

from __future__ import annotations

import csv
import json
import os
import secrets
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs, urlsplit

import requests


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILE = REPOSITORY_ROOT / "compose.da3.yml"
NGINX_LOG_PATH = REPOSITORY_ROOT / "docs" / "da3" / "results" / "nginx-logs" / "da3-access.log"
RESULTS_DIRECTORY = REPOSITORY_ROOT / "docs" / "da3" / "results"
RAW_RESULT_PATH = RESULTS_DIRECTORY / "09-distribution-raw.json"
CSV_RESULT_PATH = RESULTS_DIRECTORY / "09-distribution.csv"
MARKDOWN_RESULT_PATH = RESULTS_DIRECTORY / "09-distribution.md"
BASE_URL = "http://localhost:8080"
REQUEST_COUNT = 300
CONCURRENCY = 10
REQUEST_TIMEOUT_SECONDS = 20
LOG_SETTLE_TIMEOUT_SECONDS = 10
BACKENDS = ("backend-1", "backend-2", "backend-3")


def new_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"da3-dist-{timestamp}-{secrets.token_hex(4)}"


def run_command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments,
            cwd=REPOSITORY_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return subprocess.CompletedProcess(arguments, 127, "", "")


def discover_backend_mapping() -> tuple[dict[str, str], list[str]]:
    mapping: dict[str, str] = {}
    errors: list[str] = []

    for backend in BACKENDS:
        ps_result = run_command(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "-q", backend]
        )
        container_ids = [line.strip() for line in ps_result.stdout.splitlines() if line.strip()]
        if ps_result.returncode != 0 or len(container_ids) != 1:
            errors.append(f"could not resolve exactly one running container for {backend}")
            continue

        inspect_result = run_command(["docker", "inspect", container_ids[0]])
        if inspect_result.returncode != 0:
            errors.append(f"could not inspect container for {backend}")
            continue

        try:
            inspected = json.loads(inspect_result.stdout)
            networks = inspected[0]["NetworkSettings"]["Networks"]
            addresses = {
                details.get("IPAddress", "")
                for details in networks.values()
                if details.get("IPAddress")
            }
        except (IndexError, KeyError, TypeError, ValueError):
            errors.append(f"could not read a container address for {backend}")
            continue

        if len(addresses) != 1:
            errors.append(f"could not determine one backend address for {backend}")
            continue

        address = f"{addresses.pop()}:8000"
        if address in mapping:
            errors.append("multiple backend services resolved to the same address")
            continue
        mapping[address] = backend

    if set(mapping.values()) != set(BACKENDS):
        errors.append("dynamic backend mapping is incomplete")

    return mapping, errors


def send_request(sequence: int, run_id: str, token: str) -> dict[str, object]:
    started = perf_counter()
    result: dict[str, object] = {
        "sequence": sequence,
        "status": None,
        "served_by": None,
        "elapsed_ms": None,
        "exception_type": None,
    }
    try:
        response = requests.get(
            f"{BASE_URL}/postings",
            params={"dist": run_id, "seq": str(sequence)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        result["status"] = normalize_status(response.status_code)
        result["served_by"] = response.headers.get("X-Served-By")
    except requests.RequestException as exc:
        result["exception_type"] = type(exc).__name__
    finally:
        result["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
    return result


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


def log_is_readable() -> bool:
    if not NGINX_LOG_PATH.is_file():
        return False
    try:
        with NGINX_LOG_PATH.open("rb") as access_log:
            access_log.read(1)
    except OSError:
        return False
    return True


def request_identity(record: dict[str, object], run_id: str) -> tuple[int | None, str | None]:
    request = record.get("request")
    if not isinstance(request, str):
        return None, "request field is not a string"
    parts = request.split(" ")
    if len(parts) != 3 or parts[0] != "GET":
        return None, "request line is malformed"

    parsed = urlsplit(parts[1])
    if parsed.path != "/postings":
        return None, None
    query = parse_qs(parsed.query, keep_blank_values=True)
    if query.get("dist") != [run_id]:
        return None, None
    sequence_values = query.get("seq")
    if sequence_values is None or len(sequence_values) != 1:
        return None, "request has an invalid sequence parameter"
    try:
        return int(sequence_values[0]), None
    except ValueError:
        return None, "request sequence is not an integer"


def parse_upstream_chain(record: dict[str, object], mapping: dict[str, str]) -> dict[str, object]:
    raw_addresses = record.get("upstream_addr")
    raw_statuses = record.get("upstream_status")
    parsed: dict[str, object] = {
        "raw_upstream_addr": raw_addresses,
        "raw_upstream_status": raw_statuses,
        "upstream_addresses": [],
        "upstream_statuses": [],
        "final_upstream_addr": None,
        "final_upstream_backend": None,
        "chain_error": None,
    }
    if not isinstance(raw_addresses, str) or not isinstance(raw_statuses, str):
        parsed["chain_error"] = "upstream chain fields are not strings"
        return parsed

    addresses = [value.strip() for value in raw_addresses.split(",")]
    statuses = [value.strip() for value in raw_statuses.split(",")]
    parsed["upstream_addresses"] = addresses
    parsed["upstream_statuses"] = statuses
    if not addresses or any(not value for value in addresses):
        parsed["chain_error"] = "upstream address chain is malformed"
        return parsed
    if len(addresses) != len(statuses) or any(not value for value in statuses):
        parsed["chain_error"] = "upstream address/status chain lengths differ"
        return parsed

    final_address = addresses[-1]
    parsed["final_upstream_addr"] = final_address
    parsed["final_upstream_backend"] = mapping.get(final_address)
    return parsed


def read_run_log_records(
    run_id: str, mapping: dict[str, str]
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    records: list[dict[str, object]] = []
    malformed: list[dict[str, object]] = []
    if not NGINX_LOG_PATH.is_file():
        return records, [{"reason": "Nginx access log is unavailable"}]

    try:
        lines = NGINX_LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return records, [{"reason": "Nginx access log could not be read"}]

    for line_number, line in enumerate(lines, 1):
        if run_id not in line:
            continue
        try:
            raw_record = json.loads(line)
        except json.JSONDecodeError:
            malformed.append({"line_number": line_number, "reason": "matching log line is not JSON"})
            continue
        if not isinstance(raw_record, dict):
            malformed.append({"line_number": line_number, "reason": "matching log JSON is not an object"})
            continue

        sequence, identity_error = request_identity(raw_record, run_id)
        if identity_error is not None:
            malformed.append({"line_number": line_number, "reason": identity_error})
            continue
        if sequence is None:
            continue

        parsed_chain = parse_upstream_chain(raw_record, mapping)
        records.append(
            {
                "line_number": line_number,
                "sequence": sequence,
                "raw_status": raw_record.get("status"),
                "status": normalize_status(raw_record.get("status")),
                "status_error": (
                    None
                    if normalize_status(raw_record.get("status")) is not None
                    else "Nginx status is missing, malformed, or non-numeric"
                ),
                "request": raw_record.get("request"),
                **parsed_chain,
            }
        )
    return records, malformed


def settle_log_records(run_id: str, mapping: dict[str, str]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    deadline = time.monotonic() + LOG_SETTLE_TIMEOUT_SECONDS
    records: list[dict[str, object]] = []
    malformed: list[dict[str, object]] = []
    while True:
        records, malformed = read_run_log_records(run_id, mapping)
        if len(records) >= REQUEST_COUNT or time.monotonic() >= deadline:
            return records, malformed
        time.sleep(0.25)


def count_backends(values: list[object]) -> dict[str, int]:
    counts = Counter(value for value in values if isinstance(value, str))
    return {backend: counts[backend] for backend in BACKENDS}


def build_reconciliation(
    client_records: list[dict[str, object]],
    log_records: list[dict[str, object]],
    malformed_records: list[dict[str, object]],
    mapping: dict[str, str],
    preflight_errors: list[str],
) -> dict[str, object]:
    expected_sequences = set(range(1, REQUEST_COUNT + 1))
    client_by_sequence = {int(record["sequence"]): record for record in client_records}
    log_by_sequence: dict[int, list[dict[str, object]]] = {}
    for record in log_records:
        log_by_sequence.setdefault(int(record["sequence"]), []).append(record)

    duplicate_log_sequences = sorted(sequence for sequence, records in log_by_sequence.items() if len(records) > 1)
    log_sequences = set(log_by_sequence)
    missing_log_sequences = sorted(expected_sequences - log_sequences)
    unexpected_log_sequences = sorted(log_sequences - expected_sequences)
    http_failures = [record["sequence"] for record in client_records if record["status"] != 200]
    missing_or_unknown_headers = [
        record["sequence"]
        for record in client_records
        if record["served_by"] not in BACKENDS
    ]
    malformed_chains = [
        record["sequence"] for record in log_records if record["chain_error"] is not None
    ]
    malformed_statuses = [
        record["sequence"] for record in log_records if record["status_error"] is not None
    ]
    unknown_upstreams = [
        record["sequence"]
        for record in log_records
        if record["chain_error"] is None and record["final_upstream_backend"] not in BACKENDS
    ]
    disagreements: list[int] = []
    status_disagreements: list[int] = []
    for sequence in sorted(expected_sequences & log_sequences):
        if len(log_by_sequence[sequence]) != 1:
            continue
        client = client_by_sequence.get(sequence)
        log = log_by_sequence[sequence][0]
        if client is None or client["served_by"] != log["final_upstream_backend"]:
            disagreements.append(sequence)
        if client is None or client["status"] != log["status"]:
            status_disagreements.append(sequence)

    header_counts = count_backends([record["served_by"] for record in client_records])
    upstream_counts = count_backends([record["final_upstream_backend"] for record in log_records])
    checks = {
        "preflight_ready": not preflight_errors,
        "exactly_300_client_records": len(client_records) == REQUEST_COUNT,
        "all_client_sequences_unique": len(client_by_sequence) == REQUEST_COUNT and set(client_by_sequence) == expected_sequences,
        "all_http_statuses_successful": not http_failures,
        "all_headers_known": not missing_or_unknown_headers,
        "exactly_300_log_records": len(log_records) == REQUEST_COUNT,
        "all_log_sequences_unique": not duplicate_log_sequences and not missing_log_sequences and not unexpected_log_sequences,
        "no_malformed_log_records": not malformed_records and not malformed_chains and not malformed_statuses,
        "all_upstream_backends_known": not unknown_upstreams,
        "per_request_identity_agrees": not disagreements,
        "per_request_status_agrees": not status_disagreements,
        "aggregate_counts_agree": header_counts == upstream_counts,
        "each_backend_received_requests": all(
            header_counts[backend] > 0 and upstream_counts[backend] > 0 for backend in BACKENDS
        ),
        "dynamic_mapping_complete": set(mapping.values()) == set(BACKENDS),
    }
    return {
        "checks": checks,
        "passed": all(checks.values()),
        "header_counts": header_counts,
        "upstream_counts": upstream_counts,
        "http_failure_sequences": http_failures,
        "missing_or_unknown_header_sequences": missing_or_unknown_headers,
        "missing_log_sequences": missing_log_sequences,
        "duplicate_log_sequences": duplicate_log_sequences,
        "unexpected_log_sequences": unexpected_log_sequences,
        "malformed_log_records": malformed_records,
        "malformed_upstream_chain_sequences": malformed_chains,
        "malformed_status_sequences": malformed_statuses,
        "unknown_upstream_sequences": unknown_upstreams,
        "header_upstream_disagreement_sequences": disagreements,
        "client_log_status_disagreement_sequences": status_disagreements,
    }


def write_results(result: dict[str, object]) -> None:
    RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RAW_RESULT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    reconciliation = result["reconciliation"]
    assert isinstance(reconciliation, dict)
    header_counts = reconciliation["header_counts"]
    upstream_counts = reconciliation["upstream_counts"]
    assert isinstance(header_counts, dict) and isinstance(upstream_counts, dict)
    client_total = len(result["client_records"])
    log_total = len(result["nginx_log_records"])
    with CSV_RESULT_PATH.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output)
        writer.writerow(["backend", "header_count", "header_percent", "upstream_count", "upstream_percent"])
        for backend in BACKENDS:
            header_count = int(header_counts[backend])
            upstream_count = int(upstream_counts[backend])
            writer.writerow(
                [
                    backend,
                    header_count,
                    f"{(header_count / client_total * 100) if client_total else 0:.2f}",
                    upstream_count,
                    f"{(upstream_count / log_total * 100) if log_total else 0:.2f}",
                ]
            )

    checks = reconciliation["checks"]
    assert isinstance(checks, dict)
    lines = [
        "# DA3 Step 9 Distribution Result",
        "",
        f"Run ID: `{result['run_id']}`",
        "",
        f"Overall result: **{'PASS' if reconciliation['passed'] else 'FAIL'}**",
        "",
        "| Backend | X-Served-By count | X-Served-By % | Final upstream count | Final upstream % |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for backend in BACKENDS:
        header_count = int(header_counts[backend])
        upstream_count = int(upstream_counts[backend])
        lines.append(
            f"| {backend} | {header_count} | {(header_count / client_total * 100) if client_total else 0:.2f}% | {upstream_count} | {(upstream_count / log_total * 100) if log_total else 0:.2f}% |"
        )
    lines.extend(["", "| Acceptance check | Result |", "| --- | --- |"])
    for name, passed in checks.items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            f"Client records: {client_total}; matching Nginx records: {log_total}.",
            "Retry chains are retained in `09-distribution-raw.json` and counted once by their final upstream address.",
            "No authorization header, token, response body, database URL, or configuration path is recorded.",
        ]
    )
    MARKDOWN_RESULT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def print_summary(result: dict[str, object]) -> None:
    reconciliation = result["reconciliation"]
    assert isinstance(reconciliation, dict)
    header_counts = reconciliation["header_counts"]
    upstream_counts = reconciliation["upstream_counts"]
    checks = reconciliation["checks"]
    assert isinstance(header_counts, dict) and isinstance(upstream_counts, dict)
    assert isinstance(checks, dict)
    client_total = len(result["client_records"])
    log_total = len(result["nginx_log_records"])

    print(f"Run ID: {result['run_id']}")
    print(f"Overall: {'PASS' if reconciliation['passed'] else 'FAIL'}")
    print("Backend    Header count  Header %  Final upstream count  Final upstream %")
    for backend in BACKENDS:
        header_count = int(header_counts[backend])
        upstream_count = int(upstream_counts[backend])
        header_percent = (header_count / client_total * 100) if client_total else 0
        upstream_percent = (upstream_count / log_total * 100) if log_total else 0
        print(
            f"{backend:<10} {header_count:>12} {header_percent:>8.2f}%"
            f" {upstream_count:>21} {upstream_percent:>16.2f}%"
        )
    failed_checks = [name for name, passed in checks.items() if not passed]
    if failed_checks:
        print("Failed acceptance checks: " + ", ".join(failed_checks), file=sys.stderr)


def main() -> int:
    run_id = new_run_id()
    token = os.environ.get("LOADTEST_TOKEN")
    mapping, preflight_errors = discover_backend_mapping()
    if not token:
        preflight_errors.append("LOADTEST_TOKEN is unavailable")
    if not log_is_readable():
        preflight_errors.append("Nginx access log is unavailable or unreadable")

    client_records: list[dict[str, object]] = []
    if not preflight_errors and token is not None:
        with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = [executor.submit(send_request, sequence, run_id, token) for sequence in range(1, REQUEST_COUNT + 1)]
            for future in as_completed(futures):
                client_records.append(future.result())
        client_records.sort(key=lambda record: int(record["sequence"]))

    log_records, malformed_records = settle_log_records(run_id, mapping) if not preflight_errors else ([], [])
    reconciliation = build_reconciliation(
        client_records, log_records, malformed_records, mapping, preflight_errors
    )
    result = {
        "run_id": run_id,
        "request_count": REQUEST_COUNT,
        "concurrency": CONCURRENCY,
        "base_url": BASE_URL,
        "dynamic_backend_mapping": mapping,
        "preflight_errors": preflight_errors,
        "client_records": client_records,
        "nginx_log_records": log_records,
        "reconciliation": reconciliation,
    }
    write_results(result)
    print_summary(result)

    if reconciliation["passed"]:
        print("distribution test PASS")
        return 0
    print("distribution test FAIL", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
