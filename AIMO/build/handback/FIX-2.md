# FIX-2 — partly done

Six findings fixed; finding 2 is fixed inside the audit package and left open where another package writes the sentence.

## Findings
1. **Fixed.** `order.placed_by_agent` with a decision whose verdict is not `AUTO` raises `ValueError` and stores nothing; with no decision it reads "The agent placed order ord_7 alone. The policy decision behind it is not recorded." `order.confirmed` says "with human approval" only when an approval or the order record shows it, otherwise "How it was confirmed is not recorded." (and "Who approved is not recorded." when only the order record says a human approved). `policy.evaluated` with no decision reads "The rules were checked. The decision is not recorded." "The order is recorded in the gateway's order book" is said only when the event carries the order record. Ids only: I picked the store lookup. `record` takes the buyer profile from the stored order, approval or offer, so the profile view finds the event.
2. **Partly fixed.** `quoted()` turns every double quotation mark (ASCII and typographic) into `'`, replaces control and format characters (bidi overrides, zero width) with a space, and cuts at 200 characters; people's names go through the same at 80; a product id, sales unit, product type, claim or allergen code that does not look like a code is shown as quoted text. Tested with the given input in a request text, a pasted text and an approver's note. **Left:** the audit package puts no product name into a sentence itself. Product names arrive inside sentences other packages write, which the trail quotes as written with only control characters removed: the policy rule messages use `{line.name}` (`src/tta/policy/rules.yaml`). A name there is the policy package's to neutralise.
3. **Fixed.** Supplier facts and sentence carry product ids and product types only: no `name_terms`, no `required_claims`. `supplier_actor` passes an agent's id and kind, nothing else.
4. **Fixed.** In a view `checked` is the number of events shown; `first_bad_event_id` is set only for an event of the view; otherwise: "The audit trail does not verify: it is broken at an event outside this view. Events shown here that were written after it cannot be trusted: 2 of 3." An empty view reads the same whatever the length of the trail. `verify_chain()` is unchanged.
5. **Fixed.** (a) Triggers refuse `UPDATE` and `DELETE`. A third refuses an `INSERT` that names a stored id or previous hash: I ran `INSERT OR REPLACE` from a second connection and it replaced a row past the first two. (b) `previous_hash` is a `NOT NULL UNIQUE` column; `append_audit_event` checks the head inside one `BEGIN IMMEDIATE` transaction and raises `AuditChainConflict`. (c) `AuditTrail.record` reads the head again, 5 attempts at most, then raises `AuditChainConflict`. Tested with two trails on one file; a scratch run with 4 processes writing 150 events each stored 600, retried 13 conflicts, gave up on none, and the chain verified.
6. **Fixed as asked.** `chain.py` states what verification shows and the three things it does not (the end cut off, a rewrite to the end, who wrote an event). `AuditTrail.head()` returns the event count and the last hash. Nothing publishes or compares a head yet.
7. **Fixed.** A ratio below 1 that would print as 100% is rounded down: 0.9996 reads 99.9%.

## Built
- `src/tta/store/errors.py` — new: `AuditChainConflict(SupplierUnavailable)`.
- `src/tta/store/schema.py` — `previous_hash` column, three triggers, `BEGIN IMMEDIATE`.
- `src/tta/store/sqlite_store.py` — head check in the append transaction.
- `src/tta/store/__init__.py` — exports `AuditChainConflict`.
- `src/tta/audit/trail.py` — retry on a moved head, `head()`, view-scoped chain state, profile from stored ids.
- `src/tta/audit/chain.py` — `first_break`, `verify_view`, exact docstring.
- `src/tta/audit/phrases.py` — `plain`, `label`, safer `quoted` and `person`, `percent`, supplier request text.
- `src/tta/audit/sentences.py`, `supplier_sentences.py`, `scope.py` — sentences that state only what the context holds.
- `src/tta/audit/facts.py`, `readers.py` — supplier allow-list and supplier actor.
- `src/tta/audit/__init__.py` — docstring.
- `tests/audit/test_sentence_guards.py` — new (9 tests). New tests also in `test_chain.py`, `test_phrases.py`, `test_views.py`, `tests/store/test_sqlite_store.py`.

Existing tests changed, each because a finding changes the behaviour:
- `test_sqlite_store.py::test_audit_events_are_filtered_by_order_offer_and_profile` — its events now chain (5b).
- `test_chain.py::_change_file` — drops the triggers before rewriting a row, as someone with the file would (5a).
- `test_envelope.py::test_every_envelope_has_the_attributes_cloudevents_requires` and `test_views.py::test_the_trail_of_an_order_leaves_out_other_orders_of_the_same_offer` — the agent-placed order has an `AUTO` decision (1).
- `test_envelope.py::test_the_trail_implements_the_audit_port_and_can_only_append` — `head` is public (6).
- `test_views.py::test_the_supplier_sees_the_agent_and_only_the_rules_about_its_own_data` — no agent display name (3).
- `test_views.py::test_a_view_says_whether_the_whole_chain_verifies` — renamed, new sentence (4).

For T08 and T09: `record(ORDER_PLACED_BY_AGENT, …)` raises `ValueError` unless the decision is `AUTO`; `record` can raise `AuditChainConflict` (a `SupplierUnavailable`, 503); `person()` and `ended()`, which `src/tta/orders/wording.py` imports, now clean their input; signatures of `record`, `view`, `verify_chain` and the `Store` port are unchanged.

## Tests
`COVERAGE_FILE=<scratch>/.coverage.fix2 .venv/bin/python -m pytest tests/store tests/audit -q --cov=tta.store --cov=tta.audit --cov-report=term-missing`
```
src/tta/store/sqlite_store.py           111      0      6      0   100%
---------------------------------------------------------------------------------
TOTAL                                   849      0    176      0   100%
165 passed in 0.35s
```
`.venv/bin/ruff check src/tta/store src/tta/audit tests/store tests/audit` → `All checks passed!`

Importers: none were named. `tests/orders` appeared while I worked and imports both packages; run once at the end, not edited: `89 passed in 0.43s`. T08 was still being written.

## Assumptions
- An event given ids only takes its profile from the stored order, then approval, then offer. An id that names nothing stored leaves the event without a profile: no view by buyer profile shows it.
- A `profile_id` given on the context always wins over the stored one.
- "Rejected by a human", "sent to a human" and the expiry and not-placed wordings stay when nothing is known: they are what the event type means (only a human decides an approval), not a guess.
- The facts keep outside text in full and unchanged; only the sentence is cleaned and cut.
- A code is `[A-Za-z0-9][A-Za-z0-9_.:/+-]{0,39}`. Every sales unit (12 distinct) and id (3,614 values) in the recorded captures fits; that is a sample of live calls, not the catalog.
- For the supplier a request line with neither product id nor product type reads "a product described in free text", also when name terms were given.
- In a view `ok` is the whole chain's; a break outside the view is reported with how many of the view's events came after it, never its id or position.
- `AuditChainConflict` is a `SupplierUnavailable`: reported as 503, safe to send again. Five attempts, no wait between them.
- The append waits for another writer up to sqlite3's default busy time-out of 5 seconds.
- A database file made before this fix has no `previous_hash` column and must be deleted; there is no migration. None exists in the repository (`var/` is absent).
- Whoever can write the database file can drop the triggers; the schema docstring says so.
- `head()` reads every event: the `Store` port has no count.

## Contract changes needed
- `tta.contracts.errors`: add `AuditChainConflict`. It lives in `tta.store.errors` and `tta.audit.trail` imports it from there, the one import from another package instead of a port.
- `ports.AuditSink`: add `head() -> tuple[int, str]`, so the API can publish it through the port.
- `ports.Store`: a count or head read, so `head()` and `view` need not load every event.
- `common.Ratio`: its JSON form rounds half up to 4 places, so a fill ratio of 0.99996 is written `1.0` in facts and API bodies for a partial option (checked). Sentences are fixed; that number is not.

## Not done
- Finding 2, product names inside policy rule sentences: not my path (see above).
- `order.confirmed` for an order whose record says `placed_by: AGENT` still says "within its authority" without checking the verdict; the task named the guard for `order.placed_by_agent` only.
- The verification sentence still begins "The audit trail is intact", although a cut-off end is not shown. The limit is in the `chain.py` docstring, not in the sentence.
- Publishing the head and comparing a held head with the trail: the API's.
- A stored audit row that no longer parses still raises from `list_audit_events` instead of being named by `verify_chain` (T06's open item, not in this task).

## Questions written
0
