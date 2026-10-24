generated-by: docs/da3/scripts/aggregate_1b.py

# DA3 Step 11: one versus three backend instances

| Ordinal | Topology | Rep | Status | RPS | Mean ms | Failed | Non-2xx | Nginx statuses | Median |
| ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 1 | 1 | complete | 10.29 | 1943.935 | 0 | 0 | complete: 200:1000 | yes |
| 2 | 3 | 1 | complete | 24.88 | 803.911 | 0 | 0 | complete: 200:1000 | yes |
| 3 | 1 | 2 | complete | 8.52 | 2347.827 | 0 | 0 | complete: 200:1000 | yes |
| 4 | 3 | 2 | complete | 22.25 | 898.935 | 0 | 0 | complete: 200:1000 | yes |
| 5 | 1 | 3 | complete | 10.68 | 1872.073 | 0 | 0 | complete: 200:1000 | yes |
| 6 | 3 | 3 | complete | 27.42 | 729.359 | 0 | 0 | complete: 200:1000 | yes |

## Artifact references

| Ordinal | Raw | Result | Diagnostics |
| ---: | --- | --- | --- |
| 1 | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o1-i1-c20-r1-warmup.txt<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o1-i1-c20-r1.txt | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o1-i1-c20-r1.json<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o1-i1-c20-r1.md | docs/da3/results/11-1b-nginx-s11-20261024t093248z-c7a71d7b-o1.json |
| 2 | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o2-i3-c20-r1-warmup.txt<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o2-i3-c20-r1.txt | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o2-i3-c20-r1.json<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o2-i3-c20-r1.md | docs/da3/results/11-1b-nginx-s11-20261024t093248z-c7a71d7b-o2.json |
| 3 | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o3-i1-c20-r2-warmup.txt<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o3-i1-c20-r2.txt | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o3-i1-c20-r2.json<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o3-i1-c20-r2.md | docs/da3/results/11-1b-nginx-s11-20261024t093248z-c7a71d7b-o3.json |
| 4 | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o4-i3-c20-r2-warmup.txt<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o4-i3-c20-r2.txt | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o4-i3-c20-r2.json<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o4-i3-c20-r2.md | docs/da3/results/11-1b-nginx-s11-20261024t093248z-c7a71d7b-o4.json |
| 5 | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o5-i1-c20-r3-warmup.txt<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o5-i1-c20-r3.txt | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o5-i1-c20-r3.json<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o5-i1-c20-r3.md | docs/da3/results/11-1b-nginx-s11-20261024t093248z-c7a71d7b-o5.json |
| 6 | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o6-i3-c20-r3-warmup.txt<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o6-i3-c20-r3.txt | docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o6-i3-c20-r3.json<br>docs/da3/results/11-1b-s11-20261024t093248z-c7a71d7b-o6-i3-c20-r3.md | docs/da3/results/11-1b-nginx-s11-20261024t093248z-c7a71d7b-o6.json |

## Medians

| Topology | Eligible runs | Median RPS | Median mean ms | Three-repetition state |
| ---: | --- | ---: | ---: | --- |
| 1 | 3 of 3 | 10.29 | 1943.935 | complete |
| 3 | 3 of 3 | 24.88 | 803.911 | complete |

## Comparisons (COMPLETE)

| Metric | Value |
| --- | ---: |
| throughput_improvement_percent | 141.7881438289601554907677357 |
| throughput_speedup_factor | 2.417881438289601554907677357 |
| mean_response_time_reduction_percent | 58.64517074902195803872043047 |
| mean_response_time_improvement_factor | 2.418097276937372420578894927 |

Formulas use full available Decimal precision:
- `(median_3_backend_rps / median_1_backend_rps - 1) * 100`
- `median_3_backend_rps / median_1_backend_rps`
- `(1 - median_3_backend_mean_ms / median_1_backend_mean_ms) * 100`
- `median_1_backend_mean_ms / median_3_backend_mean_ms (greater than 1 means improvement)`

Source manifest: `11-1b-manifest-s11-20261024t093248z-c7a71d7b.json`
