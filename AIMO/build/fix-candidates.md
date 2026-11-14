# Fix candidates (kept by the orchestrator for the T16 rounds)

Cheap improvements seen in hand-backs that nobody owns yet. Each names the criterion it scores on.

- **SQLite refuses to rewrite the audit table** (20% controls): two triggers on `audit_events` that reject `UPDATE` and `DELETE`. Owner: store (T06 hand-back).
- **`milk` leaves out sour milk, coffee drinks and soy yoghurt** (20% precise match): an `exclude_terms` list on a product type, or name terms for `milk`. Owner: catalog (question T02-4).
- **Publish the head hash of the audit chain** (20% controls): on `/healthz` or on each order record, so cutting the end of the trail becomes visible. Owner: api.
- **Check allergen codes once, early** (20% match): at profile load and at request validation with `tta.allergens.is_known_code`. Owner: policy, api.
