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

- [ ] Scenario written
- [ ] Hardest-hit API named with reason
- [ ] Compose has 3 backends + Nginx
- [ ] Connected to Neon
- [ ] Distribution proof table + screenshot

## 1b — One versus three instances

- [ ] 1-instance and 3-instance runs of 1,000 requests
- [ ] Same tool/concurrency stated
- [ ] RPS and mean-latency table
- [ ] Improvement stated
- [ ] Limitations noted

## 1c — Failure resilience

- [ ] Instance killed mid-run
- [ ] Failed count before
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
