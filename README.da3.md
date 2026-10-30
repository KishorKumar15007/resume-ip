# DA3 reproduction guide

This guide reproduces the local DA3 Docker Compose experiments. It does not
replace the deployed application runbook.

## Prerequisites

- Docker Desktop, with Docker Compose v2 available in PowerShell.
- A Neon PostgreSQL database prepared for the DA3 load-test branch.
- Python from `backend/.venv` for the DA3 helper scripts.

### Private configuration boundary

`compose.da3.yml:7-8` loads its configuration from the absolute path named by
`DA3_LOADTEST_ENV_FILE`. `backend/.env.example:6-7` is a placeholder template
and explicitly says not to create or use `backend/.env`.

Therefore, do **not** copy a configuration file into `backend/.env` or
`backend/.env.loadtest`. The owner must create and maintain any private
configuration outside the repository, enter secrets privately, and set
`DA3_LOADTEST_ENV_FILE` to that absolute private path before running Compose.
No command in this guide reads or prints its contents.

The private load-test configuration must contain the names required by the
existing scripts (including `DATABASE_URL`, `GCS_BUCKET_NAME`,
`GCP_PROJECT_ID`, `PUBSUB_RESUME_UPLOADED_TOPIC`, `JWT_SECRET_KEY`, and the
`DA3_LOADTEST_BRANCH=da3-loadtest` sentinel). Use the pooled TLS database URL
for runtime traffic. Do not place values in this guide, Git, result files, or
screenshots.

## Start the isolated DA3 stack

From the repository root, privately set the path and start the three backends
and Nginx:

```powershell
$env:DA3_LOADTEST_ENV_FILE = '<absolute private load-test configuration path>'
docker compose -f compose.da3.yml up --build
```

`compose.da3.yml:3-54` defines the topology. The `loadtest` service is profile
gated and does not start in the command above.

| Service | Host port | Container port | Purpose |
| --- | ---: | ---: | --- |
| `backend-1` | 8001 | 8000 | FastAPI/Uvicorn, one worker |
| `backend-2` | 8002 | 8000 | FastAPI/Uvicorn, one worker |
| `backend-3` | 8003 | 8000 | FastAPI/Uvicorn, one worker |
| `nginx` | 8080 | 80 | Local reverse proxy used by DA3 traffic |

There is no frontend service in `compose.da3.yml`; DA3 traffic targets Nginx
at `http://localhost:8080`.

## One command per assessed part

These commands are owner-run operations. Preserve accepted artifacts before
rerunning a harness: several scripts intentionally refuse collisions, while
the Step 9 distribution script writes its canonical `09-distribution.*` paths.

| Part | Command from repository root | Expected output |
| --- | --- | --- |
| 1a | `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\distribution_test.py` | `docs/da3/results/09-distribution.md` plus `.json` and `.csv` |
| 1b | `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\run_1b.py` | a new `docs/da3/results/11-1b-manifest-<run-id>.json` and per-run artifacts |
| 1c | `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\failover_test.py --config resilient --rep <fresh-repetition>` | `docs/da3/results/13-1c-s13-resilient-r<rep>-<id>.md` and `.json` |
| 1d | `Get-Content .\docs\da3\results\14-components-table.md` | `docs/da3/results/14-components-table.md` |
| 2a | `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\argon2_check.py` | `docs/da3/results/15-argon2-check.md` |
| 2b | `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\mfa_flow_test.py --base-url http://localhost:8080 --result-path docs/da3/results/<fresh-2b-result>.md` | the requested fresh Markdown result under `docs/da3/results/` |
| 2c | `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\trivy_scan.py <image-tag> <label> --dockerfile .\backend\Dockerfile --result-prefix 23-trivy` | `docs/da3/results/23-trivy-<label>.json`, `.metadata.json`, and `.md` |
| 2d | `Get-Content .\docs\da3\2d-threat-controls.md` | `docs/da3/2d-threat-controls.md` (the source/evidence table for Table 2d.1) |

Part 1a requires `LOADTEST_TOKEN`, which the existing distribution harness reads
from the process environment; use `docs/da3/scripts/get_token.py` privately to
obtain it and never print or save it. Parts 1b and 1c acquire their own fresh
tokens through their existing harness paths. Part 2a prompts for the synthetic
users' shared password without echoing it.

## Secrets scan (Step 23)

Run the non-destructive scan only when ready:

```powershell
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\secrets_scan.py
```

It writes the sanitized summary `docs/da3/results/23-secrets-scan.md`. It runs
a version-pinned Gitleaks container against both the working tree and all Git
history, and records only counts and safe identifiers; it does not retain raw
matches or secret material.

## Teardown

Stop the isolated DA3 containers without deleting named volumes or result
artifacts:

```powershell
docker compose -f compose.da3.yml down
```

## Discrepancies

The requested instruction to copy `.env.example` into `backend/.env` and
`backend/.env.loadtest` conflicts with the checked-in template and the
repository security rules. The actual Compose contract uses the externally
maintained `DA3_LOADTEST_ENV_FILE` path, so this guide intentionally does not
provide those copy commands.
