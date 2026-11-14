-- The audit table can only be appended to, whoever is connected (SPEC section 9). Idempotent.
--
-- * audit_events_append_only refuses every UPDATE, DELETE and TRUNCATE statement on the table, and so also an
--   INSERT … ON CONFLICT DO UPDATE (PostgreSQL fires the UPDATE statement triggers for it too).
-- * audit_events_follow_head lets an event in only when its id is new and its previous_hash is the hash of the
--   last stored event (64 zeros for the first one), and gives it the next position. It first takes a lock that
--   is held until the writer's transaction ends, so writers take turns: the head it reads cannot move before the
--   row is stored, and a second writer that waited finds the head moved.
-- * previous_hash is UNIQUE (001): two events can never follow the same event, even with this trigger gone.
--
-- Both triggers are ENABLE ALWAYS, so they fire also in a session with session_replication_role = replica, which
-- the service's admin user is allowed to set.
-- Limit: whoever owns the table can still drop or disable a trigger, and the gateway connects as the owner today.
-- A runtime login that does not own the tables closes that (docs/AIVEN.md, next steps).
-- SQLSTATEs, read by tta.store.postgres: TA001 change refused · TA002 id already stored · TA003 not after the head.

CREATE OR REPLACE FUNCTION audit_events_refuse_change() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
BEGIN
    RAISE EXCEPTION 'audit_events is append-only: % is refused, an event cannot be changed or removed', TG_OP
        USING ERRCODE = 'TA001';
END;
$$;

CREATE OR REPLACE FUNCTION audit_events_check_append() RETURNS trigger
LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
DECLARE
    last_seq  bigint;
    last_hash text;
BEGIN
    -- One appender at a time on this table (its oid is the key), until its transaction ends.
    PERFORM pg_advisory_xact_lock(TG_RELID::bigint);
    IF EXISTS (SELECT 1 FROM audit_events WHERE event_id = NEW.event_id) THEN
        RAISE EXCEPTION 'audit_events is append-only: event % is already stored', NEW.event_id
            USING ERRCODE = 'TA002';
    END IF;
    SELECT seq, hash INTO last_seq, last_hash FROM audit_events ORDER BY seq DESC LIMIT 1;
    IF NEW.previous_hash IS DISTINCT FROM coalesce(last_hash, repeat('0', 64)) THEN
        RAISE EXCEPTION 'audit_events is append-only: event % does not follow the last stored event', NEW.event_id
            USING ERRCODE = 'TA003';
    END IF;
    NEW.seq := coalesce(last_seq, 0) + 1;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER audit_events_append_only
    BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_events
    FOR EACH STATEMENT EXECUTE FUNCTION audit_events_refuse_change();
CREATE OR REPLACE TRIGGER audit_events_follow_head
    BEFORE INSERT ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_events_check_append();
ALTER TABLE audit_events ENABLE ALWAYS TRIGGER audit_events_append_only;
ALTER TABLE audit_events ENABLE ALWAYS TRIGGER audit_events_follow_head;
