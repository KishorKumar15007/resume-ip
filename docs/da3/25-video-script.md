# DA3 three-minute demo video script

Target duration: **at most 3:00**. Use synthetic accounts/data only. Do not run
Apache Bench, failover, Trivy, migrations, or any long-running test while
recording: show the retained generated result and evidence instead. Never show
passwords, tokens, database URLs, secrets, QR/manual MFA keys, complete TOTP
codes, or private resume content.

## Pre-recording checklist

- [ ] Record at 1080p with browser zoom/readability checked; turn off desktop,
  browser, phone, email and chat notifications.
- [ ] Open and arrange: deployed frontend browser tab, Swagger/no-token 401
  page, local evidence/result files, architecture diagram, and GitHub branch
  page. Use one clean browser profile/window.
- [ ] If a local terminal is shown for Q1, start Docker Desktop and the already
  prepared local Compose stack first; confirm Nginx/local services are healthy.
  Do not start a benchmark or failure test during the recording.
- [ ] Ensure the owner-managed Neon environment is already available/warmed;
  do not show any database configuration, host, connection URL, environment
  file, SQL credential, or console connection-string panel.
- [ ] Use only the designated synthetic recruiter/candidate and synthetic
  posting. Prepare a fresh synthetic MFA account only if required by the live
  login demonstration; do not show account credentials.
- [ ] Hide terminal history containing headers, tokens, URLs, passwords or
  private paths. Enlarge only the selected table/result region.
- [ ] Keep the authenticator phone beside the screen with its display limited to
  the current code-entry interaction. Do not record a provisioning URI, QR
  code, manual key, or readable active TOTP value.
- [ ] Pre-open the retained fallback artifacts named in each shot. If any live
  request fails, state that the recorded result is the evidence and do not
  improvise/retry a destructive request on screen.

## Shot list (total 3:00)

| Time | What is on screen | Command/page ready | Words to say (about two sentences) | Fallback evidence |
| --- | --- | --- | --- | --- |
| **0:00–0:15** | Title slide or clean browser page with the Resume Intelligence Portal name, your name, course and `assignment-3` branch name. Show no secret/configuration panel. | GitHub repository branch page, or a simple title card containing `assignment-3`. | “I am Kishor Kumar, and this is my Resume Intelligence Portal for BACSE344 DA3 on the assignment-3 branch. The original Cloud SQL instance was suspended, so the DA3 work uses Neon PostgreSQL; all demonstrations use synthetic data.” | `docs/da3/evidence/env-cloudsql-suspended.png`; `docs/da3/evidence/env-neon-project.png`; `docs/da3/evidence/env-neon-tables.png` |
| **0:15–0:40** | First show local `docker compose -f compose.da3.yml ps -a` output with three healthy backends/Nginx, then `1a-curl-rotation.png`, then the 100/100/100 distribution table. Crop/zoom to ports, headers and counts. | Prepared terminal command: `docker compose -f compose.da3.yml ps -a`; then open `docs/da3/results/09-distribution.md`. Do **not** run `distribution_test.py` live. | “For the placement-drive scenario, three FastAPI backends run behind Nginx: host ports 8001, 8002 and 8003 map to port 8000, while Nginx is on port 8080. The recorded authenticated 300-request test reconciled client headers and Nginx logs: each backend received exactly 100 requests.” | `docs/da3/evidence/1a-compose-ps.png`; `docs/da3/evidence/1a-curl-rotation.png`; `docs/da3/evidence/1a-distribution-table.png`; `docs/da3/evidence/1a-nginx-log-upstreams.png` |
| **0:40–1:00** | Open the six-row final benchmark table and keep the two median rows/comparison visible. Do not show calibration failures as the final result. | `docs/da3/results/11-1b-table.md` or `docs/da3/evidence/1b-results-table.png`. | “Using the same authenticated GET /postings workload, Apache Bench sent 1,000 measured requests at concurrency 20 for each topology, with three interleaved repetitions. The median rose from 10.29 to 24.88 requests per second, a 2.418-times speedup, while median mean response time fell from 1,943.935 to 803.911 milliseconds.” | `docs/da3/evidence/1b-results-table.png`; `docs/da3/evidence/1b-ab-1-instance.png`; `docs/da3/evidence/1b-ab-3-instances.png` |
| **1:00–1:20** | Open the six-row before/after failure table, then briefly show the Nginx diff or retry-log evidence. Keep zero failed after rows visible. | `docs/da3/results/13-1c-table.md`; optionally `docs/da3/results/13-nginx-config.diff`. Do **not** kill a backend live. | “In the controlled no-retry baseline, killing one backend produced 298, 294 and 280 failed requests across the three repetitions. The resilient Nginx GET profile added passive failover and bounded retries; accepted repetitions 4 to 6 ended with zero failed requests, zero non-2xx responses, and zero failed health probes.” | `docs/da3/evidence/1c-before-after-table.png`; `docs/da3/evidence/1c-nginx-diff.png`; `docs/da3/evidence/1c-availability-probe.png`; `docs/da3/evidence/1c-retry-log.png` |
| **1:20–1:30** | Show the architecture diagram and point to the black DA1/DA3 components and orange dashed burst area. | `docs/da3/evidence/1d-architecture-diagram.png` or `docs/da3/diagrams/q1-architecture.png`. | “This diagram separates the deployed DA1 services from the local DA3 Nginx experiment. The orange dashed Cloud Run burst layer is proposed, not built: its six-instance cap and the nine-instance arithmetic are illustrative and require future connection-budget and routing validation.” | `docs/da3/evidence/1d-architecture-diagram.png`; `docs/da3/results/14-components-table.md` |
| **1:30–1:45** | Side-by-side labelled plaintext **demo-only** before image and real hashed-user/Argon2 proof after image. Never zoom into a complete hash or salt. | `docs/da3/evidence/2a-before-plaintext-demo.png`, `2a-after-hashed-users.png`, then `2a-argon2-check.png`. | “Resume content, identity data and submission results are sensitive, while the plaintext table is only an isolated labelled illustration with fake rows. The real application verifies two synthetic accounts as Argon2id v19, and the recorded result confirms distinct salts and hashes for the same-password test.” | `docs/da3/evidence/2a-before-plaintext-demo.png`; `docs/da3/evidence/2a-after-hashed-users.png`; `docs/da3/evidence/2a-argon2-check.png`; `docs/da3/evidence/2a-salt-proof.png` |
| **1:45–2:15** | On the deployed frontend, log in only with a synthetic enrolled account; show the MFA challenge and phone interaction without readable code, then the successful session. Immediately switch to Swagger/terminal showing a pre-prepared no-token PUT/DELETE rejection, not an authenticated mutation. | Deployed frontend URL from the current Cloud Run service; synthetic account already enrolled. Open Swagger `PUT /postings/{posting_id}` with **no** Authorization header and a known synthetic posting ID, then execute only the unauthenticated request. | “MFA is optional per account: after password login, this enrolled synthetic account must complete a TOTP second factor before receiving normal access. Server-side controls reject an unauthenticated update with HTTP 401 and enforce recruiter role and ownership separately; the retained matrix also records candidate and non-owner 403 denials.” | `docs/da3/evidence/2b-authenticator-phone.jpg`; `docs/da3/evidence/2b-login-step1.png`; `docs/da3/evidence/2b-login-success.png`; `docs/da3/evidence/2b-no-token-rejected.png`; `docs/da3/evidence/2b-authz-matrix.png`; `docs/da3/evidence/2b-authz-matrix-continuation.png` |
| **2:15–2:35** | Open the Trivy before/after table and briefly show the hardened Dockerfile/non-root proof. | `docs/da3/results/20-2c-table.md`; `docs/da3/evidence/2c-before-after-table.png`; do **not** run Trivy. | “The selected API comparison uses the same recorded Trivy database snapshot and deterministic count rule. Hardening the backend to a two-stage slim image running as UID 10001 changed the selected pair from 8 CRITICAL and 126 HIGH findings to 7 CRITICAL and 114 HIGH findings; the frontend was scanned but not hardened in this scope.” | `docs/da3/evidence/2c-before-after-table.png`; `docs/da3/evidence/2c-nonroot-proof.png`; `docs/da3/evidence/2c-trivy-hardened-summary-1.png` |
| **2:35–2:50** | Display the two-row threat/regulation table with code/result references visible. | `docs/da3/2d-threat-controls.md` or report Table 2d.1. | “The external threat is credential stuffing or account takeover, addressed by Argon2id and optional enrolled-account TOTP under the GDPR Article 32 security framing. The insider threat is cross-user access, addressed by access-scope, role and ownership checks; GDPR Article 5(1)(f) is the reference, while India’s DPDP Act is the domestic context and this is not a legal-compliance claim.” | `docs/da3/2d-threat-controls.md`; `docs/da3/results/18-authz-matrix.md`; `docs/da3/evidence/2b-authz-matrix.png` |
| **2:50–3:00** | GitHub branch page, repository name and `assignment-3` branch visibly selected. End on a clean static page. | `https://github.com/KishorKumar15007/resume-ip/tree/assignment-3` (verify accessibility before recording). | “The repository, retained results and evidence are available on this assignment-3 branch. Thank you.” | Repository branch page; report cover branch-link field in `docs/da3/02-report.md` |

## Recording safeguards and honest disclosures

- The live portion is limited to the deployed synthetic MFA login and an
  unauthenticated 401 request. Do not show an active code, an access token,
  password, secret, QR code/manual key, database URL, or personal resume.
- Q1 benchmark/failure/scanning output must be recorded-result playback, not a
  fresh run. Say “recorded” where the table is historical evidence.
- The Q1 experiments are local Compose/Nginx measurements, not Cloud Run
  performance measurements. The Q1 load generator and Nginx shared one host.
- The 1c retry result is for the tested idempotent GET profile; do not claim
  retries are safe for upload POSTs.
- The cloud-burst diagram is a design proposal only. The selected 2c comparison
  is one backend API pair; do not say every application image was hardened.
- State only implemented controls: account lockout, replay protection, Nginx
  rate limiting and security-event logging are **NOT IMPLEMENTED**.

## Files changed

- `docs/da3/25-video-script.md`
