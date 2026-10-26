# DA3 Grading Checklist

Legend:

- `[ ]` not started
- `[~]` implemented, evidence missing
- `[x]` implemented and evidenced
- `[-]` deliberately skipped / not required by the selected assignment scope

## Phase 1 — Neon configuration prerequisite

- [x] Step 4 is complete: timestamped Alembic migration evidence, required Neon-table evidence, and the 19/19 synthetic API smoke-test evidence have been verified; the owner confirms Neon branch `da3-loadtest` was created from `production`.
- [x] Pooled runtime/direct migration configuration is implemented; Alembic evidence shows head `ce1c22c4205c`, and the Neon table capture lists `alembic_version`, `users`, `job_postings`, and `submissions`.
- [x] Synthetic API smoke test passed 19/19 checks, including signup/login, posting CRUD, candidate `403` mutation rejection, and deleted-posting `404`; generated results are saved in `results/04-smoke.md` and `results/04-smoke.json`.
- [x] Neon branch `da3-loadtest` was created from the default `production` branch (owner-confirmed).
- [-] Step 5, “Run without GCP,” was deliberately skipped: the assignment scope does not explicitly require a local storage/job fallback, and the audit does not establish that the existing GCS or Pub/Sub paths are failing.

## 1a — Scale setup and distribution

- [x] Scenario written — placement-drive assumptions and the generated request-mix table are recorded in `results/07-request-mix-table.md` and the report.
- [x] Hardest-hit API named with reason — `GET /postings` is selected by assumed request volume, with the Argon2-login CPU-cost limitation recorded.
- [x] Compose has 3 backends + Nginx — the isolated default topology was owner-run and evidenced with three healthy backends and Nginx.
- [x] Connected to Neon — `/health/db` through Nginx returned HTTP 200 with `db: ok`; the topology uses the `da3-loadtest` branch configuration.
- [x] Distribution proof table + screenshots — `results/09-distribution.*` records 300 authenticated requests at concurrency 10, with 300 matching Nginx records and independent 100/100/100 header and final-upstream counts; both Step 9 screenshots were reviewed.

## 1b — One versus three instances

- [~] Step 10 harness and both C20 validation runs are recorded: rep11 (1 backend) and rep12 (3 backends) each completed 100 warm-up plus 1,000 measured requests with zero failed/non-2xx responses; they are not the required Step 11 repeated comparison.
- [~] Formal two-configuration five-level calibration matrix — partial/incomplete; the original plateau rule could not select a concurrency.
- [x] Partial rep3 calibration screenshot is captured and accurately labelled incomplete (`evidence/1b-calibration-table.png`).
- [x] C20 validation screenshots are captured for rep11 and rep12 (`evidence/1b-validation-1-instance-c20-rep11.png`, `evidence/1b-validation-3-instance-c20-rep12.png`).
- [x] Owner selected C20 for Step 11 after both C20 validations passed; the C10 fallback was not triggered.
- [~] Historical warm-up timeout screenshot is captured; it documents a failed calibration warm-up, not a result.
- [x] Live `docker stats` captures exist for the Step 11 one- and three-backend measured loads; the separate historical one-instance screenshot remains inadequate as saturation proof.
- [~] Neon connections graph is captured but does not establish a causal limit/spike explanation.
- [x] 1-instance and 3-instance runs of 1,000 requests — three interleaved Step 11 repetitions per topology completed in order 1,3,1,3,1,3 (`results/11-1b-manifest-s11-20261024t093248z-c7a71d7b.json`).
- [x] Same tool/concurrency stated — Apache Bench with `-k`, C20, 100-request warm-up excluded from each 1,000-request measurement, and the locked Step 11 order are recorded.
- [x] RPS and mean-latency table — Table 1b.2 and `evidence/1b-results-table.png` record all six Step 11 rows and topology medians.
- [x] Improvement stated — median throughput is 2.418× (141.79%) higher and median mean response time is 58.65% lower with three backends in this experiment.
- [x] Limitations noted — the report records incomplete formal calibration, shared test-machine/load-generator and remote database dependencies, three-repetition limits, pre-hardening/pre-MFA scope, and planned-versus-actual traffic.

## 1c — Failure resilience

- [x] Instance killed mid-run — the three selected baseline runs record a backend-2 `docker kill` about 12.06 seconds after each measured-run start sentinel, with verified stopped/recovery/restoration state.
- [x] Failed count before — the three selected 1,000-request baseline runs record 298, 294, and 280 failed/non-2xx requests; measured access-log diagnostics separately record the 502/504 counts.
- [ ] Nginx fix shown (config diff)
- [ ] Failed count after is 0 in every repetition
- [ ] Availability probe shows no downtime
- [ ] Before/after table

## 1d — Architecture and bursting

- [ ] Diagram uses real names and ports
- [ ] Bursting/edge component in a different colour
- [ ] Explanation ties to the 1a scenario
- [ ] Reason for choosing it
- [ ] Components-and-ports table

## 2a — Sensitive data and password hashing

- [ ] Sensitive data identified
- [ ] Argon2 verified
- [ ] Per-user salt shown
- [ ] "Before" and "after" DB screenshots (before labelled as demo)
- [ ] Sensitive-data inventory table
- [ ] Hash/salt comparison table

## 2b — MFA and authorization

- [ ] TOTP enrolment works
- [ ] Login needs the code
- [ ] PUT/DELETE role-restricted
- [ ] Rejection without token shown
- [ ] MFA-pending token rejected
- [ ] Rate limiting shown

## 2c — Image hardening

- [ ] Baseline scan saved
- [ ] Hardened Dockerfile
- [ ] Rescan saved with same flags
- [ ] CRITICAL/HIGH table
- [ ] CRITICAL/HIGH table covering every application image (or the exclusion explained)
- [ ] App still works

## 2d — Threats and regulation

- [ ] Two threat agents
- [ ] Implemented control each (with file/endpoint)
- [ ] One regulation requirement each
- [ ] Applicability reason

## Overall

- [ ] README with reproduction steps
- [ ] Clean-clone test passes
- [ ] Secrets scan clean
- [ ] A result table present for every part (1a-2d)
- [ ] Report PDF
- [ ] 3-minute video
- [ ] Branch pushed and accessible
