# Step 13 resilient failover result

- Run ID: `s13-resilient-r1-b5b070786b`
- Profile: `resilient`
- Repetition: `1`
- Completion: `incomplete`
- Error: `availability probe CSV does not cover warm-up through post-recovery health`

## Protocol

- N: 1000
- C: 20
- Apache Bench flags: `-k -r`
- Reference throughput: 24.88 requests/second
- Estimated measured duration: 40.19 seconds (N / reference RPS)
- Scheduled kill offset: 12.06 seconds after observed AB start sentinel
- Actual kill elapsed: 12.081005899934098
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

- Availability probe: `{"csv": "docs\\da3\\results\\13-probe-resilient-rep1.csv", "started_at": "2026-10-26T16:19:43.662267+00:00", "state": "verified", "stopped_at": "2026-10-26T16:21:00.215086+00:00", "summary": {"failed_probes": 0, "first_sample_at": "2026-10-26T16:19:43.573191+00:00", "http_200": 343, "last_sample_at": "2026-10-26T16:20:59.752592+00:00", "longest_observed_gap_seconds": 0.38568997383117676, "non_200": 0, "timeouts": 0, "total_samples": 343, "transport_errors": 0}}`

## Artifacts

- warmup_raw: `docs\da3\results\13-1c-s13-resilient-r1-b5b070786b-warmup.txt`
- measured_raw: `docs\da3\results\13-1c-s13-resilient-r1-b5b070786b-measured.txt`
- result_json: `docs\da3\results\13-1c-s13-resilient-r1-b5b070786b.json`
- result_markdown: `docs\da3\results\13-1c-s13-resilient-r1-b5b070786b.md`
- nginx_diagnostics: `docs\da3\results\13-1c-s13-resilient-r1-b5b070786b-nginx-diagnostics.json`
- nginx_errors: `docs\da3\results\13-1c-s13-resilient-r1-b5b070786b-nginx-errors.txt`
- probe_csv: `docs\da3\results\13-probe-resilient-rep1.csv`
- probe_stop: `docs\da3\results\.13-probe-resilient-rep1.stop`
