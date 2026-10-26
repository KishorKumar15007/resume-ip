# Step 13 resilient failover result

- Run ID: `s13-resilient-r4-fdbf8e5410`
- Profile: `resilient`
- Repetition: `4`
- Completion: `complete`
- Error: `none recorded`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.076162500074133
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
- Canonical restoration: True

- Availability probe: `{"coverage": "verified", "coverage_summary": {"failed_probes": 0, "first_sample_at": "2026-10-26T16:34:00.648107+00:00", "http_200": 336, "last_sample_at": "2026-10-26T16:35:16.864842+00:00", "longest_observed_gap_seconds": 0.3824751377105713, "non_200": 0, "timeouts": 0, "total_samples": 336, "transport_errors": 0}, "csv": "docs\\da3\\results\\13-probe-resilient-rep4.csv", "started_at": "2026-10-26T16:34:00.724936+00:00", "state": "verified", "stopped_at": "2026-10-26T16:35:17.123373+00:00", "summary": {"failed_probes": 0, "first_sample_at": "2026-10-26T16:34:00.648107+00:00", "http_200": 336, "last_sample_at": "2026-10-26T16:35:16.864842+00:00", "longest_observed_gap_seconds": 0.3824751377105713, "non_200": 0, "timeouts": 0, "total_samples": 336, "transport_errors": 0}}`

## Artifacts

- warmup_raw: `docs\da3\results\13-1c-s13-resilient-r4-fdbf8e5410-warmup.txt`
- measured_raw: `docs\da3\results\13-1c-s13-resilient-r4-fdbf8e5410-measured.txt`
- result_json: `docs\da3\results\13-1c-s13-resilient-r4-fdbf8e5410.json`
- result_markdown: `docs\da3\results\13-1c-s13-resilient-r4-fdbf8e5410.md`
- nginx_diagnostics: `docs\da3\results\13-1c-s13-resilient-r4-fdbf8e5410-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\13-1c-s13-resilient-r4-fdbf8e5410-nginx-errors.txt`
- probe_csv: `docs\da3\results\13-probe-resilient-rep4.csv`
- probe_stop: `docs\da3\results\.13-probe-resilient-rep4.stop`
