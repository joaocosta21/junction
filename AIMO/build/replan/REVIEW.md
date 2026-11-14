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

## Python (`python-reviewer`, in at Sat 14 Nov about 20:50)

Its overall reading: nothing in the code read breaks the audit hash chain or the rule that no order is placed alone with the buyer's setting off.

| # | Sev | Where | What | Basis | Sent to | State |
|---|---|---|---|---|---|---|
| P1 | HIGH | `agent/days.py` | A deadline that does not resolve is dropped: "by 31.2.", "by 32.11.", "by 2026-02-30", "by Mon", "by noon" are read with no date and no question (extends S4) | confirmed | L1-3 | open |
| P2 | HIGH | `offers/options.py:338,375`, `planning.py:86` | An option with a substitute whose stock is not confirmed is titled and summarised as a full fill: bakery, `469363`, 1,000 L: "the 1,000 L asked for, for €1,574.48" while 616 L are not confirmed; only the rule sentence says so | confirmed | FX-K | open |
| P3 | HIGH | `suggestions/guard.py:163` | Under "declared only" a product with no allergen statement passes the suggestion guard, although the offer labels it "allergen not ruled out". Shipped profiles are all strict; reachable through a request line | confirmed | FX-K | open |
| P4 | MED | `ui/shop_api.py:219-317` | The shop's routes are `async` and call the synchronous service directly: one slow call blocks every visitor | read | L4-2d | open |
| P5 | MED | `orders/service.py:77-97` | The order book's lock is held across the web-evidence lookup | read | FX-O | fixed (FX-O) |
| P6 | MED | `agent/quantity.py:58` | "1,250 kg" is read as 1,250 without a word; a Finnish buyer may mean 1.25. Decided: keep the thousands reading and say it in the reading; a comma before one or two digits is a decimal | read | L1-3 | open |
| P7 | MED | `agent/days.py` | "before Friday" is read as "by Friday". Decided: read as by Thursday, and say so | read | L1-3 | open |
| P8 | LOW | `api/wiring.py:133` | The evidence finder's HTTP client is not closed at shutdown | read | L4-2d | open |
| P9 | LOW | `policy/human_approval.py:111` | When only F-10 remains, every role the old approval named must still sign, against the docstring | read | FX-O | fixed (FX-O) |
| P10 | LOW | `suggestions/alternatives.py:126` | The cheaper and larger-pack kinds rely entirely on the guard (fine once P3 is fixed) | read | FX-K | open |
| P11 | LOW | `suggestions/trend.py:39,73` | A median of 0 raises and loses all suggestions of that offer | read | FX-K | open |
| P12 | LOW | `standing/history.py` | A renewal whose order cannot be found still counts as history | read | FX-O | fixed (FX-O) |
| P13 | LOW | several | `sandbox.KITCHEN_SETTINGS` lacks the two new settings; `shop_api._body` parses before the guard; Valio's reader is rendered "A human at the buyer"; `_claim_note` can overstate; more than 1,000 ids in one lookup; three field words missing in `audit/phrases.py` | read | L4-2d, FX-K, FX-O | open |
| P14 | LOW | `audit/supplier_decisions.py` | Valio's view shows the product id for F-03 fired by an allergen outcome, which hints that the buyer excludes an allergen (the same information is masked for P-04) | read | wave 4 (audit) | open |

## Security (`security-reviewer`, in at Sat 14 Nov about 21:10)

0 critical, 2 high, 4 medium, 4 low. It called every route with no token and with the supplier's, an approver's and an agent's token.

| # | Sev | Where | What | Basis | Sent to | State |
|---|---|---|---|---|---|---|
| H1 | HIGH | `ui/shop_api.py` | The shop's routes block the event loop: one slow call freezes the whole app, `/healthz` included (same as P4) | confirmed | L4-2d | open |
| H2 | HIGH | `api/service.py`, `contracts/request.py:16` | Total growth is unbounded: one offer with 5 lines of 2,000 characters stores about 262 kB; at the address cap that is about 0.9 GB an hour, in a trail that cannot be deleted | confirmed (size) | FX-S, after L4-2d | open |
| M1 | MED | `audit/supplier_decisions.py:144`, `audit/facts.py:98`, `ui/supplier_view.py` | Valio's view leaks the buyer's allergen exclusions through counts ("18 declaring / 5 stating nothing"), and the strict or declared-only rule | confirmed | FX-M1 | open |
| M2 | MED | `api/signing.py:117,152,164` | The "demo key" marker is outside the signature: a demo-signed record can be relabelled as signed with a set key and still verifies | confirmed | FX-S | open |
| M3 | MED | `api/service.py:163` | Product search has no rate limit and costs about 0.9 s of CPU with 10 terms | confirmed | FX-S | open |
| M4 | MED | `deploy/modal_app.py:144`, `orders/service.py` | Any visitor of the public link can spend the Context.dev budget (up to 40 calls of 100 credits), and the lookup is held under the order book's lock | read | FX-EV (the key stays off the link), FX-O (the lock) | open |
| L1 | LOW | `policy/facts.py:396` | `stands_in_for` is still free text that reaches F-09's sentence (A3 F4 half closed) | read | FX-S | open |
| L2 | LOW | `evidence/reading.py`, `wording.py:73`, `alignment.py:165` | A web page's name can close the quotation marks in the sentence shown to the person who signs | read | FX-EV | open |
| L3 | LOW | `standing/service.py:215` | The supplier's token gets 403 for an existing standing order and 404 for an unknown one | read | FX-O | fixed (FX-O) |
| L4 | LOW | `api/discovery.py:126` | Host and forwarded-proto headers go into the discovery documents; not exploitable without a shared cache | read | — | accepted |
| F3 | — | `deploy/modal_app.py` | From the earlier review, still open: no `TTA_TRUSTED_PROXY_HOPS`; if Modal shows one peer address, all visitors share one rate-limit bucket. Can only be checked on the deployed copy | read | the redeploy check | open |

Found sound: authorisation on every REST route and MCP tool (no approval tool; the supplier refused on everything but audit, recipes and schemas); the MCP `Origin` check; the customers route; the signing's canonical form and key handling; the shop's cross-site guards and its JavaScript escaping; idempotency keys; the demo-clock guard; no secret printed by any script; parameterised SQL. Earlier findings F1, F2, F5, F6 hold.

Not checked by any reviewer: live Gemini and Context.dev answers, PostgreSQL on Aiven, the deployed app's peer address, races between two approvers.
