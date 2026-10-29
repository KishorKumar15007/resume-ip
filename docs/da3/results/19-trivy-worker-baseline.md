# Trivy scan: worker-baseline

- Status: **success**
- Scan timestamp: `2026-10-29T08:39:55.500263Z`
- Image reference / ID: `resume-worker:da3-baseline` / `sha256:bdb91ee950b57b62952327f99df8edce65f17146a916b7f47458252078831864`
- Image size / configured user: `486078814` bytes / `default/root`
- Trivy image / version: `aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c` / `0.76.1`
- DB schema / version / updated: `2` / `2` / `2026-10-29T01:22:22.544155871Z`
- DB content SHA-256: `ad47d4d7f64fb08225e3d0c9f59118e724ecf82a14d5502fff71c742d6cb24b4`
- Scan arguments: `image --input /scan/image.tar --scanners vuln --pkg-types os,library --severity CRITICAL,HIGH --format json --skip-db-update --skip-java-db-update --skip-check-update --skip-version-check --offline-scan --no-progress`
- Base-image provenance is Docker-inspected at scan time:
  - `python:3.12` -> `unavailable` ({'os': 'unknown', 'architecture': 'unknown'}; not-locally-inspectable-after-build)

## Raw vulnerability occurrences

| Severity | Count |
| --- | ---: |
| CRITICAL | 19 |
| HIGH | 461 |

| Package class | CRITICAL | HIGH |
| --- | ---: | ---: |
| OS packages | 0 | 0 |
| language packages | 0 | 0 |
| unknown | 19 | 461 |

## Five most affected package groups

Ties: occurrence count, CRITICAL count, HIGH count, severity, class, package, installed, fixed, ID.

| Class | Package | Installed | Fixed | Representative ID | Severity | Occurrences |
| --- | --- | --- | --- | --- | --- | ---: |
| unknown | linux-libc-dev | 6.12.113-1 | not available | CVE-2026-93221 | CRITICAL | 61 |
| unknown | libopenexr-3-1-30 | 3.1.13-2 | not available | CVE-2026-42216 | CRITICAL | 22 |
| unknown | libopenexr-dev | 3.1.13-2 | not available | CVE-2026-42216 | CRITICAL | 22 |
| unknown | libmariadb-dev | 1:11.8.6-0+deb13u1 | not available | CVE-2026-44172 | CRITICAL | 13 |
| unknown | libmariadb-dev-compat | 1:11.8.6-0+deb13u1 | not available | CVE-2026-44172 | CRITICAL | 13 |
