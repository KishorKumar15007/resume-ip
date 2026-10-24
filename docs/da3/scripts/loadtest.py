"""DA3 Apache Bench calibration harness; owner-run only."""
from __future__ import annotations
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "compose.da3.yml"
RESULTS = ROOT / "docs" / "da3" / "results"
LEVELS = (5, 10, 20, 50, 100)
WARMUP, MEASURED, DEFAULT_REQUESTS = 100, 300, 1000
BACKENDS = ("backend-1", "backend-2", "backend-3")
RUN_LABEL = "com.resume_ip.da3_loadtest_run"
AB_TIMEOUT_SECONDS = 120
BENCHMARK_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]{0,79}")

@dataclass
class Cleanup:
    commands_succeeded: bool
    final_state_known: bool
    no_containers_remain: bool | None
    stopped_leftovers: int = 0
    forced: bool = False
    error: str | None = None
    @property
    def verified(self) -> bool:
        return self.commands_succeeded and self.final_state_known and self.no_containers_remain is True

@dataclass
class Metrics:
    requests: int
    completed_requests: int | None
    requests_per_second: str | None
    mean_time_per_request_ms: str | None
    failed_requests: int | None
    connect_failures: int | None
    receive_failures: int | None
    length_failures: int | None
    exception_failures: int | None
    non_2xx_responses: int | None
    return_code: int
    launched: bool = False
    interrupted: bool = False
    timed_out: bool = False
    execution_error: str | None = None
    invocation_id: str | None = None
    cleanup: Cleanup | None = None

@dataclass
class Point:
    instances: int
    concurrency: int
    rep: int
    warmup: Metrics | None = None
    measurement: Metrics | None = None
    error: str | None = None
    not_run: bool = False
    measurement_skipped: bool = False

def project_name() -> str | None:
    name = os.environ.get("COMPOSE_PROJECT_NAME", ROOT.name)
    return name if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name or "") else None

def compose(*args: str, nginx_conf: str | None = None) -> subprocess.CompletedProcess[str]:
    name = project_name()
    if name is None:
        return subprocess.CompletedProcess(args, 2, "", "invalid Compose project identity")
    env = os.environ.copy()
    if nginx_conf:
        env["NGINX_CONF"] = nginx_conf
    try:
        return subprocess.run(["docker", "compose", "--project-name", name, "-f", str(COMPOSE), *args], cwd=ROOT, check=False, capture_output=True, text=True, env=env, timeout=75)
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(args, 127, "", "Compose command failed or timed out")

def as_text(value: str | bytes | None) -> str:
    return "" if value is None else value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value

def append_unique(parts: list[str], value: str | bytes | None) -> None:
    value = as_text(value)
    old = "".join(parts)
    if not value:
        return
    if value.startswith(old):
        parts[:] = [value]
        return
    overlap = min(len(old), len(value))
    while overlap and old[-overlap:] != value[:overlap]:
        overlap -= 1
    parts.append(value[overlap:])

def parse_ab(output: str, requests: int, code: int) -> Metrics:
    def integer(pattern: str) -> int | None:
        match = re.search(pattern, output, re.MULTILINE)
        return int(match.group(1)) if match else None
    def decimal(pattern: str) -> str | None:
        match = re.search(pattern, output, re.MULTILINE)
        return match.group(1) if match else None
    breakdown = re.search(r"^Failed requests:\s*\d+\s*\((?P<fields>.*?)\)\s*$", output, re.MULTILINE)
    def field(name: str) -> int | None:
        match = None if breakdown is None else re.search(rf"\b{name}:\s*(\d+)", breakdown.group("fields"))
        return int(match.group(1)) if match else None
    completed = integer(r"^Complete requests:\s*(\d+)\s*$")
    requests_per_second = decimal(r"^Requests per second:\s*([0-9.]+)\s+\[#/sec\]")
    mean_time = decimal(r"^Time per request:\s*([0-9.]+)\s+\[ms\]\s+\(mean\)")
    failed = integer(r"^Failed requests:\s*(\d+)")
    non_2xx = integer(r"^Non-2xx responses:\s*(\d+)\s*$")
    if (non_2xx is None and code == 0 and completed == requests and failed == 0
            and requests_per_second is not None and mean_time is not None):
        non_2xx = 0
    return Metrics(requests, completed, requests_per_second, mean_time, failed,
                   field("Connect"), field("Receive"), field("Length"),
                   field("Exceptions"), non_2xx, code)

def invocation_containers(run_id: str) -> tuple[str, ...] | None:
    name = project_name()
    if name is None:
        return None
    try:
        result = subprocess.run(["docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={name}", "--filter", "label=com.docker.compose.service=loadtest", "--filter", f"label={RUN_LABEL}={run_id}"], cwd=ROOT, check=False, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    values = tuple(line for line in result.stdout.splitlines() if line)
    return values if result.returncode == 0 and all(re.fullmatch(r"[0-9a-f]{12,64}", value) for value in values) else None

def cleanup_invocation(run_id: str) -> Cleanup:
    ids = invocation_containers(run_id)
    if ids is None:
        return Cleanup(False, False, None, error="could not discover invocation containers")
    commands_ok, forced, stopped_leftovers = True, False, 0
    for cid in ids:
        try:
            state = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", cid], cwd=ROOT, check=False, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return Cleanup(False, False, None, stopped_leftovers, forced, "could not inspect invocation container")
        if state.returncode != 0:
            commands_ok = False
            continue
        if state.stdout.strip() == "true":
            try:
                stopped = subprocess.run(["docker", "stop", "--time", "10", cid], cwd=ROOT, check=False, capture_output=True, text=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired):
                stopped = None
            if stopped is None or stopped.returncode != 0:
                commands_ok, forced = False, True
                try:
                    killed = subprocess.run(["docker", "kill", cid], cwd=ROOT, check=False, capture_output=True, text=True, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    killed = None
                if killed is None or killed.returncode != 0:
                    commands_ok = False
        else:
            stopped_leftovers += 1
        try:
            removed = subprocess.run(["docker", "rm", "-f", cid], cwd=ROOT, check=False, capture_output=True, text=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            removed = None
        if removed is None or removed.returncode != 0:
            commands_ok = False
    remaining = invocation_containers(run_id)
    if remaining is None:
        return Cleanup(commands_ok, False, None, stopped_leftovers, forced, "could not verify invocation cleanup")
    return Cleanup(commands_ok, True, not bool(remaining), stopped_leftovers, forced, None if commands_ok and not remaining else "invocation cleanup failed or containers remain")

def benchmark_id(value: str) -> str:
    if not BENCHMARK_ID_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "--benchmark-id must contain lowercase letters, digits, and hyphens"
        )
    return value


def benchmark_target(marker: str | None, phase: str | None) -> str:
    if marker is None:
        return "/postings"
    if phase not in {"warmup", "measured"}:
        raise ValueError("benchmark phase is invalid")
    return f"/postings?bench={marker}&phase={phase}"


def run_ab(requests: int, concurrency: int, output_path: Path,
           target: str = "/postings") -> Metrics:
    name, run_id = project_name(), uuid.uuid4().hex
    if name is None:
        item = parse_ab("", requests, 127)
        item.execution_error, item.invocation_id = "invalid Compose project identity", run_id
        output_path.write_text("", encoding="utf-8")
        return item
    url = shlex.quote("http://nginx" + target)
    shell = (
        f'exec ab -k -n {requests} -c {concurrency} '
        '-H "Authorization: Bearer $LOADTEST_TOKEN" '
        + url
    )
    command = ["docker", "compose", "--project-name", name, "-f", str(COMPOSE), "--profile", "loadtest", "run", "--rm", "--no-deps", "--label", f"{RUN_LABEL}={run_id}", "-e", "LOADTEST_TOKEN", "--entrypoint", "sh", "loadtest", "-c", shell]
    parts: list[str] = []
    process: subprocess.Popen[str] | None = None
    error: str | None = None
    timed_out = interrupted = False
    clean: Cleanup | None = None
    code = 127
    try:
        try:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except OSError:
            error = "load-test command could not be launched"
        else:
            try:
                output, _ = process.communicate(timeout=AB_TIMEOUT_SECONDS)
                append_unique(parts, output)
            except subprocess.TimeoutExpired as exc:
                timed_out, error = True, (
                    f"load-test command exceeded the {AB_TIMEOUT_SECONDS}-second wall-clock limit"
                )
                append_unique(parts, exc.output)
                try:
                    process.terminate()
                    output, _ = process.communicate(timeout=15)
                    append_unique(parts, output)
                except subprocess.TimeoutExpired as later:
                    append_unique(parts, later.output)
                    try:
                        process.kill()
                        output, _ = process.communicate(timeout=10)
                        append_unique(parts, output)
                    except subprocess.TimeoutExpired as final:
                        append_unique(parts, final.output)
                        error = "load-test command could not stop within bounded termination"
                clean = cleanup_invocation(run_id)
            code = process.returncode if process.returncode is not None else 127
    except KeyboardInterrupt:
        interrupted = True
        if process is None:
            error = "load-test command interrupted before launch"
        else:
            try:
                if process.poll() is None:
                    process.terminate()
                output, _ = process.communicate(timeout=15)
                append_unique(parts, output)
            except subprocess.TimeoutExpired as exc:
                append_unique(parts, exc.output)
                try:
                    process.kill()
                    output, _ = process.communicate(timeout=10)
                    append_unique(parts, output)
                except subprocess.TimeoutExpired as later:
                    append_unique(parts, later.output)
                    error = "load-test command could not stop within bounded interruption handling"
            finally:
                clean = cleanup_invocation(run_id)
            code = process.returncode if process.returncode is not None else 127
    if process is not None and clean is None:
        clean = cleanup_invocation(run_id)
    if clean is not None and not clean.verified and error is None:
        error = "invocation cleanup was not verified"
    output = "".join(parts)
    output_path.write_text(output, encoding="utf-8")
    item = parse_ab(output, requests, code)
    item.launched, item.interrupted, item.timed_out = process is not None, interrupted, timed_out
    item.execution_error, item.invocation_id, item.cleanup = error, run_id, clean
    return item

def complete(item: Metrics | None, expected: int) -> bool:
    return bool(item and item.completed_requests == expected and item.requests_per_second is not None and item.mean_time_per_request_ms is not None and item.failed_requests is not None and item.non_2xx_responses is not None)
def warmup_ok(item: Metrics | None) -> bool:
    return bool(complete(item, WARMUP) and item and item.return_code == 0 and not item.interrupted and not item.timed_out and item.execution_error is None and item.failed_requests == 0 and item.non_2xx_responses == 0)
def measured_ok(item: Metrics | None) -> bool:
    return bool(complete(item, MEASURED) and item and item.return_code == 0 and not item.interrupted and not item.timed_out and item.execution_error is None)
def record(traffic: dict[str, int], phase: str, item: Metrics, budget: int) -> None:
    if not item.launched:
        return
    traffic[f"launched_{phase}"] += budget
    if item.completed_requests is None:
        traffic[f"unknown_{phase}"] += budget
    else:
        traffic[f"ab_reported_completed_{phase}"] += item.completed_requests
        traffic[f"unknown_{phase}"] += max(0, budget-item.completed_requests)

def selection(points: list[Point]) -> tuple[dict[int, Decimal], dict[tuple[int, int], str], int | None]:
    required = {(i,c) for i in (1,3) for c in LEVELS}
    valid = {(p.instances,p.concurrency) for p in points if measured_ok(p.measurement)}
    if valid != required:
        return {}, {key:"unknown" for key in required}, None
    maxima = {i:max(Decimal(p.measurement.requests_per_second) for p in points if p.instances == i and p.measurement) for i in (1,3)}
    eligibility = {}
    for p in points:
        m = p.measurement
        eligibility[(p.instances,p.concurrency)] = "no" if m.failed_requests or m.non_2xx_responses else "yes" if Decimal(m.requests_per_second) >= Decimal("0.90") * maxima[p.instances] else "no"
    selected = next((c for c in LEVELS if eligibility[(1,c)] == "yes" and eligibility[(3,c)] == "yes"), None)
    return maxima, eligibility, selected

def calibration_paths(rep: int) -> tuple[Path, Path, list[Path]]:
    suffix = "" if rep == 1 else "-rep" + str(rep)
    report_json = RESULTS / ("10-calibration" + suffix + ".json")
    report_markdown = RESULTS / ("10-calibration" + suffix + ".md")
    raw: list[Path] = []
    for instances in (1, 3):
        for concurrency in LEVELS:
            stem = "10-ab-calibration-i" + str(instances) + "-c" + str(concurrency) + "-rep" + str(rep)
            raw.append(RESULTS / ("10-ab-calibration-warmup-i" + str(instances) + "-c" + str(concurrency) + "-rep" + str(rep) + ".txt"))
            raw.append(RESULTS / (stem + ".txt"))
    return report_json, report_markdown, raw

def single_paths(instances: int, concurrency: int, rep: int,
                 marker: str | None = None) -> tuple[Path, Path, Path, Path]:
    if marker is not None:
        stem = "11-1b-" + marker + "-i" + str(instances) + "-c" + str(concurrency) + "-r" + str(rep)
        return (RESULTS / (stem + "-warmup.txt"), RESULTS / (stem + ".txt"),
                RESULTS / (stem + ".json"), RESULTS / (stem + ".md"))
    stem = "10-single-i" + str(instances) + "-c" + str(concurrency) + "-rep" + str(rep)
    return (RESULTS / (stem + "-warmup.txt"), RESULTS / (stem + ".txt"),
            RESULTS / (stem + ".json"), RESULTS / (stem + ".md"))

def collision(paths: list[Path]) -> str | None:
    existing = [path.name for path in paths if path.exists()]
    if existing:
        return "refusing to overwrite existing result artifact(s): " + ", ".join(existing)
    return None

def running_services() -> set[str] | None:
    result = compose("ps", "--status", "running", "--services")
    if result.returncode != 0:
        return None
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}

def topology_is_ready(instances: int) -> bool:
    running = running_services()
    if running is None:
        return False
    expected = {"nginx", "backend-1"}
    if instances == 3:
        expected.update({"backend-2", "backend-3"})
    return expected.issubset(running) and all(name not in running for name in BACKENDS if name not in expected)

def activate_topology(instances: int) -> str | None:
    if instances not in (1, 3):
        return "unsupported backend topology"
    command = ["up", "-d", "--scale", "backend-1=1",
               "--scale", "backend-2=" + ("1" if instances == 3 else "0"),
               "--scale", "backend-3=" + ("1" if instances == 3 else "0"),
               "nginx", "backend-1", "backend-2", "backend-3"]
    started = compose(*command, nginx_conf="nginx-" + str(instances) + ".conf")
    if started.returncode != 0:
        return "Compose could not activate the requested topology"
    if not topology_is_ready(instances):
        return "requested Nginx/backend topology is not ready"
    return None

def restore_three_backends() -> bool:
    return activate_topology(3) is None

def recover_topology(instances: int) -> str | None:
    time.sleep(35)
    if topology_is_ready(instances):
        return None
    return "topology or backend health could not be verified after recovery wait"

def skipped_point(instances: int, concurrency: int, rep: int, reason: str) -> Point:
    return Point(instances, concurrency, rep, error=reason, not_run=True, measurement_skipped=True)

def record_remaining_not_run(points: list[Point], traffic: dict[str, int], rep: int, reason: str) -> None:
    present = {(point.instances, point.concurrency) for point in points}
    for instances in (1, 3):
        for concurrency in LEVELS:
            if (instances, concurrency) not in present:
                points.append(skipped_point(instances, concurrency, rep, reason))
                traffic["skipped_warmup"] = traffic.get("skipped_warmup", 0) + WARMUP
                traffic["skipped_measurement"] = traffic.get("skipped_measurement", 0) + MEASURED

def status(item: Metrics | None, expected: int) -> str:
    if item is None:
        return "not run"
    if item.interrupted:
        return "interrupted"
    if item.timed_out:
        return "timed out"
    if item.execution_error:
        return "error"
    if not complete(item, expected):
        return "incomplete"
    if item.failed_requests:
        return "failed requests"
    if item.non_2xx_responses:
        return "non-2xx responses"
    if item.return_code != 0:
        return "nonzero exit"
    return "complete"

def run_calibration(rep: int) -> tuple[list[Point], dict[str, int], str | None, bool]:
    points: list[Point] = []
    traffic = {"planned_warmup": len(LEVELS) * 2 * WARMUP,
               "planned_measurement": len(LEVELS) * 2 * MEASURED,
               "launched_warmup": 0, "launched_measurement": 0,
               "ab_reported_completed_warmup": 0, "ab_reported_completed_measurement": 0,
               "unknown_warmup": 0, "unknown_measurement": 0,
               "skipped_warmup": 0, "skipped_measurement": 0}
    stopped_reason: str | None = None
    interrupted = False
    for instances in (1, 3):
        if stopped_reason:
            for concurrency in LEVELS:
                points.append(skipped_point(instances, concurrency, rep, stopped_reason))
                traffic["skipped_warmup"] += WARMUP
                traffic["skipped_measurement"] += MEASURED
            continue
        problem = activate_topology(instances)
        if problem:
            stopped_reason = problem
            for concurrency in LEVELS:
                points.append(skipped_point(instances, concurrency, rep, problem))
                traffic["skipped_warmup"] += WARMUP
                traffic["skipped_measurement"] += MEASURED
            continue
        for concurrency in LEVELS:
            point = Point(instances, concurrency, rep)
            points.append(point)
            warm_path = RESULTS / ("10-ab-calibration-warmup-i" + str(instances) + "-c" + str(concurrency) + "-rep" + str(rep) + ".txt")
            point.warmup = run_ab(WARMUP, concurrency, warm_path)
            record(traffic, "warmup", point.warmup, WARMUP)
            if point.warmup.interrupted:
                point.error = "warm-up interrupted"
                point.measurement_skipped = True
                traffic["skipped_measurement"] += MEASURED
                stopped_reason, interrupted = point.error, True
                break
            if not warmup_ok(point.warmup):
                point.error = "warm-up " + status(point.warmup, WARMUP)
                point.measurement_skipped = True
                traffic["skipped_measurement"] += MEASURED
                problem = recover_topology(instances)
                if problem:
                    stopped_reason = problem
                    break
                continue
            measured_path = RESULTS / ("10-ab-calibration-i" + str(instances) + "-c" + str(concurrency) + "-rep" + str(rep) + ".txt")
            point.measurement = run_ab(MEASURED, concurrency, measured_path)
            record(traffic, "measurement", point.measurement, MEASURED)
            if point.measurement.interrupted:
                point.error, stopped_reason, interrupted = "measurement interrupted", "measurement interrupted", True
                break
            if not measured_ok(point.measurement) or point.measurement.failed_requests or point.measurement.non_2xx_responses:
                point.error = "measurement " + status(point.measurement, MEASURED)
                problem = recover_topology(instances)
                if problem:
                    stopped_reason = problem
                    break
        if stopped_reason:
            remaining = [level for level in LEVELS if not any(point.instances == instances and point.concurrency == level for point in points)]
            for concurrency in remaining:
                points.append(skipped_point(instances, concurrency, rep, stopped_reason))
                traffic["skipped_warmup"] += WARMUP
                traffic["skipped_measurement"] += MEASURED
    return points, traffic, stopped_reason, interrupted

def serialise_metrics(item: Metrics | None) -> dict[str, object] | None:
    if item is None:
        return None
    data = asdict(item)
    cleanup = data.get("cleanup")
    if cleanup is not None:
        data["cleanup"] = cleanup
    return data

def write_calibration(rep: int, points: list[Point], traffic: dict[str, int],
                      stopped_reason: str | None, restored: bool) -> int | None:
    maxima, eligibility, selected = selection(points)
    report_json, report_markdown, _ = calibration_paths(rep)
    document = {
        "mode": "calibration", "rep": rep, "levels": list(LEVELS),
        "warmup_requests": WARMUP, "measurement_requests": MEASURED,
        "traffic": traffic, "stopped_reason": stopped_reason,
        "restored_three_backends": restored,
        "selected_concurrency": selected,
        "max_requests_per_second": {str(key): str(value) for key, value in maxima.items()},
        "eligibility": {str(key[0]) + "-" + str(key[1]): value for key, value in eligibility.items()},
        "points": [{"instances": point.instances, "concurrency": point.concurrency,
                    "rep": point.rep, "error": point.error, "not_run": point.not_run,
                    "measurement_skipped": point.measurement_skipped,
                    "warmup": serialise_metrics(point.warmup),
                    "measurement": serialise_metrics(point.measurement)} for point in points],
    }
    report_json.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Step 10 calibration", "", "| instances | concurrency | warm-up | measured | eligibility |",
             "|---:|---:|---|---|---|"]
    for point in points:
        key = str(point.instances) + "-" + str(point.concurrency)
        lines.append("| " + str(point.instances) + " | " + str(point.concurrency) + " | " +
                     status(point.warmup, WARMUP) + " | " + status(point.measurement, MEASURED) +
                     " | " + eligibility.get((point.instances, point.concurrency), "unknown") + " |")
    lines.extend(["", "Selected concurrency: " + (str(selected) if selected is not None else "none"),
                  "Restored three-backend topology: " + ("yes" if restored else "no")])
    report_markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return selected

def positive(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be positive")
    return parsed

def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="DA3 owner-run Apache Bench harness")
    mode = result.add_mutually_exclusive_group(required=True)
    mode.add_argument("--calibrate", action="store_true", help="run the locked 10-point matrix")
    mode.add_argument("--single-run", action="store_true", help="run one controlled topology")
    result.add_argument("--rep", type=positive, default=1, help="non-overwriting attempt number")
    result.add_argument("--instances", type=int, choices=(1, 3), default=3)
    result.add_argument("--concurrency", type=positive, default=10)
    result.add_argument("--requests", type=positive, default=DEFAULT_REQUESTS)
    result.add_argument("--benchmark-id", type=benchmark_id,
                        help="opt-in Step 11 request marker and result namespace")
    return result

def write_single(instances: int, concurrency: int, requests: int, rep: int,
                 warmup: Metrics | None, measured: Metrics | None, error: str | None,
                  restored: bool, output_json: Path, output_markdown: Path,
                  marker: str | None = None, activated: bool = False) -> None:
    traffic = {"planned_warmup": WARMUP, "planned_measurement": requests,
               "launched_warmup": 0, "launched_measurement": 0,
               "ab_reported_completed_warmup": 0, "ab_reported_completed_measurement": 0,
               "unknown_warmup": 0, "unknown_measurement": 0,
               "skipped_warmup": 0, "skipped_measurement": 0}
    if warmup is not None:
        record(traffic, "warmup", warmup, WARMUP)
    if measured is not None:
        record(traffic, "measurement", measured, requests)
    elif warmup is not None:
        traffic["skipped_measurement"] = requests
    document: dict[str, object] = {
        "mode": "single-run", "rep": rep, "instances": instances,
        "concurrency": concurrency, "requests": requests, "error": error,
        "topology_activated": activated, "restored_three_backends": restored, "traffic": traffic,
        "warmup": serialise_metrics(warmup), "measurement": serialise_metrics(measured),
    }
    if marker is not None:
        document["benchmark_id"] = marker
    output_json.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = ["# " + ("Step 11 benchmark run" if marker is not None else "Step 10 single run"), "",
            *( ["Run ID: " + marker] if marker is not None else []),
            "Topology: " + str(instances) + " backend(s)",
            "Concurrency: " + str(concurrency), "Warm-up: " + status(warmup, WARMUP),
            "Measured: " + status(measured, requests),
            "Restored three-backend topology: " + ("yes" if restored else "no")]
    if error:
        text.append("Error: " + error)
    output_markdown.write_text("\n".join(text) + "\n", encoding="utf-8")

def main() -> int:
    args = parser().parse_args()
    if not (project_name() and os.environ.get("LOADTEST_TOKEN") and os.environ.get("DA3_LOADTEST_ENV_FILE")):
        print("required load-test configuration is unavailable", file=sys.stderr)
        return 1
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.calibrate:
        if args.benchmark_id is not None:
            print("--benchmark-id is only valid with --single-run", file=sys.stderr)
            return 1
        report_json, report_markdown, raw = calibration_paths(args.rep)
        problem = collision([report_json, report_markdown, *raw])
        if problem:
            print(problem, file=sys.stderr)
            return 1
        points: list[Point] = []
        traffic: dict[str, int] = {}
        stopped_reason: str | None = None
        interrupted = False
        try:
            points, traffic, stopped_reason, interrupted = run_calibration(args.rep)
        except KeyboardInterrupt:
            stopped_reason, interrupted = "calibration interrupted during topology control", True
            traffic = {"planned_warmup": len(LEVELS) * 2 * WARMUP,
                       "planned_measurement": len(LEVELS) * 2 * MEASURED,
                       **traffic}
            record_remaining_not_run(points, traffic, args.rep, stopped_reason)
        finally:
            restored = restore_three_backends()
        selected = write_calibration(args.rep, points, traffic, stopped_reason, restored)
        if interrupted:
            return 130
        return 0 if selected is not None and restored and stopped_reason is None else 1
    warmup_raw, measured_raw, report_json, report_markdown = single_paths(
        args.instances, args.concurrency, args.rep, args.benchmark_id
    )
    problem = collision([warmup_raw, measured_raw, report_json, report_markdown])
    if problem:
        print(problem, file=sys.stderr)
        return 1
    warmup: Metrics | None = None
    measured: Metrics | None = None
    error: str | None = None
    interrupted = False
    activated = False
    try:
        error = activate_topology(args.instances)
        if error is None:
            activated = True
            warmup = run_ab(
                WARMUP, args.concurrency, warmup_raw,
                benchmark_target(args.benchmark_id, "warmup"),
            )
            if warmup.interrupted:
                error, interrupted = "warm-up interrupted", True
            elif not warmup_ok(warmup):
                error = "warm-up " + status(warmup, WARMUP)
            else:
                measured = run_ab(
                    args.requests, args.concurrency, measured_raw,
                    benchmark_target(args.benchmark_id, "measured"),
                )
                if measured.interrupted:
                    error, interrupted = "measurement interrupted", True
                elif not complete(measured, args.requests) or measured.return_code != 0:
                    error = "measurement " + status(measured, args.requests)
    except KeyboardInterrupt:
        error, interrupted = "single run interrupted during topology control", True
    finally:
        restored = restore_three_backends()
    write_single(args.instances, args.concurrency, args.requests, args.rep, warmup, measured,
                 error, restored, report_json, report_markdown, args.benchmark_id, activated)
    if interrupted:
        return 130
    return 0 if error is None and restored else 1

def parser_fixture_checks() -> None:
    complete_text = "Complete requests:      300\nFailed requests:        2 (Connect: 1, Receive: 0, Length: 1, Exceptions: 0)\nNon-2xx responses:      2\nRequests per second:    12.50 [#/sec]\nTime per request:       80.000 [ms] (mean)\n"
    complete_item = parse_ab(complete_text, 300, 0)
    assert complete_item.connect_failures == 1 and complete_item.length_failures == 1
    assert complete_item.non_2xx_responses == 2
    omitted_non_2xx = (
        "Complete requests:      100\n"
        "Failed requests:        0\n"
        "Requests per second:    4.49 [#/sec] (mean)\n"
        "Time per request:       1114.082 [ms] (mean)\n"
    )
    assert parse_ab(omitted_non_2xx, 100, 0).non_2xx_responses == 0
    assert parse_ab("Complete requests: 1\n", 100, 119).non_2xx_responses is None
    assert benchmark_target(None, None) == "/postings"
    assert benchmark_target("s11-example", "measured") == "/postings?bench=s11-example&phase=measured"
    parts = ["abc"]; append_unique(parts, "abcdef"); append_unique(parts, "defghi")
    assert "".join(parts) == "abcdefghi"

if __name__ == "__main__":
    raise SystemExit(main())
