# DA3 Step 14 — Components, ports, tools, and locations

This table is a design/reference artifact assembled from repository configuration, retained results, and owner-provided DA1 context. `Unknown` and `not verified` deliberately replace values that are not established by the repository.

| Component | Image/service/tool | Host port | Container port | Role | Where it runs | Status / notes |
| --- | --- | --- | --- | --- | --- | --- |
| React frontend | `frontend/Dockerfile`; Cloud Run service `resume-ip-frontend` | not applicable | Cloud Run platform port not verified | Browser interface | DA1 Google Cloud Run | Existing; deployed API base URL not inspected. |
| FastAPI API | `backend/Dockerfile` target `api`; Cloud Run service `resume-ip-api` | not applicable | Cloud Run platform port not verified | JWT/RBAC, postings, uploads, API | DA1 Google Cloud Run | Existing; deployed Neon branch unknown. |
| Resume-processing worker | `backend/Dockerfile` target `worker`; Cloud Run service `resume-ip-worker` | not applicable | Cloud Run platform port not verified | PDF extraction, required-skill matching, scoring | DA1 Google Cloud Run | Existing service; DA3 experiments did not test worker processing. |
| Cloud Storage | Google Cloud Storage | not applicable | not applicable | Private resume PDF objects | Google Cloud managed service | Existing DA1 architecture; API upload and worker download paths. |
| Pub/Sub | topic `resume.uploaded` | not applicable | not applicable | API publishes the event after a successful upload; decouples upload from scoring | Google Cloud managed service | Existing DA1 architecture; authenticated push delivery to the worker is separate. Event delivery/worker scoring were not exercised by DA3 experiments. |
| Neon PostgreSQL | pooled application endpoint | not applicable | not applicable | Structured data: users, postings, submissions | AWS Singapore managed database | DA1 Cloud SQL was suspended and migrated to Neon; endpoint host masked. Deployed API branch unknown. |
| IAM / scoped service accounts | Google Cloud IAM | not applicable | not applicable | Least-privilege cloud-resource access | Google Cloud | Distinct from application JWT/RBAC. |
| Cloud Logging | Google Cloud Logging | not applicable | not applicable | DA1 observability | Google Cloud | Existing DA1 architecture. |
| Apache Bench | `Dockerfile.loadtest` / `ab` | client targets `8080` | not applicable | DA3 HTTP load generation | DA3 local test tooling | Direct Nginx client; not a frontend test. |
| Availability probe | `docs/da3/scripts/availability_probe.py` | client targets `8080` | not applicable | DA3 Nginx health sampling | DA3 local test tooling | Direct Nginx client; separate from Apache Bench request count. |
| Docker Compose | `compose.da3.yml` | not applicable | not applicable | Manages local DA3 stack | Local machine | Existing DA3 experiment topology; no frontend service. |
| Nginx | `nginx:stable-alpine` | `8080` | `80` | Local reverse proxy/load balancer | DA3 Docker Compose | Existing; shared upstream zone. Current config has no `max_conns` or backup peer. |
| backend-1 | `backend/Dockerfile` target `api`; FastAPI/Uvicorn | `8001` | `8000` | Local primary API instance | DA3 Docker Compose | Existing; one Uvicorn worker; configured 0.5 CPU / 512 MiB. |
| backend-2 | `backend/Dockerfile` target `api`; FastAPI/Uvicorn | `8002` | `8000` | Local primary API instance | DA3 Docker Compose | Existing; one Uvicorn worker; configured 0.5 CPU / 512 MiB. |
| backend-3 | `backend/Dockerfile` target `api`; FastAPI/Uvicorn | `8003` | `8000` | Local primary API instance | DA3 Docker Compose | Existing; one Uvicorn worker; configured 0.5 CPU / 512 MiB. |
| DA3 Neon dependency | pooled application endpoint | not applicable | not applicable | Shared external database for local API experiment | AWS Singapore managed database | DA3 load-test branch `da3-loadtest`; host masked; connection budget not verified. |
| Alembic | `backend/alembic` | not applicable | not applicable | Database migrations | Owner-controlled backend tooling | Migration tool, not a request-path service. |
| Proposed Cloud Run burst API | same stateless FastAPI backend image | not verified | Cloud Run platform port not verified | Intended backup-upstream overflow capacity | Proposed Google Cloud Run | **Proposed, not built**. Maximum 6 instances is an initial design cap; URL, `max_conns`, HTTPS/SNI/Host, ingress, and Neon budget are unspecified/unverified. |
