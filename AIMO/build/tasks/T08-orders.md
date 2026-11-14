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
