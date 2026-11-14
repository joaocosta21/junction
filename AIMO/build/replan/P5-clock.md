# P5 — the demo clock (Valio's answers V6 and B3)

Agent P5, Saturday 14 Nov 2026. Every count below is over a recording (`fixtures/valio/`), never over the catalog of 17,546 products, unless it says so. Scripts and their output: `/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/replan/P5/` (`static.py`, `dist.py`, `extra.py`, `run.py`, `table.py`, `orders.py`). No repository file was changed. No outside service was called.

## 1. In five lines
1. The deadlines look static: 62 product ids are shared between the recordings (51 + 10 + 1, taken 3 h 52 min apart) and all 62 agree on every availability field compared and on the whole price record. The recordings cannot show what happens after a deadline passes: no deadline falls between them.
2. Moving the clock back frees no confirmed stock. The 366 products with a Thursday deadline are all `Terminal` with the "stock not known" placeholder. Every confirmed product is `Stock` and closes on **Sunday 15 Nov 17:00**.
3. So the six demo requests give the same options, totals and verdicts at every instant from Thursday 12 Nov 16:00 to Sunday 15 Nov 16:59. Before Thursday 15:00 no milk deadline has passed (nothing to show) and scenario 3 gets worse.
4. The real risk is the other end: from **Sunday 15 Nov 17:00** the deployed app (live mode, real clock) offers nothing, or offers and then refuses the order with `409 offer-expired`. Measured by emulation.
5. Recommend: keep the recording's own instant, **Saturday 14 Nov 2026 02:52:45 +02:00**, as the demo clock; pin the public link to it (replay) tonight; say on every page, in `/healthz`, in each offer and in its audit record that the clock is pinned and that we chose it.

## 2. What exists today
- **Three clocks.** Replay: `PinnedClock` at the capture's `time_now` (`src/tta/valio/clock.py:38-48`, `src/tta/valio/replay.py:84-86`, read from the manifest at `replay.py:136`). Live: `LiveClock`, this machine's time carried forward by the mock's `timeNow`, and it refuses a `timeNow` more than 12 hours from the machine's (`clock.py:20,73`). Audit events: `UtcClock`, real time (`src/tta/api/wiring.py:65-70,161`).
- **A cut-off is not compared with the clock but with the answer's `time_now`**: `src/tta/offers/deps.py:88` (`now=availability.time_now`), used by `classify` (`src/tta/availability/states.py:38`, `closing_time <= now` is passed). The order-time re-check reads the same (`src/tta/offers/revalidation.py:45-48`). The policy and the day's spend read the clock (`src/tta/orders/checking.py:79-84`, `src/tta/orders/spend.py:40`). In replay the two are equal. In live mode with fall-back they are not: `FallbackGateway.clock` is always the live clock (`src/tta/api/fallback.py:104-107`) while a fall-back answer carries the capture's `time_now`.
- **The deployed app is live**: `deploy/modal_app.py:99-100` (`TTA_ENV=demo`, `TTA_MODE=live`), 120 calls, then the capture (`modal_app.py:95,108-109`).
- **Labels today**: the banner "Replay: recorded Valio Aimo data, clock pinned to the recording" does not say the instant (`src/tta/ui/site.py:41`). Each offer says it ("as it stood on …", `src/tta/ui/templates/_result.html:75-76`) and carries `time_now` and `source` (`src/tta/contracts/offer.py:196`), which the audit record keeps (`src/tta/audit/facts.py:30`). `/healthz` has `mode`, `source`, `replay_capture` and no clock (measured). `docs/ASSUMPTIONS.md:31,73,141` describe the pinned clock and the two clocks.
- **Is the data static? (task 1)** `static.py`, recorded bodies only:

| Pair of recordings | Shared ids | Differ in `closingTime` | Differ in `availableDate` | Differ in amount, unit, model, block | Price records that differ |
|---|---|---|---|---|---|
| sample (Fri 23:00:35) vs demo (Sat 02:52:45) | 51 (38 with a deadline) | 0 | 0 | 0 | 0 |
| extras (Fri 23:03:30) vs demo | 10 | 0 | 0 | 0 | 0 |
| sample vs extras | 1 | 0 | 0 | 0 | 0 |

  Limit of this evidence: 0 deadlines lie between Friday 23:00:35 and Saturday 02:52:45 (`extra.py`), so we never saw a deadline pass. "Static after Sunday" is Valio's statement, not our measurement. `docs/DEMO.md:13` reports a live check at Saturday 08:12 that matched the capture (quoted, not re-run). `AIMO/docs/API.md:499-501`: `requestedDate` changes nothing.
- **Distribution in the demo capture (task 2)**, 769 products, `dist.py` with the app's own parser:

| `closingTime` | Products | Model |
|---|---|---|
| Thu 12 Nov 12:00 / 13:00 / 13:30 / 14:00 / 14:30 / 15:00 / 16:00 | 2 / 4 / 24 / 17 / 3 / **304** / 12 = 366 | all `Terminal` |
| Fri 13 Nov 13:00 | 2 (`464173`, `465869`) | `Stock` |
| Sun 15 Nov 17:00 | **256** | `Stock` |
| none (no schedule line) | 145 | — |

  `availableDate`: Monday 16 Nov on all 603 lines that carry one; 21 lines without a date (amount 0); 145 products without a schedule line. In the random sample (1,001 lines) the same shape: `Terminal` Wed 11 Nov 13:00 to Fri 13 Nov 12:30 (357, of them 229 at Thu 15:00), `Stock` 68 at Fri 13:00 and 372 at Sun 17:00; `availableDate` 16 Nov on 767 of 768.
- **The six states at candidate instants** (769 products, `classify` of `states.py`):

| Clock | Confirmed | Quantity not confirmed | Cut-off passed | Out of stock | Not deliverable | Blocked |
|---|---|---|---|---|---|---|
| Wed 11 Nov 09:00 | 125 | 478 | 0 | 21 | 145 | 0 |
| Thu 12 Nov 09:00 | 125 | 478 | 0 | 21 | 145 | 0 |
| Thu 12 Nov 14:00 | 125 | 431 | 47 | 21 | 145 | 0 |
| Thu 12 Nov 16:00, Fri 13 Nov 09:00 | 125 | 112 | 366 | 21 | 145 | 0 |
| Fri 13 Nov 14:00 to Sun 15 Nov 16:59, capture time included | 123 | 112 | 368 | 21 | 145 | 0 |
| Sun 15 Nov 18:00 and later | 0 | 0 | 603 | 21 | 145 | 0 |

  Thursday 14:00 equals 17 deadlines, so the "equal counts as passed" rule decides 17 products there (47 passed, not 30).

## 3. What Valio's answer changes
- V6 and B3 allow us to choose the date. Both notes can be read two ways. Reading 1 (ours): pin the clock to when the data was retrieved. We already do this in replay. Reading 2: go back to before the Thursday deadlines so the "order by Thursday" milk can be ordered. Measured, reading 2 buys nothing: those products become "quantity not confirmed", not confirmed (table above). B3 did not answer the rule itself (a deadline equal to now is passed); we keep `<=` and choose an instant that equals no deadline.
- The gap is not in replay. It is the deployed link (real clock) and the labels (no page says the instant or that we chose it).

**The requests at each clock (task 3).** `run.py`: the capture copied to the scratch folder with another `time_now` in its manifest, the app built on it; each offer's `time_now` equalled the instant set; `needed_by` 2026-11-16 in every run; `/v1/requests/parse` read "by Monday" as 2026-11-16 at all nine instants (reading source `recording`, re-resolved by the day rule).

| Request | Wed 09:00 · Thu 09:00 · Thu 14:00 | Thu 16:00 · Fri 09:00 · capture · Sun 12:00 | Sun 17:30 |
|---|---|---|---|
| S1: 1,000 L lactose-free milk, hotel (30 candidates) | Best confirmed €2,580.64 = 384 × `469363` + 51 × `462775` + 565 × `463380`, human (P-01). Unconfirmed alternative €1,010.00 = 1,000 × `464306`, human (F-01, P-01). Excluded 2, **no cut-off** | the same two options. Excluded 19: **17 cut-off passed**, 1 portion pack, 1 not deliverable | no option, 28 cut-off passed |
| S1 without `463380`, `462626`, `464237`, `473142` (26 candidates, through `product_ids`) | Best confirmed €1,083.39 = 384 × `469363` + 51 × `462775`, 43.5% covered, human (P-01, P-03). Alternative €1,010.00 as above. Substitute €2,512.84 with 113 × `469266` Valio Latte coffee drink at €12.65, valid until Thu 15:00 | the same best confirmed and alternative. Substitute €1,817.89 with 565 × `464237` Valio coffee milk (quantity not confirmed). Excluded 17: 15 cut-off passed | no option |
| S2: 200 L plant drink, ward | €402.00 = 200 × `464013`, agent alone. Excluded 41, 0 cut-off (6 at Thu 14:00) | the same option. Excluded 41, 12 cut-off | no option |
| Oat drink `473609`, 100 L | Unconfirmed alternative €137.00 = 100 × `473609` (F-01). Substitute €155.50 = 10 × `471690`, not confirmed, human, valid until Thu 15:00. **`475224` not offered, nothing ordered alone** | Substitute €174.00 = 100 × `475224`, agent alone. Alternative €137.00 (F-01) | no option |
| Oat drink, most reliable | €140.00 = 100 × `470863` alone; cheapest €133.00 = 100 × `472145`; alternative €117.00 = 100 × `468465`. Excluded 9 (15 at Thu 14:00) | the same. Excluded 20, 11 cut-off | no option |
| Cream 10 L | €33.10 = 10 × `463797` alone; alternative €26.30 = 10 × `464249`. Excluded 8 | the same. Excluded 32, 24 cut-off | no option |
| Beef 30 kg | €506.40 = 30 × `466988`, human (P-06). At Wed and Thu 09:00 also €512.70 = 30 × `474242`, valid until Thu 12:00 | €506.40 only. Excluded 5, 2 cut-off | no option |

Side finding for P9a and the substitutes topic: with the four coffee milks dropped from the request, a coffee milk (`464237`) or a coffee drink (`469266`) comes back as a listed substitute.

## 4. Options and recommendation
**DECISION D1 — the instant.**
- (a) **Saturday 14 Nov 2026 02:52:45 +02:00, the recording's `timeNow`. Recommended.** It is what Valio named ("when the data was retrieved"). A judge sees 3 confirmed milks to order by Sunday 17:00 and 17 milks whose Thursday deadline passed. It is our booth question word for word ("order by Thursday, delivery Monday, today is Saturday"). No number, test or document changes. It equals no deadline.
- (b) Friday 13 Nov 09:00: a working hour. The same options and totals (measured). 125 confirmed and 366 passed instead of 123 and 368. Costs: the instant is in 36 test files and about 20 documents (section 7), and the page must explain two instants (recorded Saturday, clock Friday).
- (c) Wednesday or Thursday morning: rejected. No passed deadline on the main request; scenario 3 loses "the agent orders the substitute alone".

**DECISION D2 — the public link.**
- (A) **Deploy in replay with the pinned clock. Recommended as the minimum.** One value (`deploy/modal_app.py:100`). The flow works at any hour and does not depend on the mock. Cost: the link says "replay", not "live". The booth laptop can still show live until Sunday 17:00.
- (B) Live calls judged "as of" the demo clock (work item C5). Keeps "live" on the link and survives Sunday 17:00. 2.5 hours; the page must say that live figures are judged against a chosen instant.
- (C) Leave the real clock and explain. No work. From Sunday 17:00 the flow is dead: live gives no option if the mock stays static (603 cut-off passed); the fall-back gives an offer and then `409 offer-expired` (`orders.py`, emulated: capture answers, clock at Sunday 17:30). At Sunday 12:00 the same emulation orders normally.

**The setting (design, no code).** `TTA_DEMO_CLOCK`: an instant with an offset, or `capture` (the capture's `time_now`). Honoured only when `TTA_ENV` is dev or demo; any other environment refuses to start with it set. Replay: it replaces the pinned instant. Live: a wrapper around the gateway pins `.clock` and rewrites the `time_now` of each availability answer, and keeps the mock's own `timeNow` beside it, so `deps.py:88` and `revalidation.py:45` need no change. It must not be fed to `LiveClock` (12-hour refusal, `clock.py:73`). The same clock goes to the standing-order page (`src/tta/ui/standing_page.py:92-94`, today the machine's time in live mode) and to the examples (`src/tta/api/examples.py:149`).
**Labels.** Banner on every page: "Demo clock: Saturday 14 Nov 2026, 02:52 Helsinki time, the moment Valio's data was recorded. Order deadlines are judged against it. We chose it: Valio Aimo confirmed on 14 Nov that the data is static. The audit trail is stamped with the real time." `/healthz`: `clock: {now, basis}` with basis `recording`, `supplier` or `demo_setting`. Offer and its audit record: the same `basis` beside `time_now`.
**What stays on real time.** Audit event stamps (`UtcClock`), web-evidence retrieval time, logs, the call budget.

## 5. Work items
| id | what | files | hours | who | criterion | depends on |
|---|---|---|---|---|---|---|
| C1 (minimum) | Public link in replay with the pinned clock; redeploy; check `/healthz` | `deploy/modal_app.py:100`, its test | 0.5 | computer science | 30% flow | D2 |
| C2 (minimum) | Banner states the instant and that we chose it | `src/tta/ui/site.py:41`, base template, `tests/ui` | 0.5 | biomedical | 15% assumptions, 20% | D1 |
| C3 (minimum) | Documents: clock row quotes V6 and B3; "Before you start"; one pitch sentence | `docs/ASSUMPTIONS.md:31`, `docs/DEMO.md:18`, `docs/PITCH.md` | 0.5 | biomedical | 15% | D1, D2 |
| C4 | `/healthz`, offer and audit record carry the clock's basis | `src/tta/api/routes.py:364`, `src/tta/contracts/offer.py:196`, `src/tta/offers/builder.py:59`, `src/tta/audit/facts.py:30`, tests | 1.0 | computer science | 20% logged | — |
| C5 (full) | `TTA_DEMO_CLOCK` in live mode ("as of"), one clock for the standing page and the examples, link back to live | `src/tta/config.py`, `src/tta/api/wiring.py:132-144,228`, `src/tta/api/fallback.py:104`, `src/tta/ui/standing_page.py:92`, `src/tta/api/examples.py:149`, `src/tta/ui/examples.py:23`, `deploy/modal_app.py:97`, tests | 2.5 | computer science | 30% | C4 |

Minimum is C1 + C2 + C3 = 1.5 hours. Cut C5 first, then C4.

## 6. What changes in the demo
- With D1 (a): no figure changes. Scenario 1 stays €2,580.64 and €1,010.00 until the "milk" type changes (P9a); then the measured picture is €1,083.39 for 435 L, 43.5% covered, P-01 and P-03.
- Every page names the clock. The sentence for the video: "Valio's test data is frozen at one weekend, so we pin the clock to the moment we recorded it and say so."
- The public link gives the same answers on Sunday evening and next week.

## 7. Risks and what not to do
- **Side effects checked (task 6).** Option validity: `valid_until` is the earliest cut-off or price end (`src/tta/offers/lines.py:84-96`); Sunday 17:00 on every demo option in the recommended window; Thursday 12:00 or 15:00 on options with a `Terminal` line at an earlier clock. Order-time re-check: passes with one clock (Friday 09:00: scenario 2 `ORDERED`, scenario 1 `PENDING_APPROVAL` then `ORDERED`, approval valid until Sunday 17:00; audit stamps were real time, `2026-11-14T12:53Z`); fails with two clocks after Sunday 17:00. Price validity: of 769 prices the latest `validFrom` is 2026-09-01; `validTo` is 9999-12-31 on 719 and 2026-12-31 on 50; no candidate instant is outside. Standing orders: the synthetic history is dated back from the clock (`src/tta/standing/demo.py:53-58`), so it follows. "By Monday": the clock's Helsinki date (`src/tta/agent/parser.py:269`, `src/tta/agent/days.py:140-147`); 16 Nov for any clock date from 9 to 15 Nov; a real clock gives 23 Nov from Monday; the pages hard-code 16 Nov (`src/tta/ui/examples.py:23`).
- **A pinned day never ends.** The day's spend (P-02) then adds up for ever in the shared book of the public link (`docs/ASSUMPTIONS.md:69`); the pages use a private book per visitor. Say it in `docs/DEMO.md`.
- **Pinned instant in files** (`git grep`, tracked files): `02:52` in 37 lines of 20 test files, 39 lines of 15 `AIMO/` files, 9 lines of 4 `docs/` files, 1 in `README.md`; `2026-11-14T02` in 26 lines of 13 test files; `2026, 11, 14` in 26 lines of 20 test files; 36 test files hold at least one of the three. `src/` and `deploy/` hold none. How many tests would fail at another instant was not run.
- Do not choose an instant equal to a deadline. Do not present passed deadlines as a fault. Do not call the mock to test Sunday.
- Replay does not switch the model off: `src/tta/agent/` never reads the mode (0 matches for `tta_mode`), and Gemini is used whenever its key is set (`src/tta/agent/__init__.py:70,84`). Read in the code, not run on Modal: check one pasted request on the link after C1.

## 8. Questions
- **Team:** when is the top-5 pitch, and when do Valio's judges open the link? After Sunday 17:00 option (C) fails.
- **Valio (booth shape).** Context: your mock gives every stock product the deadline Sunday 15 Nov 17:00 and delivery Monday 16 Nov. What we did: compared two recordings 4 hours apart. What we got: 62 shared products, no difference. Example: `469363`, 384 units, order by Sunday 17:00. Ask: after Sunday 17:00, do these deadlines stay, or do they move to the next week? If nobody answers: we pin the clock to Saturday 14 Nov 02:52 and say so on every page.
