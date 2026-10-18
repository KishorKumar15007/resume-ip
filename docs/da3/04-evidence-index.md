# DA3 Evidence Index

Status meanings: `needed` = not yet captured; `captured` = screenshot file is present; `verified` = screenshot and corresponding report description have been reviewed for accuracy and readability.

| File | Part | Must show | How to produce | Status |
| --- | --- | --- | --- | --- |
| `docs/da3/evidence/env-da1-url-reachable.png` | Environment / Section 0 | DA1 frontend landing page and browser address bar showing the active Cloud Run URL | Open `https://resume-ip-frontend-123719832707.asia-south1.run.app/` in the browser | captured |
| `docs/da3/evidence/env-da1-deployment-status.png` | Environment / Section 0 | Google Cloud Console → Cloud Run service list for `resume-ip-api`, `resume-ip-frontend` and `resume-ip-worker`, with region/status/access columns visible | GCP Console → project `resume-ip` → Cloud Run → Services | captured |
| `docs/da3/evidence/env-cloudsql-suspended.png` | Environment / Section 0 | Cloud SQL instance `resume-ip-db` and explicit warning that the free-trial instance is suspended | GCP Console → project `resume-ip` → Cloud SQL → Instances → `resume-ip-db` → Overview | captured |
| `docs/da3/evidence/env-db-dependent-login-error.png` | Environment / Section 0 | Login page and displayed generic message, “We could not sign you in. Please try again.”; no password or secret should be visible | Open the DA1 frontend `/login` page and capture the observed sign-in failure | captured |
| `docs/da3/evidence/env-neon-project.png` | Environment / Phase 1 | Neon project name, region, PostgreSQL version and branch list; connection strings obscured | After creating the Neon project, capture its overview page | needed |
| `docs/da3/evidence/env-alembic-head.png` | Environment / Phase 1 | Timestamp and output of `alembic upgrade head` and `alembic current`; hide database host/credentials | Run the migration commands from `backend/` against Neon | needed |
| `docs/da3/evidence/env-neon-tables.png` | Environment / Phase 1 | Neon table list including `users`, `job_postings`, `submissions` and `alembic_version` | Open the Neon tables view or SQL editor after migration | needed |
| `docs/da3/evidence/env-smoke-pass.png` | Environment / Phase 1 | Smoke-test PASS/FAIL table with all expected checks passing | Run `python docs/da3/scripts/smoke_api.py` after its creation and configuration | needed |
