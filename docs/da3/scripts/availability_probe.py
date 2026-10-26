"""Owner-run Step 13 availability probe; uses only the Python standard library."""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


FIELDS = ("timestamp_utc", "status", "latency_ms", "outcome")


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def summarise(path: Path) -> dict[str, object]:
    rows: list[dict[str, str]] = []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("probe CSV schema is invalid")
        for row in reader:
            if set(row) != set(FIELDS) or any(row.get(field) is None for field in FIELDS):
                raise ValueError("probe CSV contains missing fields")
            try:
                started = datetime.fromisoformat(str(row["timestamp_utc"]))
                latency = float(str(row["latency_ms"]))
            except (KeyError, TypeError, ValueError):
                raise ValueError("probe CSV contains malformed timestamp or latency") from None
            if started.tzinfo is None or not math.isfinite(latency) or latency < 0:
                raise ValueError("probe CSV contains invalid timestamp or latency")
            outcome, status = str(row["outcome"]), str(row["status"])
            if outcome not in {"http-200", "http-non-200", "timeout", "error"}:
                raise ValueError("probe CSV contains unknown outcome")
            if outcome == "http-200" and status != "200":
                raise ValueError("http-200 row has inconsistent status")
            if outcome == "http-non-200":
                try:
                    parsed = int(status)
                except ValueError:
                    raise ValueError("non-200 row has invalid status") from None
                if not 100 <= parsed <= 599 or parsed == 200:
                    raise ValueError("non-200 row has inconsistent status")
            if outcome in {"timeout", "error"} and status:
                raise ValueError("transport-error row must have blank status")
            row["_started"] = started.isoformat()
            rows.append(row)
    if not rows:
        raise ValueError("probe CSV contains no samples")
    moments = [datetime.fromisoformat(str(row["_started"])).timestamp() for row in rows]
    if any(later < earlier for earlier, later in zip(moments, moments[1:])):
        raise ValueError("probe timestamps are non-monotonic")
    outcomes = [str(row.get("outcome")) for row in rows]
    non_200 = sum(outcome == "http-non-200" for outcome in outcomes)
    timeouts = sum(outcome == "timeout" for outcome in outcomes)
    errors = sum(outcome == "error" for outcome in outcomes)
    return {
        "total_samples": len(rows),
        "http_200": sum(outcome == "http-200" for outcome in outcomes),
        "non_200": non_200,
        "timeouts": timeouts,
        "transport_errors": errors,
        "failed_probes": non_200 + timeouts + errors,
        "longest_observed_gap_seconds": max((later - earlier for earlier, later in zip(moments, moments[1:])), default=0.0),
        "first_sample_at": rows[0]["timestamp_utc"],
        "last_sample_at": rows[-1]["timestamp_utc"],
    }


def sample(url: str, timeout: float) -> tuple[str, str, str]:
    started = time.monotonic()
    status = ""
    outcome = "error"
    try:
        with urlopen(url, timeout=timeout) as response:
            status = str(response.status)
            outcome = "http-200" if response.status == 200 else "http-non-200"
    except HTTPError as error:
        status, outcome = str(error.code), "http-non-200"
    except TimeoutError:
        outcome = "timeout"
    except URLError as error:
        outcome = "timeout" if isinstance(error.reason, TimeoutError) else "error"
    except OSError:
        outcome = "error"
    return status, format((time.monotonic() - started) * 1000, ".3f"), outcome


def run(output: Path, stop_file: Path, url: str, interval: float, timeout: float) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or stop_file.exists():
        raise FileExistsError("refusing to overwrite probe artifacts")
    with output.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); handle.flush()
        while not stop_file.exists():
            started = timestamp()
            status, latency, outcome = sample(url, timeout)
            writer.writerow({"timestamp_utc": started, "status": status, "latency_ms": latency, "outcome": outcome})
            handle.flush()
            time.sleep(interval)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="DA3 Step 13 availability probe")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    parser.add_argument("--url", default="http://localhost:8080/health")
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--summary-only", type=Path)
    args = parser.parse_args()
    if args.summary_only:
        print(json.dumps(summarise(args.summary_only), sort_keys=True))
        return 0
    if args.interval <= 0 or args.timeout <= 0:
        parser.error("interval and timeout must be positive")
    return run(args.output, args.stop_file, args.url, args.interval, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
