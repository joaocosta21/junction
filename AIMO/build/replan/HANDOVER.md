# Hand-over — the build of Sat 14 to Sun 15 Nov

Written Sunday 15 Nov, early morning, by the run that followed `RUNBOOK.md` part 2 and João's changes during the night (`STATUS.md`, "João's changes during the run"). Code state: commit `b567e5f` (the last code change); later commits are documents. Every figure is from the recording of Valio Aimo's test data (1,163 products) unless it says "catalog" (17,546).

## 1. What works, and how to see it

| What | Proof |
|---|---|
| The whole suite | 6,213 passed, 69 skipped (68 need a PostgreSQL), 1 deselected (a timing test), run folder by folder and `tests/ui` file by file by the last lane on `b567e5f`. Before that lane, my own run on a clean copy of `5d58d85`: 5,688 passed without `tests/ui`. One process over the whole suite does not finish on this machine (16 GB): run `for d in tests/*/; do .venv/bin/python -m pytest $d -q -p no:cacheprovider; done`, and `tests/ui` file by file. `ruff check src tests deploy scripts`: clean |
| The public link | `https://joaocostared--trusted-trade-agents.us-east.modal.run/shop`, deployed from `b567e5f`: replay at the demo clock, no model, the audit trail in Aiven for PostgreSQL, one container kept running with 4,096 MiB. `.venv/bin/python deploy/check.py <url> --mode replay`: all 10 checks passed. Two networks read two rate-limit buckets on `/healthz` (João's computer and phone) |
| The brief's sentence, end to end | Hotel, "1,000 litres of lactose-free milk by Monday": three options (section 2), a person confirms, a log of 11 events that verifies, Valio Aimo's own view. Over REST, MCP and `/shop`. Checked against the recording by an independent check (CK2): the arithmetic to the cent, six exclusions by hand |
| The page `/shop` | Walked in Chrome by three independent agents (BW on `016cc08`, FP-UI on `dbb8e13`, DEMO-CHECK on `d617d5c` and again on `b567e5f`): `AIMO/DEMO-CHECK.md` has the verdict and a runbook for the live minute. Local server: `http://127.0.0.1:8011/shop` (the command is in `README.md`) |
| Guardrails | An agent's token cannot approve over REST or MCP (403, logged); limits hold under splits and races; an excluded allergen is never offered, missing data goes to a person; no substitute that is not like for like, or dearer than the buyer's premium, is ordered alone; the dietitian decides allergen doubts and formula differences at the ward and the school; a tampered audit event is named and `/healthz` says degraded (CK4's attacks, then the fixes of `REVIEW.md`) |
| Tech challenges | `AIMO/AWARDS-RUN.md`: a batch of 76 manufacturer-page lookups fanned out over 40 Modal containers in 58 seconds; 92 recorded Context.dev answers (30 kept, 39 dropped with a reason, 23 without a page); on the live Aiven trail the database refuses UPDATE and DELETE and the supplier's role reads only its view; 68 live tests passed |

## 2. The demo set (demo clock Thu 12 Nov 2026 14:15, measured through `/shop/api` by FIX-D on `dbb8e13`; scenario 3 re-measured after the price bound)

| # | Request | Answer | Who confirms |
|---|---|---|---|
| 1 | hotel, 1,000 L lactose-free milk | 435 L (384 × `469363` + 51 × `462775`) €1,083.39, P-01 P-03; 1,000 × `464306` €1,010.00, F-01 P-01; 435 L + 565 × `463380` €2,580.64, F-12 P-01 | Hanna Laine |
| 2 | ward, 200 L milk substitute | 200 × `464013` €402.00, F-10; with ordering alone on, the agent | Jussi Nieminen |
| — | hotel, ordering alone on | 302 L €748.96 by the agent; 303 L €751.44 to a person (P-01) | — / Hanna Laine |
| — | hotel, "200 litres of lactose-free milk by Monday, under €400" | €496.00, "above the €400 you named for this request" (P-01) | Hanna Laine |
| — | ward, 100 L lactose-free milk | nothing offered: 26 checked, 26 declare milk | — |
| 3 | hotel, 100 L of `473609` | 100 × `475224` €174.00, F-12 P-05 ("€37.00 more … 27% more"); `473609` €137.00, F-01; 10 × `471690` €155.50, F-01 F-12 | Hanna Laine |
| 4a | hotel, 100 L of `469512`, no milk | 100 × `473424` €236.00, F-12; `469512` €208.00, P-04, with the manufacturer's page; `473609` €137.00 | Hanna Laine |
| 4b | school, 20 L almond drink | 20 × `465793` €47.60, P-04; 20 × `474864` €28.80, F-01 P-04 | Riikka Mäkelä (dietitian) |
| 5 | hotel, 100 L lactose-free milk | 100 × `469363` €248.00; with the forgotten cooking cream €281.10 | Hanna Laine |
| 5 | bakery, 10 L whipping cream | 10 × `469346` €57.70; Valio Aimo suggests `473278` (€42.00 less on 30 L) | Marko Heikkinen |
| 5 | hotel, standing order renewed at 290 L | 290 × `469363` €719.20, P-08 ("290 L this week against a median of 100 L") | Hanna Laine |
| 6a | bakery, 40 kg of `477055` | 20 × `477055` €214.40, F-01; 27 × `477003` €339.66, F-01 F-11 F-12 P-01 P-05 | Marko Heikkinen |
| 6b | bakery, 100 L whipping cream | 85 L €549.65, P-01 P-03; 58 × `465193` €338.14, F-01 P-01 | Marko Heikkinen |
| 7 | bakery, chocolate cake for 20 | 4 of 7 ingredients €15.19; all 7 €23.44 with unconfirmed quantities | Marko Heikkinen |
| reserve | hotel, 100 L by tomorrow | "delivered Monday 16 Nov, 3 days later than asked", €248.00, F-07 | Hanna Laine |

Back office after the hotel's hero order and the forgotten cream: "2 orders confirmed · €1,364.49", "€33.10 added to baskets", "565 L asked for could not be covered by confirmed stock of the product asked for: about €1,407 at offered prices". The scripts: `AIMO/VIDEO-SHOTLIST.md` (video, 2:00), `AIMO/PITCH-SCRIPT.md` (pitch, 3:00), `docs/DEMO.md` (all scenarios, both clocks).

## 3. Not done, and why

| What | Why | Where it is said |
|---|---|---|
| A demo agent that orders alone over REST or MCP | An identity is bound to one profile, and its approver and customer file to that id; shown on `/shop` instead | `/llms.txt`, README "Next steps" |
| Stored orders tied to their audit events | Needs a field on a hashed model; a database writer can change an order and get a valid proof | README, `docs/ASSUMPTIONS.md` |
| The scheduled witness on Modal, `scripts/aiven_proof.py` | No login for Valio Aimo's reader exists and none was created | `AIMO/AWARDS-RUN.md` has the two commands |
| A model on the public link | João's choice after measuring: the key answers HTTP 429 unpredictably, and a sentence the rules would ask about then comes back as an error | `STATUS.md` |
| A model on a Modal GPU | Needs a payment method; João wants no cost | `docs/AWARDS.md` |
| Valio's view: the count of unconfirmed products at the ward; the total of candidates (a buyer-rule count follows by subtraction); a request short partly for a buyer's rule counted whole in the back office | Each needs a field on the offer or new SQL that cannot be run here | `REVIEW.md` C4-F7, FP-I's entry |
| The switch race in Settings' save and reset | Found by the last lane, outside its items; a switch during a save writes to the other customer's browser copy | `STATUS.md` |
| `required_roles` says "dietitian" where the sentence says "the purchasing manager" at the hotel | One person holds both; the sentence is pinned on purpose | `STATUS.md`, GREEN-3 |
| Recipes around a seasonal ingredient, anything proactive before a request, a mark for new or seasonal products, a nutrition standard, a scheduler for standing orders, Finnish in the fixed rules, an origin filter, a price per unit | Not in the data, or beyond the night | README "Next steps" |
| Pinned dependency versions, a lock file | A new file: João's decision (`.venv/bin/pip freeze --exclude-editable > requirements.lock`) | `AIMO/SOURCE-CODE-REVIEW.md` |

## 4. For João

**The morning, in order** (`AIMO/SUBMISSION.md` section 5 has the same list with the form's fields):
1. `git push` (the session refuses a push; everything is committed on `replan-build`).
2. Source code: the six steps of `AIMO/SOURCE-CODE-REVIEW.md`: ask Valio whether their data may be public; move the other challenges' briefs to `archive/`; `git push origin replan-build:main`; make the repository public; tell the two teammates that their commit e-mail addresses go public.
3. Deck v5: the three rows of `AIMO/PITCH-DECK-REVIEW-V5.md`; the reading table is now 126 sentences, 67 read, 59 asked about, 0 read wrong; pages 12 to 14 from `AIMO/AWARDS-RUN.md` (Context.dev: 30 of 92 kept, 39 rejected, 23 without a page). Export the PDF on the machine the deck was made on.
4. Video from `AIMO/VIDEO-SHOTLIST.md`: hard-reload the page once first.
5. The form: `AIMO/SUBMISSION.md`. Set FINAL early.
6. After the judging: `.venv/bin/modal app stop trusted-trade-agents` (one container is kept running and costs credit).

**Decisions the run took as the owner** are B1 to B70 in `DECISIONS.md`. The ones to know before a judge asks: one person confirms at the hotel and the bakery (B54); the third option with a café milk as a named substitute (B56); a product of another kind by its name is never a substitute, so 275 of 1,163 recorded products now have none (B65, B69); the price bound on a substitute was built, not claimed (B70); the demo page has no login and every claim says "over REST and MCP" (B62).

**What I got wrong during the run**, so that nothing rests on it: a live-mode server started with the team's settings wrote test events into the Aiven trail on Saturday evening (stated in `docs/AIVEN.md`); I said for hours that the Gemini key had no credits without testing it; I quoted clock times about 40 minutes ahead of the clock for part of Sunday morning (the log's own stamps are right); three commits did not hold together when made and were repaired by the next.

**`CLAUDE.md` lines that are now stale** (I did not edit it again): "Stack: … a fixed-rules reader for sentences (a model is optional and off)" is still right; "human confirmation of every order by default" is right; the awards line should add what ran on 15 Nov (`docs/AWARDS.md`).

## 5. Questions

**For Valio Aimo's mentors** (`DECISIONS.md` D1 to D6, in the booth shape):
- May your synthetic product file and the recorded answers stay in a public MIT repository? (New; it decides whether the repository goes public.)
- Product `474864` is named "almond drink" in English and "soijajuoma" / "sojadryck" in Finnish and Swedish, and its description says soya. Which is it? We send it to the dietitian.
- Of your 249 listed substitute pairs, our comparison finds 51 that keep the formula, 145 that differ and 53 that cannot be compared (whole catalog). Is a listed pair meant as like for like?
- Is there a mark for new or seasonal products? We found only `synkkaData.lastUpdated`.
- Your view of the buyer's log shows every rule that fired, with limits and allergens masked. Is that what you meant by a log for both sides?

**For the team** (`DECISIONS.md` C1 to C8): the formula tolerances (six nutrients within 15% or 1 g) and the fat-source word list need a biomedical signature; whether `VEGETARIAN` should stay a claim a substitute must keep; the list of hosts treated as a manufacturer's own page is ours and unverified; and whether a custom kitchen with no dietitian should read "goes to the dietitian" in its authority text.
