# DA3 Step 9 Distribution Result

Run ID: `da3-dist-20261020T112234Z-dd9c011e`

Overall result: **PASS**

| Backend | X-Served-By count | X-Served-By % | Final upstream count | Final upstream % |
| --- | ---: | ---: | ---: | ---: |
| backend-1 | 100 | 33.33% | 100 | 33.33% |
| backend-2 | 100 | 33.33% | 100 | 33.33% |
| backend-3 | 100 | 33.33% | 100 | 33.33% |

| Acceptance check | Result |
| --- | --- |
| preflight_ready | PASS |
| exactly_300_client_records | PASS |
| all_client_sequences_unique | PASS |
| all_http_statuses_successful | PASS |
| all_headers_known | PASS |
| exactly_300_log_records | PASS |
| all_log_sequences_unique | PASS |
| no_malformed_log_records | PASS |
| all_upstream_backends_known | PASS |
| per_request_identity_agrees | PASS |
| per_request_status_agrees | PASS |
| aggregate_counts_agree | PASS |
| each_backend_received_requests | PASS |
| dynamic_mapping_complete | PASS |

Client records: 300; matching Nginx records: 300.
Retry chains are retained in `09-distribution-raw.json` and counted once by their final upstream address.
No authorization header, token, response body, database URL, or configuration path is recorded.
