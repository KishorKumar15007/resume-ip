# DA3 final-report handoff

This is an evidence-first briefing for an author without repository access. It is not the final PDF report. Cite only the retained paths below. Do not include secrets, tokens, database URLs, passwords, complete hashes, TOTP codes, provisioning URIs, or encryption keys. All DA3 test data described here is synthetic.

## 1. Question map

Source: `docs/da3/00-question.md` (the only question file found in the repository).

| Part | Exact requirement / marks |
| --- | --- |
| 1a | **(1 mark)** “Describe your peak-demand situation and the API that will be hit hardest. Then run three instances of your backend using Docker Compose behind an Nginx load balancer, connected to your existing cloud database. Show that requests are distributed across all three instances.” |
| 1b | **(1.5 marks)** “Using Apache Bench or any suitable free load-testing tool (for example, hey, JMeter or k6), send 1,000 requests to that API, first with 1 instance and then with 3 instances, keeping the same tool and concurrency level for both runs. Tabulate requests per second and average response time, and state the improvement.” |
| 1c | **(1.5 marks)** “Stop one instance while the load test is running and record the failed requests. Then configure Nginx so that no request fails, and show the before-and-after count.” |
| 1d | **(1 mark)** “Draw the architecture diagram of your own implementation, using the actual names of your components: your frontend, the three backend containers and Nginx from part (a) (with their ports), your cloud database and hosting platform from Assignment 1, and the tools used … Then add the cloud bursting or edge/fog computing component to the same diagram, marked in a different colour, and explain how it would handle your peak-demand situation from part (a), and why you chose it for your domain.” |
| 2a | **(1 mark)** “Identify the most sensitive data your application stores … Store user passwords as salted hashes (bcrypt or Argon2) instead of plain text, and show a database screenshot before and after.” |
| 2b | **(1.5 marks)** “Add multi-factor authentication to login using a TOTP authenticator app (Google or Microsoft Authenticator). Restrict your Update and Delete APIs to logged-in users with the right role for your domain … and show a request being rejected without a valid token.” |
| 2c | **(1.5 marks)** “Scan your application's Docker image with Trivy. Harden it (smaller base image, non-root user), rescan, and tabulate the CRITICAL and HIGH counts before and after.” |
| 2d | **(1 mark)** “Name two threat agents relevant to your domain. For each, state the control you implemented against it and one requirement from the regulation that applies to your application (HIPAA for health data, GDPR for personal data in general), with a reason why that regulation applies.” |

The submission requires a report with screenshots, a result table for every part, and an `assignment-3` GitHub branch link, plus a three-minute demo video. Rubric: working plus screenshots/tables plus clear explanation earns full marks; working with missing/generic evidence or explanation earns half marks; not attempted/not working earns zero.

## 2. Repository map

| Path(s) | Purpose | Parts |
| --- | --- | --- |
| `docs/da3/00-question.md`, `DA3_PLAN.md`, `01-checklist.md`, `02-report.md`, `03-decisions-log.md`, `04-evidence-index.md` | Requirement, report draft, status, decisions, and capture register. | All |
| `compose.da3.yml`, `nginx/nginx-1.conf`, `nginx/nginx-3.conf`, `nginx/nginx-3-baseline.conf`, `nginx/nginx-3-resilient.conf`, `Dockerfile.loadtest` | Local topology, one-instance control, failure profiles, Apache Bench client. | 1a–1c |
| `scripts/seed_loadtest.py`, `distribution_test.py`, `aggregate_1a_request_mix.py` | Synthetic fixtures, distribution proof, request-mix table. | 1a |
| `scripts/loadtest.py`, `run_1b.py`, `aggregate_1b.py` | Calibration and final one-v-three harness/aggregation. | 1b |
| `scripts/failover_test.py`, `availability_probe.py`, `aggregate_1c.py` | Kill/recovery/probe harness and before-after aggregation. | 1c |
| `diagrams/q1-architecture.svg`, `q1-architecture.png`, `q1-architecture-hand-draw.md`, `results/14-components-table.md`, `1d-explanation.md` | Diagram source/render/guide/table/draft. | 1d |
| `sensitive-data-inventory.md`, `scripts/argon2_check.py`, `scripts/2a_demo*.sql` | Sensitive-data inventory, narrow Argon2 evidence, labelled demo cleanup. | 2a |
| `backend/alembic/versions/a4c7b6d92e10_add_optional_totp_mfa_to_users.py`, `backend/app/core/security.py`, `backend/app/routers/auth.py`, `scripts/mfa_flow_test.py` | Optional encrypted TOTP and flow test. | 2b |
| `backend/app/core/dependencies.py`, `backend/app/routers/postings.py`, `backend/app/routers/submissions.py`, `scripts/authz_matrix.py` | Access-scope, role/ownership enforcement and matrix. | 2b, 2d |
| `backend/Dockerfile`, `backend/Dockerfile.baseline`, `frontend/Dockerfile`, `scripts/trivy_scan.py`, `aggregate_2c.py` | Baseline, hardening, frontend coverage, immutable-snapshot scanning/comparison. | 2c |
| `2d-threat-controls.md`, `README.da3.md`, `scripts/secrets_scan.py` | Threat ledger and final reproduction/security-hygiene artifacts. | 2d, submission |
| `docs/da3/evidence/`, `docs/da3/results/` | Owner visual evidence and retained raw/generated results. | All |

## 3. Per-part packs

### 1a — Scale setup and distribution

**What was done.** The scenario models 2,000 placement-drive students over 600 seconds. `GET /postings` is selected by assumed request volume, not measured CPU cost. `compose.da3.yml:22-61` defines `backend-1`, `backend-2`, `backend-3`, and Nginx; `backend/app/main.py:31-42,134-149` supplies identity, `X-Served-By`, `/health`, and `/health/db`. `scripts/distribution_test.py:25-29,444-492` targets local Nginx and correlates a unique run ID with JSON logs. Seed data is deterministic/synthetic.

**Key results.** Source: `results/07-request-mix-table.md` and `results/09-distribution.md`.

| Item | Exact result |
| --- | ---: |
| Students / window | 2,000 / 600 seconds |
| Read / total HTTP requests | 40,000 / 44,000 |
| Read / total rate | 66.67 / 73.33 requests/s |
| `GET /postings` | 30,000; 68.18%; 50.00 requests/s |
| Distribution run | 300 client records and 300 matching Nginx records |
| Backend-1 / 2 / 3 | 100 / 100 / 100 header and final-upstream records (33.33% each) |

Formula: `requests / 600`; demand values are assumptions, not production observations. The distribution proof applies to local Compose/Nginx, not Cloud Run.

**Evidence.** Not opened. The index describes `1a-neon-branches.png`, `1a-seed-output.png` (captured/redacted), `1a-xservedby-header.png`, `1a-compose-ps.png`, `1a-curl-rotation.png`, `1a-host-resources.png`, `1a-neon-connected.png`, `1a-distribution-table.png`, and `1a-nginx-log-upstreams.png` as captured/verified. Use the evidence-index captions and preserve redaction.

**Reproduce.** Prerequisites: private owner-managed load-test configuration, Compose running, synthetic fixtures/token. Command: `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\distribution_test.py`. Outputs: `results/09-distribution-raw.json`, `.csv`, `.md`. Do not overwrite accepted canonical outputs.

**Status/disclosure:** COMPLETE for local test; do not say it measured deployed Cloud Run or proved `GET /postings` is the most CPU-expensive endpoint.

### 1b — One versus three instances

**What was done.** `scripts/run_1b.py:389-548` ran authenticated Nginx `GET /postings` using Apache Bench `-k`, C20, 100 warm-up requests excluded, then 1,000 measured requests. Order: 1,3,1,3,1,3; three repetitions per topology. Each local backend has one Uvicorn worker, 0.5 CPU and 512 MiB (`compose.da3.yml:12-14`).

**Final table.** Exact source: `results/11-1b-table.md`.

| Ordinal | Backends | Rep | RPS | Mean ms | Failed | Non-2xx |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 1 | 10.29 | 1943.935 | 0 | 0 |
| 2 | 3 | 1 | 24.88 | 803.911 | 0 | 0 |
| 3 | 1 | 2 | 8.52 | 2347.827 | 0 | 0 |
| 4 | 3 | 2 | 22.25 | 898.935 | 0 | 0 |
| 5 | 1 | 3 | 10.68 | 1872.073 | 0 | 0 |
| 6 | 3 | 3 | 27.42 | 729.359 | 0 | 0 |

Medians: one backend = 10.29 RPS/1943.935 ms; three backends = 24.88 RPS/803.911 ms. Full-precision source comparisons: speedup `24.88/10.29` = `2.417881438289601554907677357`; increase `(24.88/10.29 - 1)*100` = `141.7881438289601554907677357%`; latency reduction `(1 - 803.911/1943.935)*100` = `58.64517074902195803872043047%`.

C20 was not selected from a complete formal matrix. The matrix was incomplete; C20 was locked after the separate C20 validations: one backend 9.97 RPS/2006.793 ms and three backends 40.39 RPS/495.205 ms, both zero failed/non-2xx (`results/10-single-i1-c20-rep11.json`, `10-single-i3-c20-rep12.json`). Limitations: generator and Nginx share host; shared remote Neon; three reps; pre-hardening/pre-MFA; no linear-scaling claim.

**Evidence.** Not opened. `1b-results-table.png`, `1b-ab-1-instance.png`, `1b-ab-3-instances.png`, `1b-docker-stats-live-load.png`, and `1b-docker-stats-3-instances.png` support final results. `1b-calibration-*`, `1b-neon-connections-during-failure.png`, and idle `1b-docker-stats-1-instance.png` are historical/diagnostic only; the index explicitly calls the latter inadequate for saturation proof.

**Reproduce.** `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\run_1b.py`; expect a fresh `results/11-1b-manifest-<id>.json`, raw AB, results, diagnostics and table. Preserve manifest `11-1b-manifest-s11-20261024t093248z-c7a71d7b.json`.

**Status/disclosure:** COMPLETE benchmark evidence; disclose incomplete calibration and experimental limitations.

### 1c — Failure resilience

**What was done.** `scripts/failover_test.py:37-87,1201-1215` records controlled kill, raw AB, diagnostics, recovery/restoration. Baseline `nginx/nginx-3-baseline.conf:7-25` deliberately uses `max_fails=0` and `proxy_next_upstream off`. Accepted resilient profile `nginx/nginx-3-resilient.conf:7-27` uses `max_fails=2 fail_timeout=10s`, retry statuses, three tries, five-second retry window and one-second connection timeout. `availability_probe.py` samples Nginx health.

**Final table.** Exact numeric authority: `results/13-1c-table.md`. Kill/gap values below are rounded to six decimals.

| Set/rep | Complete | Failed/non-2xx | 5xx (502/504) | RPS | Kill s | Probe total/failed/longest gap s |
| --- | ---: | --- | --- | ---: | ---: | --- |
| baseline 1 | 1000 | 298/298 | 298 (54/244) | 10.89 | 12.074370 | n/a |
| baseline 2 | 1000 | 294/294 | 294 (42/252) | 13.93 | 12.066728 | n/a |
| baseline 3 | 1000 | 280/280 | 280 (69/211) | 14.74 | 12.064484 | n/a |
| resilient 4 | 1000 | 0/0 | 0 (0/0) | 23.38 | 12.076163 | 336/0/0.382475 |
| resilient 5 | 1000 | 0/0 | 0 (0/0) | 23.52 | 12.073591 | 362/0/0.570764 |
| resilient 6 | 1000 | 0/0 | 0 (0/0) | 23.25 | 12.208898 | 374/0/0.606952 |

Every accepted resilient repetition has zero AB failures/non-2xx and zero failed probe samples. This establishes the tested idempotent-GET path only. Resilient rep1 remains excluded: final probe timestamp was before exact post-recovery health.

**Evidence.** Not opened. Use `1c-before-ab-summary.png`, `1c-docker-kill.png`, `1c-nginx-diff.png`, `1c-after-ab-summary.png`, `1c-retry-log.png`, `1c-availability-probe.png`, `1c-before-after-table.png`. `1c-before-nginx-errors.png` only proves no matching error/warning lines, not no upstream errors.

**Reproduce.** `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\failover_test.py --config resilient --rep <fresh-positive-number>`; expect fresh result, raw AB, diagnostics and probe CSV. Aggregate with `aggregate_1c.py`. Preserve reps 4–6.

**Status/disclosure:** COMPLETE for controlled GET resilience; never generalise retries to uploads/POSTs.

### 1d — Architecture and cloud bursting

**What was done.** The SVG distinguishes DA1 Cloud Run frontend/API/worker, Cloud Storage, Pub/Sub, Logging, IAM and Neon from local DA3 Compose. Actual ports from `compose.da3.yml:22-61`: Nginx 8080→80; backend-1 8001→8000; backend-2 8002→8000; backend-3 8003→8000. Apache Bench/probe target Nginx; DA3 has no frontend. Orange dashed Cloud Run backup extension is **Proposed, not built**; current Nginx has no `max_conns`/backup peer.

**Key figures.** Sources: `results/07-request-mix-table.md`, `results/11-1b-table.md`, `results/14-components-table.md`. 40,000/600 = 66.67 assumed read RPS; 44,000/600 = 73.33 total RPS; 24.88/3 = 8.2933 illustrative per-backend RPS. `ceil(67/(24.88/3)) = ceil(8.08) = 9`; 9-3 = 6 additional. Total-rate arithmetic `ceil(73.33/(24.88/3)) = ceil(8.84) = 9`. All assume linear scaling and do not prove capacity, Neon budget, or overflow behaviour.

**Evidence.** Not opened. Report-facing capture: `evidence/1d-architecture-diagram.png` (captured/visually reviewed per index). Source/render: `diagrams/q1-architecture.svg/.png`; hand guide: `diagrams/q1-architecture-hand-draw.md`; table: `results/14-components-table.md`; `1d-explanation.md` remains owner rewrite draft. SVG text-boundary polish is optional deferred work.

**Reproduce/status.** Open the source/render/guide/table; no runtime experiment. PARTIAL because bursting is design-only and explanation rewrite/video remain outstanding.

### 2a — Sensitive data and salted password hashes

**What was done.** `sensitive-data-inventory.md` identifies resumes, password verifier, identity/role and score/status data. `backend/app/core/security.py:38-43` hashes/verifies with Argon2; `backend/app/routers/auth.py:39-119` uses it at signup/login. `scripts/argon2_check.py:21-142` checks exactly two synthetic `da3-salt-*` accounts. `2a_demo.sql` makes only labelled `da3_demo."users_plaintext_legacy_DEMO"`; it is not historical application storage.

**Key result.** Source: `results/15-argon2-check.md`.

| Accounts | Algorithm/parameters | Salt length | Verification | Salt/hash verdict |
| --- | --- | ---: | --- | --- |
| Two `da3-salt-*` synthetic accounts | Argon2id v19; m=65536 KiB, t=3, p=4; 32-byte hash | 16 bytes each | PASS / PASS | salts differ; hashes differ (PASS) |

Do not place salt values or any encoded hashes in the PDF. The before capture is a three-fake-row labelled demonstration; cleanup evidence supports the no-`da3_demo`-schema result.

**Evidence.** Not opened. `2a-before-plaintext-demo.png`, `2a-after-hashed-users.png`, `2a-salt-proof.png`, `2a-argon2-check.png`, `2a-demo-cleanup-verification.png`; all captured in the index.

**Reproduce/status.** `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\argon2_check.py`, supplying synthetic password privately; output `results/15-argon2-check.md`. COMPLETE; say plaintext table is demo-only.

### 2b — Optional TOTP MFA and authorization

**What was done.** Migration `a4c7b6d92e10_add_optional_totp_mfa_to_users.py` adds optional state. `security.py:24-25,74-141` uses scoped tokens and Fernet encrypted storage. `auth.py:105-204` implements `/auth/mfa/setup`, `/auth/mfa/confirm`, `/auth/mfa/verify`; `dependencies.py:15-55` requires access scope; `postings.py:120-166` and `submissions.py:18-57` enforce role/ownership. MFA is optional per account.

**Key results.** `results/16-mfa-flow.md` is PASS: HTTP 201 signup; HTTP 200 login/setup/confirm/challenge/verify/access; HTTP 401 for MFA token on protected route, invalid code, wrong scope, malformed, invalid-signature and expired cases; synthetic cleanup deleted one user. `results/18-authz-matrix.md` is PASS with 22/22 rows: invalid/no/MFA-scope PUT/DELETE credentials HTTP 401 with Bearer metadata; candidate/non-owner mutations HTTP 403; owner PUT 200 and DELETE 204; cross-user submission reads/list paths have recorded 403s.

**Evidence.** Not opened. Flow/storage: `2b-migration-applied.png`, `2b-secret-encrypted.png`, `2b-mfa-flow-test.png`; UI: `2b-qr-enrol-screen.png`, `2b-authenticator-phone.jpg` (second-phone photograph), `2b-login-step1.png`, `2b-login-step2.png` (intentional limited code visibility), `2b-login-success.png` (limited, does not itself prove exchange); authorization: `2b-no-token-rejected.png`, `2b-swagger-401.png`, `2b-candidate-403.png`, `2b-authz-matrix.png`, `2b-authz-matrix-continuation.png`.

**Reproduce/status.** `& .\backend\.venv\Scripts\python.exe .\docs\da3\scripts\mfa_flow_test.py --base-url http://localhost:8080`; output `results/16-mfa-flow.md`. `authz_matrix.py` writes canonical matrix outputs; preserve them. COMPLETE for tested API paths; UI/deployed-video proof remains partial. State **NOT IMPLEMENTED**: lockout, replay protection, Nginx rate limiting, security-event logging; no `mfa_enroll` token.

### 2c — Trivy scan and image hardening

**What was done.** `scripts/trivy_scan.py:26-388` pins Trivy 0.76.1 and uses an offline immutable snapshot. `backend/Dockerfile.baseline` is an explicit experimental root `python:3.12` baseline, not DA1 history. `backend/Dockerfile:1-43` is hardened two-stage `python:3.14.2-slim`, `USER 10001:10001`, health check, API/worker targets. `frontend/Dockerfile:1-17` was scanned but not hardened.

**Key table.** Exact source: `results/20-2c-table.md`; counts deduplicated within each Trivy result class/severity by vulnerability ID + package + installed version.

| Image | Size bytes | User | CRITICAL | HIGH | OS C/H | Language C/H |
| --- | ---: | --- | ---: | ---: | --- | --- |
| `resume-backend:da3-prehardening` | 83,449,753 | `app` | 8 | 126 | 6/113 | 2/13 |
| `resume-backend:da3-hardened` | 87,338,272 (+3,888,519) | `10001:10001` | 7 | 114 | 6/113 | 1/1 |

All retained rows use Trivy 0.76.1 and the same DB snapshot schema/version 2/2. Context coverage: experimental backend 19/461, worker 19/461, unchanged frontend 1/46 CRITICAL/HIGH. Selected reduction: 1 CRITICAL and 12 HIGH. `results/20-smoke-hardened.md` records 19-step standalone API PASS; `20-mfa-hardened-regression.md` records MFA PASS. Hardened authorization matrix, upload, GCS/PubSub/worker regression remain unverified.

**Evidence.** Not opened. Baseline: `2c-trivy-baseline-summary-1.png`, `-2.png`, `2c-dockerfile-baseline.png`, `2c-baseline-user-size.png`, `2c-trivy-baseline-frontend-1.png`, `-2.png`. Hardening: `2c-dockerfile-before-hardening.png`, `2c-dockerfile-hardened-1.png`, `-2.png`, `2c-hardened-build.png`, `2c-nonroot-proof.png`, `2c-image-sizes.png`, `2c-before-after-table.png`, `2c-trivy-hardened-summary-1.png`, `-2.png`, `2c-app-still-works.png`. No frontend-hardening capture is expected.

**Reproduce/status.** Use `trivy_scan.py <image> <label> --dockerfile .\backend\Dockerfile --result-prefix <fresh-prefix>` only with the recorded snapshot. PARTIAL because selected comparison is complete but full hardened regression is not.

### 2d — Threat agents and regulation

**What was done/results.** `2d-threat-controls.md` maps external credential stuffing/account takeover to Argon2id plus optional enrolled-account TOTP, and malicious/curious insider access to access-scope/role/object ownership checks. Sources: `security.py:38-43,126-141`, `dependencies.py:15-55`, `postings.py:120-166`, `submissions.py:18-57`, plus retained 15/16/18 results.

| Threat | Implemented proof | Regulation framing |
| --- | --- | --- |
| External credential stuffing/account takeover | Argon2id; optional enrolled-account TOTP | GDPR Art. 32 technical measures |
| Malicious/curious authenticated insider | Scope, role, ownership; cross-user HTTP 403 matrix outcomes | GDPR Art. 5(1)(f) integrity/confidentiality |

State GDPR is the assignment reference, Art. 3 territorial scope is qualified, DPDP Act 2023 is local context, and no legal compliance is claimed. Not implemented: lockout, replay protection, Nginx rate limit, security-event logging.

**Evidence/reproduce/status.** Reuse retained 2a/2b/18 results/captures; no new screenshot. COMPLETE as scoped analysis; do not claim coverage of upload/storage/PubSub/worker authorization.

## 4. Global facts and disclosures

| Fact/disclosure | Source / report wording |
| --- | --- |
| Database | `02-report.md:30-116`: Cloud SQL was suspended; DA3 uses Neon. Never include a connection URL. |
| DA1 architecture | `postings.py:212-280`, `worker.py:32-80`, `results/14-components-table.md`: React/FastAPI/worker, private object storage, Pub/Sub. |
| Test location | `compose.da3.yml:22-61` and Q1 scripts: Q1 is local Compose/Nginx, not Cloud Run measurement. |
| Limits | `compose.da3.yml:12-14`: one Uvicorn worker; 0.5 CPU and 512 MiB per backend. |
| C20 | `03-decisions-log.md:41,46,51`: incomplete formal matrix; C20 locked after validations. |
| 1c baseline | `nginx-3-baseline.conf:7-25`: experimental no-retry profile, not production recommendation. |
| Image scope | `results/20-2c-table.md`: Q1 pre-hardening; selected 2c API pair hardened; frontend unchanged; worker not rebuilt/rescanned in Step 20. |
| Synthetic data | Test scripts/results: all DA3 accounts, postings and PDF data synthetic. |
| Excluded controls | `03-decisions-log.md:61,73`: lockout/rate-limit/replay/event logging NOT IMPLEMENTED; TOTP optional; no `mfa_enroll`. |
| Legal | `2d-threat-controls.md`: GDPR reference framework, Art. 3 qualification, DPDP context, no legal-compliance claim. |
| Current deployed state | `.agent/CONTINUITY.md:592`: API `resume-ip-api-00014-col`, frontend `resume-ip-frontend-00003-sah`, worker `resume-ip-worker-00005-bej` at 100%; synthetic production upload returned 202 then DONE, score 100/three matched skills. This has missing Step 22b screenshot/video reconciliation. |

## 5. Claim-to-proof table

| Material claim | Proof / reproduction path | State |
| --- | --- | --- |
| 1a demand and 100/100/100 distribution | `07-request-mix-table.md`; `09-distribution.*`; `distribution_test.py` | VERIFIED locally |
| 1b six rows, medians, comparisons | `11-1b-table.md`, final manifest, raw AB/results | VERIFIED |
| 1c before failures / accepted zero after | `13-1c-table.md`; reps 4–6 raw/result/diagnostic/probe | VERIFIED for GET profile |
| 1d architecture/ports/proposal | SVG/PNG/guide/components table/diagram evidence | VERIFIED design; burst UNPROVEN |
| 2a Argon2id parameters and distinct outcomes | `15-argon2-check.md`; `argon2_check.py`; captures | VERIFIED synthetic accounts |
| 2b MFA API flow and 22 matrix rows | `16-mfa-flow.md`; `18-authz-matrix.*`; harnesses | VERIFIED tested paths |
| 2c 8/126 to 7/114 pair | `20-2c-table.md`; raw/metadata; aggregator | VERIFIED selected pair |
| Hardened smoke/MFA | `20-smoke-hardened.*`; `20-mfa-hardened-regression.md` | VERIFIED limited scope |
| 2d control/regulation analysis | `2d-threat-controls.md`; 15/16/18 results/code | VERIFIED analysis, not legal compliance |
| Latest Cloud Run end-to-end state | `.agent/CONTINUITY.md:588-592` | PARTIAL: operational record, missing report/index/media reconciliation |
| Secrets scan clean | `results/23-secrets-scan.md` | UNPROVEN/false: completed result is FAIL (4 history, 5 tree findings) |

## 6. Current report state

- `02-report.md` includes Section 0 and sections 1a–2d, then Reproduction and limitations. Preserve established captions: Table 0.1, Tables 1a.1–1a.3, 1c before/after, component table, 2a tables, 2b.1, 2c.1/2c.2, 2d.1.
- Literal `TODO(evidence)` markers: lines **554, 566, 570** (Reproduction, end limitations, evidence-index transition).
- Cover has registration number “To be filled”; branch accessibility/push unverified (`02-report.md:3-10`).
- `1d-explanation.md` needs owner rewrite. Reproduction placeholder is generic and needs actual paths. Do not use partial Step 10 calibration as final 1b proof.

## 7. Diagrams and media

| Artifact | Status/use |
| --- | --- |
| `diagrams/q1-architecture.svg` | Detailed source diagram. |
| `diagrams/q1-architecture.png` | Rendered export outside evidence folder; visually check before embedding. |
| `evidence/1d-architecture-diagram.png` | Captured report-facing architecture evidence. |
| `diagrams/q1-architecture-hand-draw.md` | Hand-draw guide, not automatically a hand-drawn final figure. |
| Demo video | Not recorded; deployed synthetic OTP-login demo remains required. |
| PDF build | No repository PDF-build method found. |

## 8. Submission readiness

| Item | State | Missing/required wording |
| --- | --- | --- |
| README | `README.da3.md` exists (working-tree addition) with setup, ports, commands, teardown. | Review/commit; uses external configuration contract. |
| Secrets scan | `results/23-secrets-scan.md` completed **FAIL**: 4 history, 5 tree findings. | Do not call clean; owner direction is defer/document, not resolve. |
| Clean clone | Deferred, not performed. | May happen later; owner says not current blocker. |
| Step 22b | Continuity records deployment/pipeline success. | Needed screenshots: `env-cloudrun-latest-revision.png`, `env-deployed-otp-login.png`; video absent. |
| Branch | Local branch `assignment-3`. | Push/accessibility not verified. |
| PDF/video | Not built/recorded. | Final owner work. |

## 9. Recommended report structure

1. Cover/TOC: fill registration number; verify branch accessibility.
2. Overview/environment: Section 0; distinguish historical Cloud SQL, Neon, local DA3 and deployed DA1.
3. 1a: Tables 1a.1–1a.3; embed Compose/rotation/database/distribution evidence. Caption: “Local DA3 Nginx distribution, 300 correlated authenticated requests.”
4. 1b: `11-1b-table.md`; AB/results/stats evidence. Caption: “Final C20 1,000-request interleaved benchmark; warm-up excluded.”
5. 1c: `13-1c-table.md`; baseline/kill/diff/after/retry/probe. Caption timing values rounded to six decimals.
6. 1d: diagram + component table; mark orange extension **Proposed, not built**; use owner-rewritten draft.
7. 2a: inventory + two-row Argon2 table; label plaintext evidence demo-only.
8. 2b: flow summary + 22-row matrix; caption TOTP optional; conceal codes/keys.
9. 2c: selected comparison table plus baseline context; state regression limits.
10. 2d: threat/control table and qualified GDPR/DPDP text.
11. Reproduction/security hygiene/limitations: `README.da3.md`, scan failure/deferred clone, local-vs-cloud separation.

Evaluator checks: exact endpoints/statuses, local ports, raw AB/formulas, accepted recovery runs, diagram actual/proposed distinction, Argon2/TOTP/RBAC negative cases, immutable Trivy comparison inputs, and truthful exclusions.

## 10. Gaps and risks, prioritised

1. **Submission-wide:** video, PDF, branch accessibility and Step 22b screenshots are absent.
2. **1d:** proposed bursting is untested; rewrite `1d-explanation.md` and retain linear/Neon/ingress caveats.
3. **2c:** hardened authorization/upload/worker regression unverified; do not imply all regressions passed.
4. **2b:** matrix is strong, but deployed OTP-login media absent; never invent excluded controls.
5. **1b/1c:** disclose same-host generator, shared database, incomplete calibration, experimental baseline, GET-only retry scope.
6. **Step 23:** scan FAIL and clone deferred; do not hide or call them passed.

## Discrepancies

1. `02-report.md:564` says live deployment uses `da3-loadtest`; later `.agent/CONTINUITY.md:592` records production deployment. Treat the later operational record as current, but reconcile it before PDF export.
2. `01-checklist.md:95` leaves Step 22b pending, while continuity records promotion/end-to-end synthetic processing; captures/video are still missing, so evidence status remains incomplete.
3. `23-secrets-scan.previous-failed.md` and current `23-secrets-scan.md` both say FAIL; current result is complete with 4 history/5 tree findings. Any pass claim conflicts with retained evidence.
4. Section 0 historical head `ce1c22c4205c` predates later MFA migration `a4c7b6d92e10`; distinguish historical Step 4 state from final schema state.

## Claims verified

Read-only commands used: `Get-Content` for question/report/index/checklist/decisions/continuity/results; `rg -n` for code/config/script anchors, TODOs, and evidence captions; `Get-ChildItem`/`rg --files` for inventory; `git branch --show-current` and `git status --short`. No runtime tests, scans, database/cloud operations or image viewing occurred.

## Images opened

None. Descriptions/status/redaction safety are from `04-evidence-index.md`; visually check every embedded image before PDF export.

## Files changed

- `docs/da3/24-report-handoff.md`
