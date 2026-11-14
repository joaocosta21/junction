# Review of the whole diff (task E3) — findings and where each went

Three reviewers read `overnight-build..HEAD` at high effort with the question "what is wrong with this". The orchestrator keeps this list: each finding, the lane that got it, and its state. "Confirmed" = the reviewer ran code; "read" = read from code.

## Silent failures (`silent-failure-hunter`, in at Sat 14 Nov about 20:25)

| # | Sev | Where | What | Basis | Sent to | State |
|---|---|---|---|---|---|---|
| S1 | HIGH | `evidence/matching.py:119` | A product with no brand passes the "page shows the brand" check for any page. 3,083 of 17,546 products have no brand, and all of them also have no allergen statement (whole catalog) | confirmed | FX-EV | open |
| S2 | HIGH | `evidence/reading.py:44`, `alignment.py:177` | Page terms over 80 characters or past 20 are dropped without a trace; the allergen is then answered "the page does not name it" | confirmed | FX-EV | open |
| S3 | HIGH | `agent/rules_reader.py:166` | A trailing sentence part with no quantity is dropped without a question: "500 kg of butter, unsalted", "200 litres of milk, cancel the order" | confirmed | L1-3 | open |
| S4 | HIGH | `agent/days.py:114` | A date that cannot exist ("31 February") makes the request undated; "before noon" is dropped; "next Friday" is guessed | confirmed | L1-3 | open |
| S5 | MED | `api/suggesting.py:151` | A failure to compute suggestions leaves an offer note and a log line but no audit event; a supplier failure leaves no log line | read | L4-2d | open |
| S6 | MED | `api/service.py`, `suggesting.py:215` | An accepted suggestion in live mode is ignored without a note; a failed lookup says "no earlier offer showed it" | read | L4-2d | open |
| S7 | MED | `api/wiring.py:147`, `store/postgres.py:373`, `api/health.py:105` | The fall-back from PostgreSQL to SQLite hides the cause, and applies in prod, where orders and the trail would be lost at restart | read | L4-2d | open |
| S8 | MED | `api/signing.py:134`, `deploy/modal_app.py` | The deployed gateway can only sign with a throwaway key: `TTA_SIGNING_KEY` is not passed to the container; `/healthz` stays "ok" | read | FX-EV (deploy), L4-2d (health) | open |
| S9 | MED | `deploy/witness.py:73` | The witness reads an unmoved head as healthy, so it cannot see a gateway that fell back to SQLite | read | FX-EV | open |
| S10 | MED | `deploy/evidence_batch.py:154`, `scripts/record_evidence.py:104` | The scripts exit 0 after total failure; an unreadable paid answer is not stored | read | FX-EV | open |
| S11 | MED | `catalog/kinds.py`, `offers/substitutes.py:288` | A flavour no word list knows reads as plain ("Rum & Raisin", "Tiramisu", "Cookies & Cream", honey), and 14,685 of 17,546 products have none of our 32 types, so type is not judged for them (whole catalog): such a swap reads "Replaceable" and F-12 does not fire | confirmed | FX-K | open |
| S12 | LOW | `offers/substitutes.py:215` | A listed substitute missing from the catalog is dropped without a note | read | FX-K | open |
| S13 | LOW | `api/app.py:114` | A customer whose standing orders cannot be built at start is skipped; `/healthz` does not say | read | L4-2d | open |
| S14 | LOW | `customers/checks.py` | The docstring says the checks run at start-up; nothing calls them | read | FX-K | open |
| S15 | LOW | `suggestions/alternatives.py:112`, `supplier.py:142` | An unknown product type in a customer file gives silent "no related product" | read | FX-K | open |
| S16 | LOW | `api/suggesting.py:176` | After a validation error the buyer's view says nothing was dropped | read | L4-2d | open |
| S17 | LOW | `evidence/answers.py:142` | The on-disk request count is used only when passed in; the scripts pass none, so the approved total is not enforced across runs | read | FX-EV | open |
| S18 | LOW | `store/postgres.py`, `api/mcp_origin.py`, `deploy/modal_app.py` | Left-over `getattr(settings, name, default)` for settings that now exist | read | FX-EV, L4-2d | open |
| S19 | LOW | `policy/premium_facts.py` | A missing premium reads as 0; documented | read | — | accepted |

Found sound by this reviewer: the suggestion guard, the formula measure, the stand-in and safe-first code, F-10, F-11 and F-12's missing-fact paths, the demo-clock and signing-key checks at start, the MCP origin check, the evidence finder's failure paths, the witness's cut or rewritten trail.

## Python (`python-reviewer`)
Not in yet.

## Security (`security-reviewer`)
Not in yet.
