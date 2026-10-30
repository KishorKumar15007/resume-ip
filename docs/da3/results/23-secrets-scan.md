# DA3 Step 23 secrets scan

Overall result: **FAIL**

Container image: `zricethezav/gitleaks:v8.18.4` (version-pinned; not `latest`).
The scanner mounts the repository read-only, uses no network after image availability, and writes only redacted temporary JSON outside the repository.

| Scan | Complete | Findings | Exit status | Diagnostic |
| --- | --- | ---: | ---: | --- |
| Git history (--all) | yes | 4 | 1 | complete |
| working tree | yes | 5 | 1 | complete |

## Targeted pattern checks

These checks record paths/counts only; they never write matching text or values.

| Pattern | Working-tree files | History commits |
| --- | --- | ---: |
| neon_host | `.agent/CONTINUITY.md`, `local/da3.md` | 0 |
| postgresql_password_url | `DEPLOYMENT.md`, `backend/.env.example` | 0 |
| jwt_secret_assignment | `backend/.env.example` | 2 |
| mfa_key_assignment | `backend/.env.example` | 1 |

No secret values, URLs, token text, or raw Gitleaks reports are retained in this result.
