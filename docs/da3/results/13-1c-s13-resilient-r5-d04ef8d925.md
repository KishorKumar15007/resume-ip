# Step 13 resilient failover result

- Run ID: `s13-resilient-r5-d04ef8d925`
- Profile: `resilient`
- Repetition: `5`
- Completion: `complete`
- Error: `none recorded`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.073590900050476
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

- Availability probe: `{"coverage": "verified", "coverage_summary": {"failed_probes": 0, "first_sample_at": "2026-10-26T16:36:19.601187+00:00", "http_200": 362, "last_sample_at": "2026-10-26T16:37:42.472163+00:00", "longest_observed_gap_seconds": 0.5707640647888184, "non_200": 0, "timeouts": 0, "total_samples": 362, "transport_errors": 0}, "csv": "docs\\da3\\results\\13-probe-resilient-rep5.csv", "started_at": "2026-10-26T16:36:19.719587+00:00", "state": "verified", "stopped_at": "2026-10-26T16:37:42.758502+00:00", "summary": {"failed_probes": 0, "first_sample_at": "2026-10-26T16:36:19.601187+00:00", "http_200": 362, "last_sample_at": "2026-10-26T16:37:42.472163+00:00", "longest_observed_gap_seconds": 0.5707640647888184, "non_200": 0, "timeouts": 0, "total_samples": 362, "transport_errors": 0}}`

## Artifacts

- warmup_raw: `docs\da3\results\13-1c-s13-resilient-r5-d04ef8d925-warmup.txt`
- measured_raw: `docs\da3\results\13-1c-s13-resilient-r5-d04ef8d925-measured.txt`
- result_json: `docs\da3\results\13-1c-s13-resilient-r5-d04ef8d925.json`
- result_markdown: `docs\da3\results\13-1c-s13-resilient-r5-d04ef8d925.md`
- nginx_diagnostics: `docs\da3\results\13-1c-s13-resilient-r5-d04ef8d925-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\13-1c-s13-resilient-r5-d04ef8d925-nginx-errors.txt`
- probe_csv: `docs\da3\results\13-probe-resilient-rep5.csv`
- probe_stop: `docs\da3\results\.13-probe-resilient-rep5.stop`
