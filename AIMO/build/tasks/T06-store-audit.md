# T06 — Store and audit trail

**Scores on:** 20% ("how decisions are logged and auditable") · the audit trail "for both buyer and Valio Aimo" · 15% (open format).
**Needs:** T00. **Owns:** `src/tta/store/`, `src/tta/audit/`, `tests/store/`, `tests/audit/`.
**Read first:** SPEC §8, §9 · `AIMO/policy/LOG-FORMAT.md` (Gabriela's Friday work; drop its "data-quality report back to Valio Aimo") · the CloudEvents 1.0 specification (read it; do not rely on memory) · `tta/contracts/audit.py`, `order.py`, `ports.py`.

## Build
- **Store** implementing the `Store` port on SQLite (standard library): offers, orders, approvals, idempotency keys, audit events. JSON columns, WAL mode, path from config, in-memory for tests. No ORM.
- **Audit** implementing the `AuditSink` port:
  - `record(...)` builds a CloudEvents 1.0 envelope; the data holds the actor, the sentence, the rule ids and facts, the policy hash, the previous event's hash and this event's hash (SHA-256 over the canonical JSON).
  - Append-only: the module exposes no update and no delete.
  - `verify_chain()` → ok, or the first event that does not match.
  - **Sentences** from templates, one per event type of SPEC §9, written for a person who was not there. Never produced by a model.
  - `view(order_id, reader)` → the events as the buyer or as the supplier sees them, following the table of SPEC §9.

## Tests to write first
- Round trip of an offer, an order, an approval.
- An idempotency key stored twice returns the first record.
- Changing one stored event makes `verify_chain()` name it.
- Every envelope has the attributes CloudEvents requires.
- The supplier view contains no limit value, no allergen exclusion, no approver name or note; the buyer view contains them.
- Exact sentence for: an order placed by the agent within its authority; an order sent to a human, naming the rules; an approval by a named role choosing another option; a rejection; an expiry.
