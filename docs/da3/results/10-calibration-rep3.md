# DA3 Step 10 Calibration

This is calibration only, not the Step 11 reported benchmark.

- Cleanup commands succeeded: None; final matching-container state known: None; no matching containers: None; overall cleanup verified: None.
- Environment ready for another test: True; three-backend restoration verified: True; run valid: False.
- Planned/ launched/ completed/ unknown/ skipped traffic is recorded in the JSON result.

| Instances | Concurrency | Status | Reason | Completed | Requests/s | Failed | Non-2xx | Eligible |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 1 | 5 | measured | — | 300 | 16.61 | 0 | 0 | no |
| 1 | 10 | measured | — | 300 | 24.80 | 0 | 0 | no |
| 1 | 20 | measured | — | 300 | 21.42 | 0 | 0 | no |
| 1 | 50 | warm-up failed; measured skipped | warm-up did not complete cleanly | — | — | — | — | no |
| 1 | 100 | warm-up failed; measured skipped | warm-up did not complete cleanly | — | — | — | — | no |
| 3 | 5 | measured | — | 300 | 15.78 | 0 | 0 | no |
| 3 | 10 | measured | — | 300 | 32.41 | 0 | 0 | no |
| 3 | 20 | measured | — | 300 | 50.14 | 0 | 0 | no |
| 3 | 50 | measured | — | 300 | 66.82 | 0 | 0 | no |
| 3 | 100 | measured | — | 300 | 64.68 | 0 | 0 | no |

No shared concurrency selected; calibration is incomplete, invalid, or ineligible.
