# DA3 Q2(a) — Sensitive-data inventory

This is a concise inventory of the current resume portal implementation. It does not list real records, environment values, or credentials.

| Data | Current location | Sensitivity and reason | Repository evidence / access boundary |
| --- | --- | --- | --- |
| Resume PDF content | Private Cloud Storage object; the `submissions.storage_path` field records the controlled object URI | **Highest sensitivity.** A resume can contain a person's name, contact details, education and employment history. | `backend/app/services/gcs_storage.py` limits object names to server-generated submission PDFs. `backend/app/routers/submissions.py` restricts status access to the submitting candidate or the posting's recruiter. Object-level IAM/runtime verification is UNKNOWN. |
| Password verifier | `users.password_hash` | **High sensitivity.** It is an authentication verifier and must not be exposed, even though the application stores an Argon2id hash rather than plaintext. | `backend/app/core/security.py` uses `argon2.PasswordHasher()`; `backend/app/routers/auth.py` hashes on signup and verifies on login. |
| User email address and role | `users.email`, `users.role` | Personal contact/identity data; role affects application authorization. | `backend/app/models/user.py`; authenticated user identity is derived from a verified JWT in `backend/app/core/dependencies.py`. |
| Submission status, score and matched skills | `submissions.status`, `submissions.score`, `submissions.matched_skills` | Can reveal a candidate's application progress and assessment outcome. | `backend/app/models/submission.py`; `backend/app/routers/submissions.py` enforces candidate ownership or recruiter posting ownership before returning status data. |
| Job-posting title, description and required skills | `job_postings` | Business/recruitment content; it may reveal hiring requirements and can be linked to recruiter identity. | `backend/app/models/job_posting.py`; write/update/delete actions require a recruiter and posting ownership in `backend/app/routers/postings.py`. |

## Security configuration and future data

- The JWT signing configuration is a security secret, not application-row data. It is loaded by `SecuritySettings` in `backend/app/core/security.py` and must never appear in SQL output, screenshots, source artifacts or documentation.
- TOTP secrets are **future Step 16 data**. No repository evidence currently establishes a stored TOTP secret or MFA enrollment record.
- The repository supports Cloud Storage-backed resume handling, but exact live bucket access policy, retained object contents and deployment IAM configuration are **UNKNOWN** from static source inspection.

## Q2(a) evidence boundary

The planned before-state table is an explicitly labelled demonstration only: the application did **not** historically store plaintext passwords. The after-state evidence must be limited to the two later synthetic `da3-salt-*` accounts, with no unrelated user hashes exported.
