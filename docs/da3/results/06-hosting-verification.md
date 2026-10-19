# DA3 Step 6 Hosting Verification

## Recorded outcome

| Item | Recorded result | Source / verification boundary |
| --- | --- | --- |
| Selected option | Option A: the existing Cloud Run deployment was retained. | Owner-confirmed. |
| Target database | Neon `production` migration head is `ce1c22c4205c`. | Owner-confirmed; `evidence/env-neon-production-migration-head.png` visibly shows `alembic current` at that head but does not itself display the branch name. |
| API database binding | `DATABASE_URL` references Secret Manager secret `resume-ip-neon-production-database-url`, numeric version `1`. | `evidence/env-cloudrun-service.png`. No connection URL or secret value was recorded. |
| API identity access | `resume-ip-api-sa@resume-ip.iam.gserviceaccount.com` has `roles/secretmanager.secretAccessor` on the database secret. | Owner-confirmed. |
| API revision | Created and ready revision: `resume-ip-api-00007-676`; Cloud Run reported the API service, configuration, and routes Ready. | `evidence/env-cloudrun-service.png`. |
| Database-backed CRUD | Synthetic database-backed CRUD flow worked. | Owner-confirmed. Individual HTTP status codes and detailed output were not provided and are not inferred here. |
| Services changed | Only `resume-ip-api` was changed. The frontend and worker were left unchanged. | Owner-confirmed. |

## Evidence checked

- `evidence/env-cloudrun-api-before.png` exists and shows the prior API revision,
  100-percent traffic allocation, service identity, environment-variable names,
  and no ordinary environment-variable values.
- `evidence/env-neon-production-migration-head.png` exists and shows timestamped
  `alembic current` output at `ce1c22c4205c (head)`.
- `evidence/env-cloudrun-service.png` exists and shows API readiness, revision
  `resume-ip-api-00007-676`, and the secret-reference metadata with numeric
  version `1`.
- `evidence/env-deployed-url-works.png` exists and shows the deployed frontend
  sign-in page. It does not provide individual CRUD request output.

## Scope limits

This Step 6 record does not establish end-to-end Google Cloud Storage upload,
Pub/Sub delivery, worker scoring, or worker database connectivity. It does not
replace the preserved Step 4 local 19/19 smoke-test results.
