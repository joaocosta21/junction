# Fix candidates (kept by the orchestrator for the T16 rounds)

Cheap improvements seen in hand-backs that nobody owns yet. Each names the criterion it scores on. Items of round 1 that became fix tasks are gone from this list.

- **F-05 wording** (20% controls): for a substitute that raises "may contain" to "contains", the rule's title and message still say "adds an allergen the original does not declare". Owner: policy (`rules.yaml`). From FIX-1 and FIX-3.
- **Expiry boundary in orders** (15% exceptions): `src/tta/orders/records.py` `is_past_order_by` uses `deadline < now`; the policy, availability and the offer re-check use `<=`. At that one instant the order still shows as pending while the policy blocks it. Owner: orders.
- **F-07 on a dated option with an unknown delivery-date claim on a line** (20% controls): defence in depth against an offer whose needed-by check contradicts its lines. Owner: policy.
- **`SubstituteAllergenCheck.raised`** (15% openness): a field of its own for raised allergens instead of listing them under `added`. Owner: contracts, allergens.
- **Supplier error details** (15% production path): budget file, recording and replay capture errors still name files and settings in the detail a caller sees. Owner: valio (FIX-4 hand-back).
- **Publish the head hash of the audit chain** (20% controls): on `/healthz` or on each order record. Owner: api (needs `AuditTrail.head()` from FIX-2).
- **A unit of work in the store** (15% production path): order, approval and audit event saved in one transaction; a version check on saves. Owner: store, orders. Next step, not tonight.
