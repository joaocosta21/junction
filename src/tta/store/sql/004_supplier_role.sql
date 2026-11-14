-- A role that can read audit_supplier and nothing else of this schema. Idempotent.
-- Its name is the schema's followed by _supplier: tta_supplier for the gateway's schema. It cannot log in; the
-- supplier's own login is made a member of it (docs/AIVEN.md). Granting SELECT on the view alone is enough:
-- a view reads its tables with its owner's rights, so the role reads the projection and never the rows behind it.
-- Where the connected user may not create roles, the view stays, the database warns, and the store logs it.

DO $$
DECLARE
    reader text := current_schema() || '_supplier';
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = reader) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', reader);
    END IF;
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I', current_schema(), reader);
    EXECUTE format('GRANT SELECT ON %I.audit_supplier TO %I', current_schema(), reader);
EXCEPTION WHEN insufficient_privilege THEN
    RAISE WARNING 'The supplier role % was not created: %', reader, SQLERRM;
END;
$$;
