# DA3 Step 18 Authorization Matrix

Run: `s18-20261029-084722`
Attempt: `1`
Phase: **complete**
Overall: **PASS**

| Request | Token type | Expected | Actual | PASS/FAIL |
| --- | --- | --- | --- | --- |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | No token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Malformed token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Expired token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Signature-tampered token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | MFA-scope token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | No token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Malformed token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Expired token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Signature-tampered token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | MFA-scope token | HTTP 401; WWW-Authenticate: Bearer | HTTP 401; WWW-Authenticate: Bearer | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Candidate A access token | HTTP 403 | HTTP 403 | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Recruiter B non-owner access token | HTTP 403 | HTTP 403 | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Candidate A access token | HTTP 403 | HTTP 403 | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Recruiter B non-owner access token | HTTP 403 | HTTP 403 | PASS |
| PUT /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Recruiter A owner access token | HTTP 200 | HTTP 200 | PASS |
| GET /submissions/91e77743-21a8-56b1-8306-711a900bb948 | Candidate A access token | HTTP 200 | HTTP 200 | PASS |
| GET /submissions/91e77743-21a8-56b1-8306-711a900bb948 | Candidate B access token | HTTP 403 | HTTP 403 | PASS |
| GET /submissions/91e77743-21a8-56b1-8306-711a900bb948 | Recruiter A owner access token | HTTP 200 | HTTP 200 | PASS |
| GET /submissions/91e77743-21a8-56b1-8306-711a900bb948 | Recruiter B non-owner access token | HTTP 403 | HTTP 403 | PASS |
| GET /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162/submissions | Recruiter A owner access token | HTTP 200 | HTTP 200 | PASS |
| GET /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162/submissions | Recruiter B non-owner access token | HTTP 403 | HTTP 403 | PASS |
| DELETE /postings/7be1c1fa-d050-5322-8bfd-8517ef58f162 | Recruiter A owner access token | HTTP 204 | HTTP 204 | PASS |

Tokens, passwords, connection strings, and response bodies are intentionally omitted.
