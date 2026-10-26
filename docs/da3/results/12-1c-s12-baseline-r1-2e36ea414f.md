# Step 12 failure-before-fix result

- Run ID: `s12-baseline-r1-2e36ea414f`
- Profile: `baseline`
- Repetition: `1`
- Completion: `complete`
- Error: `none recorded`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.074370400048792
- Kill exit / stopped verification: 0 / True

## Measured results

| Field | Value |
|---|---|
| AB completed requests | 1000 |
| AB failed requests | 298 |
| Connect / Receive / Length / Exceptions | 0 / 0 / 298 / 0 |
| AB non-2xx responses | 298 |
| Measured Nginx status counts | `{"200": 702, "502": 54, "504": 244}` |
| Measured Nginx 502 / 504 counts | 54 / 244 |
| Access diagnostic availability | readable |
| Nginx error-log availability | captured-no-matching-lines |

## Recovery and restoration

- Load-test cleanup verified: True
- Backend recovery: verified
- Canonical restoration: True

## Artifacts

- warmup_raw: `docs\da3\results\12-1c-s12-baseline-r1-2e36ea414f-warmup.txt`
- measured_raw: `docs\da3\results\12-1c-s12-baseline-r1-2e36ea414f-measured.txt`
- result_json: `docs\da3\results\12-1c-s12-baseline-r1-2e36ea414f.json`
- result_markdown: `docs\da3\results\12-1c-s12-baseline-r1-2e36ea414f.md`
- nginx_diagnostics: `docs\da3\results\12-1c-s12-baseline-r1-2e36ea414f-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\12-1c-s12-baseline-r1-2e36ea414f-nginx-errors.txt`
