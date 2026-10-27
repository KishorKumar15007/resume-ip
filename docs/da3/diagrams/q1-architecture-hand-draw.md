# Q1(d) hand-draw guide — same facts as `q1-architecture.svg`

Use A4 **landscape**. Draw the existing architecture with a black pen. Draw the proposed burst extension in orange with a dashed outline; it must visibly say **“Proposed, not built”**. This guide simplifies presentation only: it must not add, remove, or change a relationship from the detailed SVG.

## Layout and principal boxes

Reserve the top half for DA1, the lower-left half for the DA3 local experiment, and a lower-right orange dashed panel for the proposal. Leave a narrow strip along the bottom for the tools and legend.

| # | Position | Exact label / contents | Ports / status |
| ---: | --- | --- | --- |
| 1 | Top left | **Candidate / Recruiter — browser** | JWT application session |
| 2 | Upper left-centre | **React frontend — Cloud Run**; static Vite bundle | Cloud Run platform port; live `VITE_API_BASE_URL` unknown |
| 3 | Upper centre | **FastAPI API — Cloud Run (`resume-ip-api`)**; JWT/RBAC, postings and uploads | platform port not verified; deployed Neon branch UNKNOWN |
| 4 | Upper right-centre | **Neon PostgreSQL — AWS Singapore**; pooled endpoint, host masked | DA1 deployed branch UNKNOWN |
| 5 | Upper right | **Cloud Storage**; private resume PDFs | managed service; no container port |
| 6 | Mid-right | **Pub/Sub — `resume.uploaded`** | managed service; no container port |
| 7 | Far right | **Resume worker — Cloud Run (`resume-ip-worker`)**; extract → match → score | platform port not verified |
| 8 | Lower left | **Apache Bench + availability probe** | direct test tools to `http://localhost:8080`; no React frontend here |
| 9 | Lower centre-left | **Nginx — Docker Compose** | host `8080` → container `80`; shared upstream zone; current config has no `max_conns` or backup peer |
| 10 | Lower centre | **backend-1 — FastAPI/Uvicorn** | host `8001` → container `8000`; one worker |
| 11 | Lower centre | **backend-2 — FastAPI/Uvicorn** | host `8002` → container `8000`; one worker |
| 12 | Lower centre | **backend-3 — FastAPI/Uvicorn** | host `8003` → container `8000`; one worker |

Draw a shared black Neon database symbol beside boxes 10–12 rather than counting it as another principal local box. Label it **“Neon PostgreSQL — AWS Singapore — pooled endpoint — DA3 load-test branch `da3-loadtest`; host masked”**. Draw a small tool strip: **Docker Compose**, **Alembic (migration tool, not request path)**, **IAM + scoped service accounts**, and **Cloud Logging**.

## Exact arrows

### Existing black arrows

1. Browser → React frontend: `HTTPS`.
2. React frontend → FastAPI API: `HTTPS / API — configured live target unknown`.
3. FastAPI API → Neon: `SQLAlchemy → pooled DB`.
4. FastAPI API → Cloud Storage: `PDF upload / object metadata`.
5. FastAPI API → Pub/Sub: `API publishes resume.uploaded after successful upload`.
6. Pub/Sub → worker: `authenticated push delivery`.
7. Worker → Cloud Storage: `download PDF`.
8. Worker → Neon: `persist QUEUED/PROCESSING/DONE/FAILED, score, matched skills`.
9. Apache Bench → Nginx: `GET /postings through http://localhost:8080`.
10. Availability probe → Nginx: `GET /health through http://localhost:8080`.
11. Nginx → each backend: `HTTP/1.1 upstream; container :8000`.
12. Each backend → shared DA3 Neon symbol: `pooled DB connection`.

Do **not** connect the React frontend to the DA3 Nginx box. Do not draw the DA3 Apache Bench path as a Cloud Run path.

### Orange dashed proposal arrows

13. From Nginx to the orange panel: `intended overflow after all local primary max_conns limits; compatible configuration and isolated hand-off test pending`.
14. Orange **Proposed Cloud Run burst API service** → shared DA3 Neon symbol: `intended shared pooled endpoint`.

The orange panel must state: **same stateless FastAPI image; maximum 6 burst instances proposed; URL, max_conns value, HTTPS/SNI/Host, ingress authorization and Neon connection budget not verified.**

## Required annotations

- Under the DA1 top region, write exactly: **Cloud SQL (DA1) suspended, migrated to Neon**.
- Near the DA3 test region: `Step 11 measured median: 24.88 requests/s with three backends; local Compose result, not Cloud Run performance.`
- In the orange panel:
  - `40,000 reads / 600 s = 66.67 ≈ 67 assumed read requests/s`
  - `44,000 total HTTP requests / 600 s = 73.33 total requests/s`
  - `24.88 / 3 = 8.2933 ≈ 8.3 illustrative requests/s per backend`
  - `ceil(67 / (24.88 / 3)) = ceil(8.08) = 9 total instances`
  - `9 total − 3 local = 6 additional burst instances`
  - `ceil(73.33 / (24.88 / 3)) = ceil(8.84) = 9 total instances`
  - `Linear scaling, Nginx overflow behavior, and Neon capacity are not verified.`

## Drawing order

1. Write the title: **Resume Intelligence Portal — DA1 deployment, DA3 experiment, and cloud-bursting proposal**.
2. Draw and label the black DA1 region across the top; add boxes 1–7 and arrows 1–8.
3. Add the Cloud SQL migration sentence beneath the DA1 API/database area.
4. Draw the lower-left black DA3 Docker Compose region; add boxes 8–12, the shared Neon symbol, and arrows 9–12.
5. Add the Docker Compose, Alembic, IAM/scoped-service-accounts, and Cloud Logging tool strip/labels.
6. Draw the lower-right orange dashed extension panel and write **Proposed, not built**.
7. Add the proposed Cloud Run burst API service, the two orange dashed arrows, and all unverified-setting labels.
8. Add the capacity annotation exactly as above.
9. Finish with the legend: **black solid = existing/built**; **orange dashed = Proposed, not built**.

## Honesty boundary

The burst route is a design proposal only. The current Nginx configuration has no `max_conns` or backup upstream, no Cloud Run burst service exists, and no runtime test establishes saturation hand-off, Cloud Run behavior, or a sufficient Neon connection budget.

Do not state that reaching `max_conns` definitely selects the backup peer; that intended behavior still requires a compatible Nginx configuration and an isolated hand-off test.
