# DA3 Step 16 MFA Flow Test

Overall: **PASS**

| Step | Expected | Actual |
| --- | --- | --- |
| Preflight local DA3 API | HTTP 200 from a DA3 backend | HTTP 200 |
| Validate local DA3 target | backend instance identity | backend identity present |
| Validate host clock | UTC clock available | UTC clock available |
| Validate backend-1 clock | within 5 seconds of the host clock | clock aligned |
| Validate backend-2 clock | within 5 seconds of the host clock | clock aligned |
| Validate backend-3 clock | within 5 seconds of the host clock | clock aligned |
| Register synthetic MFA user | HTTP 201 | HTTP 201 |
| Login before MFA enrolment | HTTP 200 with access token | HTTP 200 |
| Set up MFA | HTTP 200 with in-memory provisioning URI | HTTP 200 |
| Confirm MFA | HTTP 200 | HTTP 200 |
| Login after MFA enrolment | HTTP 200 with MFA challenge | HTTP 200 |
| Validate MFA login challenge | MFA token only | MFA challenge fields present |
| Reject MFA token on protected route | HTTP 401 | HTTP 401 |
| Verify MFA token and code | HTTP 200 with access token | HTTP 200 |
| Use verified access token | HTTP 200 | HTTP 200 |
| Reject invalid MFA code | HTTP 401 | HTTP 401 |
| Reject wrong-scope access token | HTTP 401 | HTTP 401 |
| Reject malformed MFA token | HTTP 401 | HTTP 401 |
| Reject invalidly signed MFA token | HTTP 401 | HTTP 401 |
| Reject expired MFA token | HTTP 401 | HTTP 401 |
| Clean up synthetic MFA user | exactly one created user removed | rows deleted: 1 |

Tokens, provisioning URIs, TOTP secrets, Fernet keys, and connection details are intentionally omitted.
