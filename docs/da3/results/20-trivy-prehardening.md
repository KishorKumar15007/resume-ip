# Trivy scan: prehardening

- Status: **success**
- Scan timestamp: `2026-10-29T12:55:20.926591Z`
- Image reference / ID: `resume-backend:da3-prehardening` / `sha256:3253974718dead99b95136a686556dbe82dfd5a93917ef1956b4e79a9102aabf`
- Image size / configured user: `83449753` bytes / `app`
- Trivy image / version: `aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c` / `0.76.1`
- DB schema / version / updated: `2` / `2` / `2026-10-29T01:22:22.544155871Z`
- DB content SHA-256: `ad47d4d7f64fb08225e3d0c9f59118e724ecf82a14d5502fff71c742d6cb24b4`
- Scan arguments: `image --input /scan/image.tar --scanners vuln --pkg-types os,library --severity CRITICAL,HIGH --format json --skip-db-update --skip-java-db-update --skip-check-update --skip-version-check --offline-scan --no-progress`
- Base-image provenance is Docker-inspected at scan time:
  - `python:3.14.2-slim` -> `unavailable` ({'os': 'unknown', 'architecture': 'unknown'}; not-locally-inspectable-after-build)

## Raw vulnerability occurrences

| Severity | Count |
| --- | ---: |
| CRITICAL | 8 |
| HIGH | 126 |

| Package class | CRITICAL | HIGH |
| --- | ---: | ---: |
| OS packages | 6 | 113 |
| language packages | 2 | 13 |
| unknown | 0 | 0 |

## Five most affected package groups

Ties: occurrence count, CRITICAL count, HIGH count, severity, class, package, installed, fixed, ID.

| Class | Package | Installed | Fixed | Representative ID | Severity | Occurrences |
| --- | --- | --- | --- | --- | --- | ---: |
| os-pkgs | perl-base | 5.40.1-6 | 5.40.1-6+deb13u1 | CVE-2026-13221 | CRITICAL | 7 |
| os-pkgs | libssl3t64 | 3.5.4-1~deb13u2 | 3.5.5-1~deb13u2 | CVE-2026-31789 | CRITICAL | 5 |
| os-pkgs | openssl | 3.5.4-1~deb13u2 | 3.5.5-1~deb13u2 | CVE-2026-31789 | CRITICAL | 5 |
| os-pkgs | openssl-provider-legacy | 3.5.4-1~deb13u2 | 3.5.5-1~deb13u2 | CVE-2026-31789 | CRITICAL | 5 |
| os-pkgs | bsdutils | 1:2.41-5 | 2.41.5-0+deb13u1 | CVE-2026-53612 | HIGH | 4 |
