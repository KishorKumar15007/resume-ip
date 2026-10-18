# DA3 Grading Checklist

Legend:

- `[ ]` not started
- `[~]` implemented, evidence missing
- `[x]` implemented and evidenced

## Phase 1 — Neon configuration prerequisite

- [~] Pooled runtime/direct migration configuration and static checks complete; `env-neon-project.png` captures the Neon project, Singapore region, and default `production` branch. Neon migration and runtime checks remain pending.

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
- [ ] Failed count after
- [ ] Before/after table

## 1d — Architecture and bursting

- [ ] Diagram uses real names and ports
- [ ] Bursting/edge component in a different colour
- [ ] Explanation ties to the 1a scenario
- [ ] Reason for choosing it

## 2a — Sensitive data and password hashing

- [ ] Sensitive data identified
- [ ] Argon2 verified
- [ ] Per-user salt shown
- [ ] "Before" and "after" DB screenshots (before labelled as demo)

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
- [ ] Report PDF
- [ ] 3-minute video
- [ ] Branch pushed and accessible
