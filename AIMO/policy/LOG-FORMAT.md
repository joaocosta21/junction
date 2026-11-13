# AIMO audit log — format (draft v0.1, Bio 2)

Every decision the agent or a human makes becomes **one event**. An event is JSON (machine-verifiable) **and** carries one plain-English sentence (human-readable). The sentence is built from the `message` templates in [`policy.yaml`](policy.yaml) — **no LLM writes it**, so it can never say something the data does not.

Storage: JSONL file tonight → **Aiven Postgres** table in Fase 1 (same fields, see bottom).

## Event fields

| Field | Type | Meaning |
|---|---|---|
| `event_id` | string (uuid) | unique id of this event |
| `ts` | datetime, Helsinki offset | when it happened |
| `order_id` | string | the order this belongs to |
| `seq` | int | 1, 2, 3… within the order |
| `actor` | `{type: agent\|human\|system, id, role?}` | who did it; `role` for humans (from `policy.yaml` roles) |
| `action` | enum (below) | what happened |
| `policy_id`, `policy_version`, `policy_hash` | string | which rules were in force — `policy_hash` from `policy_check.py` |
| `verdict` | `AUTO\|APPROVAL\|BLOCK` \| null | only on `POLICY_EVALUATED` |
| `rules_fired` | list of `{id, verdict, approver_role?, line_id?, message}` | every rule that fired, not just the winner |
| `trust_findings` | list of `{code, line_id?, message}` | data problems detected (contradictions, sentinels…) |
| `inputs` | object | the facts the decision used: lines, quantities, prices, totals |
| `sentence` | string | one human-readable sentence summarising the event |
| `visibility` | `BUYER\|SUPPLIER\|BOTH` | who may see it — the log is for buyer *and* Valio Aimo |
| `prev_hash` | string | `hash` of the previous event of this order (`"GENESIS"` for seq 1) |
| `hash` | string | `sha256:` of this event's canonical JSON without `hash` — makes the log tamper-evident |

### Actions
`REQUEST_RECEIVED` · `CANDIDATES_FOUND` · `OFFER_ISSUED` · `POLICY_EVALUATED` · `APPROVAL_REQUESTED` · `HUMAN_DECIDED` · `ORDER_PLACED` · `ORDER_BLOCKED` · `TRUST_FINDING` · `OFFER_EXPIRED`

### Rules for writing events
1. **Append-only.** Never edit or delete an event; corrections are new events.
2. `rules_fired` lists **all** fired rules, so the approval panel can show every reason, not only the strongest.
3. Every number in `sentence` must appear in `inputs` (test this when the engine exists).
4. Prices are **ex-VAT** in `inputs`; `tax_rate` comes from the price API, never from the catalog `vatCode`.
5. Quantities are in **sales units** (`ST`, `KI`…). Litres are shown only as a derived value with its `volume_source`.

---

## Example 1 — canonical milk order → APPROVAL (spend cap)
*1,000 L lactose-free milk → product 464306 → 1,000 ST → €1,010.00 ex-VAT. Cap is €750, so a human decides.*

```json
{
  "event_id": "7d2f0c1e-5b7a-4a8e-9a51-0b1f3c2d4e01",
  "ts": "2026-11-13T23:05:12+02:00",
  "order_id": "ord-0001",
  "seq": 4,
  "actor": {"type": "agent", "id": "buyer-agent-hotel-01"},
  "action": "POLICY_EVALUATED",
  "policy_id": "aimo-default",
  "policy_version": "0.1.0",
  "policy_hash": "sha256:05e4f60893e948e15dcb35a77dfa5571701b623960311d4935e1fd299b472f1c",
  "verdict": "APPROVAL",
  "rules_fired": [
    {"id": "P-01", "verdict": "APPROVAL", "approver_role": "purchasing_manager",
     "message": "Order total €1010.00 exceeds the €750 autonomous spend cap."}
  ],
  "trust_findings": [],
  "inputs": {
    "allergen_policy": "REJECT_CONTAINS_ONLY",
    "constrained_allergens": [],
    "lines": [{
      "id": "464306",
      "name": "Valio Hyvä suomalainen Arki Eila semi skimmed milk drink 1 l lactose free",
      "qty_sales_units": 1000, "sales_unit": "ST",
      "litres_per_sales_unit": 1.0, "volume_source": "catalog_volume",
      "unit_price_ex_vat": 1.01, "tax_rate": 13.5, "line_total_ex_vat": 1010.00
    }],
    "total_ex_vat": 1010.00
  },
  "sentence": "The order of 1,000 ST of 464306 (€1,010.00 ex-VAT) exceeds the €750 autonomous cap, so it was sent to the purchasing manager for approval.",
  "visibility": "BOTH",
  "prev_hash": "sha256:…",
  "hash": "sha256:…"
}
```

…followed by the human's decision:

```json
{
  "order_id": "ord-0001", "seq": 6, "ts": "2026-11-13T23:11:40+02:00",
  "actor": {"type": "human", "id": "maija", "role": "purchasing_manager"},
  "action": "HUMAN_DECIDED",
  "policy_hash": "sha256:05e4f608…",
  "inputs": {"decision": "APPROVE", "rules_acknowledged": ["P-01"], "comment": "Weekly volume, OK."},
  "sentence": "Maija (purchasing manager) approved the €1,010.00 order at 23:11, acknowledging rule P-01.",
  "visibility": "BOTH"
}
```

## Example 2 — hospital nut-free ward → BLOCK (may contain + supplier contradiction)
*Product 462382 (frozen carrot bread dough) states FREE_FROM tree nuts (AN) **and** MAY_CONTAIN walnut (SW). One of 44 such products in the catalog. Prices are left out: the line is blocked before price matters.*

```json
{
  "order_id": "ord-0002", "seq": 4, "ts": "2026-11-13T23:20:03+02:00",
  "actor": {"type": "agent", "id": "buyer-agent-hospital-01"},
  "action": "POLICY_EVALUATED",
  "policy_id": "aimo-default", "policy_version": "0.1.0",
  "policy_hash": "sha256:05e4f60893e948e15dcb35a77dfa5571701b623960311d4935e1fd299b472f1c",
  "verdict": "BLOCK",
  "rules_fired": [
    {"id": "P-03a", "verdict": "BLOCK", "line_id": "462382",
     "message": "Vaasan Porkkanaleipätaikina 23x440g frozen carrot bread dough may contain traces of an excluded allergen."}
  ],
  "trust_findings": [
    {"code": "ALLERGEN_FAMILY_CONTRADICTION", "line_id": "462382",
     "message": "Vaasan Porkkanaleipätaikina 23x440g frozen carrot bread dough says it is free from tree nuts but may contain a specific nut; the stricter statement was used."}
  ],
  "inputs": {
    "allergen_policy": "REQUIRE_EXPLICIT_FREE_FROM",
    "constrained_allergens": ["AN"],
    "lines": [{
      "id": "462382", "qty_sales_units": 4, "sales_unit": "KI",
      "allergens": {"AN": "MAY_CONTAIN"},
      "allergen_raw": {"AN": ["FREE_FROM"], "SW": ["MAY_CONTAIN"]}
    }]
  },
  "sentence": "462382 was blocked for the nut-free ward: it claims to be free from tree nuts but also says it may contain walnut, and this ward requires an explicit, consistent free-from statement.",
  "visibility": "BOTH",
  "prev_hash": "sha256:…", "hash": "sha256:…"
}
```
`visibility: BOTH` on purpose: the contradiction is a **data-quality report back to Valio Aimo**.

## Example 3 — smaller milk order → AUTO
*500 L of the same milk = €505.00, below the €750 cap; no rule fires.*

```json
{
  "order_id": "ord-0003", "seq": 4, "ts": "2026-11-13T23:31:47+02:00",
  "actor": {"type": "agent", "id": "buyer-agent-hotel-01"},
  "action": "POLICY_EVALUATED",
  "policy_id": "aimo-default", "policy_version": "0.1.0",
  "policy_hash": "sha256:05e4f60893e948e15dcb35a77dfa5571701b623960311d4935e1fd299b472f1c",
  "verdict": "AUTO",
  "rules_fired": [],
  "trust_findings": [],
  "inputs": {
    "allergen_policy": "REJECT_CONTAINS_ONLY", "constrained_allergens": [],
    "lines": [{"id": "464306", "qty_sales_units": 500, "sales_unit": "ST",
               "litres_per_sales_unit": 1.0, "volume_source": "catalog_volume",
               "unit_price_ex_vat": 1.01, "tax_rate": 13.5, "line_total_ex_vat": 505.00}],
    "total_ex_vat": 505.00
  },
  "sentence": "No guardrail was triggered: 500 ST of 464306 for €505.00 ex-VAT is within the €750 autonomous cap, so the agent placed the order itself.",
  "visibility": "BOTH",
  "prev_hash": "sha256:…", "hash": "sha256:…"
}
```

---

## Aiven Postgres table (Fase 1)

```sql
CREATE TABLE audit_event (
  event_id       uuid PRIMARY KEY,
  order_id       text        NOT NULL,
  seq            int         NOT NULL,
  ts             timestamptz NOT NULL,
  actor_type     text        NOT NULL CHECK (actor_type IN ('agent','human','system')),
  actor_id       text        NOT NULL,
  actor_role     text,
  action         text        NOT NULL,
  policy_id      text        NOT NULL,
  policy_version text        NOT NULL,
  policy_hash    text        NOT NULL,
  verdict        text        CHECK (verdict IN ('AUTO','APPROVAL','BLOCK')),
  rules_fired    jsonb       NOT NULL DEFAULT '[]',
  trust_findings jsonb       NOT NULL DEFAULT '[]',
  inputs         jsonb       NOT NULL,
  sentence       text        NOT NULL,
  visibility     text        NOT NULL CHECK (visibility IN ('BUYER','SUPPLIER','BOTH')),
  prev_hash      text        NOT NULL,
  hash           text        NOT NULL,
  UNIQUE (order_id, seq)
);
-- append-only: the app role gets INSERT and SELECT, never UPDATE or DELETE.
```

## What other people need to provide (from `policy.yaml` → `facts`, status `todo`)

**Bio 1 — add to the candidate record in `catalog_search.py`:**
- `allergens` — map code → `CONTAINS | MAY_CONTAIN | FREE_FROM | SILENT`. Gotchas found in the catalog:
  - `UNDECLARED` unit exists (303×) → SILENT.
  - 3 products state the same code twice with conflicting units → least safe wins.
  - 44 products say FREE_FROM `AN` and MAY_CONTAIN a specific nut.
  - Lactose-free ≠ milk-free: 464306 is `FREE_FROM_LACTOSE` (nutritionalClaim) but `AM CONTAINS`.
- `unspecified_allergen` — X99 stated as CONTAINS/MAY_CONTAIN.
- `variable_unit` (`synkkaData.variableUnit`), `has_deposits` (`deposits` non-empty).

**CS — from the gateway:** `unit_price_ex_vat`, `tax_rate`, `price_valid_to` (price API); `deliverable`, `available_amount_is_sentinel`, `closing_time_status` (availability API).

**Request / agent:** `qty_sales_units`, `allergen_policy`, `constrained_allergens`, `quantity_in_litres`, substitution flags.

## Open decisions for the team
1. **Spend cap €750 or €1,500?** At €750, the canonical milk order is the "escalates to a human" case for the 13:00 checkpoint.
2. **`allergen_policy` required with no default?** (Proposal: yes — defaulting it is a safety decision.)
3. **MAY_CONTAIN under the lenient policy:** dietitian approval (current) or block?
4. **Hash chain on events:** keep (≈15 min) or drop?
