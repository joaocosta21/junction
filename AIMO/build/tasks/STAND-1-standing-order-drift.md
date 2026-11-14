# STAND-1 — Standing orders, with drift detection before a renewal

Scores on the 20% "autonomy and controls" ("what the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable") and on Valio's example scenario, verbatim: "Standing order drift detection: the agent learns a kitchen's recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it."

Hand back by **15:30**. Other agents work at the same time on the delivery and sustainability comparison (SUST-1, in `offers/`), recipes (MENU-1) and a rule-based reader (FALLBACK-1).

## What exists
- Since `576e4cc`, `PurchaseRequest.standing_order_id` exists in the contract: "The standing order this request renews: its history is checked (rule P-08). It can only add a check, never remove one." Nothing reads it yet.
- The policy context is built in two places: `src/tta/offers/options.py` (`context = PolicyContext(now=now, day_committed_net_eur=deps.day_spend(profile.profile_id))`) at offer time, and `src/tta/orders/checking.py` (`_look`) at order and approval time. `OfferDeps` (`offers/deps.py`) carries `day_spend`. Rule P-02 and `orders/spend.py` are the pattern to follow: a fact the engine needs that is not on the option.
- `AIMO/USE-CASES.md` §6 measured today's gap: seven orders of `469363` growing from 100 to 290 L were all AUTO with no rule fired.
- The mock has **no order history**. Any history the demo shows is synthetic and must say so wherever it appears.

## Build
1. **Contract** `src/tta/contracts/standing.py` (new): a standing order (id, profile, agent, a name, the typed `PurchaseRequest` it renews, cadence in days, created at) and its history (past renewals: when, per line product id, quantity, unit, unit price net EUR, the order id when there is one, and `synthetic: bool`). `PolicyContext` (in `contracts/policy.py`) gets an optional history field; `None` means "not a renewal" and must **not** count as a missing fact (F-03).
2. **Rule P-08** in `src/tta/policy/rules.yaml`, a profile rule (`fixed: false`), wired as P-02 is: a renewal whose quantity on a line, or whose unit price on a line, differs from the median of that line's last N renewals by more than the profile's tolerance goes to a human (purchasing manager). Its sentence states the numbers ("290 L this week against a median of 100 L over the last 6 renewals, more than the 25% tolerance of profile hotel-kitchen"). Fewer than a minimum number of past renewals: the rule does not fire, and the offer says the history is too short to judge. The profile setting (name it, e.g. `standing_order_drift_ratio`) goes in `BuyerProfile`, both profile files, and the "Your kitchen" page (`ui/kitchen_page.py`, `templates/kitchen.html`) with its rule sentence, as the other settings are shown. Named constants for N and the minimum.
3. **Plumbing:** `OfferDeps` gets a lookup of a standing order's history by profile and id; `offers/options.py` (only the `PolicyContext(...)` line and what it needs) and `orders/checking.py` pass it into `PolicyContext`. An unknown `standing_order_id` for the caller's profile is an `invalid-request` with a plain sentence.
4. **Store:** standing orders and their renewals in both `SqliteStore` and the PostgreSQL store (`src/tta/store/`), with the same port. The audit trail gets events for "standing order created" and "renewed" (with the drift found) in `src/tta/audit/` (buyer and supplier sentences, as the other events have).
5. **Service** `src/tta/standing/` (new package): create a standing order from a typed request; renew it (optionally with this week's quantities) → an offer built from the stored request with `standing_order_id` set → the normal order flow (`place_order` on the top option, within authority or to a human). The renewal is recorded in the history when an order exists. A demo loader that creates "Weekly lactose-free milk, hotel kitchen" (100 L of `469363` a week) with 6 synthetic past renewals, labelled synthetic, built from the capture's prices.
6. **REST** in a new module `src/tta/api/standing_routes.py` (an `APIRouter` under `/v1`): `POST /v1/standing-orders`, `GET /v1/standing-orders`, `GET /v1/standing-orders/{id}`, `POST /v1/standing-orders/{id}/renew`. Same identity, errors (RFC 9457) and rate limits as `api/routes.py` (import its dependencies; do not edit it). Export a function the orchestrator includes in `api/app.py`.
7. **Page** `src/tta/ui/standing_page.py` + `templates/standing.html`: list the book's standing orders, load the demo one, renew with this week's quantity, show the history (synthetic marked), the drift found and the outcome (ordered alone, or the approval it waits for, with a link to `/approvals`). Export `add_routes(app, site)` as the other page modules do; the orchestrator registers it and adds the menu link.

## Owns (exception to AGENT-RULES rule 1: these contract files are yours for this task)
- `src/tta/contracts/standing.py` (new), `PolicyContext` and `BuyerProfile` in `src/tta/contracts/policy.py`, new methods on the store port in `src/tta/contracts/ports.py` (only additions)
- `src/tta/policy/` (rules.yaml P-08, facts, profile files), `src/tta/store/`, `src/tta/audit/` (new event types and sentences), `src/tta/orders/checking.py`, `src/tta/offers/deps.py` and the `PolicyContext(...)` line in `src/tta/offers/options.py` (SUST-1 owns the rest of `offers/`: touch nothing else there)
- `src/tta/standing/` (new), `src/tta/api/standing_routes.py` (new), `src/tta/ui/standing_page.py` (new), `src/tta/ui/templates/standing*.html` (new), `src/tta/ui/kitchen_page.py`, `src/tta/ui/templates/kitchen.html`
- tests: `tests/standing/` (new), and tests under `tests/policy/`, `tests/store/`, `tests/audit/`, `tests/orders/` for what you change
- `AIMO/build/handback/STAND-1.md`, `AIMO/build/questions/STAND-1.md`

Not yours: `src/tta/api/app.py`, `api/routes.py`, `api/wiring.py`, `api/sandbox.py`, `ui/routes.py`, `templates/base.html`, the MCP surface, docs. The orchestrator wires and registers. Say in the hand-back exactly what to add and where (the function to call, its arguments), including what each page sandbox needs.

## Live service
The PostgreSQL store's tests run against the real Aiven service when `DATABASE_URL` is set (approved: creating and using tables there). Use the test schema the existing tests use, never the deployed app's schema. No Valio, Gemini or Context.dev calls.

## Checks before hand-back
- `.venv/bin/python -m pytest tests/standing tests/policy tests/store tests/audit tests/orders tests/ui/test_kitchen_page.py -q -p no:cacheprovider` (set `COVERAGE_FILE` to a scratch path) all pass; every existing policy test still passes (P-08 never fires on a request with no `standing_order_id`).
- `.venv/bin/ruff check` on every file you touched.
- In the hand-back: the demo run, verified in replay — the demo standing order renewed at 100 L (the verdict and why) and at 290 L (P-08 with its sentence), with the audit sentences.
