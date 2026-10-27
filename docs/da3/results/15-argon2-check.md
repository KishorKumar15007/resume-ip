# DA3 Q2(a) Argon2 verification

Status: PASS

The two existing synthetic users were read through the application's configured SQLAlchemy session. Password verification used `app.core.security.verify_password`; the prompted password was not saved or echoed.

| Email | User ID | Algorithm | Version | Memory (KiB) | Time cost | Parallelism | Hash length (bytes) | Salt (PHC base64) | Salt length (bytes) | Password verification |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |
| da3-salt-a@example.com | 55d7eb18-f4a2-4240-b0b2-9e441dae1ed1 | argon2id | 19 | 65536 | 3 | 4 | 32 | `YN4BnoJLPn1JHiOhUuWncg` | 16 | PASS |
| da3-salt-b@example.com | 148b3412-fd82-4590-b18d-5bbd46198248 | argon2id | 19 | 65536 | 3 | 4 | 32 | `Y6Ahmj5zHs5a1ZaEn/9tOQ` | 16 | PASS |

Salt-distinctness verdict: PASS — salts differ.
Hash-distinctness verdict: PASS — hashes differ.

Complete encoded hashes, plaintext passwords, database URLs, and other credentials are intentionally omitted.
