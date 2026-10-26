# Step 12 failure-before-fix result

- Run ID: `s12-baseline-r3-db7ba83bd0`
- Profile: `baseline`
- Repetition: `3`
- Completion: `complete`
- Error: `none recorded`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.06448379997164
- Kill exit / stopped verification: 0 / True

## Measured results

| Field | Value |
|---|---|
| AB completed requests | 1000 |
| AB failed requests | 280 |
| Connect / Receive / Length / Exceptions | 0 / 0 / 280 / 0 |
| AB non-2xx responses | 280 |
| Measured Nginx status counts | `{"200": 720, "502": 69, "504": 211}` |
| Measured Nginx 502 / 504 counts | 69 / 211 |
| Access diagnostic availability | readable |
| Nginx error-log availability | captured-no-matching-lines |

## Recovery and restoration

- Load-test cleanup verified: True
- Backend recovery: verified
- Canonical restoration: True

## Artifacts

- warmup_raw: `docs\da3\results\12-1c-s12-baseline-r3-db7ba83bd0-warmup.txt`
- measured_raw: `docs\da3\results\12-1c-s12-baseline-r3-db7ba83bd0-measured.txt`
- result_json: `docs\da3\results\12-1c-s12-baseline-r3-db7ba83bd0.json`
- result_markdown: `docs\da3\results\12-1c-s12-baseline-r3-db7ba83bd0.md`
- nginx_diagnostics: `docs\da3\results\12-1c-s12-baseline-r3-db7ba83bd0-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\12-1c-s12-baseline-r3-db7ba83bd0-nginx-errors.txt`
