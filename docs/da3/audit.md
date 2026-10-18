# DA3 Phase 0 — Repository Audit

Audit date: 2026-10-18. Findings are repository-based; no secret environment file or live cloud resource was inspected.

## 1. API endpoints and roles

[`backend/app/main.py`](../../backend/app/main.py) includes the auth, postings, and submissions routers and exposes unauthenticated `GET /health` returning `{"status":"ok"}`.

| Endpoint | Access | Evidence |
| --- | --- | --- |
| `POST /auth/signup`, `POST /auth/login` | Public; signup accepts `candidate` or `recruiter`, and both issue bearer JWTs. | [`backend/app/routers/auth.py`](../../backend/app/routers/auth.py), [`backend/app/schemas/auth.py`](../../backend/app/schemas/auth.py) |
| `POST /postings` | Recruiter. | [`backend/app/routers/postings.py`](../../backend/app/routers/postings.py) |
| `GET /postings`, `GET /postings/{posting_id}` | Authenticated user. | [`backend/app/routers/postings.py`](../../backend/app/routers/postings.py) |
| `PUT /postings/{posting_id}`, `DELETE /postings/{posting_id}` | Recruiter and server-checked posting owner. | [`backend/app/routers/postings.py`](../../backend/app/routers/postings.py) |
| `POST /postings/{posting_id}/submissions` | Candidate; validates PDF upload and returns `202`. | [`backend/app/routers/postings.py`](../../backend/app/routers/postings.py) |
| `GET /postings/{posting_id}/submissions?sort=score` | Recruiter and server-checked posting owner. | [`backend/app/routers/postings.py`](../../backend/app/routers/postings.py), [`backend/app/schemas/submission.py`](../../backend/app/schemas/submission.py) |
| `GET /submissions/{submission_id}` | Candidate owner or recruiter who owns the related posting. | [`backend/app/routers/submissions.py`](../../backend/app/routers/submissions.py) |
| `POST /internal/pubsub/resume-uploaded` | Separate worker FastAPI app; validates Pub/Sub envelope. Repository code does not itself enforce Cloud Run/IAM identity. | [`backend/app/worker.py`](../../backend/app/worker.py) |

JWT handling and shared role dependency are in [`backend/app/core/security.py`](../../backend/app/core/security.py) and [`backend/app/core/dependencies.py`](../../backend/app/core/dependencies.py). Object ownership is checked in posting mutation and submission-read handlers.

## 2. Frontend

A React, TypeScript, Vite frontend exists in [`frontend/`](../../frontend/). Routes in [`frontend/src/app/App.tsx`](../../frontend/src/app/App.tsx) cover landing, login, signup, session, forbidden/not-found, candidate posting list/detail/upload, recruiter posting list/create/edit, and recruiter ranked submissions. [`frontend/src/api/client.ts`](../../frontend/src/api/client.ts) uses `fetch`, sends the in-memory bearer token, and resolves `VITE_API_BASE_URL` with `/api` fallback. Endpoint-specific callers are [`frontend/src/api/auth.ts`](../../frontend/src/api/auth.ts), [`frontend/src/api/postings.ts`](../../frontend/src/api/postings.ts), and [`frontend/src/api/submissions.ts`](../../frontend/src/api/submissions.ts). Frontend guards in [`frontend/src/auth/RequireAuth.tsx`](../../frontend/src/auth/RequireAuth.tsx) are navigation controls; API authorization remains authoritative.

## 3. Worker, scoring, and upload flow

`create_submission` in [`backend/app/routers/postings.py`](../../backend/app/routers/postings.py) requires the candidate role, checks media type and `%PDF-` signature, writes a GCS object, commits a `QUEUED` submission, then publishes an event. The worker endpoint in [`backend/app/worker.py`](../../backend/app/worker.py) decodes base64 Pub/Sub data and calls `process_submission` in [`backend/app/services/submission_processor.py`](../../backend/app/services/submission_processor.py). The processor atomically claims only `QUEUED` rows, downloads/extracts PDF text with `pypdf`, case-insensitively substring-matches required skills, and persists `score = matched_skill_count / required_skill_count * 100`, matched skills, and `DONE` or `FAILED`. Models/schemas are [`backend/app/models/submission.py`](../../backend/app/models/submission.py) and [`backend/app/schemas/submission.py`](../../backend/app/schemas/submission.py).

## 4. Storage, publishing, environment, and unavailable credentials

| Concern | Repository evidence |
| --- | --- |
| Storage | [`backend/app/services/gcs_storage.py`](../../backend/app/services/gcs_storage.py) uses `google.cloud.storage` and controlled `gs://<bucket>/submissions/<uuid>.pdf` paths. |
| Publishing | [`backend/app/services/resume_event_publisher.py`](../../backend/app/services/resume_event_publisher.py) uses `google.cloud.pubsub_v1.PublisherClient` to publish a JSON resume-uploaded event after commit. |
| Required configuration | [`backend/app/database.py`](../../backend/app/database.py) requires `DATABASE_URL`, `GCS_BUCKET_NAME`, `GCP_PROJECT_ID`, and `PUBSUB_RESUME_UPLOADED_TOPIC`; [`backend/app/core/security.py`](../../backend/app/core/security.py) requires `JWT_SECRET_KEY`. `CORS_ALLOWED_ORIGINS`, `JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` have optional/default behavior. |
| Credentials | Both cloud clients use Application Default Credentials; no service-account key loading was found. |
| No GCP credentials | Client construction is lazy, so import/startup does not create a cloud client, but non-secret GCP setting names are still required. Failed GCS upload returns controlled HTTP 500; failed publication marks the submission failed, attempts cleanup, and returns controlled HTTP 500. Worker download failure becomes `FAILED`. No local storage or queue fallback was found. |

Effective environment values and current credential validity are **unknown**.

## 5. Containers and Compose

| File | Base image(s) | User | Command / Uvicorn workers | Ports | Environment file |
| --- | --- | --- | --- | --- | --- |
| [`backend/Dockerfile`](../../backend/Dockerfile) | `python:3.14.2-slim` | Creates/selects unprivileged `app`. | API target runs `uvicorn app.main:app`; worker target runs `uvicorn app.worker:app`; no `--workers`, so one worker process. | `8080`, from `PORT` defaulting to 8080. | None. |
| [`frontend/Dockerfile`](../../frontend/Dockerfile) | build `node:24.14.0-alpine`; runtime `nginxinc/nginx-unprivileged:1.29-alpine` | Unprivileged Nginx runtime. | Vite build then Nginx default command. | `8080`; Nginx template reads `PORT`. | None; public `VITE_API_BASE_URL` is build-time. |
| [`docker-compose.yml`](../../docker-compose.yml) | `postgres:16` | No user configured. | PostgreSQL default command; no API, worker, frontend, or Nginx service. | Host `5433` to container `5432`. | Current uncommitted value: `../.env`. |

[`backend/.dockerignore`](../../backend/.dockerignore) and [`frontend/.dockerignore`](../../frontend/.dockerignore) constrain build context. No Nginx API load-balancer configuration or Compose services named `backend-1`, `backend-2`, or `backend-3` were found.

## 6. Environment-file loading and hardcoded paths

- [`backend/app/database.py`](../../backend/app/database.py) currently uses `Path(__file__).resolve().parents[3] / ".env"`.
- [`backend/app/core/security.py`](../../backend/app/core/security.py) currently uses `Path(__file__).resolve().parents[4] / ".env"`.
- [`docker-compose.yml`](../../docker-compose.yml) currently uses `../.env` from the repository root.
- [`backend/alembic/env.py`](../../backend/alembic/env.py) imports application database settings, not a separate environment file.

These paths are uncommitted working-tree changes. No hardcoded absolute path literal was found in current source; the Python expressions resolve paths from their source files. Environment contents were not inspected.

## 7. Alembic

The repository migration-graph head is `ce1c22c4205c`; the applied revision in the configured database is **unknown** because this audit did not connect to it.

| Revision | Parent | Migration |
| --- | --- | --- |
| `56b5051256ac` | none | [`create_initial_schema`](../../backend/alembic/versions/56b5051256ac_create_initial_schema.py): users, postings, submissions, constraints. |
| `ce1c22c4205c` | `56b5051256ac` | [`add_password_hash_to_users`](../../backend/alembic/versions/ce1c22c4205c_add_password_hash_to_users.py): non-null `users.password_hash`. |

## 8. Deployment artifacts and state

[`README.md`](../../README.md) and [`DEPLOYMENT.md`](../../DEPLOYMENT.md) describe three Cloud Run services, Cloud SQL, GCS, Pub/Sub, Artifact Registry, and IAM. These are repository claims. Independently verified current deployment state is **unknown**: this audit did not query Google Cloud or a live URL. [`.agent/CONTINUITY.md`](../../.agent/CONTINUITY.md) records prior manual/static verification and image-push history, but also includes older conflicting deployment/environment statements; it is historical context, not current cloud inventory.

## 9. Tests and scripts

No repository-owned automated test directory, test-runner configuration, CI workflow, or project script directory was found. [`frontend/package.json`](../../frontend/package.json) provides frontend development, build, and type-check scripts, not an automated test suite. Historical manual/static checks—including CRUD, GCS/Pub/Sub/worker, and container checks—are recorded in [`.agent/CONTINUITY.md`](../../.agent/CONTINUITY.md). This audit did not rerun them.

## DA3 prerequisite assessment

| Prerequisite | Status | Evidence |
| --- | --- | --- |
| Neon-ready database configuration | needs work | [`backend/app/database.py`](../../backend/app/database.py) passes one `DATABASE_URL` directly to `create_engine`; no repository configuration distinguishes pooled/direct URLs, enforces SSL, or limits pools for three instances. |
| Runs without GCP credentials | needs work | GCS/Pub/Sub operations require ADC and no local storage/queue fallback exists. |
| Dockerfile suitable for three backend instances | needs work | The backend Dockerfile can build an API image, but [`docker-compose.yml`](../../docker-compose.yml) only defines PostgreSQL; three named backends, Nginx, and distribution evidence are not found. |
| Health endpoint | ready | `GET /health` exists in [`backend/app/main.py`](../../backend/app/main.py). Runtime reachability was not tested. |
| Frontend present | ready | React/Vite routes and API clients exist under [`frontend/src/`](../../frontend/src/). Browser runtime was not tested. |
| MFA-ready authentication | needs work | Auth is password plus JWT only; no TOTP state, enrollment/verification, MFA token, rate-limit, or lockout code was found in auth/security/models. |
