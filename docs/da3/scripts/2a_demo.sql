-- Illustration only. The application NEVER stored plaintext passwords; this table exists solely to show the 'before' state the question asks about.
-- This demonstration is isolated from the application schema and does not represent historical data.

BEGIN;

-- Deliberately no IF NOT EXISTS: a pre-existing schema is a conflict and must fail.
CREATE SCHEMA da3_demo;

CREATE TABLE da3_demo."users_plaintext_legacy_DEMO" (
    demo_id integer PRIMARY KEY,
    demo_email text NOT NULL UNIQUE,
    plaintext_password_illustration text NOT NULL,
    demo_role text NOT NULL
);

INSERT INTO da3_demo."users_plaintext_legacy_DEMO" (
    demo_id,
    demo_email,
    plaintext_password_illustration,
    demo_role
)
VALUES
    (1, 'legacy-demo-a@example.invalid', 'NOT_A_REAL_PASSWORD_DEMO_A', 'candidate'),
    (2, 'legacy-demo-b@example.invalid', 'NOT_A_REAL_PASSWORD_DEMO_B', 'candidate'),
    (3, 'legacy-demo-c@example.invalid', 'NOT_A_REAL_PASSWORD_DEMO_C', 'recruiter');

SELECT demo_id, demo_email, plaintext_password_illustration, demo_role
FROM da3_demo."users_plaintext_legacy_DEMO"
ORDER BY demo_id;

COMMIT;
