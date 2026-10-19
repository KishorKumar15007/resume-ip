# DA3 Evidence Index

Status meanings: `needed` = not yet captured; `captured` = screenshot file is present; `verified` = screenshot and corresponding report description have been reviewed for accuracy and readability.

| File | Part | Must show | How to produce | Status |
| --- | --- | --- | --- | --- |
| `docs/da3/evidence/env-da1-url-reachable.png` | Environment / Section 0 | DA1 frontend landing page and browser address bar showing the active Cloud Run URL | Open `https://resume-ip-frontend-123719832707.asia-south1.run.app/` in the browser | captured |
| `docs/da3/evidence/env-da1-deployment-status.png` | Environment / Section 0 | Google Cloud Console → Cloud Run service list for `resume-ip-api`, `resume-ip-frontend` and `resume-ip-worker`, with region/status/access columns visible | GCP Console → project `resume-ip` → Cloud Run → Services | captured |
| `docs/da3/evidence/env-cloudsql-suspended.png` | Environment / Section 0 | Cloud SQL instance `resume-ip-db` and explicit warning that the free-trial instance is suspended | GCP Console → project `resume-ip` → Cloud SQL → Instances → `resume-ip-db` → Overview | captured |
| `docs/da3/evidence/env-db-dependent-login-error.png` | Environment / Section 0 | Login page and displayed generic message, “We could not sign you in. Please try again.”; no password or secret should be visible | Open the DA1 frontend `/login` page and capture the observed sign-in failure | captured |
| `docs/da3/evidence/env-neon-project.png` | Environment / Phase 1 | Neon project name, region, and default branch, with connection strings obscured. The captured file shows `resume-ip-da3`, AWS Asia Pacific 1 (Singapore), and default `production`. PostgreSQL 18 is owner-confirmed but not visible in this image; no separate version screenshot is required for Step 3. | Captured Neon branch overview. | captured |
| `docs/da3/evidence/env-alembic-head.png` | Environment / Phase 1 | Timestamped terminal output for the migration commands and `ce1c22c4205c (head)`, with database host/credentials hidden. | Captured from `backend/` after migration; content and report claim reviewed. | verified |
| `docs/da3/evidence/env-neon-tables.png` | Environment / Phase 1 | Neon Tables view visibly listing `alembic_version`, `job_postings`, `submissions`, and `users`, with `ce1c22c4205c` visible in `alembic_version`. | Existing owner capture; content and report claim reviewed. | verified |
| `docs/da3/evidence/env-smoke-pass.png` | Environment / Phase 1 | Saved synthetic smoke-test table showing overall PASS and all 19 checks. | Existing owner capture; content and report claim reviewed against `results/04-smoke.*`. | verified |
| `docs/da3/evidence/env-local-upload-done.png` | Environment / Step 5 | Synthetic submission shown as DONE with score and matched skills. | Run the Step 5 local-upload workflow, then capture the status/result view. | needed |
| `docs/da3/evidence/env-cloudrun-service.png` | Environment / Step 6A | Cloud Run service/revision with secret values hidden. | Follow the approved hosting-redeploy verification procedure. | needed |
| `docs/da3/evidence/env-deployed-url-works.png` | Environment / Step 6A | Redeployed URL loading successfully. | Open the deployed URL after verification. | needed |
| `docs/da3/evidence/env-hosting-status.png` | Environment / Step 6B | Actual hosting state when Cloud Run is unavailable. | Capture the relevant console or browser state. | needed |
| `docs/da3/evidence/1a-neon-branches.png` | 1a / Step 7 | Neon branches `production` and `da3-loadtest`. | Neon Console → Branches; hide connection strings. | needed |
| `docs/da3/evidence/1a-seed-output.png` | 1a / Step 7 | Synthetic seed output with database host redacted. | Run the approved seed script against `da3-loadtest`. | needed |
| `docs/da3/evidence/1a-xservedby-header.png` | 1a / Step 7 | `curl -i` response showing `X-Served-By`. | Run the documented health request. | needed |
| `docs/da3/evidence/1a-compose-ps.png` | 1a / Step 8 | Three backends and Nginx with ports. | Run `docker compose ps` for the DA3 topology. | needed |
| `docs/da3/evidence/1a-curl-rotation.png` | 1a / Step 8 | Multiple responses rotating `X-Served-By`. | Send six requests through Nginx. | needed |
| `docs/da3/evidence/1a-host-resources.png` | 1a / Step 8 | Docker host resources and configured CPU limit. | Capture documented `docker info` and `docker inspect` output. | needed |
| `docs/da3/evidence/1a-neon-connected.png` | 1a / Step 8 | `/health/db` through Nginx returning `db: ok`. | Run the health check with host redacted. | needed |
| `docs/da3/evidence/1a-distribution-table.png` | 1a / Step 9 | Per-backend distribution table. | Run `scripts/distribution_test.py`. | needed |
| `docs/da3/evidence/1a-nginx-log-upstreams.png` | 1a / Step 9 | Nginx log lines with distinct `$upstream_addr` values. | Capture the logged upstream slice. | needed |
| `docs/da3/evidence/1b-calibration-table.png` | 1b / Step 10 | Calibration table. | Run the bounded calibration mode. | needed |
| `docs/da3/evidence/1b-docker-stats-1-instance.png` | 1b / Step 10 | One-instance saturation in `docker stats`. | Capture during the calibration run. | needed |
| `docs/da3/evidence/1b-ab-1-instance.png` | 1b / Step 11 | One-instance Apache Bench summary. | Capture a reported 1-instance repetition. | needed |
| `docs/da3/evidence/1b-ab-3-instances.png` | 1b / Step 11 | Three-instance Apache Bench summary. | Capture a reported 3-instance repetition. | needed |
| `docs/da3/evidence/1b-results-table.png` | 1b / Step 11 | Aggregated one-versus-three table. | Run `scripts/aggregate_1b.py`. | needed |
| `docs/da3/evidence/1b-docker-stats-3-instances.png` | 1b / Step 11 | Three backend containers sharing load. | Capture `docker stats` during a 3-instance run. | needed |
| `docs/da3/evidence/1c-before-ab-summary.png` | 1c / Step 12 | Failure baseline Apache Bench summary. | Run the approved failover baseline. | needed |
| `docs/da3/evidence/1c-before-nginx-errors.png` | 1c / Step 12 | Nginx upstream errors around the kill. | Capture the baseline log slice. | needed |
| `docs/da3/evidence/1c-docker-kill.png` | 1c / Step 12 | Timestamped backend kill during load. | Capture the documented PowerShell command. | needed |
| `docs/da3/evidence/1c-after-ab-summary.png` | 1c / Step 13 | Resilient failover Apache Bench summary. | Run the resilient configuration. | needed |
| `docs/da3/evidence/1c-nginx-diff.png` | 1c / Step 13 | Nginx resilience configuration diff. | Capture `results/13-nginx-config.diff`. | needed |
| `docs/da3/evidence/1c-retry-log.png` | 1c / Step 13 | Retried request with two upstream addresses. | Capture resilient Nginx retry logs. | needed |
| `docs/da3/evidence/1c-before-after-table.png` | 1c / Step 13 | Generated before/after failure table. | Run `scripts/aggregate_1c.py`. | needed |
| `docs/da3/evidence/1c-availability-probe.png` | 1c | Probe summary showing total probes and 0 failed probes during a resilient run. | `scripts/availability_probe.py` summary shown during `failover_test.py --config resilient`. | needed |
| `docs/da3/evidence/1d-architecture-diagram.png` | 1d / Step 14 | Final architecture diagram with proposed burst component. | Export the approved diagram. | needed |
| `docs/da3/evidence/2a-before-plaintext-demo.png` | 2a / Step 15 | Labelled plaintext demonstration table. | Capture the demo exactly as labelled. | needed |
| `docs/da3/evidence/2a-after-hashed-users.png` | 2a / Step 15 | Real users table with Argon2id hashes. | Capture after approved hashing verification. | needed |
| `docs/da3/evidence/2a-salt-proof.png` | 2a / Step 15 | Same-password users with distinct hashes. | Capture the salt demonstration. | needed |
| `docs/da3/evidence/2a-argon2-check.png` | 2a / Step 15 | Argon2 parameter-check output. | Run the approved check script. | needed |
| `docs/da3/evidence/2b-migration-applied.png` | 2b / Step 16 | MFA migration revision and columns. | Capture Alembic/Neon after MFA migration. | needed |
| `docs/da3/evidence/2b-secret-encrypted.png` | 2b / Step 16 | Encrypted TOTP field, with ciphertext blurred. | Capture the approved database view. | needed |
| `docs/da3/evidence/2b-mfa-flow-test.png` | 2b / Step 16 | MFA flow PASS/FAIL table. | Run the MFA flow script. | needed |
| `docs/da3/evidence/2b-lockout.png` | 2b / Step 16 | Wrong-code lockout response. | Capture the controlled test response. | needed |
| `docs/da3/evidence/2b-qr-enrol-screen.png` | 2b / Step 17 | TOTP setup screen with secret hidden. | Capture the frontend setup view. | needed |
| `docs/da3/evidence/2b-authenticator-phone.png` | 2b / Step 17 | Authenticator entry and code only. | Capture a cropped phone screen. | needed |
| `docs/da3/evidence/2b-login-step1.png` | 2b / Step 17 | First login step. | Capture the frontend flow. | needed |
| `docs/da3/evidence/2b-login-step2.png` | 2b / Step 17 | Second login step. | Capture the frontend flow. | needed |
| `docs/da3/evidence/2b-login-success.png` | 2b / Step 17 | Successful MFA login. | Capture the frontend flow. | needed |
| `docs/da3/evidence/2b-recruiter-forced-enrol.png` | 2b / Step 17 | Required recruiter enrolment, if implemented. | Capture the frontend flow. | needed |
| `docs/da3/evidence/2b-no-token-rejected.png` | 2b / Step 18 | 401 rejection without a token. | Capture the command and response. | needed |
| `docs/da3/evidence/2b-swagger-401.png` | 2b / Step 18 | Swagger unauthorised DELETE response. | Capture Swagger Try it out. | needed |
| `docs/da3/evidence/2b-authz-matrix.png` | 2b / Step 18 | Full authorisation matrix, all PASS. | Run `scripts/authz_matrix.py`. | needed |
| `docs/da3/evidence/2b-candidate-403.png` | 2b / Step 18 | Candidate receives 403 for posting mutation. | Capture the controlled request. | needed |
| `docs/da3/evidence/2c-trivy-baseline-summary.png` | 2c / Step 19 | Baseline CRITICAL/HIGH totals with versions. | Run the approved containerised Trivy scan. | needed |
| `docs/da3/evidence/2c-trivy-baseline-frontend.png` | 2c | Trivy totals for the frontend baseline image (only if a frontend image exists). | `scripts/trivy_scan.py resume-frontend:da3-baseline frontend-baseline`. | needed |
| `docs/da3/evidence/2c-dockerfile-baseline.png` | 2c / Step 19 | Baseline Dockerfile. | Capture the reviewed file. | needed |
| `docs/da3/evidence/2c-baseline-user-size.png` | 2c / Step 19 | Baseline image user and size. | Capture documented Docker output. | needed |
| `docs/da3/evidence/2c-trivy-hardened-summary.png` | 2c / Step 20 | Hardened CRITICAL/HIGH totals. | Run the identical hardened scan. | needed |
| `docs/da3/evidence/2c-trivy-hardened-frontend.png` | 2c | Trivy totals for the frontend after hardening (only if a frontend image exists and is hardened). | `scripts/trivy_scan.py resume-frontend:da3-hardened frontend-hardened`. | needed (conditional on the Step 20 decision to harden the frontend) |
| `docs/da3/evidence/2c-dockerfile-hardened.png` | 2c / Step 20 | Hardened Dockerfile. | Capture the reviewed file. | needed |
| `docs/da3/evidence/2c-nonroot-proof.png` | 2c / Step 20 | Container UID 10001. | Run the documented container `id` command. | needed |
| `docs/da3/evidence/2c-image-sizes.png` | 2c / Step 20 | Baseline and hardened image sizes. | Capture `docker images`. | needed |
| `docs/da3/evidence/2c-before-after-table.png` | 2c / Step 20 | Generated scan comparison table. | Run `scripts/aggregate_2c.py`. | needed |
| `docs/da3/evidence/2c-app-still-works.png` | 2c / Step 20 | Regression scripts passing on hardened image. | Capture the approved checks. | needed |
