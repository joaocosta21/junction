-- The two readers of SPEC section 9, in SQL. Idempotent.
-- Each view reads the event as stored and shows what `tta.audit.views.project` shows that reader: the same
-- id, type, time, actor, sentence, rule ids, facts and hash (tests/store_pg/test_reader_views.py checks both
-- against it). The ids of the offer, order and approval are columns as well, to find an order's events.
--
-- audit_buyer: everything, with the buyer profile, so a buyer's query names its own profile. Keeping one buyer
--   from another is the gateway's (it checks who asks); in SQL that is a login per buyer, a next step.
-- audit_supplier: what Valio Aimo may see (package S4, Valio's answers of 14 Nov). No buyer profile; the
--   supplier's sentence and facts, which the audit package builds from an allow-list; every rule that fired,
--   each id once, in the order they fired (tta.audit.readers.supplier_rule_ids); an agent by kind and id only;
--   a human by the approver roles the gateway knows, never by name or id (tta.audit.readers.supplier_actor);
--   Valio Aimo's own token as "Valio Aimo's reader". An event stored before review finding M1 was fixed holds,
--   in the supplier's sentence and facts, how many products were left out for an allergen the buyer excludes:
--   both are masked here as the reader masks them (tta.audit.readers.shown_sentence, shown_facts), with the
--   same texts in the same order. So is the product evidence was attached for, in an event stored before it was
--   masked: evidence is attached only for a product rule P-04 fired on, which Valio Aimo is not shown.
--   tests/audit/test_sql_view.py compares this file with the reader offline: the columns, the roles, the words.
--
-- audit_supplier is dropped and created again at every start. CREATE OR REPLACE VIEW refuses a change of a
-- column's name, order or type, and a refused statement would fail the whole start-up; a drop cannot meet that.
-- The drop also removes the grant to the supplier's role, which sql/004 gives again right after, at every start.
-- Nothing depends on the view. audit_buyer keeps its columns, so it is replaced in place.

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

DROP VIEW IF EXISTS audit_supplier;

CREATE VIEW audit_supplier AS
SELECT
    e.seq,
    e.offer_id,
    e.order_id,
    e.approval_id,
    e.event_id AS id,
    e.type,
    e.time,
    CASE event.body #>> '{data,actor,kind}'
        WHEN 'human' THEN CASE
            WHEN event.body #>> '{data,actor,role}' = 'supplier' THEN jsonb_build_object(
                'kind', 'human', 'id', 'supplier-reader', 'role', 'supplier', 'display_name', 'Valio Aimo''s reader')
            ELSE jsonb_build_object(
                'kind', 'human',
                'id', 'buyer-human',
                'role', held.roles,
                'display_name', coalesce('The buyer''s ' || replace(held.roles, '_', ' '), 'A human at the buyer'))
        END
        WHEN 'agent' THEN jsonb_build_object(
            'kind', 'agent', 'id', event.body #> '{data,actor,id}', 'role', NULL, 'display_name', NULL)
        ELSE event.body #> '{data,actor}'
    END AS actor,
    regexp_replace(regexp_replace(regexp_replace(regexp_replace(
        event.body #>> '{data,supplier_sentence}',
        '[0-9][0-9,]* products? (was|were) considered and left out: ',
        'Left out for a reason in Valio Aimo''s own data (products left out for a requirement of the buyer''s, if any, are not shown or counted): ',
        'g'),
        '(\x3B )?[0-9][0-9,]* (declaring|stating nothing about) an allergen the buyer excludes \(which allergen and which products are not shown\)',
        '',
        'g'),
        'are not shown or counted\): \.',
        'are not shown or counted): none.',
        'g'),
        'attached to an approval for product .*\. It changes no status',
        'attached to an approval (the product is not named in this step). It changes no status',
        'g') AS sentence,
    ARRAY(
        SELECT rule.id
        FROM jsonb_array_elements_text(event.body #> '{data,rule_ids}') WITH ORDINALITY AS rule (id, position)
        GROUP BY rule.id
        ORDER BY min(rule.position)
    ) AS rule_ids,
    coalesce(event.body #> '{data,supplier_facts}', '{}'::jsonb)
        #- '{offer,excluded_by_reason,ALLERGEN_DECLARED}'
        #- '{offer,excluded_by_reason,ALLERGEN_NOT_STATED}'
        #- '{evidence,product_id}' AS facts,
    e.hash
FROM audit_events AS e
CROSS JOIN LATERAL (SELECT e.body::jsonb AS body) AS event
CROSS JOIN LATERAL (
    -- The roles of the actor that are approver roles, in the order given; NULL when it holds none.
    SELECT string_agg(actor_role.name, ', ' ORDER BY actor_role.position) AS roles
    FROM unnest(string_to_array(event.body #>> '{data,actor,role}', ', ')) WITH ORDINALITY AS actor_role (name, position)
    WHERE actor_role.name IN ('purchasing_manager', 'dietitian', 'finance')
) AS held;
