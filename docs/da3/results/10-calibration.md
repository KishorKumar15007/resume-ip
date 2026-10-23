# DA3 Step 10 Calibration

This is calibration only, not the Step 11 reported benchmark.

- Apache Bench used `-k` for every warm-up and measured run.
- Warm-up: 100 requests per point; measured run: 300 requests per point.
- Requests/s is Apache Bench `Requests per second`; average response time is its first `Time per request (mean)` value.
- Docker CPU percentage is approximately relative to one full core; a backend limited to 0.5 CPU can appear near 50% when saturated.
- Planned traffic: 1000 warm-up + 3000 measured = 4000 total.
- Launched budgets: 400 warm-up + 900 measured.
- Apache Bench-reported completed: 300 warm-up + 900 measured; unreported/unknown: 100 warm-up + 0 measured.

| Instances | Concurrency | Measured requests | Requests/s | Average response time (ms) | Failed | Non-2xx | % of own maximum | Eligible |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 5 | 300 | 10.49 | 476.725 | 0 | 0 | — | no |
| 1 | 10 | 300 | 17.18 | 582.220 | 0 | 0 | — | no |
| 1 | 20 | 300 | 16.13 | 1239.827 | 0 | 0 | — | no |
| 1 | 50 | — | — | — | — | — | — | no |

Calibration incomplete: warm-up did not complete cleanly; no shared concurrency can be selected from this run.

Observed equal backend limits: {'backends': {'backend-1': {'nano_cpus': 500000000, 'memory_bytes': 536870912}, 'backend-2': {'nano_cpus': 500000000, 'memory_bytes': 536870912}, 'backend-3': {'nano_cpus': 500000000, 'memory_bytes': 536870912}}, 'equal_across_backends': True, 'uvicorn_workers_per_backend': 1}.

Three-backend restoration verified: yes.
