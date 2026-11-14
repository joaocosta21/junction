# FX-O — partly done (P5, P9, P12 done; the phrase-table item is not in a file I own)

## Per finding
- **P5 (evidence lookup inside the order book's lock) — done, two-phase version.** `place_order` now: lock → idempotency key, offer, "no order yet", profile, order-time check → release → `for_approval` → lock → read all of it again → write. Second phase (`OrderBookService._place_after_lookup`) re-reads the key (returns that key's order if another request used it meanwhile), the offer, that the offer has no order yet, the profile; `OrderTimeChecker.still_holds` (new) compares the option's "order by" time with the clock, the day's spend and the standing order's history with those the policy judged on. Any difference: the full order-time check runs again and the order is written on that check. Evidence is kept when the new check has the same verdict, rules and roles; otherwise it is looked up again for the new decision, that once with the lock held. With no evidence finder or an AUTO verdict nothing changed: one lock, as before. Chosen over the time-limit fallback because every input of the check can be re-read cheaply, so the order-time check is not weakened and no evidence is dropped.
  Tests: `tests/orders/test_evidence_outside_the_lock.py` (5): `test_a_slow_evidence_lookup_does_not_block_a_concurrent_get_order` (also `list_approvals`), `..._order_placed_on_the_same_offer_during_the_lookup_refuses_the_one_that_waited`, `..._same_key_used_during_the_lookup_gives_that_keys_order_and_places_no_second`, `..._spend_that_changed_during_the_lookup_has_the_check_run_again` (P-02 then fires, reasons say €2,800.00), `..._order_by_time_that_passed_during_the_lookup_has_the_check_run_again`. All 5 failed before the change.
- **P9 (`let_a_named_role_sign`) — done.** When F-10 is the only rule left, `required_roles` is now the named roles the signer holds, not every role the approval named: one signature of a named role, or of the purchasing manager, completes it. Docstrings (`human_approval.py`, `records.signed_by_a_named_role`) say so. `NAMED_ROLES_SENTENCE` unchanged (policy hash unchanged). Tests: `tests/orders/test_decide.py::test_when_only_f10_is_left_one_of_two_named_roles_completes_the_approval` (approval names purchasing manager + finance; finance approves the small option: `ORDERED`, "Confirmed by Finance (demo) (finance): ordered for €265.00 net."), `tests/policy/test_prepared_wording.py::test_of_two_roles_the_approval_names_the_one_who_signs_completes_it`. Both failed before.
- **P12 (`standing/history.py`) — done in my file; the sentence is not wired.** A renewal counts only when it is synthetic or its order is found and `ORDERED`. One whose order is missing is left out; `renewals_without_order(store, profile_id, standing_order_id, excluding_offer_id=)` counts them (and logs a warning), `not_counted_note(count)` gives "1 past renewal has no order record and was not counted." / "2 past renewals have no order record and were not counted." / None. Tests: `tests/standing/test_history_needs_an_order_record.py` (2).
- **Low (`CHANGED_FIELD_WORDS`) — not done.** The table is in `src/tta/policy/facts.py:61`, not in `src/tta/audit/phrases.py` (which has no such table). Not my path.

## Tests (verbatim last lines)
`.venv/bin/python -m pytest -q -p no:cacheprovider tests/orders tests/standing tests/policy/test_ordering_alone.py tests/policy/test_prepared_wording.py tests/audit/test_phrases.py tests/audit/test_pinned_hashes.py`
```
1 failed, 303 passed in 12.51s
```
The one failure is `tests/standing/test_rest_and_page.py::test_the_page_loads_the_demo_renews_it_and_shows_the_drift_and_the_outcome`: `page.count("Synthetic: made up for the demo")` is 78, pinned 8. Cause: the uncommitted change in `src/tta/ui/standing_page.py` (the page now loads every demo customer's standing orders, `load_customer_standing_orders`), not this lane. Pin left unedited. `tests/audit/test_pinned_hashes.py` green, unedited.
`ruff check` on my paths: `All checks passed!`

## Files
Changed: `src/tta/orders/service.py`, `src/tta/orders/checking.py`, `src/tta/orders/records.py`, `src/tta/policy/human_approval.py`, `src/tta/standing/history.py`, `tests/orders/test_decide.py`, `tests/policy/test_prepared_wording.py`.
Created: `tests/orders/test_evidence_outside_the_lock.py`, `tests/standing/test_history_needs_an_order_record.py`, `AIMO/build/handback/FX-O.md`.

## Contract fields added
None. (`OrderTimeCheck.standing`, default None, is a dataclass of `orders/records.py`, not a contract.)

## Figures measured
None new.

## Pinned figures that moved in tests I do not own
None.

## Needed from another lane
1. `src/tta/policy/facts.py`, `CHANGED_FIELD_WORDS`: add `"tax_rate": "the tax rate"`, `"delivery_date": "the delivery date"`, `"sales_unit": "the sales unit"`. The fallback at line 179 already prints exactly these words, so no sentence changes.
2. P12's note in the drift sentence: `contracts/standing.py` `StandingHistory.renewals_without_order: int = 0` (set in `standing_history` from `renewals_without_order`), and `src/tta/policy/drift.py` appends `tta.standing.history.not_counted_note(...)` to `DriftReport.sentence`. Until then the count is only available by calling the function, and in the log.
3. `tests/standing/test_rest_and_page.py:91`: the pin 8 → 78 (or the page change), for whoever owns `ui/standing_page.py`.

## Defaults taken; open questions
- P5: after a second check that asks for different rules, the one further evidence lookup runs with the lock held (bounded: at most once per order, only when the book changed during the first lookup).
- P5: the lock still spans the supplier re-check (`revalidate`), as the service's comment already says; only the evidence lookup was in scope.
- P9: a signer holding two named roles signs both; a signer holding neither a named role nor purchasing manager is refused as before.
- P12: a missing order is logged at warning level, never raised.

## For the interface
- Nothing new to call. An approval decided by one of two named roles when only F-10 is left now reads `status: ORDERED`, `decision.required_roles: ["finance"]`, sentence "Confirmed by Finance (demo) (finance): ordered for €265.00 net."
