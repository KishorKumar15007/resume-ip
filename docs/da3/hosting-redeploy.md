# DA3 Step 6 — Cloud Run to Neon production runbook

**Owner-run procedure.** This runbook changes configuration on the existing Cloud
Run services only. It does not create a replacement service, rebuild an image, or
change the frontend URL. Run commands one section at a time and stop at every
stated stop condition.

## Scope and safety boundary

- The rollout target is the existing `resume-ip-api` service in `resume-ip` /
  `asia-south1`.
- `resume-ip-worker` remains unchanged. Step 5 was deliberately skipped by
  assignment scope, so DA3 does not verify upload, Pub/Sub delivery, or scoring.
  `resume-ip-frontend` also remains unchanged; it has no database setting for
  this switch.
- The target database is Neon branch `production`. `da3-loadtest` is not part of
  this hosting reconciliation.
- `DATABASE_URL` is the pooled Neon application URL. It must be a
  `postgresql+psycopg2` URL with `sslmode=require`.
- `MIGRATION_DATABASE_URL` is a direct Neon URL for Alembic only. Do not place it
  in Cloud Run.
- Never paste a connection URL, password, token, or environment-file content into
  PowerShell, this repository, a screenshot, or chat. In particular, do not read
  `C:\Github\Repos\.env`.
- Do not use `latest` for the Cloud Run secret reference. Pin an enabled numeric
  Secret Manager version.

The configuration design is implemented in
`backend/app/database.py`: runtime processes read `DATABASE_URL` using synchronous
SQLAlchemy/psycopg2 with `pool_pre_ping=True`, `pool_recycle=300`,
`DB_POOL_SIZE=5`, and `DB_MAX_OVERFLOW=5`. `backend/alembic/env.py` rejects a
non-local migration unless `MIGRATION_DATABASE_URL` is present, so migrations use
the direct URL rather than the pooled runtime URL.

## 1. Set safe identifiers and record the current state

Open a PowerShell session authenticated to the intended Google Cloud project.
The following commands print only Cloud Run metadata, service identities,
revision names, traffic allocations, environment-variable names, and secret
reference metadata. They do **not** print ordinary environment-variable values.

```powershell
$ProjectId = "resume-ip"
$Region = "asia-south1"
$ApiService = "resume-ip-api"
$DatabaseSecret = "resume-ip-neon-production-database-url"

$ApiUrl = gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="value(status.url)"

$ApiServiceAccount = gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="value(spec.template.spec.serviceAccountName)"

$PriorApiRevision = gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="value(status.latestReadyRevisionName)"

$PriorApiTraffic = @(gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="json(status.traffic)" | ConvertFrom-Json)

if ([string]::IsNullOrWhiteSpace($ApiServiceAccount) -or
    [string]::IsNullOrWhiteSpace($PriorApiRevision) -or
    $PriorApiTraffic.Count -eq 0) {
  throw "Stop: a required existing service identity, ready revision, or traffic allocation was not established."
}

[pscustomobject]@{
  service = $ApiService
  url = $ApiUrl
  serviceAccount = $ApiServiceAccount
  latestReadyRevision = $PriorApiRevision
  traffic = $PriorApiTraffic
} | ConvertTo-Json -Depth 5

```

Only the explicitly projected URLs, identities, revision names, and traffic
metadata are held in PowerShell memory. Do **not** retrieve, print, save, or
share a full Cloud Run service description: it can include ordinary
environment-variable values.

Use this metadata-only inspection to determine how `DATABASE_URL` is currently
bound. It projects the variable name and secret reference fields only; a blank
secret name/version for `DATABASE_URL` means it is ordinary or absent, not that
its value should be inspected.

```powershell
gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="table(spec.template.spec.containers[0].env.name,spec.template.spec.containers[0].env.valueFrom.secretKeyRef.name,spec.template.spec.containers[0].env.valueFrom.secretKeyRef.key)"

```

Capture the displayed original revisions and traffic allocations privately before
continuing. Do not assume either service has one revision at 100 percent.

## 2. Confirm the Neon production migration precondition

In a separate owner-controlled session, make the direct Neon **production** URL
available privately as `MIGRATION_DATABASE_URL`. Do not echo it or use it in a
command line. From the repository root, run:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m alembic current
```

Proceed only if the output identifies `ce1c22c4205c (head)`. If it does not,
stop. Determine whether Neon `production` needs the existing migration graph
applied; only after that decision, and only against `production`, run:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

Do not migrate `da3-loadtest` in this procedure. There is no new migration to
create: `ce1c22c4205c` is the repository migration head.

## 3. Create or reuse a Secret Manager secret and pin a numeric version

First check whether the selected secret exists. This returns metadata only:

```powershell
gcloud secrets describe $DatabaseSecret --project=$ProjectId
```

If it is absent, create the secret container:

```powershell
gcloud secrets create $DatabaseSecret `
  --project=$ProjectId `
  --replication-policy=automatic
```

In the Google Cloud Console, add a version privately using the pooled Neon
**production** URL. Do not use a terminal command that accepts the URL, and do
not add the direct Alembic URL. Then list only version metadata and select one
enabled numeric version:

```powershell
gcloud secrets versions list $DatabaseSecret `
  --project=$ProjectId `
  --filter="state=ENABLED" `
  --format="table(name,state,createTime)"

$DatabaseSecretVersion = "<enabled-numeric-version>"
if ($DatabaseSecretVersion -notmatch '^[1-9][0-9]*$') {
  throw "Stop: DATABASE_URL must reference one enabled numeric Secret Manager version, never latest."
}
```

Reuse an existing secret only after confirming it contains the intended pooled
Neon **production** URL through an owner-controlled secret-management workflow.
Never inspect or print its value in this procedure.

## 4. Grant access to the discovered API identity

Use the API service-account value discovered in section 1. Do not substitute an
assumed name. If the Cloud Run service identity is unknown, disabled, or the
deployer cannot grant this secret-scoped role, stop for an owner/IAM decision.

```powershell
gcloud secrets add-iam-policy-binding $DatabaseSecret `
  --project=$ProjectId `
  --member="serviceAccount:$ApiServiceAccount" `
  --role="roles/secretmanager.secretAccessor"

```

This is the least-privilege role for this one database secret. Do not alter the
existing service identities, Cloud SQL attachment, GCS, Pub/Sub, ingress, or
frontend configuration during this database switch.

## 5. API-first replacement of `DATABASE_URL`

Update the API first. The command creates a new revision from the existing service
configuration and image; it does not build an image or create a service.

If the metadata-only inspection in section 1 showed `DATABASE_URL` as an existing
secret binding, run:

```powershell
gcloud run services update $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --update-secrets="DATABASE_URL=$DatabaseSecret`:$DatabaseSecretVersion"
```

If `DATABASE_URL` was ordinary (or absent), use the Cloud Run Console for this
one replacement: edit the existing API service, remove the ordinary
`DATABASE_URL` entry if present, add `DATABASE_URL` as a Secret Manager reference
to `$DatabaseSecret` and the selected numeric version, review the configuration
diff, and deploy the change. This avoids ever reading the ordinary value and
avoids an intermediate revision without a database setting. Stop if the console
cannot show an unambiguous replacement diff.

After either path, inspect only the safe metadata:

```powershell
$ApiAfterRevision = gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="value(status.latestReadyRevisionName)"

gcloud run services describe $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --format="table(spec.template.spec.containers[0].env.name,spec.template.spec.containers[0].env.valueFrom.secretKeyRef.name,spec.template.spec.containers[0].env.valueFrom.secretKeyRef.key)"

if ($ApiAfterRevision -eq $PriorApiRevision) {
  throw "Stop: the API did not produce a new Ready revision."
}
```

The expected result is exactly one `DATABASE_URL` metadata row referencing the
chosen secret and numeric version. If it is absent, remains ordinary, references
`latest`, or the revision is not Ready, stop and use the rollback section.

## 6. Verify the API

`GET /health` proves only process liveness because `backend/app/main.py` returns
a static health response; it does not query PostgreSQL.

```powershell
Invoke-WebRequest "$ApiUrl/health" -UseBasicParsing
```

Expected: HTTP 200 with the health response. Then perform a controlled
database-backed check through the API. Use a syntactically valid synthetic email
and a deliberately incorrect password in a private client or Swagger at
`$ApiUrl/docs`; do not print a token or password. `POST /auth/login` should return
the controlled authentication response (HTTP 401), not a database-related HTTP
500. Stop and roll back on a 5xx response, timeout, TLS error, or unexpected
database error.

Next, perform the synthetic CRUD/RBAC sequence manually against `$ApiUrl`:

1. Register a synthetic recruiter and a synthetic candidate; log both in without
   recording their tokens.
2. As recruiter, create and read a posting (expected 201 then 200).
3. As candidate, read that posting (200); candidate create, update, and delete
   attempts must each return 403.
4. As recruiter, update then delete the posting (200 then 204).
5. Read the deleted posting (404).

Do **not** run `docs/da3/scripts/smoke_api.py` unchanged against Cloud Run: it
writes `docs/da3/results/04-smoke.md` and `04-smoke.json` and would overwrite the
preserved Step 4 local record. Do not test uploads in this runbook.

Do not update or verify `resume-ip-worker` as part of this runbook. The DA3
experiments do not exercise uploads, Pub/Sub delivery, or scoring, and this
procedure does not establish that those paths work.

## 7. Rollback without assuming 100 percent traffic

Build a traffic specification from the allocations recorded in section 1. It
restores the prior distribution rather than assuming a single 100-percent
revision. Run the relevant command only after verifying that every prior entry
has a revision name and percentage.

```powershell
$ApiRollbackTraffic = ($PriorApiTraffic | ForEach-Object {
  if ([string]::IsNullOrWhiteSpace($_.revisionName) -or $null -eq $_.percent) {
    throw "Stop: the recorded API traffic allocation is incomplete."
  }
  "$($_.revisionName)=$($_.percent)"
}) -join ","

gcloud run services update-traffic $ApiService `
  --project=$ProjectId `
  --region=$Region `
  --to-revisions=$ApiRollbackTraffic
```

Rollback restores the recorded traffic allocation, but the prior revision points
at suspended Cloud SQL and is therefore not expected to restore SQL-backed
functionality. Do not delete the Secret Manager secret, delete a revision, remove
Cloud SQL attachments, or change any IAM outside this secret-scoped access while
rolling back.

## 8. Evidence and reporting handoff

Capture only sanitized evidence; do not overwrite the existing Step 1 or Step 4
captures:

- `docs/da3/evidence/env-cloudrun-api-before.png`: current API revision, traffic
  allocation, and `DATABASE_URL` variable-name/secret-reference metadata before
  this change, with all ordinary values hidden.
- `docs/da3/evidence/env-neon-production-migration-head.png`: the direct Neon
  `production` migration check showing `ce1c22c4205c (head)`, distinct from the
  existing `env-alembic-head.png`.

- `docs/da3/evidence/env-cloudrun-service.png`: API service/revision after the
  change, with `DATABASE_URL` visible only as a Secret Manager reference and
  secret values hidden.
- `docs/da3/evidence/env-deployed-url-works.png`: deployed URL and successful
  non-secret verification result.

The current DA3 playbook also retains `env-hosting-status.png` as the alternative
Option B artifact; do not create it for this Option A run unless the actual state
requires the alternative path. A later DOCS UPDATE prompt must record results in
the report, checklist, decisions log, and evidence index. It must not claim that
this procedure tested end-to-end GCS upload, Pub/Sub delivery, or worker scoring;
it does not.

## Acceptance and stop conditions

Acceptance requires all of the following:

- Neon `production` is confirmed at `ce1c22c4205c (head)` before the service
  change.
- The API uses its actual discovered identity and receives only
  `roles/secretmanager.secretAccessor` on the selected database secret.
- The API first references a selected enabled numeric secret version, starts a
  new Ready revision, passes liveness, the database-backed controlled login, and
  the manual synthetic CRUD/RBAC sequence.
- The existing worker, frontend URL, services, images, and service identities
  remain unchanged.

Stop before or during rollout if the target migration state is unknown, the
service identity cannot be established, a secret reference cannot be verified
without exposing a value, Secret Manager access fails, Cloud Run cannot reach
Neon, a new revision is not Ready, or a database-backed API action returns 5xx.
The known remaining risk is Neon connection capacity: configured per-process pool
limits do not prove that Cloud Run API scaling fits the Neon plan.
