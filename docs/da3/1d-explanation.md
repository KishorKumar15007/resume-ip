# Q1(d) explanation draft — owner rewrite required

> Draft only. Rewrite this explanation in your own words before submission. It describes a design proposal; it does not claim that the Cloud Run bursting route has been implemented or tested.

## Placement-drive demand and the tested baseline

During a placement-drive morning, many students can sign in, browse job postings, refresh the available openings, and check the status of a submitted resume in a short period. Step 7 models 2,000 students over ten minutes. Its request mix contains 40,000 **read** requests, so the assumed read rate is `40,000 / 600 = 66.67`, approximately **67 read requests/s**. It also contains 44,000 total HTTP requests, so the separate total-rate estimate is `44,000 / 600 = 73.33`, approximately **73.3 total HTTP requests/s**. These are scenario assumptions, not observed production traffic.

The DA3 experiment did not run the React frontend or the deployed Cloud Run services. Instead, Apache Bench sent authenticated `GET /postings` traffic directly to local Nginx at `http://localhost:8080`. Nginx distributed requests to three Docker Compose FastAPI/Uvicorn containers, `backend-1`, `backend-2`, and `backend-3`. Each container maps its host port (`8001`, `8002`, or `8003`) to container port `8000`; Nginx maps host `8080` to container `80`. The three-backend Step 11 median was **24.88 requests/s**. This is a local Compose measurement through a shared external Neon database, not a Cloud Run performance result.

## Proposed cloud bursting path

The fixed three-container local group is the primary capacity in the proposal. The intended future configuration would give each local Nginx primary an explicit `max_conns` limit. A compatible Nginx configuration would then be evaluated to determine whether a backup upstream can route eligible overflow requests to a Cloud Run service running the same stateless FastAPI backend image; that saturation hand-off is not implemented or tested. The API already uses JWT/RBAC for application authentication and keeps structured state in the shared external Neon database, so individual API instances do not require local user-session state. This placement-drive spike is a short-lived increase in centralized web-API demand, making temporary cloud-burst capacity a design direction worth evaluating.

The bursting component is a design proposal and is not implemented. The current Nginx configuration has no `max_conns` limits and no backup peer. No burst service URL, `max_conns` value, HTTPS/SNI/Host configuration, ingress authorization, compatible overflow configuration, or isolated saturation hand-off test has been established. The proposed Cloud Run service is capped at **six** burst instances only as an initial design control, not as a verified safe operating limit.

## Illustrative instance arithmetic and caveats

Using the Step 11 result only as an illustrative linear estimate gives `24.88 / 3 = 8.2933`, approximately **8.3 requests/s per backend**. Applying the assumed read rate gives:

```text
ceil(67 / (24.88 / 3)) = ceil(8.08) = 9 total instances
9 total - 3 local = 6 additional burst instances
```

For completeness, sizing against the separate total-HTTP estimate gives:

```text
ceil(73.33 / (24.88 / 3)) = ceil(8.84) = 9 total instances
```

Both calculations happen to round to nine, but neither proves nine-instance capacity. They assume linear scaling beyond the measured three-instance result. Step 11 did not test higher instance counts, Cloud Run cold-start behavior, a Cloud Run upstream, or Nginx saturation fallback. The local and proposed burst APIs would also share the Neon pooled endpoint, so database latency, pool limits, compute behavior, and aggregate connection capacity can become the bottleneck. A connection-budget validation must precede any deployment; the six-instance cap helps control exposure but is not evidence that the Neon plan can support the resulting connections.

## Operational considerations

Cloud Run can add short-lived capacity for a predictable spike and scale it down afterward, which is preferable to permanently running many idle API containers for a short placement window. Before building this proposal, the deployment must set a maximum instance count, a Cloud Run concurrency policy, Secret Manager/IAM access, a pooled Neon runtime URL, and alerting/cost controls. It must also validate cold-start latency, HTTPS proxy configuration, Host/SNI behavior, ingress authorization, Nginx `max_conns` and backup-peer behavior, and the database connection budget under realistic load.

The DA1 frontend, API, and worker remain separate Cloud Run services. The frontend/API relationship is shown as HTTPS/API traffic, but the live deployed `VITE_API_BASE_URL` and the deployed API's Neon branch have not been inspected. The proposed burst path must not be confused with the DA1 resume upload, Pub/Sub delivery, or worker-scoring flow, which the DA3 scale experiments did not exercise.
