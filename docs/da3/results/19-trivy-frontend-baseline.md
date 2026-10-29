# Trivy scan: frontend-baseline

- Status: **success**
- Scan timestamp: `2026-10-29T09:09:04.473863Z`
- Image reference / ID: `resume-frontend:da3-baseline` / `sha256:fe14911292943904e0f7b51eca118a83a27a0ef035387bcbe13186176e62e146`
- Image size / configured user: `23193203` bytes / `101`
- Trivy image / version: `aquasec/trivy:0.76.1@sha256:790fd66d1697395d8693d1acaa1ea702406a20f109b6fc7bac8db623eca6c06c` / `0.76.1`
- DB schema / version / updated: `2` / `2` / `2026-10-29T01:22:22.544155871Z`
- DB content SHA-256: `ad47d4d7f64fb08225e3d0c9f59118e724ecf82a14d5502fff71c742d6cb24b4`
- Scan arguments: `image --input /scan/image.tar --scanners vuln --pkg-types os,library --severity CRITICAL,HIGH --format json --skip-db-update --skip-java-db-update --skip-check-update --skip-version-check --offline-scan --no-progress`
- Base-image provenance is Docker-inspected at scan time:
  - `node:24.14.0-alpine` -> `unavailable` ({'os': 'unknown', 'architecture': 'unknown'}; not-locally-inspectable-after-build)
  - `nginxinc/nginx-unprivileged:1.29-alpine` -> `unavailable` ({'os': 'unknown', 'architecture': 'unknown'}; not-locally-inspectable-after-build)

## Raw vulnerability occurrences

| Severity | Count |
| --- | ---: |
| CRITICAL | 1 |
| HIGH | 46 |

| Package class | CRITICAL | HIGH |
| --- | ---: | ---: |
| OS packages | 1 | 46 |
| language packages | 0 | 0 |
| unknown | 0 | 0 |

## Five most affected package groups

Ties: occurrence count, CRITICAL count, HIGH count, severity, class, package, installed, fixed, ID.

| Class | Package | Installed | Fixed | Representative ID | Severity | Occurrences |
| --- | --- | --- | --- | --- | --- | ---: |
| os-pkgs | curl | 8.17.0-r1 | 8.22.0-r0 | CVE-2026-11352 | HIGH | 8 |
| os-pkgs | libcurl | 8.17.0-r1 | 8.22.0-r0 | CVE-2026-11352 | HIGH | 8 |
| os-pkgs | libuuid | 2.41.4-r0 | 2.41.6-r0 | CVE-2026-53612 | HIGH | 5 |
| os-pkgs | libexpat | 2.7.5-r0 | 2.8.4-r0 | CVE-2026-66046 | HIGH | 4 |
| os-pkgs | pcre2 | 10.47-r0 | 10.48-r0 | CVE-2026-86145 | HIGH | 3 |
