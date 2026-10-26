"""DA3 Step 12/13 controlled failure harness; owner-run only.

The script deliberately keeps the bearer token in process memory.  It preserves
partial Apache Bench output and restores the canonical three-backend topology in
``finally``; it does not claim that restoration succeeded unless it is observed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import queue
import re
import shlex
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[2]
sys.path.insert(0, str(SCRIPTS))
import loadtest  # noqa: E402  # existing safe Compose/project helpers

_PROBE_SPEC = importlib.util.spec_from_file_location("da3_availability_probe", SCRIPTS / "availability_probe.py")
assert _PROBE_SPEC and _PROBE_SPEC.loader
availability_probe = importlib.util.module_from_spec(_PROBE_SPEC)
_PROBE_SPEC.loader.exec_module(availability_probe)

RESULTS = ROOT / "docs" / "da3" / "results"
NGINX_LOG = RESULTS / "nginx-logs" / "da3-access.log"
PROFILES = {"default": "nginx-3-default.conf", "baseline": "nginx-3-baseline.conf",
            "resilient": "nginx-3-resilient.conf"}
WARMUP, MEASURED, CONCURRENCY = 100, 1000, 20
KILL_OFFSET_SECONDS = 12.06
HEALTH_WAIT_SECONDS = 120
PROBE_COVERAGE_WAIT_SECONDS = 5
PASSIVE_WINDOW_SECONDS = 12
RUN_LABEL = loadtest.RUN_LABEL
REFERENCE_RPS = 24.88
ESTIMATED_MEASURED_SECONDS = MEASURED / REFERENCE_RPS
KILL_TOLERANCE_SECONDS = 2.0
FAILOVER_TIMEOUT_SECONDS = 120
READER_JOIN_SECONDS = 10
KILL_JOIN_SECONDS = 35


def now() -> str:
    return datetime.now(UTC).isoformat()


def progress(message: str) -> None:
    print(now() + " " + message, flush=True)


def profile(value: str) -> str:
    if value not in PROFILES:
        raise argparse.ArgumentTypeError("--config must be default, baseline, or resilient")
    return value


def run_id(config: str, rep: int) -> str:
    step = "s13" if config == "resilient" else "s12"
    return f"{step}-{config}-r{rep}-{uuid.uuid4().hex[:10]}"


def artifact_paths(identifier: str) -> dict[str, Path]:
    stem = f"{'13' if identifier.startswith('s13-') else '12'}-1c-{identifier}"
    paths = {
        "warmup_raw": RESULTS / f"{stem}-warmup.txt",
        "measured_raw": RESULTS / f"{stem}-measured.txt",
        "result_json": RESULTS / f"{stem}.json",
        "result_markdown": RESULTS / f"{stem}.md",
        "nginx_diagnostics": RESULTS / f"{stem}-nginx-diagnostics.json",
        "nginx_errors": RESULTS / f"{stem}-nginx-errors.txt",
    }
    if identifier.startswith("s13-resilient-r"):
        rep = identifier.split("-", 3)[2].removeprefix("r")
        paths["probe_csv"] = RESULTS / f"13-probe-resilient-rep{rep}.csv"
        paths["probe_stop"] = RESULTS / f".13-probe-resilient-rep{rep}.stop"
    return paths


def collision(paths: dict[str, Path]) -> str | None:
    candidates = list(paths.values())
    candidates.extend(path.with_suffix(path.suffix + ".tmp") for path in paths.values()
                      if path.suffix == ".json")
    existing = [path.name for path in candidates if path.exists()]
    return None if not existing else "refusing to overwrite existing result artifact(s): " + ", ".join(existing)


def start_probe(paths: dict[str, Path]) -> tuple[subprocess.Popen[str] | None, str | None]:
    """Start a separate no-secret probe process and require its CSV header."""
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, str(SCRIPTS / "availability_probe.py"), "--output", str(paths["probe_csv"]),
             "--stop-file", str(paths["probe_stop"])], cwd=ROOT, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                return process, "availability probe exited before its CSV header was verified"
            if paths["probe_csv"].is_file():
                try:
                    availability_probe.summarise(paths["probe_csv"])
                    return process, None
                except (OSError, ValueError):
                    pass
            time.sleep(0.05)
    except (OSError, KeyError):
        return process, "availability probe could not be started"
    return process, "availability probe CSV header was not verified"


def utc_instant(value: object) -> datetime:
    """Parse an offset-bearing timestamp and normalize it for instant comparison."""
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(UTC)


def probe_coverage(summary: dict[str, Any] | None, start_at: str | None, recovery_at: str | None) -> bool:
    if not isinstance(summary, dict) or not start_at or not recovery_at:
        return False
    try:
        first = utc_instant(summary["first_sample_at"])
        last = utc_instant(summary["last_sample_at"])
        start, recovery = utc_instant(start_at), utc_instant(recovery_at)
    except (KeyError, TypeError, ValueError):
        return False
    return first <= start and last >= recovery


def wait_for_probe_coverage(process: subprocess.Popen[str] | None, paths: dict[str, Path],
                            start_at: str | None, recovery_at: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Require a persisted, valid probe sample at/after successful recovery."""
    if process is None:
        return None, "availability probe was not running for coverage verification"
    deadline = time.monotonic() + PROBE_COVERAGE_WAIT_SECONDS
    summary: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return summary, "availability probe exited before coverage was established"
        try:
            summary = availability_probe.summarise(paths["probe_csv"])
        except (OSError, ValueError):
            summary = None
        if probe_coverage(summary, start_at, recovery_at):
            return summary, None
        time.sleep(0.05)
    return summary, "availability probe CSV did not persist a sample through post-recovery health"


def stop_probe(process: subprocess.Popen[str] | None, paths: dict[str, Path]) -> tuple[dict[str, Any] | None, str | None]:
    if process is None:
        return None, "availability probe was not running"
    try:
        if process.poll() is None:
            paths["probe_stop"].write_text("stop\n", encoding="utf-8")
        process.wait(timeout=10)
        if process.returncode != 0:
            return None, "availability probe exited unsuccessfully"
        return availability_probe.summarise(paths["probe_csv"]), None
    except (OSError, subprocess.TimeoutExpired, ValueError):
        try:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            try:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                return None, "availability probe could not be stopped"
        return None, "availability probe summary could not be verified"

def atomic_json(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def compose(*args: str, nginx_conf: str | None = None) -> subprocess.CompletedProcess[str]:
    return loadtest.compose(*args, nginx_conf=nginx_conf)


def health_ok() -> bool:
    try:
        with urlopen("http://127.0.0.1:8080/health", timeout=3) as response:
            return response.status == 200
    except (URLError, OSError):
        return False


def _normalise_mount_path(value: str) -> str:
    """Normalise Windows host paths and Docker Desktop Linux-VM mount aliases."""
    value = value.strip().strip('"').replace("\\", "/")
    # Docker Desktop may expose a Windows drive path through its Linux VM instead
    # of returning the original C:/... source path from docker inspect.
    prefixes = (
        (r"^/run/desktop/mnt/host/([a-zA-Z])/(.*)$", r"\1:/\2"),
        (r"^/host_mnt/([a-zA-Z])/(.*)$", r"\1:/\2"),
        (r"^/mnt/([a-zA-Z])/(.*)$", r"\1:/\2"),
    )
    for pattern, replacement in prefixes:
        value = re.sub(pattern, replacement, value)
    value = re.sub(r"^([a-zA-Z]):(?=/)", lambda match: match.group(1).lower() + ":", value)
    return os.path.normpath(value).replace("\\", "/").rstrip("/").casefold()


def nginx_profile_loaded(config: str) -> bool:
    """Verify both the mounted source and the effective directives Nginx loaded."""
    if config not in (*PROFILES, "canonical"):
        return False
    try:
        result = compose("exec", "-T", "nginx", "nginx", "-T")
        if result.returncode != 0:
            return False
        mounts = compose("ps", "-q", "nginx")
        ids = [value.strip() for value in mounts.stdout.splitlines() if value.strip()]
        if mounts.returncode != 0 or len(ids) != 1 or not re.fullmatch(r"[0-9a-f]{12,64}", ids[0]):
            return False
        source = subprocess.run(
            ["docker", "inspect", "--format",
             '{{range .Mounts}}{{if eq .Destination "/etc/nginx/conf.d/default.conf"}}{{.Source}}{{end}}{{end}}', ids[0]],
            cwd=ROOT, check=False, capture_output=True, text=True, timeout=10,
        )
        expected_file = "nginx-3.conf" if config == "canonical" else PROFILES[config]
        expected = str((ROOT / "nginx" / expected_file).resolve())
        if source.returncode != 0 or not source.stdout.strip():
            return False
        if _normalise_mount_path(source.stdout) != _normalise_mount_path(expected):
            return False

        effective = result.stdout
        # Restrict directive checks to the included site file when nginx -T labels it.
        marker = "# configuration file /etc/nginx/conf.d/default.conf:"
        if marker in effective:
            effective = effective.split(marker, 1)[1].split("\n# configuration file ", 1)[0]
        if '"upstream_addr":"$upstream_addr"' not in effective or '"upstream_status":"$upstream_status"' not in effective:
            return False
        upstream = re.search(r"upstream\s+resume_ip_backends\s*\{(?P<body>[^}]*)\}", effective, re.S)
        if not upstream or not re.search(r"zone\s+resume_ip_backends\s+64k\s*;", upstream.group("body")):
            return False
        body = upstream.group("body")
        for service in ("backend-1", "backend-2", "backend-3"):
            matches = re.findall(rf"server\s+{re.escape(service)}:8000(?P<options>[^;]*)\s*;", body)
            if len(matches) != 1:
                return False
            options = matches[0]
            if config == "baseline" and not re.search(r"\bmax_fails\s*=\s*0\b", options):
                return False
            if config == "resilient" and not (re.search(r"\bmax_fails\s*=\s*2\b", options)
                                                and re.search(r"\bfail_timeout\s*=\s*10s\b", options)):
                return False
            if config not in ("baseline", "resilient") and "max_fails" in options:
                return False
        if config == "baseline":
            if not re.search(r"proxy_next_upstream\s+off\s*;", effective):
                return False
            if not re.search(r"proxy_connect_timeout\s+2s\s*;", effective):
                return False
        elif config == "resilient":
            for directive in (
                r"proxy_next_upstream\s+error timeout http_502 http_503 http_504\s*;",
                r"proxy_next_upstream_tries\s+3\s*;",
                r"proxy_next_upstream_timeout\s+5s\s*;",
                r"proxy_connect_timeout\s+1s\s*;",
            ):
                if not re.search(directive, effective):
                    return False
        else:
            if re.search(r"proxy_next_upstream\s+off\s*;", effective):
                return False
            if re.search(r"proxy_connect_timeout\s+2s\s*;", effective):
                return False
        for directive in ("proxy_set_header Host $http_host;", "proxy_set_header X-Real-IP $remote_addr;",
                          "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
                          "proxy_set_header X-Forwarded-Proto $scheme;"):
            if directive not in effective:
                return False
        return True
    except (OSError, subprocess.TimeoutExpired, KeyError, ValueError):
        return False

def activate(config: str) -> str | None:
    """Select a profile and prove Nginx itself was recreated with clean state."""
    if not all(backend_identity(name)[0] for name in ("backend-1", "backend-2", "backend-3")):
        return "all backend health checks must pass before profile selection"
    old_id, old_problem = service_container_id("nginx")
    if old_problem or not old_id:
        return "existing Nginx container identity is not verified"
    result = compose("up", "-d", "--force-recreate", "nginx", nginx_conf=PROFILES[config])
    if result.returncode != 0:
        return "Compose could not activate the requested Nginx profile"
    new_id, new_problem = service_container_id("nginx")
    if new_problem or not new_id or new_id == old_id:
        return "Nginx recreation could not be verified"
    if not loadtest.topology_is_ready(3) or not health_ok():
        return "three-backend topology or Nginx health could not be verified"
    return None if nginx_profile_loaded(config) else "selected Nginx profile could not be verified"


def service_container_id(service: str) -> tuple[str | None, str | None]:
    """Return one running container with verified Compose service/project labels."""
    try:
        listing = compose("ps", "-q", service)
        ids = [line.strip() for line in listing.stdout.splitlines() if line.strip()]
        if listing.returncode != 0 or len(ids) != 1:
            return None, f"{service} container identity is missing or ambiguous"
        container_id = ids[0]
        if not re.fullmatch(r"[0-9a-f]{12,64}", container_id):
            return None, f"{service} container ID format is invalid"
        labels = subprocess.run(
            ["docker", "inspect", "--format", "{{json .Config.Labels}}", container_id], cwd=ROOT,
            check=False, capture_output=True, text=True, timeout=10,
        )
        running = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_id], cwd=ROOT,
            check=False, capture_output=True, text=True, timeout=10,
        )
        try:
            value = json.loads(labels.stdout)
        except (json.JSONDecodeError, TypeError):
            value = None
        expected_project = loadtest.project_name()
        if (labels.returncode != 0 or running.returncode != 0 or running.stdout.strip() != "true"
                or not isinstance(value, dict)
                or value.get("com.docker.compose.service") != service
                or value.get("com.docker.compose.project") != expected_project):
            return None, f"{service} container identity, Compose labels, or running state could not be verified"
        return container_id, None
    except (OSError, subprocess.TimeoutExpired):
        return None, f"{service} container inspection failed or timed out"


def backend_identity(service: str) -> tuple[str | None, str | None]:
    container_id, problem = service_container_id(service)
    if problem or not container_id:
        return None, problem or f"{service} container identity could not be verified"
    try:
        health = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id], cwd=ROOT,
            check=False, capture_output=True, text=True, timeout=10,
        )
        if health.returncode != 0 or health.stdout.strip() != "healthy":
            return None, f"{service} health could not be verified"
        return container_id, None
    except (OSError, subprocess.TimeoutExpired):
        return None, f"{service} health inspection failed or timed out"

def backend_two_id() -> tuple[str | None, str | None]:
    return backend_identity("backend-2")


def ab_command(requests: int, marker: str, phase: str) -> list[str]:
    name = loadtest.project_name()
    if name is None:
        raise ValueError("invalid Compose project identity")
    target = shlex.quote("http://nginx" + loadtest.benchmark_target(marker, phase))
    sentinel = f"DA3_AB_START:{marker}:{phase}"
    end = f"DA3_AB_END:{marker}:{phase}:"
    shell = (f"printf '{sentinel}\\n' >&2; ab -k -r -n {requests} -c {CONCURRENCY} "
             '-H "Authorization: Bearer $LOADTEST_TOKEN" ' + target
             + f"; code=$?; printf '{end}%s\\n' \"$code\" >&2; exit $code")
    return ["docker", "compose", "--project-name", name, "-f", str(loadtest.COMPOSE), "--profile", "loadtest",
            "run", "--rm", "--no-deps", "--label", f"{RUN_LABEL}={marker}", "-e", "LOADTEST_TOKEN",
            "--entrypoint", "sh", "loadtest", "-c", shell]


def run_ab(requests: int, marker: str, phase: str, raw: Path,
           kill_id: str | None = None, *, token: str) -> tuple[loadtest.Metrics, dict[str, Any]]:
    """Run one AB invocation; a single reader owns stdout for its whole lifetime."""
    raw_parts: list[str] = []
    kill: dict[str, Any] = {
        "scheduled_offset_seconds": None,
        "sentinel_timestamp": None,
        "monotonic_start": None,
        "kill_started_at": None,
        "kill_completed_at": None,
        "actual_elapsed_seconds": None,
        "return_code": None,
        "stopped_verified": None,
        "completion_timestamp": None,
        "start_sentinel_seen": False,
        "end_sentinel_seen": False,
        "end_sentinel_timestamp": None,
        "end_monotonic": None,
        "late_kill_refused": False,
        "timer_joined": None,
        "reader_joined": None,
        "cleanup_verified": False,
        "error": None,
    }
    process: subprocess.Popen[str] | None = None
    reader_thread: threading.Thread | None = None
    timer: threading.Timer | None = None
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()
    callback_started = threading.Event()
    ab_ended = threading.Event()
    lifecycle_lock = threading.Lock()
    in_ab_output = False
    timed_out = False
    interrupted = False
    execution_error: str | None = None
    command: list[str] = []
    sentinel = f"DA3_AB_START:{marker}:{phase}"
    end_prefix = f"DA3_AB_END:{marker}:{phase}:"

    def add_error(message: str) -> None:
        existing = kill.get("error")
        if not existing:
            kill["error"] = message
        elif message not in existing:
            kill["error"] = str(existing) + "; " + message

    def kill_backend() -> None:
        callback_started.set()
        try:
            # Do not allow an already-fired timer to kill a backend after AB has
            # reported its end sentinel. This also closes the timer-cancel race.
            with lifecycle_lock:
                if ab_ended.is_set():
                    kill["late_kill_refused"] = True
                    add_error("Apache Bench ended before the scheduled kill; late kill was refused")
                    return
                if kill["monotonic_start"] is None:
                    add_error("kill callback started without an observed AB start sentinel")
                    return
                kill["kill_started_at"] = now()
                kill["actual_elapsed_seconds"] = time.monotonic() - float(kill["monotonic_start"])
                elapsed = float(kill["actual_elapsed_seconds"])
            progress("backend-2 kill starting at " + format(elapsed, ".2f") + " seconds")
            result = subprocess.run(
                ["docker", "kill", kill_id or ""], cwd=ROOT, check=False,
                capture_output=True, text=True, timeout=15,
            )
            kill["return_code"] = result.returncode
            stopped = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", kill_id or ""], cwd=ROOT,
                check=False, capture_output=True, text=True, timeout=10,
            )
            kill["stopped_verified"] = stopped.returncode == 0 and stopped.stdout.strip() == "false"
            kill["kill_completed_at"] = now()
            progress("backend-2 kill completed; exit=" + str(result.returncode) + "; stopped=" + str(kill["stopped_verified"]))
            if result.returncode != 0 or not kill["stopped_verified"]:
                add_error("backend kill or stopped-state verification failed")
        except (OSError, subprocess.TimeoutExpired):
            add_error("backend kill command could not be completed")
        except Exception:
            add_error("unexpected backend kill verification error")

    def reader() -> None:
        try:
            assert process is not None and process.stdout is not None
            for line in process.stdout:
                lines.put(("line", line))
        except Exception:
            lines.put(("reader-error", "output reader failed"))
        finally:
            lines.put(("eof", None))

    def consume_line(line: str, allow_timer: bool) -> None:
        nonlocal in_ab_output, timer
        cleaned = line.strip()
        if cleaned == sentinel:
            if not kill["start_sentinel_seen"]:
                kill["start_sentinel_seen"] = True
                kill["sentinel_timestamp"] = now()
                kill["monotonic_start"] = time.monotonic()
                in_ab_output = True
                progress(phase + " Apache Bench start sentinel observed")
                if kill_id is not None:
                    kill["scheduled_offset_seconds"] = KILL_OFFSET_SECONDS
                    if allow_timer:
                        timer = threading.Timer(KILL_OFFSET_SECONDS, kill_backend)
                        timer.daemon = True
                        timer.start()
                        progress("backend kill scheduled at " + str(KILL_OFFSET_SECONDS) + " seconds")
            return
        if cleaned.startswith(end_prefix):
            with lifecycle_lock:
                kill["end_sentinel_seen"] = True
                kill["end_sentinel_timestamp"] = now()
                kill["end_monotonic"] = time.monotonic()
                kill["ab_exit_status"] = cleaned[len(end_prefix):]
                ab_ended.set()
            in_ab_output = False
            return
        if in_ab_output:
            raw_parts.append(line)

    try:
        command = ab_command(requests, marker, phase)
        if not token or any(character.isspace() for character in token):
            raise ValueError("a fresh load-test token is required")
        child_env = os.environ.copy()
        child_env["LOADTEST_TOKEN"] = token
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, env=child_env)
        reader_thread = threading.Thread(target=reader, name=f"da3-ab-reader-{phase}", daemon=True)
        reader_thread.start()
        deadline = time.monotonic() + FAILOVER_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, FAILOVER_TIMEOUT_SECONDS)
            try:
                kind, payload = lines.get(timeout=min(0.1, remaining))
            except queue.Empty:
                continue
            if kind == "eof":
                break
            if kind == "reader-error":
                execution_error = payload or "output reader failed"
                continue
            if payload is not None:
                consume_line(payload, allow_timer=True)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            execution_error = "Compose client did not exit within the bounded post-AB shutdown wait"
            raise subprocess.TimeoutExpired(command, FAILOVER_TIMEOUT_SECONDS)
        kill["completion_timestamp"] = now()
        if process.returncode not in (0, None):
            execution_error = execution_error or "load-test Compose process exited nonzero"
        if not kill["end_sentinel_seen"]:
            execution_error = execution_error or "Apache Bench end sentinel was not observed"
        if kill.get("ab_exit_status") != "0":
            execution_error = execution_error or "Apache Bench did not report a successful process exit"
    except subprocess.TimeoutExpired:
        timed_out = True
        execution_error = execution_error or f"load-test command exceeded the {FAILOVER_TIMEOUT_SECONDS}-second wall-clock limit"
    except KeyboardInterrupt:
        interrupted = True
        execution_error = execution_error or "load-test command interrupted by user"
    except (OSError, ValueError):
        execution_error = execution_error or "load-test command could not be prepared or launched"
    except Exception:
        execution_error = execution_error or "unexpected load-test runner error"
    finally:
        # An interruption/timeout/exception without an end sentinel means AB is no
        # longer an active experiment. Publish that state under the same lock used by
        # the timer callback *before* cancelling/joining it, so a callback racing with
        # cleanup cannot initiate a new backend kill after an aborted run.
        if not kill["end_sentinel_seen"]:
            with lifecycle_lock:
                ab_ended.set()
        # Stop the Compose client before joining the reader; that closes its pipe.
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    add_error("load-test process could not be stopped within bounded waits")
            except OSError:
                add_error("load-test process termination could not be verified")
        if timer is not None:
            # cancel() only prevents a callback that has not started; join the callback
            # long enough for its bounded Docker kill/inspect calls to finish.
            if not callback_started.is_set():
                timer.cancel()
            try:
                timer.join(timeout=KILL_JOIN_SECONDS)
                kill["timer_joined"] = not timer.is_alive()
            except RuntimeError:
                kill["timer_joined"] = False
            if not kill["timer_joined"]:
                add_error("kill timer/callback did not finish within the bounded wait")
        else:
            kill["timer_joined"] = True
        if kill_id is not None and (timer is None or not callback_started.is_set()):
            add_error("scheduled backend kill did not execute during the measured AB run")
        if kill_id is not None and kill["actual_elapsed_seconds"] is not None:
            elapsed = float(kill["actual_elapsed_seconds"])
            if abs(elapsed - KILL_OFFSET_SECONDS) > KILL_TOLERANCE_SECONDS:
                add_error("kill timing exceeded tolerance")
        if reader_thread is not None:
            try:
                reader_thread.join(timeout=READER_JOIN_SECONDS)
                kill["reader_joined"] = not reader_thread.is_alive()
            except RuntimeError:
                kill["reader_joined"] = False
            if not kill["reader_joined"]:
                add_error("output reader did not stop within the bounded wait")
        else:
            kill["reader_joined"] = True
        # Only the queue is drained here; process.stdout is consumed solely by reader().
        while True:
            try:
                kind, payload = lines.get_nowait()
            except queue.Empty:
                break
            if kind == "line" and payload is not None:
                consume_line(payload, allow_timer=False)
            elif kind == "reader-error":
                execution_error = execution_error or (payload or "output reader failed")
        if kill_id is not None and not kill["start_sentinel_seen"]:
            add_error("measured AB start sentinel was never observed")
        if kill_id is not None and kill["start_sentinel_seen"] and not callback_started.is_set():
            add_error("backend kill was not completed")
        try:
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("".join(raw_parts), encoding="utf-8")
        except OSError:
            execution_error = execution_error or "raw Apache Bench output could not be saved"
        try:
            clean = loadtest.cleanup_invocation(marker)
            kill["cleanup_verified"] = bool(clean.verified)
            if not clean.verified:
                add_error("load-test invocation cleanup was not verified")
        except Exception:
            kill["cleanup_verified"] = False
            add_error("load-test invocation cleanup raised an error")

    output = "".join(raw_parts)
    process_code = process.returncode if process is not None and process.returncode is not None else 127
    item = loadtest.parse_ab(output, requests, process_code)
    # A Compose process alone is not proof that Apache Bench reached its start sentinel.
    item.launched = bool(process is not None and kill["start_sentinel_seen"])
    item.interrupted = interrupted
    item.timed_out = timed_out
    errors: list[str] = []
    for message in (execution_error, kill.get("error")):
        if message and message not in errors:
            errors.append(str(message))
    item.execution_error = "; ".join(errors) if errors else None
    kill["completion_timestamp"] = kill.get("completion_timestamp") or now()
    return item, kill

def recover_backend_two() -> str | None:
    started = compose("up", "-d", "backend-2")
    if started.returncode != 0:
        return "backend-2 restart failed"
    deadline = time.monotonic() + HEALTH_WAIT_SECONDS
    while time.monotonic() < deadline:
        container_id, problem = backend_two_id()
        if container_id and health_ok():
            health = subprocess.run(["docker", "inspect", "--format", "{{.State.Health.Status}}", container_id], cwd=ROOT,
                                    check=False, capture_output=True, text=True, timeout=10)
            if health.returncode == 0 and health.stdout.strip() == "healthy":
                time.sleep(PASSIVE_WINDOW_SECONDS)
                rechecked_id, _ = backend_two_id()
                if rechecked_id == container_id and health_ok():
                    return None
        time.sleep(2)
    return "backend-2 recovery health or Nginx health could not be verified"


def restore_canonical() -> bool:
    started = compose("up", "-d", "backend-1", "backend-2", "backend-3")
    if started.returncode != 0:
        return False
    deadline = time.monotonic() + HEALTH_WAIT_SECONDS
    while time.monotonic() < deadline:
        if all(backend_identity(name)[0] for name in ("backend-1", "backend-2", "backend-3")):
            result = compose("up", "-d", "--force-recreate", "nginx", nginx_conf="nginx-3.conf")
            return result.returncode == 0 and health_ok() and nginx_profile_loaded("canonical")
        time.sleep(2)
    return False


def _normalise_status(value: Any) -> int | None:
    try:
        status = int(value)
    except (TypeError, ValueError):
        return None
    return status if 100 <= status <= 599 else None


def nginx_diagnostics(marker: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        phase: {
            "availability": "unavailable", "matching_lines": 0, "malformed_lines": 0,
            "unparseable_statuses": 0, "status_counts": {}, "upstream_status_counts": {},
            "502_count": 0, "504_count": 0, "non_2xx_records": [],
            "non_2xx_records_truncated": False,
        }
        for phase in ("warmup", "measured")
    }
    try:
        with NGINX_LOG.open("r", encoding="utf-8", errors="replace") as log_file:
            for line in log_file:
                if marker not in line:
                    continue
                phase = next((name for name in result if f"phase={name}" in line), None)
                if phase is None:
                    continue
                target = result[phase]
                try:
                    row = json.loads(line)
                    request = str(row.get("request") or "")
                    if f"bench={marker}&phase={phase}" not in request:
                        target["malformed_lines"] += 1
                        continue
                except (json.JSONDecodeError, AttributeError, TypeError):
                    target["malformed_lines"] += 1
                    continue
                target["availability"] = "readable"
                target["matching_lines"] += 1
                status = _normalise_status(row.get("status"))
                if status is None:
                    target["unparseable_statuses"] += 1
                    continue
                key = str(status)
                target["status_counts"][key] = target["status_counts"].get(key, 0) + 1
                target["502_count"] += int(status == 502)
                target["504_count"] += int(status == 504)
                upstream = str(row.get("upstream_status") or "")
                if upstream:
                    target["upstream_status_counts"][upstream] = target["upstream_status_counts"].get(upstream, 0) + 1
                if not 200 <= status < 300:
                    if len(target["non_2xx_records"]) < 50:
                        target["non_2xx_records"].append({
                            "time": row.get("time"), "status": status,
                            "upstream_status": row.get("upstream_status"),
                            "upstream_addr": row.get("upstream_addr"),
                            "request_time": row.get("request_time"),
                        })
                    else:
                        target["non_2xx_records_truncated"] = True
    except OSError:
        return result
    for target in result.values():
        if target["availability"] == "unavailable":
            target["availability"] = "readable-no-matching-records"
    return result

def nginx_error_excerpt(marker: str, started_at: str | None = None,
                        ended_at: str | None = None) -> tuple[str, dict[str, Any]]:
    """Capture only real Nginx warning/error lines for this run, before recreation."""
    try:
        container_id, identity_problem = service_container_id("nginx")
        if identity_problem or not container_id:
            return "Nginx error log unavailable: Nginx container identity is not verified.\n", {"availability": "unavailable"}
        if not started_at:
            return "Nginx error log unavailable: run start timestamp is unavailable.\n", {"availability": "unavailable"}
        ended_at = ended_at or now()
        command = ["docker", "logs", "--timestamps", "--since", started_at,
                   "--until", ended_at, "--tail", "500", container_id]
        logged = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        return "Nginx error log unavailable: bounded Docker log capture failed.\n", {"availability": "unavailable"}
    if logged.returncode != 0:
        return "Nginx error log unavailable: Docker log command failed.\n", {"availability": "unavailable"}
    severity = re.compile(r"\d{4}/\d{2}/\d{2}\s+\[(?:emerg|alert|crit|error|warn)\]", re.IGNORECASE)
    phases = ("warmup", "measured")
    matching = [
        line for line in (logged.stdout + logged.stderr).splitlines()
        if marker in line and severity.search(line)
        and any(f"phase={phase}" in line for phase in phases)
    ]
    selected = matching[:50]
    if not selected:
        return "No matching Nginx error/warning entries were observed in the bounded capture.\n", {
            "availability": "captured-no-matching-lines", "truncated": False,
            "matching_lines": 0, "container_id": container_id[:12],
            "started_at": started_at, "ended_at": ended_at,
        }
    return "\n".join(selected) + "\n", {
        "availability": "captured", "truncated": len(matching) > 50,
        "matching_lines": len(matching), "container_id": container_id[:12],
        "started_at": started_at, "ended_at": ended_at,
    }

def serialise(item: loadtest.Metrics) -> dict[str, Any]:
    return {name: getattr(item, name) for name in (
        "requests", "completed_requests", "requests_per_second", "mean_time_per_request_ms", "failed_requests",
        "connect_failures", "receive_failures", "length_failures", "exception_failures", "non_2xx_responses",
        "return_code", "launched", "interrupted", "timed_out", "execution_error")}


def acquire_token() -> str | None:
    command = [sys.executable, str(SCRIPTS / "get_token.py"), "--base-url", "http://localhost:8080"]
    try:
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token and not any(character.isspace() for character in token) else None


def write_markdown(path: Path, document: dict[str, Any]) -> None:
    measured = document.get("measured", {})
    diagnostic = document.get("nginx_diagnostics", {}).get("measured", {})
    traffic = document.get("traffic", {})
    kill = document.get("kill", {})
    artifacts = document.get("artifacts", {})
    rows = [
        f"# Step {'13 resilient failover' if document.get('config') == 'resilient' else '12 failure-before-fix'} result", "",
        f"- Run ID: `{document.get('run_id')}`",
        f"- Profile: `{document.get('config')}`",
        f"- Repetition: `{document.get('rep')}`",
        f"- Completion: `{document.get('completion')}`",
        f"- Error: `{document.get('error') or 'none recorded'}`", "",
        "## Protocol", "",
        f"- N: {document.get('protocol', {}).get('measured_requests')}",
        f"- C: {document.get('protocol', {}).get('concurrency')}",
        f"- Apache Bench flags: `-k -r`",
        f"- Reference throughput: {REFERENCE_RPS} requests/second",
        f"- Estimated measured duration: {ESTIMATED_MEASURED_SECONDS:.2f} seconds (N / reference RPS)",
        f"- Scheduled kill offset: {KILL_OFFSET_SECONDS:.2f} seconds after observed AB start sentinel",
        f"- Actual kill elapsed: {kill.get('actual_elapsed_seconds')}",
        f"- Kill exit / stopped verification: {kill.get('return_code')} / {kill.get('stopped_verified')}", "",
        "## Measured results", "",
        "| Field | Value |", "|---|---|",
        f"| AB completed requests | {measured.get('completed_requests')} |",
        f"| AB failed requests | {measured.get('failed_requests')} |",
        f"| Connect / Receive / Length / Exceptions | {measured.get('connect_failures')} / {measured.get('receive_failures')} / {measured.get('length_failures')} / {measured.get('exception_failures')} |",
        f"| AB non-2xx responses | {measured.get('non_2xx_responses')} |",
        f"| Measured Nginx status counts | `{json.dumps(diagnostic.get('status_counts', {}), sort_keys=True)}` |",
        f"| Measured Nginx 502 / 504 counts | {diagnostic.get('502_count')} / {diagnostic.get('504_count')} |",
        f"| Access diagnostic availability | {diagnostic.get('availability', 'unavailable')} |",
        f"| Nginx error-log availability | {document.get('nginx_error_log', {}).get('availability', 'unavailable')} |", "",
        "## Recovery and restoration", "",
        f"- Load-test cleanup verified: {kill.get('cleanup_verified')}",
        f"- Backend recovery: {document.get('recovery', 'not reached')}",
        f"- Canonical restoration: {document.get('canonical_restoration', 'not reached')}", "",
        f"- Availability probe: `{json.dumps(document.get('availability_probe', {}), sort_keys=True)}`", "",
        "## Artifacts", "",
    ]
    for key, value in artifacts.items():
        rows.append(f"- {key}: `{value}`")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

def preflight_error(config: str, rep: int) -> str | None:
    if config not in PROFILES:
        return "unsupported Nginx profile"
    if rep < 1:
        return "repetition number must be positive"
    if loadtest.project_name() is None:
        return "Compose project identity is invalid"
    env_file = os.environ.get("DA3_LOADTEST_ENV_FILE")
    env_path = Path(env_file) if env_file else None
    if env_path is not None and not env_path.is_absolute():
        env_path = ROOT / env_path
    if env_path is None or not env_path.is_file() or not os.access(env_path, os.R_OK):
        return "required external load-test environment file is unavailable"
    required_files = (
        loadtest.COMPOSE,
        SCRIPTS / "get_token.py",
        ROOT / "nginx" / "nginx-3.conf",
        ROOT / "nginx" / PROFILES[config],
    )
    if any(not path.is_file() for path in required_files):
        return "one or more required DA3 source/configuration files are unavailable"
    return None


def metrics_accounted(item: loadtest.Metrics | None, expected: int, *, warmup: bool = False) -> bool:
    """Validate AB summary and request accounting without rejecting intended measured failures."""
    if not item or item.requests != expected or not item.launched:
        return False
    if item.return_code != 0 or item.interrupted or item.timed_out or item.execution_error:
        return False
    if (item.completed_requests is None or item.failed_requests is None
            or item.non_2xx_responses is None or item.requests_per_second is None
            or item.mean_time_per_request_ms is None):
        return False
    if (not 0 <= item.completed_requests <= expected or not 0 <= item.failed_requests <= expected
            or not 0 <= item.non_2xx_responses <= expected):
        return False
    if item.failed_requests > 0 and any(value is None for value in (
            item.connect_failures, item.receive_failures, item.length_failures, item.exception_failures)):
        return False
    # ApacheBench builds can report Complete requests as N (with failures a separate
    # diagnostic) or as N - Failed requests. Accept either representation, but not gaps.
    accounted = item.completed_requests == expected or item.completed_requests + item.failed_requests == expected
    if not accounted:
        return False
    if warmup and (item.failed_requests != 0 or item.non_2xx_responses != 0 or item.completed_requests != expected):
        return False
    return True


def diagnostics_usable(report: dict[str, Any] | None) -> bool:
    if not isinstance(report, dict):
        return False
    for phase in ("warmup", "measured"):
        value = report.get(phase)
        if (not isinstance(value, dict) or value.get("availability") != "readable"
                or value.get("matching_lines", 0) <= 0
                or value.get("malformed_lines", 0) != 0
                or value.get("unparseable_statuses", 0) != 0):
            return False
    return True


def record_traffic(document: dict[str, Any], phase: str, item: loadtest.Metrics, budget: int) -> None:
    traffic = document["traffic"]
    completed = item.completed_requests
    failed = item.failed_requests
    if not item.launched:
        traffic[f"skipped_{phase}"] += budget
        traffic["skipped"] += budget
        return
    traffic[f"launched_{phase}"] += budget
    traffic["launched"] += budget
    if completed is not None:
        traffic[f"ab_reported_completed_{phase}"] += completed
        traffic["ab_reported_completed"] += completed
    if failed is not None:
        traffic[f"ab_reported_failed_{phase}"] += failed
        traffic["ab_reported_failed"] += failed
    if completed is None:
        unknown = budget
    else:
        unknown = max(0, budget - completed - (failed or 0))
    traffic[f"unknown_{phase}"] += unknown
    traffic["unknown"] += unknown


def finalise_traffic(document: dict[str, Any]) -> None:
    """Mark whole phases that never launched as skipped, without double counting."""
    traffic = document["traffic"]
    for phase, budget in (("warmup", WARMUP), ("measured", MEASURED)):
        if (traffic[f"launched_{phase}"] == 0 and traffic[f"unknown_{phase}"] == 0
                and traffic[f"ab_reported_completed_{phase}"] == 0
                and traffic[f"ab_reported_failed_{phase}"] == 0
                and traffic[f"skipped_{phase}"] == 0):
            traffic[f"skipped_{phase}"] = budget
            traffic["skipped"] += budget


def execute(config: str, rep: int) -> tuple[int, dict[str, Any]]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    identifier = run_id(config, rep)
    paths = artifact_paths(identifier)
    problem = collision(paths)
    if problem:
        return 1, {"error": problem, "completion": "incomplete"}
    document: dict[str, Any] = {
        "run_id": identifier,
        "config": config,
        "rep": rep,
        "protocol": {
            "keep_alive": True, "ab_continue_on_errors": True, "ab_flags": ["-k", "-r"],
            "concurrency": CONCURRENCY, "warmup_requests": WARMUP, "measured_requests": MEASURED,
            "reference_rps": REFERENCE_RPS,
            "estimated_measured_seconds": ESTIMATED_MEASURED_SECONDS,
            "estimated_duration_formula": f"{MEASURED} / {REFERENCE_RPS}",
            "scheduled_kill_offset_seconds": KILL_OFFSET_SECONDS,
            "kill_timing_tolerance_seconds": KILL_TOLERANCE_SECONDS,
            "request_accounting": "AB-reported completed plus failed counts; partial/unreported requests remain unknown",
        },
        "started_at": now(),
        "artifacts": {key: str(path.relative_to(ROOT)) for key, path in paths.items()},
        "raw_files": {key: str(path.relative_to(ROOT)) for key, path in paths.items() if key.endswith("raw")},
        "traffic": {
            "planned": WARMUP + MEASURED,
            "planned_warmup": WARMUP, "planned_measured": MEASURED,
            "launched": 0, "ab_reported_completed": 0, "ab_reported_failed": 0, "unknown": 0,
            "skipped": 0,
            "launched_warmup": 0, "ab_reported_completed_warmup": 0,
            "ab_reported_failed_warmup": 0, "unknown_warmup": 0, "skipped_warmup": 0,
            "launched_measured": 0, "ab_reported_completed_measured": 0,
            "ab_reported_failed_measured": 0, "unknown_measured": 0, "skipped_measured": 0,
        },
        "completion": "incomplete", "error": None,
        "activation": "not attempted", "recovery": "not reached",
        "canonical_restoration": "not needed", "nginx_error_log": {"availability": "not captured"},
    }
    code = 1
    runtime_mutated = False
    probe_process: subprocess.Popen[str] | None = None
    try:
        problem = preflight_error(config, rep)
        if problem:
            document["error"] = problem
        else:
            token = acquire_token()
            if token is None:
                document["error"] = "fresh token acquisition failed (sanitized)"
            else:
                # Activation can partially mutate runtime state even when it reports failure.
                runtime_mutated = True
                progress("preflight passed")
                activation = activate(config)
                document["activation"] = "verified" if activation is None else "failed"
                if activation is not None:
                    document["error"] = activation
                else:
                    progress("selected Nginx profile verified")
                    if config == "resilient":
                        probe_process, probe_problem = start_probe(paths)
                        document["availability_probe"] = {"csv": str(paths["probe_csv"].relative_to(ROOT)),
                                                          "state": "running" if probe_process and not probe_problem else "failed",
                                                          "started_at": now()}
                        if probe_problem:
                            document["error"] = probe_problem
                    if document.get("error"):
                        pass
                    else:
                        warmup, _warmup_kill = run_ab(WARMUP, identifier, "warmup", paths["warmup_raw"], token=token)
                        document["warmup"] = serialise(warmup)
                        document["warmup_lifecycle"] = _warmup_kill
                        record_traffic(document, "warmup", warmup, WARMUP)
                    if not document.get("error") and not metrics_accounted(warmup, WARMUP, warmup=True):
                        document["traffic"]["skipped_measured"] = MEASURED
                        document["traffic"]["skipped"] += MEASURED
                        document["error"] = "warm-up was incomplete or had failed/non-2xx responses; backend kill was not attempted"
                    elif not document.get("error"):
                        target, target_error = backend_two_id()
                        if target_error or not target:
                            document["traffic"]["skipped_measured"] = MEASURED
                            document["traffic"]["skipped"] += MEASURED
                            document["error"] = (target_error or "backend-2 identity was not verified") + "; backend kill was not attempted"
                        else:
                            progress("backend-2 identity and health verified; container=" + target[:12])
                            measured, kill = run_ab(MEASURED, identifier, "measured", paths["measured_raw"], target, token=token)
                            document["measured"], document["kill"] = serialise(measured), kill
                            record_traffic(document, "measured", measured, MEASURED)
                            try:
                                document["nginx_diagnostics"] = nginx_diagnostics(identifier)
                            except Exception:
                                document["nginx_diagnostics"] = {
                                    "warmup": {"availability": "unavailable", "matching_lines": 0, "status_counts": {}},
                                    "measured": {"availability": "unavailable", "matching_lines": 0, "status_counts": {}},
                                }
                            try:
                                error_text, error_state = nginx_error_excerpt(identifier, document["started_at"], now())
                                paths["nginx_errors"].write_text(error_text, encoding="utf-8")
                                document["nginx_error_log"] = error_state
                            except Exception:
                                document["nginx_error_log"] = {"availability": "unavailable"}
                                document["error"] = "Nginx error-log evidence could not be captured"
                            if kill.get("timer_joined") is not True:
                                document["runtime_state_uncertain"] = True
                                document["recovery"] = "not attempted because the kill callback may still be active"
                                recovery_problem = "kill callback was not quiescent; recovery was blocked to avoid a race"
                            else:
                                try:
                                    recovery_problem = recover_backend_two()
                                except Exception:
                                    recovery_problem = "backend recovery raised an exception"
                                document["recovery"] = "verified" if recovery_problem is None else "failed"
                                document["post_recovery_health_at"] = now() if recovery_problem is None else None
                                if recovery_problem is None and config == "resilient":
                                    coverage_summary, coverage_problem = wait_for_probe_coverage(
                                        probe_process, paths,
                                        document.get("warmup_lifecycle", {}).get("sentinel_timestamp"),
                                        document["post_recovery_health_at"],
                                    )
                                    document["availability_probe"]["coverage_summary"] = coverage_summary
                                    document["availability_probe"]["coverage"] = (
                                        "verified" if coverage_problem is None else "insufficient"
                                    )
                                    if coverage_problem:
                                        document["completion"] = "incomplete"
                                        document["error"] = document.get("error") or coverage_problem
                            if recovery_problem:
                                document["error"] = document.get("error") or recovery_problem
                            elif kill.get("error"):
                                document["error"] = document.get("error") or str(kill["error"])
                            elif kill.get("cleanup_verified") is not True:
                                document["error"] = document.get("error") or "load-test invocation cleanup was not verified"
                            elif not metrics_accounted(measured, MEASURED):
                                document["error"] = document.get("error") or "measured Apache Bench output is incomplete or request accounting is inconsistent"
                            elif not kill.get("start_sentinel_seen") or not kill.get("end_sentinel_seen") or kill.get("ab_exit_status") != "0":
                                document["error"] = document.get("error") or "measured Apache Bench sentinel lifecycle is incomplete"
                            elif kill.get("timer_joined") is not True or kill.get("reader_joined") is not True:
                                document["error"] = document.get("error") or "measured subprocess/timer cleanup was not verified"
                            elif not diagnostics_usable(document.get("nginx_diagnostics")):
                                document["error"] = document.get("error") or "phase-separated Nginx access diagnostics were unavailable or incomplete"
                            elif document.get("nginx_error_log", {}).get("availability") == "unavailable":
                                document["error"] = document.get("error") or "Nginx error-log capture was unavailable"
                            elif document.get("error") is not None:
                                pass
                            else:
                                document["completion"] = "complete"
                                document["error"] = None
    except KeyboardInterrupt:
        document["error"] = document.get("error") or "Step 12 run interrupted by user"
    except Exception:
        # Do not echo arbitrary exception text; it may contain protected environment data.
        document["error"] = document.get("error") or "unexpected Step 12 harness exception; details were sanitized"
    finally:
        # The token is scoped to each load-test child environment; it is never added
        # to the parent process environment or inherited by restoration/diagnostics.
        # Evidence collection must happen against the experiment container, before restoration recreates it.
        if config == "resilient":
            summary, probe_problem = stop_probe(probe_process, paths)
            document["availability_probe"] = document.get("availability_probe", {})
            document["availability_probe"]["summary"] = summary
            document["availability_probe"]["state"] = "verified" if probe_problem is None else "failed"
            document["availability_probe"]["stopped_at"] = now()
            if probe_problem:
                document["completion"] = "incomplete"
                document["error"] = document.get("error") or probe_problem
            try:
                paths["probe_stop"].unlink(missing_ok=True)
            except OSError:
                document["completion"] = "incomplete"
                document["error"] = document.get("error") or "availability probe stop-control cleanup failed"
            warmup_start = document.get("warmup_lifecycle", {}).get("sentinel_timestamp")
            recovery_at = document.get("post_recovery_health_at")
            coverage_established = document["availability_probe"].get("coverage") == "verified"
            if not coverage_established:
                document["completion"] = "incomplete"
                document["error"] = document.get("error") or "availability probe coverage could not be established"
            elif not probe_coverage(summary, warmup_start, recovery_at):
                document["completion"] = "incomplete"
                document["error"] = document.get("error") or "availability probe CSV does not cover warm-up through post-recovery health"
        if runtime_mutated:
            if not isinstance(document.get("nginx_diagnostics"), dict):
                try:
                    document["nginx_diagnostics"] = nginx_diagnostics(identifier)
                except Exception:
                    document["nginx_diagnostics"] = {"warmup": {"availability": "unavailable"},
                                                     "measured": {"availability": "unavailable"}}
            if document.get("nginx_error_log", {}).get("availability") in ("not captured", "unavailable"):
                try:
                    error_text, error_state = nginx_error_excerpt(identifier, document.get("started_at"), now())
                    paths["nginx_errors"].write_text(error_text, encoding="utf-8")
                    document["nginx_error_log"] = error_state
                except Exception:
                    document["nginx_error_log"] = {"availability": "unavailable"}
            if document.get("runtime_state_uncertain"):
                document["canonical_restoration"] = "not attempted because a kill callback may still be active"
            else:
                try:
                    document["canonical_restoration"] = bool(restore_canonical())
                except Exception:
                    document["canonical_restoration"] = False
            progress("canonical restoration " + ("verified" if document["canonical_restoration"] is True else "not attempted" if isinstance(document["canonical_restoration"], str) and document["canonical_restoration"].startswith("not attempted") else "failed"))
        else:
            document["canonical_restoration"] = "not needed"
            if not paths["nginx_errors"].exists():
                try:
                    paths["nginx_errors"].write_text("Not captured because runtime profile mutation was not attempted.\n", encoding="utf-8")
                except OSError:
                    document["nginx_error_log"] = {"availability": "unavailable"}
            if not isinstance(document.get("nginx_diagnostics"), dict):
                document["nginx_diagnostics"] = {
                    phase: {"availability": "not captured", "matching_lines": 0, "status_counts": {}}
                    for phase in ("warmup", "measured")
                }

        finalise_traffic(document)
        document["finished_at"] = now()
        if runtime_mutated and document.get("canonical_restoration") is not True:
            document["completion"] = "incomplete"
            document["error"] = document.get("error") or "canonical three-backend restoration could not be verified"
        if document.get("completion") != "complete" or document.get("canonical_restoration") not in (True, "not needed"):
            code = 1
        else:
            code = 0
        if config == "resilient":
            measured = document.get("measured", {})
            probe = document.get("availability_probe", {}).get("summary") or {}
            accepted = (document.get("completion") == "complete" and measured.get("failed_requests") == 0
                        and measured.get("non_2xx_responses") == 0 and probe.get("failed_probes") == 0)
            document["acceptance"] = "passed" if accepted else "failed"
            if not accepted:
                code = 1

        # Persist each artifact independently so one write failure does not skip all remaining attempts.
        write_errors: list[str] = []
        try:
            atomic_json(paths["nginx_diagnostics"], document["nginx_diagnostics"])
        except OSError:
            write_errors.append("Nginx diagnostics JSON could not be saved")
        try:
            if not paths["nginx_errors"].exists():
                paths["nginx_errors"].write_text("Nginx error-log artifact was not produced.\n", encoding="utf-8")
        except OSError:
            write_errors.append("Nginx error-log artifact could not be saved")
        if write_errors:
            document["completion"] = "incomplete"
            document["error"] = document.get("error") or "; ".join(write_errors)
            code = 1
        try:
            write_markdown(paths["result_markdown"], document)
        except OSError:
            document["completion"] = "incomplete"
            document["error"] = document.get("error") or "result Markdown could not be saved"
            code = 1
        try:
            atomic_json(paths["result_json"], document)
        except OSError:
            print("ERROR: result JSON could not be saved", file=sys.stderr)
            code = 1
    return code, document

def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Run the Step 12 controlled failure-before-fix experiment")
    value.add_argument("--config", type=profile, required=True)
    value.add_argument("--rep", type=int, required=True)
    return value


def main() -> int:
    args = parser().parse_args()
    if args.rep < 1:
        parser().error("--rep must be positive")
    code, document = execute(args.config, args.rep)
    if document.get("error"):
        print(str(document["error"]), file=sys.stderr)
    return 1 if code or document.get("canonical_restoration") is not True else 0


if __name__ == "__main__":
    raise SystemExit(main())
