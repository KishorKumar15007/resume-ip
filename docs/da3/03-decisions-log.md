# DA3 Decisions Log

| date | step | decision | reason | alternatives rejected |
| --- | --- | --- | --- | --- |
| 2026-10-18 | 0.2 | Use the `assignment-3` branch and small reviewable patches. | DA3 plan branch and scope default. | Direct work on `main`. |
| 2026-10-18 | 0.2 | Keep configuration in gitignored repo-local `.env` files with placeholder `.env.example` files; never commit secrets. | DA3 plan security default. | Committing secrets or hardcoding configuration. |
| 2026-10-18 | 0.2 | Plan first and require approval for schema or authentication changes. | Those changes have high compatibility and security risk. | Unplanned schema/auth changes. |
| 2026-10-18 | 0.2 | Use Neon with pooled app and direct Alembic URLs, required SSL, pre-ping/recycle, and small pools when the database migration step is approved. | The plan targets Neon and three backend instances. | Reusing the existing configuration unchanged without assessing Neon limits. |
| 2026-10-18 | 0.2 | Use placement-drive morning as the proposed scale scenario and `GET /postings` as the proposed hardest-hit endpoint; confirm after calibration. | The plan describes read-heavy candidate refreshes. | Declaring the target final before calibration. |
| 2026-10-18 | 0.2 | Use three explicit Compose backend services and Nginx; keep one Uvicorn worker per backend. | Required for DA3 distribution and comparable load tests. | A single backend, implicit replicas, or changing Uvicorn worker count between tests. |
| 2026-10-18 | 0.2 | Keep Nginx in both one- and three-instance comparisons and use a deterministic no-retry failure baseline before passive failover. | Preserves a comparable proxy hop and a reproducible before/after test. | Changing multiple topology variables or using graceful stop as the failure trigger. |
| 2026-10-18 | 0.2 | Treat cloud bursting as a diagram/explanation component, not an implementation. | The plan explicitly limits it to a conceptual overflow path. | Building Kubernetes or cloud-burst infrastructure. |
| 2026-10-18 | 0.2 | Retain Argon2id and implement TOTP with encrypted-at-rest secret, MFA-pending token rejection, rate limiting, and recruiter enrolment when approved. | DA3 security plan default. | Plain passwords, unencrypted TOTP secrets, or bypassable MFA. |
| 2026-10-18 | 0.2 | Use identical Trivy severity flags for baseline and hardened scans; retain raw output and generate comparison tables by script. | Ensures evidence is comparable and not hand-typed. | Different scan criteria or manually entered counts. |
| 2026-10-18 | 0.2 | Frame the two specified threat agents against GDPR requirements with an honest India/DPDP applicability note. | The assignment requests HIPAA/GDPR while the plan records the domain context. | Claiming GDPR is the sole domestic law without qualification. |
| 2026-10-18 | 0.2 | Record the current environment-path discrepancy without changing runtime configuration in this documentation step. | Audit documents uncommitted path changes while this task prohibits environment changes. | Altering application or environment configuration during documentation setup. |
