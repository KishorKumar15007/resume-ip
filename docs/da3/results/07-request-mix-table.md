# DA3 1a Request Mix

**Scenario assumptions, not observations.**

| method | path | category | per student | total requests | share of total | average requests/s |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| POST | `/auth/login` | write | 1 | 2000 | 4.55% | 3.33 |
| GET | `/postings` | read | 15 | 30000 | 68.18% | 50.00 |
| GET | `/submissions/{submission_id}` | read | 5 | 10000 | 22.73% | 16.67 |
| POST | `/postings/{posting_id}/submissions` | write | 1 | 2000 | 4.55% | 3.33 |

- Students: 2000
- Peak window: 600 seconds
- Read requests: 40000
- Total HTTP requests: 44000
- Average total request rate: 73.33 requests/s
- Shares and rates are rounded with ROUND_HALF_UP to 2 and 2 decimal places respectively.
