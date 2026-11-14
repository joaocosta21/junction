# T12 — Pages: demo, approvals, order and audit

**Scores on:** 30% (the visible half of the flow) · 20% (the human approval panel, the readable audit trail). Judges give each team little time: the first screen must show what is confirmed, what is not, and what was excluded and why.
**Needs:** T09. **Owns:** `src/tta/ui/`, `tests/ui/`.
**Read first:** SPEC §12, §9 · `AIMO/PLAN.md` §3 (what the judge sees in each scenario) · the contracts `offer.py`, `order.py`, `audit.py`.

## Build — server-rendered Jinja2, plain CSS and a little plain JavaScript, no external assets (the venue network may fail)
- **`/`** — a text box with the three scenario requests as one-click examples, a "who is asking" selector (the demo agents and their profiles), Run. Result, top to bottom: the parsed request; the options side by side, each line with a mark per claim (confirmed, not confirmed, ruled out — a word and a colour, never colour alone); the constraint checks; the verdict with the rules in plain sentences; the excluded products with reasons (collapsed after the first five); then the outcome: "Ordered by the agent" or "Sent for approval".
- **`/approvals`** — pending approvals as cards: why a human is needed, the options, "order by" time, approve (with a choice of option) or reject with a note; a selector for the demo approver and role.
- **`/orders/{id}`** — the order record, the statements it relied on, and the audit trail as a timeline of sentences, switchable between the buyer's and the supplier's view; a mark showing the hash chain verifies.
- **`/assumptions`** — renders `docs/ASSUMPTIONS.md` when it exists.
- A visible "replay" label when the data is recorded. Illustrative values (profiles) are labelled as such.
- Pages call the same service functions as the API, with the demo identity chosen on the page. Every piece of dynamic text is escaped: product names are untrusted.
- Readable from two metres: large type, high contrast, no decoration.

## Tests to write first
- Each page answers 200 in replay.
- Scenario 1's result shows a confirmed option, an unconfirmed alternative and the exclusion reasons; scenario 2's shows "Ordered by the agent".
- Approving on `/approvals` changes the order to `ORDERED`.
- A product name containing `<script>` is rendered escaped.
- The supplier view shows no limit value.

## Hand-back extra
Start the app in replay and save a screenshot description (what is on each page, top to bottom) so the team can review without running it.

## Notes from the API (read `AIMO/build/handback/T09.md` first; `src/tta/api/hooks.py` is the exact contract of your hook)
- **The service** is `tta.api.service.Gateway`: the `GatewayService` port of `tta/contracts/ports.py` (now with `list_orders`). It checks what an identity may do, applies the rate limit, stores, and writes the audit events. Call it and nothing below it.
- **Tests:** `build_parts(settings, catalog=..., ...)` then `create_app(settings, parts=parts)` — see `tests/api/conftest.py` (a session catalog, one app per test, a database under `tmp_path`, `Settings.for_tests(...)` in replay). Copy what you need into a `conftest.py` in your own test folder; do not import from another test folder.
- **Demo tokens** (`src/tta/api/demo_tokens.yaml`): `demo-agent-hotel-kitchen`, `demo-agent-allergy-ward`, `demo-approver-hotel-purchasing`, `demo-approver-hotel-finance`, `demo-approver-hotel-dietitian`, `demo-approver-ward-dietitian`, `demo-approver-ward-purchasing`, `demo-approver-ward-finance`, `demo-supplier-valio-aimo`.
- **Tonight in replay** (capture `2026-11-14-demo`): scenario 1 (hotel, 1,000 L lactose-free milk by Monday 16 Nov 2026) → option 1 three confirmed milks, €2,580.64, `APPROVAL` by P-01; option 2 `464306` unconfirmed, €1,010.00, `APPROVAL` by F-01 and P-01. Scenario 2 (ward, 200 L plant drink, `AM` and `AW` excluded by the profile, confirmed only) → 200 × `464013`, €402.00, `AUTO` → `ORDERED`. Scenario 3: substitutes of `473609` → `471690` passes but its cut-off has passed; `471881` and `464320` fail (`SUBSTITUTE_ADDS_ALLERGEN`); best orderable `475224`. Backup: 30 kg `beef_chuck` → 30 × `466988`, €506.40, `APPROVAL` by P-06.
- **Untrusted text:** product names (`OfferLine.name`, `Exclusion.name`, `SubstituteCandidate.name`), the buyer's pasted text and approvers' notes are data. The sentences the gateway writes are already cleaned; the name fields are not.
- An offer can have one live order; a second order on it is `invalid-request`. Another buyer's id answers `not-found`. The idempotency key is 1 to 100 characters of `[A-Za-z0-9._:-]`.
- Coverage runs: set `COVERAGE_FILE` to a file in a private folder of the scratch directory.
- **Your hook:** `tta.ui.routes` defines `create_surface(context: SurfaceContext) -> ASGI app`, mounted at `/` only when `TTA_ENV` is `dev` or `demo`. `context.service` is the service, `context.demo_identities` are the nine demo identities (two agents, six approvers, the supplier), `context.settings` the settings. The pages act as the identity chosen on the page and call the service directly; no token is typed.
- **Running a request from the page:** paste → `service.parse_request(identity, text)` → `service.create_offer(identity, request)` → `service.place_order(identity, offer_id, option_id, key)` with the top option → show the order or "sent for approval". Until T10 lands the parser answers `supplier-unavailable`: the page must then still work from the three one-click examples, which carry their typed request with them (keep the typed requests of the examples in your package so the demo never depends on the model). When `service.run_agent` is available, show the agent's trace as well.
- **Forms that change state** (run, approve, reject) are POST with a per-session CSRF token; the identity selector is a cookie, not a URL parameter. Escape everything; set a Content-Security-Policy that allows no external source and no inline script (put the little JavaScript in a static file).
- A "fits, not needed" note and every other note of an offer are shown under the exclusions.
- The order page shows `GET`-equivalent data from `service.get_order`, `service.get_audit(identity, reader=...)` for both readers, the chain state, and the audit head from `/healthz`.
