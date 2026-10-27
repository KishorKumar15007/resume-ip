-- Remove only the isolated Q2(a) plaintext demonstration after its screenshot is checked.
-- No CASCADE is used: unexpected objects must block cleanup for manual diagnosis.

BEGIN;

DO $$
DECLARE
    unexpected_relations text;
    unexpected_routines text;
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_namespace
        WHERE nspname = 'da3_demo'
    ) THEN
        RAISE EXCEPTION 'Expected demonstration schema da3_demo does not exist';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_class AS relation
        JOIN pg_namespace AS schema
          ON schema.oid = relation.relnamespace
        WHERE schema.nspname = 'da3_demo'
          AND relation.relname = 'users_plaintext_legacy_DEMO'
          AND relation.relkind = 'r'
    ) THEN
        RAISE EXCEPTION 'Expected demonstration table da3_demo.users_plaintext_legacy_DEMO does not exist';
    END IF;

    SELECT string_agg(quote_ident(relation.relname), ', ' ORDER BY relation.relname)
    INTO unexpected_relations
    FROM pg_class AS relation
    JOIN pg_namespace AS schema
      ON schema.oid = relation.relnamespace
    WHERE schema.nspname = 'da3_demo'
      AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
      AND relation.relname <> 'users_plaintext_legacy_DEMO';

    IF unexpected_relations IS NOT NULL THEN
        RAISE EXCEPTION 'Unexpected relations in da3_demo: %', unexpected_relations;
    END IF;

    SELECT string_agg(routine.oid::regprocedure::text, ', ' ORDER BY routine.oid::regprocedure::text)
    INTO unexpected_routines
    FROM pg_proc AS routine
    JOIN pg_namespace AS schema
      ON schema.oid = routine.pronamespace
    WHERE schema.nspname = 'da3_demo';

    IF unexpected_routines IS NOT NULL THEN
        RAISE EXCEPTION 'Unexpected routines in da3_demo: %', unexpected_routines;
    END IF;
END;
$$;

DROP TABLE da3_demo."users_plaintext_legacy_DEMO";
DROP SCHEMA da3_demo;

COMMIT;
