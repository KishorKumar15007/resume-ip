# docs/da3: what this folder is and why it exists

## Why we are doing all this
This is Digital Assignment 3 (BACSE344). It is graded per part (1a, 1b, 1c, 1d, 2a, 2b, 2c, 2d) with one rule: full marks if the feature works AND there are screenshots/tables AND a clear explanation specific to this app; HALF marks if evidence or explanation is missing or generic; zero if it doesn't work. Working code alone scores half. The final submission is (1) a PDF report with screenshots, result tables for every part and the GitHub link to branch assignment-3, and (2) a 3-minute demo video. This folder is where the report and every piece of proof are built up step by step, so the report is assembled from real evidence instead of being written from memory at the end.

## What each file is for
| Path | Purpose |
|---|---|
| 00-question.md | The official question, verbatim. The source of truth for what is required. |
| 01-checklist.md | One line per requirement. [ ] not started, [~] built but evidence missing, [x] built AND evidenced. Never mark [x] because code "looks right". |
| 02-report.md | The report being written progressively, one section per part (Requirement / What I built / Commands run / Result / Evidence / Explanation / Honesty notes). This becomes the submitted PDF. |
| 03-decisions-log.md | Every decision with the reason and the rejected alternatives (why Neon, why this concurrency, why this baseline). Decisions are recorded when made. |
| 04-evidence-index.md | One row per screenshot: filename, what it must show, exact command or page, status (needed / captured). The master list of what proof exists. |
| audit.md | The Step 1 audit of the repository (facts with file paths). |
| DA3_PLAN.md | The overall plan, planned defaults, checklist items and report template. |
| STANDING_RULES.md | Earlier rules block; AGENTS.md now carries the permanent rules. |
| evidence/ | Screenshots taken by the user, named <part>-<what>.png (for example env-neon-tables.png, 1a-compose-ps.png). Codex never creates, renames, edits or deletes these. |
| results/ | RAW output of scripts and tests (smoke JSON/MD, load-test output, scan JSON, Nginx logs). Tables in the report must be generated from these files. |
| scripts/ | Scripts that produce results/ files and tables. |

## Precedence
If DA3_PLAN.md or STANDING_RULES.md disagree with this README or AGENTS.md, this README and AGENTS.md win. In particular: DA3_PLAN.md section 4.4 ("every prompt updates the docs") and section 4.6 now apply ONLY to prompts titled "DOCS UPDATE". Code prompts never edit docs/da3/ report files. DA3_PLAN.md remains the reference for the checklist items (4.2), the report template (4.3), the planned defaults (3) and the roadmap numbering (5).

## The chain every report part must have
Requirement -> implementation -> experiment or demonstration -> raw output in results/ -> table generated from it -> screenshot in evidence/ -> explanation that names this app's real components. If any link is missing, that part loses marks.

## How a DOCS UPDATE is done (when told "DOCS UPDATE for step N")
1. Do not change code, config, scripts, images or results. Docs only.
2. Read the result files named in the prompt yourself. Never trust numbers typed in a prompt, never estimate, round or invent. A number appears in the report only if it is in a results/ file; cite the file name under the table. If a generator script exists, run it; otherwise build the table from the raw file.
3. Fill the part's section in 02-report.md using the seven fields. Insert any prose supplied in the prompt verbatim. Replace {{from results/...}} placeholders with values read from the named file. Leave TODO(evidence) wherever evidence is missing; never fill a gap with plausible text.
4. Embed screenshots by relative link with a numbered caption, and only for files that exist.
5. Update 01-checklist.md: [x] only if the code is verified AND every required result file and screenshot exists; otherwise [~]. State the reason for every item you do not tick.
6. Update 04-evidence-index.md: status needed -> captured only for files that exist AND passed the capture check below. Add rows for evidence files that exist but are not listed.
7. Log decisions in 03-decisions-log.md (date, step, decision, reason, alternatives rejected).
8. Update .agent/CONTINUITY.md with FACT / DECISION / UNKNOWN lines (no transcript, no secrets).
9. End with: files changed, remaining TODO(evidence), capture-check results, final git status. Do not commit.

## How to verify a capture (do this in every DOCS UPDATE and when asked)
For every screenshot row in 04-evidence-index.md and every file in evidence/:
- exists, is a real PNG (check the file signature), is not empty or tiny, and its name follows <part>-<what>.png in lowercase;
- is not a byte-identical duplicate of another evidence file (compare hashes);
- is listed in the index; if not, report it;
- if you can open images: check it actually shows what the "must show" column says (command AND output visible, a timestamp where required, the real container/endpoint/table names), and check that any numbers visible agree with the matching results/ file;
- if you can open images: check that NO secret is visible (database URL or password, JWT, encryption key, TOTP secret, full access token). If one is visible, flag it as SECRET RISK;
- if you cannot open images, say "NOT VISUALLY VERIFIED"; never claim a capture is correct from its filename alone.
Report one line per file: OK / PROBLEM / NEEDS HUMAN CHECK, with the reason. Never fix, rename, move or delete an image; the user retakes it.

## Integrity rules (always)
- No invented, estimated or hand-typed results. Unknown is a valid state; write UNKNOWN or TODO(evidence).
- Never record a demo or experimental baseline as real history (for example the 2a plaintext table is a labelled demo; Argon2 has been used since DA1).
- No secrets (database URLs, JWT/encryption keys, TOTP secrets, tokens) in any doc, result or log.
- Synthetic data only.
