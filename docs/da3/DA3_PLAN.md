# DA3 — Plan and Documentation Protocol

For AI coding agents (Codex) and the owner. Read this together with `AGENTS.md`, `.agent/CONTINUITY.md` and the DA1 handoff (`resume-portal-full-handoff.md`) before doing anything on this branch.

Source-of-truth order when things disagree: **the repository and `.agent/CONTINUITY.md` > this file > the DA1 handoff.** If the repo contradicts a claim here, trust the repo and record the discrepancy in the decisions log.

---

## 1. What DA3 is

- Course: BACSE344 Cloud Infrastructure and Architecture, C1 slot. Digital Assignment 3. **Due 30/10/2026** on MS Teams.
- Work continues on the same application as DA1 (the Resume/Document Intelligence Portal) on a branch named **`assignment-3`** of the `resume-ip` repository.
- Submission: (1) a report with screenshots and a result table for every part, (2) the GitHub link to the `assignment-3` branch, (3) a 3-minute demo video.
- Grading rule for **every part**: full marks if it works with screenshots/tables and a clear explanation; **half marks if it works but evidence or explanation is missing or generic**; zero if not attempted or not working.

**Consequence: evidence is as important as code.** A feature with no screenshot, no table and no specific explanation is worth half. Everything below exists to prevent that.

The question text is in Appendix A. The part-by-part summary:

| Part | Marks | Requirement in one line |
|---|---|---|
| 1a | 1 | Peak-demand scenario + hardest-hit API; 3 backend instances via Docker Compose behind Nginx on the existing cloud DB; show requests spread across all 3 |
| 1b | 1.5 | 1,000 requests with 1 instance then 3, same tool and concurrency; table of requests/sec and average response time; state the improvement |
| 1c | 1.5 | Stop one instance mid-test and record failed requests; configure Nginx so none fail; show before/after count |
| 1d | 1 | Architecture diagram with real component names and ports; add a cloud-bursting or edge/fog component in a different colour; explain how it handles the 1a peak and why it fits the domain |
| 2a | 1 | Identify the most sensitive data; salted password hashes (bcrypt/Argon2); DB screenshot before and after |
| 2b | 1.5 | TOTP MFA with an authenticator app; Update/Delete APIs restricted to logged-in users with the right role; show a request rejected without a valid token |
| 2c | 1.5 | Trivy scan; harden (smaller base, non-root); rescan; table of CRITICAL and HIGH before and after |
| 2d | 1 | Two threat agents; for each, the control implemented plus one requirement from the applicable regulation (HIPAA/GDPR) with a reason it applies |

---

## 2. Situation carried over from DA1

- App: recruiters post jobs with required skills; candidates upload PDF resumes; a worker extracts text and computes a skill-match compatibility score; recruiters see a ranked shortlist. Stack: React, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Argon2, JWT + RBAC. Details live in the DA1 handoff.
- **Cloud SQL is suspended.** The database moves to **Neon** (Postgres). Start with a fresh schema via Alembic; no data carry-over is needed.
- **GCP may be unavailable.** Do not assume Cloud Run, Cloud Storage or Pub/Sub still work. The stack must run without GCP credentials. The hosting platform shown in the DA3 diagram must be whatever is actually true.
- **The real extent of DA1 completion is unverified.** The last confirmed state was Job Posting CRUD verified against live Postgres. The first prompt audits the repo and reports facts; later prompts marked *(if needed)* depend on it.

---

## 3. Planned defaults (change only with the owner's approval; log any change)

**Branch and environment**
- All work on `assignment-3`. Small reviewable patches. Plan first and wait for approval for anything touching schema or auth.
- Repo-local gitignored `.env`; committed `.env.example` with placeholders. **No hardcoded absolute paths on this branch** (a cloned branch must run with `docker compose up`).
- Never commit or print secrets: Neon URLs, JWT secret, encryption keys, TOTP secrets.

**Database (Neon)**
- Pooled connection string for the app; direct string for Alembic. `sslmode=require`. `pool_pre_ping=True`, `pool_recycle`, and small pool sizes so three instances stay under the plan's connection limit.
- Neon compute can suspend when idle, so the first query after idle is slow. Warm up before any measurement and note this in the report.

**Q1: scale**
- Scenario: placement-drive morning. Many students log in and refresh openings and submission status at once (the app uses manual refresh, so read endpoints dominate). Default hardest-hit API: `GET /postings`. The final choice comes from calibration and is recorded in the decisions log.
- Three explicit Compose services `backend-1/2/3` (host ports 8001–8003, container port 8000), one uvicorn worker each, a CPU limit per container; Nginx on host port 8080, round-robin. The backend sets an `X-Served-By` header; Nginx logs `$upstream_addr`.
- For 1-instance runs use an Nginx config with a single upstream, so the Nginx hop stays constant between runs.
- Load tool runs in a container (ab, hey or k6), exactly 1,000 requests, identical tool and concurrency for both runs. Concurrency is calibrated on the 1-instance setup until it is saturated, then locked. Report medians of 3 repetitions. Warm-up before each run.
- Failover "before": a deterministic baseline Nginx config (retries off) so the failure is reproducible, disclosed as such. Kill the backend with `docker kill`, not a graceful stop; with `ab` use `-r` so it does not abort on errors. "After": passive failover with `max_fails`, `fail_timeout`, `proxy_next_upstream` (error, timeout, 502, 503, 504), a short `proxy_connect_timeout` and limited `proxy_next_upstream_tries`. Same test, same load.
- Cloud bursting is a **diagram and explanation only** and is not built: overflow beyond the fixed Compose capacity goes to elastic instances on the hosting platform, justified by spiky, short-lived load, a stateless API and an external database.

**Q2: security**
- Keep Argon2id (salt is embedded in each hash). Show per-user salts: the same password gives different hashes.
- TOTP with `pyotp`; TOTP secret encrypted at rest with a key from the environment; two-step login with a short-lived MFA token that must be **rejected on every normal endpoint**; rate limiting and lockout on login and on code verification; recruiters are required to enrol.
- RBAC and ownership checks on PUT/DELETE; candidates see only their own submissions; recruiters only submissions for their own postings.
- Trivy runs in a container with **identical flags for both scans** (`--severity CRITICAL,HIGH`). Hardening: slim base image, multi-stage build, non-root numeric user, no build tools in the final image, `.dockerignore`, upgraded vulnerable dependencies. Regression-test after hardening.
- Threat agents (suggested): (1) external attacker doing credential stuffing or account takeover → Argon2, TOTP, rate limiting → GDPR Art. 32 (security of processing); (2) malicious or curious insider → RBAC and ownership checks → GDPR Art. 5(1)(f) (integrity and confidentiality) or Art. 25 (data protection by design). Applicability reasoning must be honest: a campus portal in India is primarily governed by the Digital Personal Data Protection Act, 2023; GDPR is cited as the framework the question prescribes, applying to personal data in resumes, and the DPDP Act is mentioned as the domestic equivalent.

**Out of scope:** actually building cloud bursting, Kubernetes, new frameworks, new product features, ML, unrelated refactors.

---

## 4. The documentation protocol

### 4.1 Folder layout (create in the first DA3 prompt)

```
docs/da3/
  00-question.md          verbatim question text (Appendix A)
  01-checklist.md         every gradable item with a status
  02-report.md            the living report: one section per part
  03-decisions-log.md     every decision, with the reason
  04-evidence-index.md    manifest of screenshots/outputs still needed or captured
  evidence/               screenshots, named <part>-<what>.png  (owner captures)
  results/                raw outputs and generated tables, named <part>-<what>.{txt,csv,json,md}
  scripts/                measurement, test and table-generation scripts
```

### 4.2 Checklist statuses (`01-checklist.md`)

Separate "built" from "evidenced":

- `[ ]` not started
- `[~]` implemented, **evidence not yet captured**
- `[x]` implemented **and** evidenced (raw output saved, table generated, screenshot present, explanation written)

Never mark `[x]` without the evidence existing. Checklist items:

| Part | Items |
|---|---|
| 1a | Scenario written · Hardest-hit API named with reason · Compose has 3 backends + Nginx · Connected to Neon · Distribution proof table + screenshot |
| 1b | 1-instance and 3-instance runs of 1,000 requests · Same tool/concurrency stated · RPS and mean-latency table · Improvement stated · Limitations noted |
| 1c | Instance killed mid-run · Failed count before · Nginx fix shown (config diff) · Failed count after · Before/after table |
| 1d | Diagram uses real names and ports · Bursting/edge component in a different colour · Explanation ties to the 1a scenario · Reason for choosing it |
| 2a | Sensitive data identified · Argon2 verified · Per-user salt shown · "Before" and "after" DB screenshots (before labelled as demo) |
| 2b | TOTP enrolment works · Login needs the code · PUT/DELETE role-restricted · Rejection without token shown · MFA-pending token rejected · Rate limiting shown |
| 2c | Baseline scan saved · Hardened Dockerfile · Rescan saved with same flags · CRITICAL/HIGH table · App still works |
| 2d | Two threat agents · Implemented control each (with file/endpoint) · One regulation requirement each · Applicability reason |
| Overall | README with reproduction steps · Clean-clone test passes · Secrets scan clean · Report PDF · 3-minute video · Branch pushed and accessible |

### 4.3 Report section template (`02-report.md`)

Every part uses the same structure:

```
## <Part> — <title>
Requirement:    (quoted from the question)
What I built:   (2-3 sentences, with file paths / endpoint names)
Commands run:   (exact commands)
Result:         (table, generated from results/ files)
Evidence:       (screenshot filenames, each with a one-line caption)
Explanation:    (3-4 sentences, specific to the resume portal)
Honesty notes:  (labelled demos, resource limits, caveats)
```

Explanations must name this application's own things (endpoints, scenario, components). Generic text such as "high traffic degrades performance" costs marks.

### 4.4 What every prompt must do before it finishes

1. Save raw output to `results/<part>-<what>.*`.
2. Generate any table **from the raw files with a script**; never type numbers by hand.
3. Update that part's section in `02-report.md`.
4. Add rows to `04-evidence-index.md` for every screenshot the owner must capture: filename, what it must show, the exact command or page to open. The owner captures them while the state is live.
5. Update statuses in `01-checklist.md` (`[~]` until evidence exists).
6. Append decisions and reasons to `03-decisions-log.md`.
7. Update `.agent/CONTINUITY.md`.

Evidence index format:

```
| File | Part | Must show | How to produce | Status |
| 1b-ab-3-instances.png | 1b | ab summary for the 3-instance run | scripts/run-load.ps1 3 | needed |
```

### 4.5 Integrity rules

- **No invented, estimated or rounded-up numbers.** Tables come from raw files. Keep odd or failed runs in `results/` and mention them.
- If results disagree with expectations (for example 3 instances are not faster), report them honestly and explain why; do not tune the test until it flatters the result. Calibration runs are allowed but must be labelled as calibration and kept separate from reported runs.
- **"Before" states that never existed must be labelled.** DA1 already used Argon2, so the 2a plaintext "before" is a clearly labelled demonstration table, not history. If the current Dockerfile is already slim and non-root, the 2c "before" is a labelled naive baseline. Put this in each part's honesty notes.
- Screenshots must not reveal secrets (Neon URL, JWT secret, encryption key). Use a throwaway account for the TOTP QR code, since it contains a real secret. Use synthetic resumes only, never real personal data.

### 4.6 Division of work

- The owner writes and sends the prompts, runs long tests (load runs, failover runs, scans) and takes the screenshots. This is deliberate, to conserve tokens.
- Codex writes the scripts, config and code, and the documentation updates above. It does not run long load tests unless explicitly asked.
- Use containers by default. Do not install host packages without explicit instruction.

---

## 5. Roadmap

Pacing: Phases 0–1 by 20 Oct, Phase 2 by 24 Oct, Phase 3 by 27 Oct, Phase 4 by 29 Oct. 30 Oct is a buffer only. The prompt count may grow slightly in Phases 2 and 3.

**Phase 0: Baseline**

| # | Prompt | What it does |
|---|---|---|
| 1 | Repo audit + branch | Create `assignment-3`. Read-only report on what DA1 actually implements (endpoints, frontend, worker, Dockerfiles, storage/publisher code, roles), what is deployed and where, and what breaks without GCP. |
| 2 | DA3 context and docs scaffold | Create the `docs/da3/` structure from section 4, add this plan and the audit findings to `.agent/CONTINUITY.md` and a DA3 handoff. |

**Phase 1: Neon migration**

| # | Prompt | What it does |
|---|---|---|
| 3 | Neon-ready DB config | Pooled vs direct URLs, SSL, pool settings, `.env`/`.env.example` (owner creates the Neon project). |
| 4 | Migrate and smoke test | `alembic upgrade head` on Neon, confirm the head revision; owner verifies signup/login/CRUD in Swagger. |
| 5 | Run without GCP *(if needed)* | Config switches so storage and job publishing work locally with no GCP credentials. |
| 6 | Hosting reconciliation *(if GCP is live)* | Re-point the deployed API to Neon, or record the true hosting state for the diagram. |

**Phase 2: Q1 Scale**

| # | Prompt | What it does |
|---|---|---|
| 7 | 1a: scenario, target API, fixtures | Scenario text, API justification, `X-Served-By` header, request log line, seed script, load-test token. |
| 8 | 1a: Compose and Nginx | Three backends + Nginx, CPU limits, `$upstream_addr` logging, single-upstream variant. |
| 9 | 1a: distribution proof | Script tallies requests per instance (header + Nginx log); table + screenshot. |
| 10 | 1b: load harness | Containerised tool, warm-up, fixed `-n 1000`, calibrated concurrency, CSV output. |
| 11 | 1b: 1 vs 3 results | 3 repetitions each, medians, improvement and speedup, limitations note. |
| 12 | 1c: failure, before | Deterministic baseline config, `docker kill` mid-run, failed count. |
| 13 | 1c: failure, after | Passive failover config, identical rerun, before/after table. |
| 14 | 1d: diagram and bursting | Real names and ports, bursting component in a different colour, explanation. |

**Phase 3: Q2 Secure**

| # | Prompt | What it does |
|---|---|---|
| 15 | 2a: sensitive data and hashing | Inventory, Argon2 parameters, per-user salts, labelled before/after DB evidence. |
| 16 | 2b: TOTP backend | Encrypted secret, setup/confirm/verify, two-step login, rate limiting and lockout. |
| 17 | 2b: TOTP frontend | QR enrolment and second-step login. |
| 18 | 2b: access-control matrix | PUT/DELETE across no/invalid/expired/MFA-pending/wrong-role/non-owner/owner; 401/403/200/204 table. |
| 19 | 2c: Trivy baseline | Containerised scan, fixed flags, JSON and table. |
| 20 | 2c: harden and rescan | Hardened image, identical-flags rescan, before/after table, regression test. |
| 21 | 2d: threat agents and regulation | Two agents, controls mapped to code, GDPR articles, honest applicability, DPDP note. |

**Phase 4: Evidence and submission**

| # | Prompt | What it does |
|---|---|---|
| 22 | Evidence audit | Reconcile `01-checklist.md` and `04-evidence-index.md`; list every gap. |
| 23 | README, clean-clone test, secrets scan | Reproduction README; fresh clone runs with `docker compose up`; scan full history for secrets. |
| 24 | Report | Finish `02-report.md`; export to PDF. |
| 25 | Demo video script | 3-minute shot list (about 90 s each for Q1 and Q2), pre-recorded clips for long runs. |
| 26 | Final submission pass | Push branch, verify the GitHub link works for the evaluator, check file names against the Teams announcement, upload a day early. |

---

## Appendix A: the question, verbatim (copy into `docs/da3/00-question.md`)

BACSE344 - Cloud Infrastructure and Architecture
Digital Assignment 3 Question
C1 Slot
Last date to submit in MSTeams: 30/10/2026

General instruction:
Continue with the same application you built and deployed in Digital Assignment 1 (hospital, institute, industry or any other domain). Every answer must be based on your own application and domain.

**Question 1 - Scale your application (5 marks)**
Your application's user base is about to grow sharply. Identify a realistic peak-demand situation for your own domain (for example, an outpatient rush in a hospital, results day at an institute, or a production shift change in a factory) and make your application handle it without downtime.

a) Describe your peak-demand situation and the API that will be hit hardest. Then run three instances of your backend using Docker Compose behind an Nginx load balancer, connected to your existing cloud database. Show that requests are distributed across all three instances. (1 mark)

b) Using Apache Bench or any suitable free load-testing tool (for example, hey, JMeter or k6), send 1,000 requests to that API, first with 1 instance and then with 3 instances, keeping the same tool and concurrency level for both runs. Tabulate requests per second and average response time, and state the improvement. (1.5 marks)

c) Stop one instance while the load test is running and record the failed requests. Then configure Nginx so that no request fails, and show the before-and-after count. (1.5 marks)

d) Draw the architecture diagram of your own implementation, using the actual names of your components: your frontend, the three backend containers and Nginx from part (a) (with their ports), your cloud database and hosting platform from Assignment 1, and the tools used (e.g., MongoDB Atlas, Render, Firebase). Then add the cloud bursting or edge/fog computing component to the same diagram, marked in a different colour, and explain how it would handle your peak-demand situation from part (a), and why you chose it for your domain. (1 mark)

**Question 2 - Secure your application (5 marks)**
Your application stores data about real people in your chosen domain. Secure it before it goes live.

a) Identify the most sensitive data your application stores (for example, patient records, student marks, or employee/production data). Store user passwords as salted hashes (bcrypt or Argon2) instead of plain text, and show a database screenshot before and after. (1 mark)

b) Add multi-factor authentication to login using a TOTP authenticator app (Google or Microsoft Authenticator). Restrict your Update and Delete APIs to logged-in users with the right role for your domain (for example, doctor, faculty, or supervisor), and show a request being rejected without a valid token. (1.5 marks)

c) Scan your application's Docker image with Trivy. Harden it (smaller base image, non-root user), rescan, and tabulate the CRITICAL and HIGH counts before and after. (1.5 marks)

d) Name two threat agents relevant to your domain. For each, state the control you implemented against it and one requirement from the regulation that applies to your application (HIPAA for health data, GDPR for personal data in general), with a reason why that regulation applies. (1 mark)

**What to submit**
- A report with screenshots, result tables for every part, and the GitHub link to an assignment-3 branch of your assignment 1 repository.
- A demo video of 3 minutes.

**Evaluation rubric**
The same scale applies to every part of both questions.
- Working, with screenshots/tables and a clear explanation: Full marks for that part
- Works, but evidence or explanation is missing or generic: Half marks
- Not attempted or not working: Zero