# Hardened-image MFA and authorization regression runbook

This runbook is for an owner-run verification after the implementation patch is reviewed. It does not claim that any command below has run successfully.

## Prepare the local paths and Compose project

Run from any clone location; the commands resolve the Git root and its parent without printing environment-file contents.

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
Set-Location $repoRoot
$environmentParent = Split-Path -Parent $repoRoot
$hostEnvironment = Join-Path $environmentParent ".env"
$loadtestEnvironment = Join-Path $environmentParent ".env.loadtest"

if (-not (Test-Path -LiteralPath $hostEnvironment -PathType Leaf)) { throw "Parent-level .env is unavailable." }
if (-not (Test-Path -LiteralPath $loadtestEnvironment -PathType Leaf)) { throw "Parent-level .env.loadtest is unavailable." }

$env:DA3_LOADTEST_ENV_FILE = $loadtestEnvironment
$env:COMPOSE_PROJECT_NAME = "resume-ip-da3-hardened-regression"
$env:NGINX_CONF = "nginx-3.conf"
```

`DA3_LOADTEST_ENV_FILE` is consumed by `compose.da3.yml` and by both host-side regression scripts. Do not print or source either environment file into the terminal session.

## Start and identify the hardened three-backend topology

```powershell
docker image inspect resume-backend:da3-hardened --format '{{.Id}}'
docker compose -f .\compose.da3.yml -f .\compose.da3.hardened.yml config --images
docker compose -f .\compose.da3.yml -f .\compose.da3.hardened.yml up -d --no-build --wait

$expectedImageId = (docker image inspect resume-backend:da3-hardened --format '{{.Id}}').Trim()
foreach ($service in "backend-1", "backend-2", "backend-3") {
    $containerId = (docker compose -f .\compose.da3.yml -f .\compose.da3.hardened.yml ps -q $service).Trim()
    $actualImageId = (docker inspect $containerId --format '{{.Image}}').Trim()
    if ($actualImageId -ne $expectedImageId) { throw "$service is not running the hardened image." }
}

docker compose -f .\compose.da3.yml -f .\compose.da3.hardened.yml ps
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/health/db
```

The override changes only the images of `backend-1`, `backend-2`, and `backend-3`; the base Compose file retains ports, Nginx, health checks, resource limits, and environment loading. `--no-build` prevents an unreviewed rebuild.

## Run the isolated MFA regression

```powershell
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\mfa_flow_test.py `
  --base-url http://127.0.0.1:8080 `
  --result-path .\docs\da3\results\20-mfa-hardened-regression.md
```

The custom result path must not exist already. The script uses synthetic data, performs its existing host-and-three-backend clock preflight, and removes its synthetic MFA user when possible.

## Run the isolated authorization lifecycle

Choose a fresh lower-case run ID, then use the same argument set for every lifecycle command.

```powershell
$runId = "s20-hardened-$(Get-Date -Format yyyyMMdd-HHmmss)"
$matrixArgs = @(
  "--run-id", $runId,
  "--base-url", "http://127.0.0.1:8080",
  "--results-stem", "20-authz-hardened-regression",
  "--fixture-stem", "20-authz-hardened-fixture",
  "--capture-prefix", "2c-authz-hardened-regression"
)

& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --prepare
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --run-matrix
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --capture-no-token
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --capture-candidate-denial
```

Before finalizing the owner DELETE, capture the three readable PNGs below. Do not expose tokens, passwords, database URLs, encryption keys, QR payloads, or TOTP codes.

```text
docs/da3/evidence/2c-authz-hardened-regression-no-token-rejected.png
docs/da3/evidence/2c-authz-hardened-regression-swagger-401.png
docs/da3/evidence/2c-authz-hardened-regression-candidate-403.png
```

Then perform the capture gate and finalization:

```powershell
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --verify-captures
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --finalize-delete
```

Capture the completed matrix at:

```text
docs/da3/evidence/2c-authz-hardened-regression-matrix.png
```

Finally validate that capture and remove only the exact run-scoped fixture:

```powershell
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --verify-complete-captures
& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\authz_matrix.py @matrixArgs --cleanup
```

The isolated outputs are `20-authz-hardened-fixture-<run-id>.json`, attempt files under the `20-authz-hardened-regression-<run-id>-attempt-*` stem, and the final `20-authz-hardened-regression.md` / `.json` pair. The existing Step 18 artifacts are not selected by these arguments.

## Manual frontend review

The manual-key UI review is separate from the automated regression runs. Use a synthetic account only. Keep `VITE_API_BASE_URL` unset so the browser uses `/api`, and proxy that route to Nginx:

```powershell
Set-Location (Join-Path $repoRoot "frontend")
$env:API_PROXY_TARGET = "http://127.0.0.1:8080"
npm run dev
```

If capturing the manual-key block, obscure the QR payload and the actual setup key. No pre-change screenshot exists, so do not represent a later capture as a before/after comparison.

## Tear down

```powershell
Set-Location $repoRoot
docker compose -f .\compose.da3.yml -f .\compose.da3.hardened.yml down --remove-orphans
```

This targets only the dedicated `COMPOSE_PROJECT_NAME` and does not remove volumes.
