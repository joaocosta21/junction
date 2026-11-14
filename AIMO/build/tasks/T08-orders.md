# T08 — Orders and approvals

**Scores on:** 30% (the order and approval half of the flow) · 20% (human sign-off) · Core 2 and Core 3.
**Needs:** T05, T06. **Owns:** `src/tta/orders/`, `tests/orders/`.
**Read first:** SPEC §7, §8, §9 · the contracts `order.py`, `policy.py`, `ports.py`.

## Build — a service over the ports (`Store`, `PolicyEngine`, `OfferRevalidator`, `AuditSink`, `Clock`); use fakes for the revalidator in tests
- **`place_order(offer_id, option_id, identity, idempotency_key)`:** re-check → policy → `ORDERED`, `PENDING_APPROVAL`, or the typed error for stale, expired or blocked. An audit event at every step.
- **`decide(approval_id, identity, decision, option_id=None, note=None)`:** only an approver identity; the approval completes when the approving humans hold every required role; choosing another option re-runs the policy on it, and `BLOCK` still blocks; a re-check before `ORDERED`.
- **Expiry:** a pending order past `valid_until` becomes `EXPIRED` when it is next read or listed.
- **Daily spend** per profile: orders in `ORDERED` and `PENDING_APPROVAL` on the clock's current date.
- **Idempotency:** the same key returns the first outcome and creates nothing.
- The order record keeps the statements it relied on and says that the mock has no order endpoint (SPEC §8).

## Tests to write first
- `AUTO` → `ORDERED`, with no approval created.
- `APPROVAL` → `PENDING_APPROVAL` → approve → `ORDERED`; reject → `REJECTED`; time passes → `EXPIRED`.
- Stale price at order time → `offer-stale`, no order. Blocked → `policy-blocked`, no order, one audit event.
- The same key twice → one order.
- An agent identity calling `decide` → `not-authorised`, and an audit event records the attempt.
- Two roles required: one approver with one role leaves it pending; the second completes it.
- The approver picks the unconfirmed alternative → the policy runs again → `ORDERED` with F-01 recorded as approved by that human.
- The second order of the day crosses the daily limit → `APPROVAL` by P-02.
- The audit events of one order, in order, form a valid chain.

## Notes from wave 1 (read the hand-backs in `AIMO/build/handback/` for T05 and T06)
- **Entry points:** `SqliteStore()` in memory for tests, `open_store(settings)` (`tta.store.sqlite_store`) · `AuditTrail(store, clock, policy=engine)` (`tta.audit`; the docstring of `tta/audit/__init__.py` lists what each event type reads from `AuditContext` — pass the objects, the trail writes the sentences) · `RulePolicyEngine.from_files()` (`tta.policy`).
- Implement the `OrderService` port of `tta/contracts/ports.py`. The service receives an `AuditSink` that is already built; it never builds one. The audit trail has its own clock (real time, decision T06-2); your `Clock` is the data clock, used for expiry and for the day's spend.
- **At order time** call `evaluate(option, profile, PolicyContext(now=..., day_committed_net_eur=..., at_order_time=True, revalidation=...))`. The option must carry `valid_until` or F-03 fires. When F-04 fires, its `FiredRule.facts` carry `revalidation.expired` and `revalidation.changes`: raise `OfferExpired` or `OfferStale` accordingly (with the changes as an extension member), write `order.not_placed`, create no order. T09 adds the fresh offer to the response; you do not build offers.
- **The day's spend** as a module-level function `day_committed_net_eur(store, clock, profile_id) -> Decimal` in `tta.orders`, used by the service method of the same name. T09 wires the same function into the offer builder.
- **Who may decide:** an approver whose `profile_id` is the order's and who holds at least one role still missing. An approver of another buyer is `not-authorised`. An agent on `decide` is `not-authorised` and writes `authorisation.refused` (F-06). The supplier reader can do neither.
- **Who may read:** an agent or approver reads orders and approvals of its own profile only; the supplier reads none through this service (it has the audit view).
- Demo approvers exist for every role on both profiles; the identities of `tests/conftest.py` cover the hotel's purchasing manager and finance and the ward's dietitian. Build others in your own `conftest.py` when a test needs them.
- Ids: `ord_` and `apr_` + 12 hex characters. The reliance statements are built from the option's lines at the moment of the re-check.
- Coverage runs: set `COVERAGE_FILE` to a file in your scratch directory; agents running in parallel share `.coverage` in the repository root.
