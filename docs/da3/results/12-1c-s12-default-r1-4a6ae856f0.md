# Step 12 failure-before-fix result

- Run ID: `s12-default-r1-4a6ae856f0`
- Profile: `default`
- Repetition: `1`
- Completion: `incomplete`
- Error: `fresh token acquisition failed (sanitized)`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: None
- Kill exit / stopped verification: None / None

## Measured results

| Field | Value |
|---|---|
| AB completed requests | None |
| AB failed requests | None |
| Connect / Receive / Length / Exceptions | None / None / None / None |
| AB non-2xx responses | None |
| Measured Nginx status counts | `{}` |
| Measured Nginx 502 / 504 counts | None / None |
| Access diagnostic availability | not captured |
| Nginx error-log availability | not captured |

## Recovery and restoration

- Load-test cleanup verified: None
- Backend recovery: not reached
- Canonical restoration: not needed

## Artifacts

- warmup_raw: `docs\da3\results\12-1c-s12-default-r1-4a6ae856f0-warmup.txt`
- measured_raw: `docs\da3\results\12-1c-s12-default-r1-4a6ae856f0-measured.txt`
- result_json: `docs\da3\results\12-1c-s12-default-r1-4a6ae856f0.json`
- result_markdown: `docs\da3\results\12-1c-s12-default-r1-4a6ae856f0.md`
- nginx_diagnostics: `docs\da3\results\12-1c-s12-default-r1-4a6ae856f0-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\12-1c-s12-default-r1-4a6ae856f0-nginx-errors.txt`
