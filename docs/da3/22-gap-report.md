# DA3 Step 22 — Evidence and submission gap audit

## Scope and method

This documentation-only re-audit reconciles [`01-checklist.md`](01-checklist.md), [`04-evidence-index.md`](04-evidence-index.md), [`02-report.md`](02-report.md), `docs/da3/results/`, and `docs/da3/evidence/`. It performs no runtime command, capture, database operation, or source/configuration change. Code and retained result artifacts take precedence over project-record prose.

Table provenance was checked against the retained artifacts and generators: [`scripts/aggregate_1a_request_mix.py`](scripts/aggregate_1a_request_mix.py) produces `results/07-request-mix-table.md`; [`scripts/aggregate_1b.py`](scripts/aggregate_1b.py) produces `results/11-1b-table.md`; [`scripts/aggregate_1c.py`](scripts/aggregate_1c.py) produces `results/13-1c-table.md`; and [`scripts/aggregate_2c.py`](scripts/aggregate_2c.py) produces the Step 20 comparison after accepted inputs. Table 1d.1 is sourced from [`results/14-components-table.md`](results/14-components-table.md); Tables 2a.1, 2a.2, 2b.1, and 2d.1 cite their retained inventory, verifier, flow, matrix, and source-evidence artifacts below.

## Per-part reconciliation

| Part | Checklist items by status | Report tables, sources, and scripts | Indexed screenshots versus files present | Remaining gap verdict |
| --- | --- | --- | --- | --- |
| 1a | All listed items are `[x]`. | Request-mix table: `results/07-request-mix-table.md` / `aggregate_1a_request_mix.py`; distribution table: `results/09-distribution.md` / `distribution_test.py`. | The indexed Step 7–9 PNGs, including `1a-xservedby-header.png`, are present. The owner-censored `1a-seed-output.png` is present and indexed as captured/redacted. | Closed for Step 22. |
| 1b | Final Step 11 comparison items are `[x]`; calibration/connection-explanation items remain `[~]`. | Table 1b.2: `results/11-1b-table.md` / `aggregate_1b.py`; accepted manifest `results/11-1b-manifest-s11-20261024t093248z-c7a71d7b.json`. | Final-result, calibration, validation, and live-load captures indexed for 1b are present. Historical diagnostic references remain unavailable where the index says unavailable. | Retained experimental limitation, not an open Step 22 action. |
| 1c | All listed items are `[x]`. | Table 1c.1: `results/13-1c-table.md` / `aggregate_1c.py`; raw run and probe artifacts are retained under `results/13-1c-*`. | All indexed 1c PNGs are present. | **No open 1c acceptance gap.** Resilient reps 4–6 each record 1,000 complete, **0 failed**, and **0 non-2xx**. Their probe totals/failures are 336/0, 362/0, and 374/0. Reported kill/gap display values are rounded; `results/13-1c-table.md` is the numeric authority. |
| 1d | Diagram/table items are `[x]`; explanation/reason items are `[~]` because the owner must rewrite the draft. | Table 1d.1: `results/14-components-table.md`; design artifacts: `diagrams/q1-architecture.svg` and `diagrams/q1-architecture-hand-draw.md`. | `evidence/1d-architecture-diagram.png` is present, non-empty, indexed as captured, and linked from the report. | **Step 24:** owner rewrite of `1d-explanation.md`. The components-and-ports table exists. |
| 2a | All listed items are `[x]`. | Tables 2a.1/2a.2: `sensitive-data-inventory.md` and `results/15-argon2-check.md`; queries/scripts are retained in `scripts/2a_*` and `scripts/argon2_check.py`. | Indexed before-demo, after-hash, cleanup, salt-proof, and Argon2 captures are present. | No identified result-table or capture gap. The before table remains an explicitly labelled demonstration, not historical application data. |
| 2b | All listed items are `[x]`. | MFA flow table: `results/16-mfa-flow.md` / `scripts/mfa_flow_test.py`; authorization matrix: `results/18-authz-matrix.md` and `.json` / `scripts/authz_matrix.py`. | All indexed Step 16–18 captures are present. `2b-authenticator-phone.jpg` is present and indexed as captured; this audit checked JPEG file markers only, not its content. | No capture gap identified. Step 18 remains limited to the documented posting/submission authorization paths. |
| 2c | Scan/hardening items are `[x]`; the broad app-regression item remains `[~]`. | Tables 2c.1/2c.2: `results/20-2c-table.md`, raw Trivy JSON, and metadata / `aggregate_2c.py`. Hardened smoke: `results/20-smoke-hardened.md`; hardened MFA regression: `results/20-mfa-hardened-regression.md`. | All indexed baseline/hardening/smoke images are present. No separate hardened-MFA screenshot exists; the passing result file is indexed as a verified artifact, not a screenshot. | **Step 22b:** no accepted hardened authorization-matrix, upload, or worker-processing result exists; retain them as unverified pending the live-deployed test. |
| 2d | All listed items are `[x]`. | Table 2d.1: `2d-threat-controls.md`, with code paths and retained results including `results/18-authz-matrix.md`. | No distinct new screenshot is required; the table cites retained 2a/2b evidence. | The required result table is present. This part uses a source/evidence table rather than a standalone generated `results/` table. |
| 22b / overall | Step 22b, README, clean-clone, secrets scan, PDF, video, and branch-accessibility items are `[ ]`. | No Step 22b result artifact exists. | `env-cloudrun-latest-revision.png` and `env-deployed-otp-login.png` remain indexed as **needed**; this task deliberately leaves them untouched. | **Step 22b / Step 23/24:** outstanding submission and live-deployment work remains. |

## Screenshot and evidence inventory

The present evidence directory contains the indexed 1a–2c files named above. The reconciliation confirms the corrected 1d architecture PNG and the added `2b-authenticator-phone.jpg`; the latter is a valid JPEG by file markers only. The following indexed items remain needed or otherwise non-final:

| Indexed item | State from index/files | Gap classification |
| --- | --- | --- |
| `evidence/env-local-upload-done.png` | needed; absent | Scope-excluded Step 5 workflow; not evidence for a claimed upload/scoring result |
| `evidence/env-cloudrun-latest-revision.png` | needed; absent | **Step 22b** |
| `evidence/env-deployed-otp-login.png` | needed; absent | **Step 22b** |
| `evidence/env-hosting-status.png` | needed; absent | Conditional Step 6B capture; current records describe Step 6A, not a Cloud Run outage |
| `results/10-health-and-postings-diagnostics.txt` and `results/10-queuepool-nginx-correlation.txt` | indexed as unavailable | Historical 1b diagnostic gaps; do not recreate or imply a causal explanation |
| `evidence/1a-seed-output.png` | present; owner-censored and indexed as captured/redacted | Closed for Step 22 |
| `1d-explanation.md` | present; owner rewrite pending | **Step 24** |
| hardened authorization-matrix/upload/worker regression evidence | no corresponding accepted result artifact | **Step 22b** live-deployed test |
| README, clean-clone, secrets scan, PDF, video, branch-accessibility deliverables | checklist pending | **Step 23/24** |

## Report TODO(evidence) and specificity review

The remaining `TODO(evidence)` markers in [`02-report.md`](02-report.md) are final-audit/submission work (**Step 23/24**). The completed seed-output redaction TODO was removed after the owner-censored capture was checked.

The substantive explanation paragraphs now identify portal-specific material: `GET /postings`/Nginx in 1a, the Step 11 manifest and Apache Bench in 1b, the resilient Nginx retry/probe configuration in 1c, the Compose/Neon placement model in 1d, `hash_password`/`verify_password` in 2a, `/auth/mfa/verify` in 2b, `resume-backend:da3-prehardening` and `resume-backend:da3-hardened` plus `results/20-2c-table.md` in 2c, and `get_current_user`, `GET /submissions/{submission_id}`, and `results/18-authz-matrix.md` in 2d. No additional explanation paragraph was found that is both substantive and without an application-specific endpoint, container, table, or retained artifact reference.

## Numeric and result checks

- Every part 1a–2d has at least one report result/evidence table.
- `results/13-1c-table.md` is authoritative for the 1c values. It records zero failed requests and zero non-2xx responses in every accepted after repetition (4, 5, and 6); this requirement is satisfied.
- The accepted availability-probe rows record zero failed probes (336/0, 362/0, and 374/0). This is sampled evidence, not an absolute availability guarantee.
- `results/20-2c-table.md` has Trivy rows for the backend, worker, and separately Dockerfile-based frontend; the frontend is explicitly an unchanged exclusion from backend hardening, not an omitted image.
- `results/14-components-table.md` exists and supplies Table 1d.1.
- The report’s displayed 1c kill times and longest gaps are labelled as six-decimal rounded values, while `results/13-1c-table.md` retains the full precision. Other headline comparison values are either present in their result table or explicitly derived/labelled as illustrative arithmetic (for example the Step 14 capacity calculation).

The audit found no unlabelled measured-result number in the report that lacks a retained result source. Values whose displayed textual form is derived rather than a raw-result field are labelled accordingly: the 1c six-decimal display values derive from the full-precision 1c table; the Step 11 improvement factors/percentages derive from Table 1b.2; and the Step 14 8.2933-per-backend and nine/six-instance figures are explicitly illustrative arithmetic from the recorded 24.88 requests/s and placement-drive assumptions.

## Discrepancies resolved or retained

1. The prior Step 22 gap report said the 1d PNG and authenticator-phone capture were absent. Both are now present and indexed using their actual filenames; that older statement is superseded.
2. `results/20-mfa-hardened.md` records a topology-preflight failure, whereas the newer `results/20-mfa-hardened-regression.md` records the full hardened MFA PASS. The report now distinguishes those artifacts and cites the later passing regression result; no authorization-matrix or upload/worker success is inferred.
3. No source/result disagreement was found for the accepted 1c zero-failure and probe claims, the 1d components-table claim, or the per-application-image Trivy coverage claim.

## Prioritised remaining gaps

1. **Step 22b:** redeploy the latest intended services, retain the two specified Cloud Run/OTP captures, and perform only the live-deployed authorization/upload/worker checks that have no accepted result artifact.
2. **Step 23/24:** owner rewrite of `1d-explanation.md`; then README/reproduction review, clean-clone test, secrets scan, final PDF, video, and accessible branch confirmation.

**Step 22: closed. Remaining items are Step 22b and Step 23/24.**

## Claims verified

- Directory inventory confirmed the actual 1d PNG, `2b-authenticator-phone.jpg`, retained result artifacts, and absence of the two Step 22b evidence files.
- `results/13-1c-table.md` confirmed all accepted after repetitions have zero failed/non-2xx responses and zero failed probe samples.
- `results/20-2c-table.md` confirmed Trivy coverage rows for backend, worker, frontend, prehardening, and hardened API images.
- `results/20-mfa-hardened-regression.md` confirmed the retained hardened MFA-flow PASS; no runtime command was rerun.
- The checklist, evidence index, report tables, and cited generator/source paths were cross-checked without exposing secret values.
