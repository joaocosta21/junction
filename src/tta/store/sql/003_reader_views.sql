-- The two readers of SPEC section 9, in SQL. Idempotent.
-- Each view reads the event as stored and shows what `tta.audit.views.project` shows that reader: the same
-- id, type, time, actor, sentence, rule ids, facts and hash (tests/store_pg/test_reader_views.py checks both
-- against it). The ids of the offer, order and approval are columns as well, to find an order's events.
--
-- audit_buyer: everything, with the buyer profile, so a buyer's query names its own profile. Keeping one buyer
--   from another is the gateway's (it checks who asks); in SQL that is a login per buyer, a next step.
-- audit_supplier: what Valio Aimo may see. No buyer profile; the supplier's sentence and facts, which the audit
--   package builds from an allow-list; an agent by kind and id only, a human only as "a human at the buyer"
--   (tta.audit.readers.supplier_actor); and only the rules about the supplier's own data or the caller's identity
--   (the keys of tta.audit.readers.SUPPLIER_RULE_MEANINGS; a test fails when the two lists differ).

CREATE OR REPLACE VIEW audit_buyer AS
SELECT
    e.seq,
    e.profile_id,
    e.offer_id,
    e.order_id,
    e.approval_id,
    e.event_id AS id,
    e.type,
    e.time,
    event.body ->> 'subject' AS subject,
    event.body #> '{data,actor}' AS actor,
    event.body #>> '{data,sentence}' AS sentence,
    ARRAY(
        SELECT rule.id
        FROM jsonb_array_elements_text(event.body #> '{data,rule_ids}') WITH ORDINALITY AS rule (id, position)
        ORDER BY rule.position
    ) AS rule_ids,
    event.body #> '{data,facts}' AS facts,
    event.body #>> '{data,policy_hash}' AS policy_hash,
    e.previous_hash,
    e.hash
FROM audit_events AS e
CROSS JOIN LATERAL (SELECT e.body::jsonb AS body) AS event;

CREATE OR REPLACE VIEW audit_supplier AS
SELECT
    e.seq,
    e.offer_id,
    e.order_id,
    e.approval_id,
    e.event_id AS id,
    e.type,
    e.time,
    CASE event.body #>> '{data,actor,kind}'
        WHEN 'human' THEN jsonb_build_object(
            'kind', 'human', 'id', 'buyer-human', 'role', NULL, 'display_name', 'A human at the buyer')
        WHEN 'agent' THEN jsonb_build_object(
            'kind', 'agent', 'id', event.body #> '{data,actor,id}', 'role', NULL, 'display_name', NULL)
        ELSE event.body #> '{data,actor}'
    END AS actor,
    event.body #>> '{data,supplier_sentence}' AS sentence,
    ARRAY(
        SELECT rule.id
        FROM jsonb_array_elements_text(event.body #> '{data,rule_ids}') WITH ORDINALITY AS rule (id, position)
        WHERE rule.id IN ('F-01', 'F-03', 'F-04', 'F-05', 'F-06', 'F-07', 'F-08')
        GROUP BY rule.id
        ORDER BY min(rule.position)
    ) AS rule_ids,
    coalesce(event.body #> '{data,supplier_facts}', '{}'::jsonb) AS facts,
    e.hash
FROM audit_events AS e
CROSS JOIN LATERAL (SELECT e.body::jsonb AS body) AS event;
