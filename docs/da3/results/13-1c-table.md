# DA3 1c before/after failover comparison

Failure rate = AB failed requests / AB complete requests × 100.

| Set | Rep | Complete | Failed | Connect/Receive/Length/Exceptions | Non-2xx | 5xx (502/504) | RPS | Failure rate | Kill s | Recovery / restoration | Probe total / failed / longest gap s |
|---|---:|---:|---:|---|---:|---|---:|---:|---:|---|---|
| baseline | 1 | 1000 | 298 | 0/0/298/0 | 298 | 298 (54/244) | 10.89 | 29.8000% | 12.074370400048792 | verified / True | n/a |
| baseline | 2 | 1000 | 294 | 0/0/294/0 | 294 | 294 (42/252) | 13.93 | 29.4000% | 12.066727500059642 | verified / True | n/a |
| baseline | 3 | 1000 | 280 | 0/0/280/0 | 280 | 280 (69/211) | 14.74 | 28.0000% | 12.06448379997164 | verified / True | n/a |
| resilient | 4 | 1000 | 0 | None/None/None/None | 0 | 0 (0/0) | 23.38 | 0.0000% | 12.076162500074133 | verified / True | 336 / 0 / 0.3824751377105713 |
| resilient | 5 | 1000 | 0 | None/None/None/None | 0 | 0 (0/0) | 23.52 | 0.0000% | 12.073590900050476 | verified / True | 362 / 0 / 0.5707640647888184 |
| resilient | 6 | 1000 | 0 | None/None/None/None | 0 | 0 (0/0) | 23.25 | 0.0000% | 12.208897599950433 | verified / True | 374 / 0 / 0.6069519519805908 |
| baseline median | — | 1000 | 294 | — | 294 | 294 | 13.93 | 29.4000% | — | — | — |
| resilient median | — | 1000 | 0 | — | 0 | 0 | 23.38 | 0.0000% | — | — | — |
