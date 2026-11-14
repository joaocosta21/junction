# FIX-7 — done

All ten findings are fixed in `src/tta/orders/` and `src/tta/store/`. **One change is needed outside my paths, read it first:** `AuditTrail.record` takes its own lock and then calls the store; a thread inside `store.atomic()` holds the store and then needs that lock. Two threads can wait for each other. Today that ends after 5 seconds with `supplier-unavailable` for the thread outside the block; the fix is two lines in `src/tta/audit/trail.py` (see "Contract changes needed", item 1).

## Findings
1. **Fixed.** `SqliteStore.atomic()`: `BEGIN IMMEDIATE` … commit, rollback on any exception; a block inside a block of the same thread is a savepoint; every store method, the audit append included, joins an open block and works as before without one; the head check holds inside it. Every outcome of the order book (placed alone, sent to a human, approved, rejected, expired, and each refused attempt that writes an event) does its saves, its key binding and its `audit.record` in one block (`src/tta/orders/outcomes.py`; the checker's refusals in `checking.py`). Fault injection on every write of 10 outcomes (27 cases): the store holds nothing of the outcome, the same call sent again succeeds, the chain verifies.
2. **Fixed.** A second `place_order` on an offer whose order is `ORDERED` or `PENDING_APPROVAL` (any option, another key) is `invalid-request`: "Offer off_… already has an order: ord_…, which is waiting for approval. …", with `offer_id` and `order_id` as extension members. After `REJECTED` or `EXPIRED` the offer can be ordered again; a waiting order past its time is expired in that call.
3. **Fixed.** `decide` (approve) runs the order-time check first, then asks whether the approver holds a role the new decision still needs. A rejection is unchanged (assumption 6).
4. **Fixed.** An `ORDERED` order counts on the date it became `ORDERED`, a waiting one on the date it was created, both in the clock's offset.
5. **Fixed.** Any exception from the fresh look, the day's spend or the policy writes `order.not_placed` with `facts.error_type` (the class name, never the text), then is raised again.
6. **Fixed.** `RelianceStatement.time_now` is the offer's `time_now`; `rechecked_at` is the re-check's `checked_at`.
7. **Fixed.** An approval for an option with no `valid_until` gets its creation time plus 24 hours (`HOURS_TO_DECIDE_WITHOUT_ORDER_BY`); the status sentence, the expiry sentence, the `offer-expired` detail and its `valid_until` member use that time; the order expires at it.
8. **Fixed.** An order found past its time by `decide` is `EXPIRED` with its event in its own block before `offer-expired` is raised. Also when the time passes during the order-time check of the proposed option (the supplier call takes time): the order is `EXPIRED` in that call (events `order.not_placed`, `order.expired`).
9. **Fixed.** `get_order`, `get_approval`, `decide` (approver) and the offer lookup answer `not-found` with the same body for another buyer's id and an unknown one. A refused attempt on another buyer's approval is recorded under the caller's own profile, with no approval id.
10. **Fixed.** A key must match `[A-Za-z0-9._:-]{1,100}` in full; anything else is `invalid-request` and the key is not echoed.

## Built
- `src/tta/store/sqlite_store.py` — `atomic()`, savepoints, `_session` joins an open block, bounded wait for the connection (`LOCK_WAIT_SECONDS = 5.0`).
- `src/tta/store/schema.py` — three savepoint statements.
- `src/tta/orders/outcomes.py` — new: `OutcomeWriter`, one block per outcome.
- `src/tta/orders/service.py` — reworked: key form, one order per offer, `not-found` for another buyer, check before roles, expiry in the same call.
- `src/tta/orders/checking.py` — any failure of the check is recorded; its events are written in a block.
- `src/tta/orders/records.py` — `decide_by`, `is_overdue`, `roles_still_needed`, reliance times. `is_past_order_by` not touched (FIX-5 changed it to `<=` while I worked; `is_overdue` delegates to it).
- `src/tta/orders/spend.py`, `access.py`, `wording.py` — day of an order, `is_of_another_buyer`, new sentences.
- Tests, new: `tests/store/test_atomic.py` (16), `tests/orders/test_atomic_outcomes.py` (29), `test_decide_at_order_time.py` (7), `test_decide_other_buyer.py` (5), `test_approval_window.py` (6), `test_one_order_per_offer.py` (5), `test_idempotency_key.py` (12).

Existing tests changed, each because a finding changes the behaviour:
- `test_place_order.py`: `test_another_key_places_another_order` now uses two offers (2); `test_an_agent_cannot_order_from_an_offer_made_for_another_buyer` expects `not-found`, renamed (9); `time_now` assertion in the reliance test (6); one assertion added for `error_type` (5).
- `test_decide.py`: `time_now` assertion (6); the "approver of another buyer" case left the refusal test and `test_an_approval_nobody_issued_is_not_found` moved to `test_decide_other_buyer.py`, where it now expects one event in the caller's own trail (9).
- `test_reads.py`: another buyer expects `not-found`; the supplier case is a test of its own (9).
- `test_spend.py`: the offset test restamps `updated_at` too (4).
- `tests/orders/conftest.py`: the store is wrapped to make a chosen write fail; the fake revalidator and policy can fail; `Book.waiting`.
- No existing store test changed. `tests/orders/test_expiry.py` was changed by FIX-5, not by me.

## Tests
`COVERAGE_FILE=<scratch>/fix7/.coverage .venv/bin/python -m pytest tests/orders tests/store -q -p no:cacheprovider --cov=tta.orders --cov=tta.store --cov-report=term-missing`
```
src/tta/orders/service.py         185      0     62      0   100%
src/tta/store/sqlite_store.py     154      0     12      0   100%
---------------------------------------------------------------------------
TOTAL                             668      0    102      0   100%
201 passed in 1.24s
```
`.venv/bin/ruff check src/tta/orders src/tta/store tests/orders tests/store` → `All checks passed!`

Importers, run and not edited: `tests/audit` 137 passed · `tests/offers` 185 passed · `tests/api` 147 passed at my last run (it exists; `src/tta/api/service.py` already calls `store.atomic()` around an offer and its events).

The new tests were written before the code and seen failing (54 orders tests, 15 store tests), except those that state behaviour which already held. Three were added after the code, each for a branch the first ones did not reach: a block whose commit fails, an order whose offer is no longer stored, the supplier's refused attempt.

## Assumptions
1. A block inside a block is a savepoint: when it fails, only its own writes are taken back and the outer block can go on.
2. A thread waits at most 5 seconds for the store while another thread uses it or has a block open, then gets `supplier-unavailable` ("busy … the same request can be sent again"). The value is sqlite3's default wait for another connection.
3. The supplier call is never inside a block: a block holds local writes only.
4. One order per offer is checked among the buyer's `ORDERED` and `PENDING_APPROVAL` orders, read by profile and filtered by offer in Python. The refusal writes no audit event.
5. Approvals already given for the same option count towards the roles of the new decision. When the new decision needs nobody, or every role it asks for was already given, any approver listed for this buyer completes the order (question 1).
6. A rejection asks the supplier nothing, so it is still held against the roles the approval record waits for.
7. `updated_at` of an `ORDERED` order is the moment it became `ORDERED`: nothing changes an order after that.
8. A waiting order created on an earlier day is in no day's spend until it is approved; then it is spend of the approval day.
9. `error_type` is the exception's class name. The supplier's facts do not carry it (the audit package's allow-list).
10. `RelianceStatement.source` stays the re-check's source.
11. The 24 hours run from the approval's creation; a first approval does not move them. The boundary is `is_past_order_by`'s.
12. When the re-check reports a passed cut-off while the order's own time has not passed, or a chosen other option has expired, the order keeps waiting, as in T08's question 1.
13. An approver deciding an id that is not an approval of its own buyer gets `not-found` and one `authorisation.refused` event under its own profile, also for an id nobody issued (before: no event). Otherwise its own trail would tell the two apart.
14. An agent or the supplier on an approval route stays `not-authorised`, the same answer whether the id exists. The supplier's refused attempt on an existing approval stays in that buyer's trail (question 2).
15. A key with spaces around it is now invalid; a blank key keeps its own sentence.
16. A key found bound to another order inside the block (a second process) is `supplier-unavailable` and stores nothing.
17. An approval needs the stored offer for its data time; an order whose offer is gone answers `not-found` and keeps waiting.

## Contract changes needed
1. **`src/tta/audit/trail.py`, `AuditTrail.record`:** replace `with self._lock:` by `with self._store.atomic(), self._lock:`. Then every writer takes the store first and the trail's lock second. Scratch run, two threads, 900 `record` calls, wait set to 0.05 s: trail as it is, 209 calls answered "busy"; with `record` wrapped in `store.atomic()`, 0, chain intact. Not run against `tests/audit` (not my path). Without it, the one caller exposed today is `Gateway._record_received` in `src/tta/api/service.py` (`request.received`, outside a block); wrapping that call in `store.atomic()` closes it for the API only.
2. `Store.list_orders`: a filter by offer, for finding 2 at volume.
3. `Order`: a field `ordered_at`, instead of reading `updated_at`.
4. `tta.contracts.errors`: still no conflict type (409). "Offer already has an order" is 422; the key bound by another writer is 503.
5. `AuditEventType`: nothing for a refused order placement, so a refused second order on an offer leaves no event.

## Not done
- The lock order between the audit trail and the store (item 1 above): bounded by the 5-second wait, not removed.
- Known and left as it is, as the task says: the one lock of the order book is held across the supplier call and protects one process only. One order per offer and the limit per day are checked under that lock, before the block, so two gateway processes on one database can still each place an order on one offer.
- A rejection is not checked against a fresh policy decision (assumption 6).

## Questions written
2, both for the team — `AIMO/build/questions/FIX-7.md`
