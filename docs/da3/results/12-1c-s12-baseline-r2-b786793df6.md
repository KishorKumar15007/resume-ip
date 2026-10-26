# Step 12 failure-before-fix result

- Run ID: `s12-baseline-r2-b786793df6`
- Profile: `baseline`
- Repetition: `2`
- Completion: `complete`
- Error: `none recorded`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.066727500059642
- Kill exit / stopped verification: 0 / True

## Measured results

| Field | Value |
|---|---|
| AB completed requests | 1000 |
| AB failed requests | 294 |
| Connect / Receive / Length / Exceptions | 0 / 0 / 294 / 0 |
| AB non-2xx responses | 294 |
| Measured Nginx status counts | `{"200": 706, "502": 42, "504": 252}` |
| Measured Nginx 502 / 504 counts | 42 / 252 |
| Access diagnostic availability | readable |
| Nginx error-log availability | captured-no-matching-lines |

## Recovery and restoration

- Load-test cleanup verified: True
- Backend recovery: verified
- Canonical restoration: True

## Artifacts

- warmup_raw: `docs\da3\results\12-1c-s12-baseline-r2-b786793df6-warmup.txt`
- measured_raw: `docs\da3\results\12-1c-s12-baseline-r2-b786793df6-measured.txt`
- result_json: `docs\da3\results\12-1c-s12-baseline-r2-b786793df6.json`
- result_markdown: `docs\da3\results\12-1c-s12-baseline-r2-b786793df6.md`
- nginx_diagnostics: `docs\da3\results\12-1c-s12-baseline-r2-b786793df6-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\12-1c-s12-baseline-r2-b786793df6-nginx-errors.txt`
