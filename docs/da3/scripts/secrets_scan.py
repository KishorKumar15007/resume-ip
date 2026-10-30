"""Run a redacted DA3 Step 23 secrets scan without retaining secret values."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "docs" / "da3" / "results"
OUTPUT = RESULTS / "23-secrets-scan.md"
# Exact version tag; changing this scanner requires an explicit reviewed change.
GITLEAKS_IMAGE = "zricethezav/gitleaks:v8.18.4"

TREE_PATTERNS = {
    "neon_host": rb"neon\.tech",
    "postgresql_password_url": rb"postgresql(?:\+[A-Za-z0-9_]+)?://[^\s:@/]+:[^\s@]+@",
    "jwt_secret_assignment": rb"(?im)^\s*JWT_SECRET(?:_KEY)?\s*=\s*[^\s#]+",
    "mfa_key_assignment": rb"(?im)^\s*MFA_ENCRYPTION_KEY\s*=\s*[^\s#]+",
}

# `git log -G` uses Git's regular-expression engine, so keep its patterns
# deliberately POSIX-compatible rather than passing Python-specific syntax.
HISTORY_PATTERNS = {
    "neon_host": r"neon\.tech",
    "postgresql_password_url": r"postgresql://[^[:space:]]*:[^[:space:]@]*@",
    "jwt_secret_assignment": r"JWT_SECRET(_KEY)?[[:space:]]*=",
    "mfa_key_assignment": r"MFA_ENCRYPTION_KEY[[:space:]]*=",
}


@dataclass(frozen=True)
class ScanResult:
    label: str
    completed: bool
    finding_count: int | None
    exit_code: int | None
    diagnostic: str


def command(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            arguments,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(arguments, 127, "", type(exc).__name__)


def sanitized_diagnostic(value: str) -> str:
    """Return a non-sensitive diagnostic category, never raw scanner output."""
    text = value.lower()
    if "not found" in text or "no such file" in text:
        return "required executable or file unavailable"
    if "timeout" in text:
        return "scan timed out"
    if text.strip():
        return "scanner returned a non-sensitive diagnostic"
    return "no diagnostic output"


def gitleaks_scan(label: str, arguments: list[str], report_path: Path) -> ScanResult:
    completed = command(arguments)
    findings: int | None = None
    if report_path.is_file():
        try:
            parsed = json.loads(report_path.read_text(encoding="utf-8"))
            findings = len(parsed) if isinstance(parsed, list) else None
        except (OSError, ValueError):
            return ScanResult(label, False, None, completed.returncode, "redacted report unreadable")
    # Gitleaks uses exit 1 when leaks are found. Any other nonzero result is an
    # incomplete scan rather than a clean result.
    complete = completed.returncode in (0, 1) and findings is not None
    return ScanResult(
        label,
        complete,
        findings,
        completed.returncode,
        "complete" if complete else sanitized_diagnostic(completed.stderr or completed.stdout),
    )


def iter_tree_files() -> list[Path]:
    excluded = {".git", ".venv", "node_modules", "__pycache__"}
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in excluded for part in path.parts):
            continue
        if path.resolve() == Path(__file__).resolve():
            continue
        paths.append(path)
    return paths


def tree_matches(pattern: bytes) -> list[str]:
    expression = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    matches: list[str] = []
    for path in iter_tree_files():
        try:
            if expression.search(path.read_bytes()):
                matches.append(path.relative_to(ROOT).as_posix())
        except OSError:
            continue
    return matches


def history_commit_count(pattern: str) -> int | None:
    completed = command(["git", "log", "--all", "-G", pattern, "--format=%H", "--"])
    if completed.returncode:
        return None
    return len({line.strip() for line in completed.stdout.splitlines() if line.strip()})


def write_report(scans: list[ScanResult], tree: dict[str, list[str]], history: dict[str, int | None]) -> None:
    status = "PASS" if all(scan.completed and scan.finding_count == 0 for scan in scans) else "FAIL"
    lines = [
        "# DA3 Step 23 secrets scan",
        "",
        f"Overall result: **{status}**",
        "",
        f"Container image: `{GITLEAKS_IMAGE}` (version-pinned; not `latest`).",
        "The scanner mounts the repository read-only, uses no network after image availability, and writes only redacted temporary JSON outside the repository.",
        "",
        "| Scan | Complete | Findings | Exit status | Diagnostic |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for scan in scans:
        findings = "unknown" if scan.finding_count is None else str(scan.finding_count)
        exit_code = "unknown" if scan.exit_code is None else str(scan.exit_code)
        lines.append(f"| {scan.label} | {'yes' if scan.completed else 'no'} | {findings} | {exit_code} | {scan.diagnostic} |")
    lines.extend(["", "## Targeted pattern checks", "", "These checks record paths/counts only; they never write matching text or values.", "", "| Pattern | Working-tree files | History commits |", "| --- | --- | ---: |"])
    for name in TREE_PATTERNS:
        paths = tree[name]
        path_text = "none" if not paths else ", ".join(f"`{path}`" for path in paths)
        history_count = "unknown" if history[name] is None else str(history[name])
        lines.append(f"| {name} | {path_text} | {history_count} |")
    lines.extend(["", "No secret values, URLs, token text, or raw Gitleaks reports are retained in this result."])
    RESULTS.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if OUTPUT.exists():
        print("secrets scan stopped: refusing to overwrite an existing result", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="da3-gitleaks-") as temporary:
        output = Path(temporary)
        mount_root = str(ROOT.resolve())
        mount_output = str(output.resolve())
        shared = ["docker", "run", "--rm", "--network", "none", "-v", f"{mount_root}:/repo:ro", "-v", f"{mount_output}:/out", GITLEAKS_IMAGE]
        scans = [
            gitleaks_scan("Git history (--all)", shared + ["detect", "--source=/repo", "--log-opts=--all", "--no-banner", "--redact=100", "--report-format=json", "--report-path=/out/history.json"], output / "history.json"),
            gitleaks_scan("working tree", shared + ["detect", "--no-git", "/repo", "--no-banner", "--redact=100", "--report-format=json", "--report-path=/out/tree.json"], output / "tree.json"),
        ]
        tree = {name: tree_matches(pattern) for name, pattern in TREE_PATTERNS.items()}
        history = {name: history_commit_count(pattern) for name, pattern in HISTORY_PATTERNS.items()}
        write_report(scans, tree, history)
    return 0 if all(scan.completed and scan.finding_count == 0 for scan in scans) else 1


if __name__ == "__main__":
    raise SystemExit(main())
