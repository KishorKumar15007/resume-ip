# Step 12 failure-before-fix result

- Run ID: `s12-default-r1-a0c3a9b18e`
- Profile: `default`
- Repetition: `1`
- Completion: `incomplete`
- Error: `canonical three-backend restoration could not be verified`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.068534799967892
- Kill exit / stopped verification: 0 / True

## Measured results

| Field | Value |
|---|---|
| AB completed requests | 1000 |
| AB failed requests | 0 |
| Connect / Receive / Length / Exceptions | None / None / None / None |
| AB non-2xx responses | 0 |
| Measured Nginx status counts | `{"200": 1000}` |
| Measured Nginx 502 / 504 counts | 0 / 0 |
| Access diagnostic availability | readable |
| Nginx error-log availability | captured-no-matching-lines |

## Recovery and restoration

- Load-test cleanup verified: True
- Backend recovery: verified
- Canonical restoration: False

## Artifacts

- warmup_raw: `docs\da3\results\12-1c-s12-default-r1-a0c3a9b18e-warmup.txt`
- measured_raw: `docs\da3\results\12-1c-s12-default-r1-a0c3a9b18e-measured.txt`
- result_json: `docs\da3\results\12-1c-s12-default-r1-a0c3a9b18e.json`
- result_markdown: `docs\da3\results\12-1c-s12-default-r1-a0c3a9b18e.md`
- nginx_diagnostics: `docs\da3\results\12-1c-s12-default-r1-a0c3a9b18e-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\12-1c-s12-default-r1-a0c3a9b18e-nginx-errors.txt`
