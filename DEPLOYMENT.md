# Manual Google Cloud deployment

This guide prepares the existing containers for one manual deployment to project
`resume-ip` in `asia-south1`. It does not create, modify, or deploy Google Cloud
resources by itself. Do not commit or print secret values.

## Target services

| Cloud Run service | Image build target | Access |
| --- | --- | --- |
| `resume-ip-api` | `backend/Dockerfile` target `api` | Public browser API |
| `resume-ip-worker` | `backend/Dockerfile` target `worker` | Private, authenticated Pub/Sub push only |
| `resume-ip-frontend` | `frontend/Dockerfile` | Public static React application |

All containers listen on the Cloud Run-provided `PORT`. The backend and worker
use attached service identities and Application Default Credentials; do not set
`GOOGLE_APPLICATION_CREDENTIALS` or add key files.

## Preflight and image tags

Install and authenticate the Google Cloud CLI manually, then run these PowerShell
commands. The Artifact Registry repository could not be read-verified from this
workspace because `gcloud` is unavailable here. The first command is therefore a
required manual preflight; stop if it does not report an existing Docker repository.

```powershell
$ProjectId = "resume-ip"
$Region = "asia-south1"
$Repository = "resume-portal"
$Tag = "2026-09-13-r1"
$Registry = "$Region-docker.pkg.dev"

gcloud config set project $ProjectId
gcloud artifacts repositories describe $Repository --project $ProjectId --location $Region --format="yaml(name,format,location)"
gcloud auth configure-docker $Registry

$ApiImage = "$Registry/$ProjectId/$Repository/resume-ip-api:$Tag"
$WorkerImage = "$Registry/$ProjectId/$Repository/resume-ip-worker:$Tag"
$FrontendImage = "$Registry/$ProjectId/$Repository/resume-ip-frontend:$Tag"
```

The date-and-revision tag identifies this release; never reuse it for a later
image. Cloud Run resolves a deployed tag to an immutable digest for its revision.
Do not use `latest` as the only deployment reference.

Build and push the API and worker before the frontend. These commands do not use
or copy the ignored `.env` file.

```powershell
docker build --target api --tag $ApiImage backend
docker push $ApiImage

docker build --target worker --tag $WorkerImage backend
docker push $WorkerImage
```

## Service identities and IAM

Create or select these user-managed service accounts manually. Do not use
Owner, Editor, Storage Admin, or service-account JSON keys.

| Identity | Attached to | Required role and narrowest scope |
| --- | --- | --- |
| `resume-ip-api-sa@$ProjectId.iam.gserviceaccount.com` | `resume-ip-api` | `roles/cloudsql.client` on project; `roles/storage.objectUser` on `gs://resume-ip-uploads`; `roles/pubsub.publisher` on topic `resume-uploaded` |
| `resume-ip-worker-sa@$ProjectId.iam.gserviceaccount.com` | `resume-ip-worker` | `roles/cloudsql.client` on project; `roles/storage.objectViewer` on `gs://resume-ip-uploads` |
| `resume-ip-pubsub-push-sa@$ProjectId.iam.gserviceaccount.com` | Pub/Sub push identity | `roles/run.invoker` on only `resume-ip-worker` |
| `resume-ip-frontend-sa@$ProjectId.iam.gserviceaccount.com` | `resume-ip-frontend` | No application resource role; it makes no Google API calls |

The API writes and deletes its own private GCS objects, so `roles/storage.objectUser`
is sufficient at bucket scope. The worker only downloads PDFs, so it receives
viewer access only. Both application service accounts need Cloud SQL Client to
use the attached Unix socket. The API alone publishes to Pub/Sub.

Run the following IAM commands manually after replacing no values other than the
declared variables. They are intentionally scoped to the bucket, topic, service
account, or Cloud Run service where supported.

```powershell
$ApiServiceAccount = "resume-ip-api-sa@$ProjectId.iam.gserviceaccount.com"
$WorkerServiceAccount = "resume-ip-worker-sa@$ProjectId.iam.gserviceaccount.com"
$PushServiceAccount = "resume-ip-pubsub-push-sa@$ProjectId.iam.gserviceaccount.com"
$FrontendServiceAccount = "resume-ip-frontend-sa@$ProjectId.iam.gserviceaccount.com"
$ProjectNumber = (gcloud projects describe $ProjectId --format="value(projectNumber)")
$PubSubServiceAgent = "service-$ProjectNumber@gcp-sa-pubsub.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$ApiServiceAccount" --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding $ProjectId --member="serviceAccount:$WorkerServiceAccount" --role="roles/cloudsql.client"

gcloud storage buckets add-iam-policy-binding gs://resume-ip-uploads --member="serviceAccount:$ApiServiceAccount" --role="roles/storage.objectUser"
gcloud storage buckets add-iam-policy-binding gs://resume-ip-uploads --member="serviceAccount:$WorkerServiceAccount" --role="roles/storage.objectViewer"

gcloud pubsub topics add-iam-policy-binding resume-uploaded --project=$ProjectId --member="serviceAccount:$ApiServiceAccount" --role="roles/pubsub.publisher"
```

After the worker service exists, bind the push identity to that service only and
allow the Pub/Sub service agent to mint its OIDC token. The deployer also needs
`roles/iam.serviceAccountUser` on each service identity it attaches; the person
modifying the subscription needs `iam.serviceAccounts.actAs` on the push identity.

```powershell
gcloud run services add-iam-policy-binding resume-ip-worker --project=$ProjectId --region=$Region --member="serviceAccount:$PushServiceAccount" --role="roles/run.invoker"
gcloud iam service-accounts add-iam-policy-binding $PushServiceAccount --member="serviceAccount:$PubSubServiceAgent" --role="roles/iam.serviceAccountTokenCreator"
```

If the Cloud Run deployment cannot pull an Artifact Registry image, inspect the
Cloud Run service agent's access and grant `roles/artifactregistry.reader` on
only the `resume-portal` repository. Do not grant Artifact Registry Writer to
runtime service accounts; the manual image publisher needs Writer only while
pushing images.

## Environment configuration

The application needs these values. `DATABASE_URL` includes the database password
and is a secret. `JWT_SECRET_KEY` is a secret. Enter them manually in the Cloud
Run Variables & Secrets UI or provide them from a protected current shell; never
put their values in a repository file, command history, screenshot, or chat.

| Service | Secret variables | Non-secret variables |
| --- | --- | --- |
| API | `DATABASE_URL`, `JWT_SECRET_KEY` | `GCS_BUCKET_NAME=resume-ip-uploads`, `GCP_PROJECT_ID=resume-ip`, `PUBSUB_RESUME_UPLOADED_TOPIC=resume-uploaded`, `JWT_ALGORITHM=HS256`, `ACCESS_TOKEN_EXPIRE_MINUTES=60`, `CORS_ALLOWED_ORIGINS=<actual frontend HTTPS URL>` |
| Worker | `DATABASE_URL` | `GCS_BUCKET_NAME=resume-ip-uploads`, `GCP_PROJECT_ID=resume-ip`, `PUBSUB_RESUME_UPLOADED_TOPIC=resume-uploaded` |
| Frontend | none | none at runtime; `VITE_API_BASE_URL` is a public image-build argument |

For both API and worker, construct the Cloud SQL Unix-socket URL with the real
database password URL-encoded:

```text
postgresql+psycopg2://resume_app:<URL-ENCODED-DB-PASSWORD>@/resume-portal?host=/cloudsql/resume-ip:asia-south1:resume-ip-db
```

Do not configure a TCP host, local PostgreSQL port, Cloud SQL public exposure, or
`GOOGLE_APPLICATION_CREDENTIALS`. Cloud Run's Cloud SQL attachment exposes the
socket at `/cloudsql/resume-ip:asia-south1:resume-ip-db` and ADC supplies Google
API credentials.

## Deploy API, then worker

Prepare the two secret-bearing current-shell variables by a secure manual method
before running these commands. The commands refer only to variable names; do not
replace them with literal secret values in this guide.

```powershell
gcloud run deploy resume-ip-api `
  --project=$ProjectId `
  --region=$Region `
  --image=$ApiImage `
  --service-account=$ApiServiceAccount `
  --add-cloudsql-instances="resume-ip:asia-south1:resume-ip-db" `
  --allow-unauthenticated `
  --ingress=all `
  --min=0 `
  --max=3 `
  --concurrency=20 `
  --cpu=1 `
  --memory=512Mi `
  --timeout=60 `
  --set-env-vars="DATABASE_URL=$env:DATABASE_URL,JWT_SECRET_KEY=$env:JWT_SECRET_KEY,GCS_BUCKET_NAME=resume-ip-uploads,GCP_PROJECT_ID=resume-ip,PUBSUB_RESUME_UPLOADED_TOPIC=resume-uploaded,JWT_ALGORITHM=HS256,ACCESS_TOKEN_EXPIRE_MINUTES=60"

$ApiUrl = (gcloud run services describe resume-ip-api --project=$ProjectId --region=$Region --format="value(status.url)")
Invoke-WebRequest "$ApiUrl/health" -UseBasicParsing
```

Deploy the worker after its Cloud SQL and GCS IAM bindings are present. It remains
private: do not add `allUsers`, do not use `--allow-unauthenticated`, and do not
run a pull subscriber. Internal ingress accepts the same-project Pub/Sub
subscription while Cloud Run IAM requires the OIDC push identity.

```powershell
gcloud run deploy resume-ip-worker `
  --project=$ProjectId `
  --region=$Region `
  --image=$WorkerImage `
  --service-account=$WorkerServiceAccount `
  --add-cloudsql-instances="resume-ip:asia-south1:resume-ip-db" `
  --no-allow-unauthenticated `
  --ingress=internal `
  --min=0 `
  --max=2 `
  --concurrency=4 `
  --cpu=1 `
  --memory=1Gi `
  --timeout=300 `
  --set-env-vars="DATABASE_URL=$env:DATABASE_URL,GCS_BUCKET_NAME=resume-ip-uploads,GCP_PROJECT_ID=resume-ip,PUBSUB_RESUME_UPLOADED_TOPIC=resume-uploaded"

$WorkerUrl = (gcloud run services describe resume-ip-worker --project=$ProjectId --region=$Region --format="value(status.url)")
```

Then run the two IAM bindings from the preceding section and configure the
existing subscription. Do not create a topic, subscription, or pull consumer.
Keep the default Pub/Sub message wrapper because `app.worker` expects the base64
push envelope.

```powershell
gcloud pubsub subscriptions modify-push-config resume-worker-sub `
  --project=$ProjectId `
  --push-endpoint="$WorkerUrl/internal/pubsub/resume-uploaded" `
  --push-auth-service-account=$PushServiceAccount `
  --push-auth-token-audience=$WorkerUrl
```

## Build and deploy frontend

`VITE_API_BASE_URL` is compiled into the browser bundle and is public. Build only
after retrieving the real API URL; never invent or commit a Cloud Run URL.

```powershell
docker build --build-arg "VITE_API_BASE_URL=$ApiUrl" --tag $FrontendImage frontend
docker push $FrontendImage

gcloud run deploy resume-ip-frontend `
  --project=$ProjectId `
  --region=$Region `
  --image=$FrontendImage `
  --service-account=$FrontendServiceAccount `
  --allow-unauthenticated `
  --ingress=all `
  --min=0 `
  --max=2 `
  --concurrency=80 `
  --cpu=1 `
  --memory=256Mi `
  --timeout=60

$FrontendUrl = (gcloud run services describe resume-ip-frontend --project=$ProjectId --region=$Region --format="value(status.url)")
```

The frontend and API are separate origins. After obtaining `$FrontendUrl`, add
only that exact HTTPS origin to the API and create a new API revision. The API
refuses wildcard, path, query, fragment, and credential-bearing origins.

```powershell
gcloud run services update resume-ip-api `
  --project=$ProjectId `
  --region=$Region `
  --update-env-vars="CORS_ALLOWED_ORIGINS=$FrontendUrl"
```

The Nginx production image preserves React Router deep links with `try_files`.

## Required execution order

1. Verify the existing Artifact Registry repository.
2. Build and push the API image.
3. Deploy `resume-ip-api`.
4. Retrieve its URL and verify `/health`.
5. Apply the API service identity's Cloud SQL, bucket, and topic IAM bindings before testing database, storage, or upload routes.
6. Build and push the worker image.
7. Deploy private `resume-ip-worker`.
8. Grant only the Pub/Sub push identity Cloud Run Invoker on the worker and grant the Pub/Sub service agent token-creation access on that identity.
9. Modify the existing `resume-worker-sub` push configuration for the worker endpoint and OIDC identity.
10. Build/push the frontend image with the actual API URL, then deploy `resume-ip-frontend`.
11. Add the actual frontend HTTPS URL to the API's explicit CORS configuration.
12. Perform the end-to-end verification and then apply or confirm cost guardrails and billing alerts.

## Cost guardrails and manual verification

The commands set request-based, scale-to-zero services (`--min=0`) with service
maximums of API `3`, worker `2`, and frontend `2`. The selected concurrencies are
API `20`, worker `4`, and frontend `80`; the worker's atomic queued-state claim
makes limited parallel processing safe, so concurrency `1` is unnecessary. These
limits are cost safeguards, not DDoS protection, and Cloud Run can briefly exceed
a maximum during spikes.

In Cloud Billing, create a project-scoped monthly budget with alerts at 50%, 80%,
and 100%. If the Billing UI offers the eligible Cloud Run spend-cap budget option,
review its pause behavior before enabling it: it can stop new eligible usage but
does not stop fixed persistent-resource charges. An alerts-only budget does not
cap spending.

Verify manually after deployment:

1. Confirm Artifact Registry reports the Docker repository and all three tagged images.
2. Confirm API `/health` returns `200` and the API service is public.
3. Confirm API and worker revisions list the Cloud SQL instance attachment and use their distinct service identities.
4. Confirm the bucket remains private; API has Object User, worker has Object Viewer, and neither has Storage Admin.
5. Confirm the worker has no `allUsers` invoker binding; only the push identity has `roles/run.invoker`.
6. From the frontend origin, sign up, sign in, browse postings, and confirm browser preflight/API calls succeed only from the configured CORS origin.
7. Upload a valid PDF as a candidate. Confirm `202`, one private GCS object, a `resume-uploaded` event, authenticated subscription delivery, worker `204`, and persisted `DONE` score/matched skills.
8. Confirm duplicate submission returns `409`, invalid PDF returns `422`, recruiter upload returns `403`, and duplicate delivery does not overwrite a `DONE` result.
9. Open a React Router deep link directly and confirm the frontend serves it.
10. Confirm all service minimums are zero, maximums/concurrencies match this guide, Cloud Run is request-based, and the Billing budget is active.

## Deferred and unresolved

No Cloud Run service, service account, IAM binding, Artifact Registry push,
subscription change, Cloud SQL setting, bucket policy, or billing configuration
was performed from this repository. Artifact Registry existence is unconfirmed
until the manual preflight command succeeds. Actual deployed URLs, real secret
values, service-account creation, deployment permissions, and end-to-end cloud
verification remain manual Prompt 18 work.

## Sources

- [Cloud Run maximum instances](https://cloud.google.com/run/docs/configuring/max-instances)
- [Cloud SQL PostgreSQL from Cloud Run](https://cloud.google.com/sql/docs/postgres/connect-run)
- [Pub/Sub authenticated push subscriptions](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions)
- [Artifact Registry Docker authentication](https://cloud.google.com/artifact-registry/docs/docker/authentication)
- [Cloud Run environment variables](https://cloud.google.com/run/docs/configuring/services/environment-variables)
- [Cloud Billing budgets and spend caps](https://cloud.google.com/billing/docs/how-to/budgets)
