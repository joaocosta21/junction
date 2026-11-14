# P13 — The four tech awards next to the main challenge

Written Saturday 14 Nov, 15:10. Code read at `7f09ce7`; the deployed app is `8163d5d`, and `git diff --stat 8163d5d HEAD -- src deploy fixtures` is empty, so the deployed code is today's code. Measurements were made in replay with no key, each in a fresh data folder (scripts in the scratch folder `replan/P13/`). I called no service and did not touch the deployed app: every statement about it is quoted from a named file. Sponsor pages were read on 14 Nov 2026; every URL is under "Sources".

## 1. In five lines
1. **Scores today, each against its own brief:** Gemini 5/10, Modal 3/10, Context.dev 6/10, Aiven 5/10. All four are real code with tests. None needs to be withdrawn; some claims need to be dropped or reworded.
2. **Gemini's problem is not code.** The key has no credits, so the deployed app never calls the model: every reading there is a recording or the fixed rules. Only 4 of the 11 recordings came from the model; the photo and Finnish were never read live. Google's billing page explains the refusal and names two ways out (§4, DECISION 2).
3. **Aiven is built, tested and, by `AIMO/build/STATUS.md:110`, in use on the deployed app,** although `CLAUDE.md` and `AIMO/PLAN.md:173` say it was dropped. But no page reads it: the pages use an in-memory book per browser, so a judge on the demo link sees nothing of Aiven.
4. **Best gain per hour:** restore live Gemini and re-record (0.75 h, needs credits), correct `docs/AWARDS.md` (0.75 h), prove Aiven on the deployed app with the supplier's own login (0.5 h). That is the minimum, 2.0 h, no new code. Then: web evidence on every dietitian card, not only on silence (1.5 h), and a measured reading table (2 h).
5. **Modal stays hosting-only.** Its brief asks for a GPU model, Sandboxes, fine-tuning or a batch fan-out; none serves a Valio criterion at a fair price. One exception: if Gemini cannot be restored, an open model on a Modal GPU becomes a main-challenge decision (6 h, DECISION 4).

## 2. What exists today

### 2.1 The bar of each award, in its brief's words

| Award | Judging bar (verbatim) | Must be submitted | Where |
|---|---|---|---|
| **Google DeepMind — Best Use of Gemini API** | "a meaningful, innovative, and technically impressive use of Gemini"; "Projects that go beyond simply adding an LLM to an application." (`GOOGLE-CHALLENGE.md:8,11`) | "The submission should clearly explain: What problem you're solving and why it matters · How you've integrated the Gemini API · What makes your use of Gemini innovative or technically impressive · Why Gemini is an important part of your solution" (`:13-17`) | The brief names no form. Participants must be 18 or older (`:29`). |
| **Best Use of Modal** | "the most ambitious working AI system built on Modal, where Modal does the heavy lifting and the team spends its 48 hours on the problem." Asks: "Serve an open model on a GPU · Run your agent's code in secure Sandboxes · Fine-tune a model on your own data · Fan out a big batch job" (`MODAL-CHALLENGE.md:11-19`) | Nothing listed. "you compete in it on top of your main challenge" (`:5`) | The brief names no form. |
| **Context.dev — Best Use, "Fully Structured Web"** (tech track; the stackable one) | "extract exactly what you need from the web and nothing more"; "To count, the project must call at least one Context.dev endpoint in its core flow, not just as a side feature."; "The data from Context.dev must visibly drive something in the demo." (`CONTEXTDEV-TECH-CHALLENGE.md:6,10,14`) | "A GitHub repository and a demo, plus a short note on which endpoints were used and why." (`:17`) | The brief names no form. No rubric is published (`CONTEXTDEV-CHALLENGE.md:47`). The CTO is "challenge lead and lead judge" (`CONTEXTDEV-TECH-CHALLENGE.md:61`). |
| **Best Use of Aiven** | "the most impressive use of Aiven technology: a thoughtful implementation that makes a meaningful difference to the working solution."; "Use at least one Aiven service as a meaningful part of the project, and demonstrate what it enables."; "A well-executed use of one service can be just as impressive as a solution combining several." (`AIVEN-CHALLENGE.md:6-10`) | Nothing listed. | The brief names no form. |

`CONTEXTDEV-CHALLENGE.md` is Context.dev's own main challenge ("turns live web data into decisions, actions or experiences that weren't possible before", `:11`). We are in Valio Aimo's challenge, so only the tech track applies. Where the write-ups go is not in any of the five briefs: question 8.3.

### 2.2 Gemini — 5/10
**What the code does (verified).**
- Model `gemini-3.6-flash`, `generateContent`, API `v1`, thinking `low`, 30 s time-out, one retry (`src/tta/agent/gemini.py:58-65`). `google-genai` 3.3.0 is installed.
- **Structured output.** A JSON Schema where every field is required and `null` means "the text does not say" (`src/tta/agent/schema.py:82-117`). 31 product-type keys, 21 claim codes, 16 label codes, 44 allergen codes (counted from the loaded tables). The instruction is `src/tta/agent/prompts.py:20-66`.
- **Checked against the text without a model** (`src/tta/agent/textcheck.py`), then refused by field name, never corrected (`src/tta/agent/parser.py:1-18`).
- **Function calling.** Four declarations (`src/tta/agent/tools.py:46-74`). The agent's function layer accepts only the option ranked 1 (`tools.py:213-215`) and at most two offers a run (`:76`). The report is built from the gateway's sentences (`src/tta/agent/runner.py:97-108`).
- **Photo.** Two steps: transcribe to lines under a schema, then the same parser (`src/tta/agent/photo.py:99-116`, `gemini.py:247-254`). Finnish and Swedish by prompt rule 14 (`prompts.py:54-58`).
- **When the model does not answer:** recording, then fixed rules, then a refusal that names what was missing (`src/tta/agent/fallback.py:116-145`). A 401, 402 or 403 counts as out of reach (`gemini.py:74,280-283`).
- 505 tests in `tests/agent/` (collected at `7f09ce7`). None calls Gemini.

**What is weaker than the write-up reads.**
- **The deployed app cannot call Gemini.** "the deployed key ran on a zero balance on 14 Nov" (`docs/AWARDS.md:28`). Google's billing page: on a prepay plan "Requests then fail with an HTTP 402 Payment Required error until you add credits", and "Your projects aren't automatically downgraded to the Free Tier."
- **Live evidence is thin.** `fixtures/agent/` holds 11 recordings: 4 from the model (`parse-scenario-1`, `parse-scenario-2`, `run-scenario-2`, `parse-no-quantity`) and 7 written by hand (the brief's sentence ×2, Finnish ×2, the photo ×2, the run of scenario 1). I read the `source` field of each file. About 25 requests were sent in all (`AIMO/build/STATUS.md:100` counts 24; `AIMO/build/handback/FALLBACK-1.md:25` adds one).
- **"Why Gemini matters" is not measured.** The fixed rules read the common sentences without it. Measured: of 16 buyer sentences I wrote (English, Finnish, Swedish; my own set, not a catalog figure), the app with no model read 6 (1 live recording, 1 hand-built recording, 4 fixed rules), refused 10 with the reason, and misread 0. Among the refused: "200 litres of a milk substitute…", "two hundred litres…", "We are out of cream, send 40 l for tomorrow", "300 litraa kaurajuomaa maanantaiksi", "500 liter laktosfri mjölk till måndag", "100 x 1 l organic oat drink…". Nobody has measured what Gemini reads of the same set.
- **Slow.** "21.7 s for a one-word answer and 29 s to read scenario 1" (`docs/AWARDS.md:48`).
- The docs index now presents the Interactions API first and calls `generateContent` legacy; we use `generateContent` because Interactions answered 503 (`gemini.py:7-11`). Honest, and already written down.

**Score 5/10.** The design is the strong part: the model proposes, tested code decides, and a reading the text does not support is refused. It loses points because a judge who opens the link today sees no Gemini call, the multimodal claim was never run, and the field is the most crowded of the event (`GOOGLE-CHALLENGE.md:33`). With live calls restored and a measured table: 7/10.

### 2.3 Modal — 3/10
- One function, `web`: an ASGI endpoint, one container, 1 core, 1 GiB, no GPU, scale to zero after 10 minutes (`deploy/modal_app.py:64-69,340-352`). A Secret of five named values (`:114-116`), a Volume (`:336`), an image defined in code (`:186-194`). `TTA_MODE=live` with a budget of 120 Valio calls (`:95-110`).
- `grep -c "Cron\|Period\|Sandbox\|\.map(\|spawn\|gpu=" deploy/modal_app.py` gives 0. Modal hosts; it computes nothing of its own.
- 50 tests in `tests/deploy/`. Three deploys on 14 Nov, `deploy/check.py` 7 of 7 after each (`AIMO/build/STATUS.md:23,110,115`).
- **Score 3/10.** It is a clean, honest deployment, and the write-up already says "By the brief's own bar this is a light use of Modal" (`docs/AWARDS.md:63`). The brief's four asks are all absent. It still earns the main challenge its public link (30%).

### 2.4 Context.dev — 6/10
- One endpoint: Answers, mode `ultra`, 40 s deadline with `behavior: "fail"` (`src/tta/evidence/answers.py:27-33,119-129`). Our own shape of seven fields (`:42-50`). Only the product's two names and brand are sent.
- Checks before anything is shown: the link must be in `sources` (`src/tta/evidence/reading.py:53-60`), the page must name this product and brand (`src/tta/evidence/matching.py:41-60`), text is bounded, the answer is hashed (`reading.py:68-70`).
- **Trigger:** only rule P-04 with a finding that is `NOT_STATED` or `UNDECLARED` (`src/tta/evidence/finder.py:35-37,49-65`). Called before the approval is written (`src/tta/orders/service.py:92`). Shown first on the approval card (`src/tta/ui/templates/_evidence.html`).
- Measured in replay: Elovena `469512`, no milk → P-04, **1 evidence entry**, found. Almond drink `465793`, no nuts (declaration says free from, ingredients name almond) → P-04, relation `MAY_CONTAIN`, **0 evidence entries**. A contradiction gets no evidence today.
- 5 recordings in `fixtures/evidence/`, 90 tests. 17 requests used (`docs/CONTEXTDEV.md:69`).
- **The budget of 60 is not enforced on the deployed app.** The key is in the deploy secret (`deploy/modal_app.py:114-116`). The only cap is 40 lookups per process, counted in memory (`answers.py:37,150,173-177`); a container that restarts starts at 0. A visitor who sends a product with no allergen statement to the dietitian triggers a live lookup at 100 credits. Nobody has counted what the deployed app spent since 11:15.
- "Manufacturer's page" is not checked: the gateway checks that the brand appears in the page name, title or host (`matching.py:41-43`). A retailer's page that names the brand would pass under that heading.
- **Score 6/10.** It meets both minimum requirements, the extraction is exact and guarded, and the note exists (`docs/CONTEXTDEV.md`). It loses points because one endpoint feeds one card that one example button reaches, the evidence informs a person and drives no decision of the system, and the video shot list has no shot of it (`docs/PITCH.md:64-72`).

### 2.5 Aiven — 5/10
**The real state.** `CLAUDE.md` (section Status) and `AIMO/PLAN.md:173,279,301` say Aiven was dropped on 14 Nov. That is out of date.
- Built overnight as task S1 (`67f3b00`): `src/tta/store/postgres.py` (380 lines) behind the same `Store` port, five idempotent migrations in `src/tta/store/sql/`.
- **The database guards the trail.** Triggers refuse `UPDATE`, `DELETE` and `TRUNCATE`, and an insert that does not follow the head; both fire always (`002_audit_append_only.sql:17-54`). A supplier view and a role that can read only that view (`003_reader_views.sql:38-65`, `004_supplier_role.sql:7-19`). Standing orders since `fa07e39` (`005_standing_orders.sql`).
- **Wired:** PostgreSQL when `DATABASE_URL` is set, else SQLite; a database that cannot be reached at start leaves the gateway on SQLite with a reason in `/healthz` (`src/tta/api/wiring.py:119-129`).
- **Deployed app:** "mode live, Aiven connected (no fall-back)" at 11:15 (`AIMO/build/STATUS.md:23,110`). The 13:00 line (`:115`) reports 7 of 7 and does not repeat the fall-back check. I did not check it: the round forbids touching the deployed app.
- **Tests:** 119 in `tests/store_pg` and `tests/api/test_store_choice.py`. Run with `DATABASE_URL` empty: 52 passed, 67 skipped. The 67 run only with `-m live` against the real service.

**What is weaker than it reads.**
- **No page uses it.** Every page reads and writes the browser's own book, an in-memory SQLite store (`src/tta/ui/site.py:96-100`, `src/tta/api/wiring.py:193`). Only REST and MCP callers write to Aiven. `grep` finds "Aiven" and "PostgreSQL" in no template.
- **The supplier login does not exist.** The role cannot log in; a login is "created by hand" (`AIMO/build/handback/S1.md:74`). The claim "Valio reads its own view" was shown by a test login, never as Valio.
- **"History that survives a redeploy" was never shown on the deployed app** (`S1.md:97`, "Not done"), although two redeploys have happened since.
- The gateway logs in as the owner of the tables and could drop a trigger (`docs/AIVEN.md:58`).
- An offer takes 0.65–0.72 s against 0.02–0.03 s on SQLite, measured from the laptop (`docs/AIVEN.md:97`); from Modal it was not measured.
- **Score 5/10.** The implementation is thoughtful and beyond a database swap. "Demonstrate what it enables" is the gap: today the proof is a document and skipped tests.

## 3. What Valio's answers change
- **V8 (the user always confirms).** P8 turns ordering alone off through rule P-00. Then `docs/AWARDS.md:27` ("ordered 200 × `464013` for €402.00 with no human") and `:44` ("order within authority") describe a setting that is off by default. The Gemini function surface needs no change: `place_order` already says "The gateway decides whether the order is placed at once or waits for a human" (`src/tta/agent/tools.py:60-61`), and the live recording `run-scenario-2.json` replays the same calls. Any Modal job that renews an order must end as a suggestion that waits for a person.
- **V5 (when unsure, ask).** Web evidence fits as it is: it never changes a verdict and is shown to the person who is asked. The gap is the contradiction case (§2.4): the person is asked, with nothing from the web beside the question. Gemini fits too: a `null` is a named missing field, which is the question to ask.
- **V10 (the formula).** P10 builds the formula measure from Valio's own nutrition and ingredient data. Whole catalog, my count through the gateway's loader: 3,557 of 17,546 products (20.3%) have no ingredient text, and in 49 of 250 listed-substitute pairs one side has none. Those are the cases where the maker's page is the only source. P10 also adds a field to the reader's schema (`keep_formula`); a schema change needs one live Gemini request to prove, as FALLBACK-1 did.
- **B13 ("all the steps and decisions").** The note can be read two ways: Valio's view already shows every step, or Valio wants what we hide. If the supplier's view changes in Python, `003_reader_views.sql` must change with it. The test that compares them is live-only, so a default test run will not notice.
- **V1/V2 (generated customer data, user pattern).** No effect on the awards, except that a standing-order history is the "user pattern" a scheduled job would act on.

## 4. Options and recommendation

### 4.1 Gemini
| # | Improvement | Hours | Main criterion | Needs | Shown as | V5 · V8 · V10 |
|---|---|---|---|---|---|---|
| G1 | **Restore live calls and re-record.** Finnish ×2, the run of scenario 1, the brief's sentence, one sentence for `my-kitchen`. The command exists (`AIMO/build/MORNING.md:42`). The photo is P14's PV-3. | 0.75 | 30% (the link runs a model) · 20% match | Credits or a free-tier key; about 15 requests; an approved redeploy (recordings are in the image, and a new key is read at deploy time) | Write-up: "read live on 14 Nov" replaces "written by hand". Video: the caption "Read by gemini-3.6-flash." on the reading | fits |
| G2 | **A measured reading table.** 40 buyer sentences with the typed request each should give; three columns: Gemini, fixed rules, refused. Counts of exact, refused and wrong. The rules column can be run now. | 2.0 | 20% match ("least manual correction", measured) | Credits for the Gemini column (40–80 requests); none for the rest | Write-up §3 and §4: the numbers. Deck: one table. Not in the video | fits; a refusal is counted as the right outcome when the text is incomplete (V5) |
| G3 | **Gemini reads the kitchen's own recipe** (text, PDF or photo) into the recipe shape, product types held to the 31 keys; the kitchen confirms the reading. PDF goes inline as `application/pdf`. | 4–5 | 20% match · V10 (the buyer's own formula) | Credits; a new route and page | A new example | fits only if the model proposes no alternative ingredient (V10) and the reading is confirmed (V8) |

Tested and rejected:
- **Gemini explains an offer from the gateway's sentences.** The gateway's sentences are already the explanation, and "the model's closing words are discarded" (`docs/AWARDS.md:36`) is a selling point. A rewritten allergen sentence can change its meaning, and a check on numbers would not catch that. It would add a 20–30 s call to every offer. No.
- **Speech.** P14 rejects it; I agree.

**Recommendation:** G1, then G2. G3 only if credits arrive before 18:00 and a person is free; it is the first thing to cut.

**DECISION 2 — how to get a working key.** (a) Ask the Google DeepMind booth for the event credits and add them to the prepay account: the same key works again and only new recordings need a redeploy. (b) Use the Free tier: the pricing page lists `gemini-3.6-flash` as "Free of charge" there, and the billing page says a project is downgraded by disabling billing on it (a new project with no billing account is the other route). Its limits are shown only in AI Studio, and a new key needs a redeploy. (c) Leave it, and drop "photo" and "Finnish" from the award's headline. Recommend (a), then (b) if the booth cannot help. Decide by 18:00.

### 4.2 Modal
| # | Improvement | Hours | Main criterion | Needs | Shown as | V5 · V8 · V10 |
|---|---|---|---|---|---|---|
| M1 | **A scheduled witness of the audit trail.** A `modal.Cron` function reads the head of the trail (count and last hash) from Aiven with the supplier's read-only login, checks that the head it noted last time is still in the chain, and keeps its notes on Modal. `src/tta/audit/chain.py:13-22` says the chain cannot show a cut or a rewrite unless "another party" holds an earlier head, and that nobody does. | 2.0 | 20% (decisions logged and auditable) | Deploy approval; the supplier login (A1); no Valio, Gemini or Context.dev call | Write-up: "Modal runs a job the gateway cannot do for itself." Video: none, or the dashboard's run log for 3 s | fits; it reads and orders nothing |
| M2 | **Fan-out that fills the evidence store.** `.map` over the products most likely to reach the dietitian, so no card waits 40 s. | 2.0 | 30% (no wait) · 20% | Deploy approval; Context.dev requests (43 left of the 60), 100 credits each | Write-up: the batch | fits |
| M3 | **An open model on a Modal GPU as the second reader,** between Gemini and the fixed rules. Modal's vLLM example serves `google/gemma-4-26B-A4B-it` on an H200 behind an OpenAI-style API. | 6+ | 30% and 20% only while Gemini is down | Deploy approval; Modal credits (H200 list price $0.001261 a second); a live check of schema-held output, which the example page does not cover | The link reads free text with a model again | fits; the same parser and text check hold it |

Tested and rejected:
- **A scheduled job that renews standing orders.** It fits V8 as "the agent prepares overnight, a person confirms". But each renewal spends Valio calls from the budget of 120, the pages cannot show its result (they read the browser's own book), and a cron is not on the brief's list. M1 is the cheaper scheduled job.
- **Sandboxes.** Modal describes them as "secure containers for executing untrusted code". Our agent writes no code.
- **A batch job that builds an index of the catalog.** Search by name terms already covers products outside the 31 types; an embedding index adds a model to the request path.

**Recommendation:** leave Modal as it is (0 h) and correct the write-up. M1 only in the full version, and cut it first if P12's signed audit head (W8) is built: the two close the same gap. **DECISION 4:** build M3 only if DECISION 2 fails and the team wants a model behind the public link.

Facts to plan around: a schedule starts only on deploy ("To activate the schedule, deploy your App"); `modal.Period` "resets" on each deploy, `modal.Cron` is "not disturbed by deploys"; "Schedules currently cannot be paused"; the Starter plan allows "5 deployed crons".

### 4.3 Context.dev
| # | Improvement | Hours | Main criterion | Needs | Shown as | V5 · V8 · V10 |
|---|---|---|---|---|---|---|
| C1 | **Evidence on every dietitian card, and an honest heading.** Widen the trigger from "not stated" to every P-04 finding that goes to a human (`finder.py:37,49-55`). A small table of brand-owner domains decides the heading: "the manufacturer's page" only for a listed domain, else "a web page that names this product; its owner was not checked". | 1.5 | 20% (controls) · 15% (noisy data, V5) | 2 requests for 2 new recordings (almond drink `465793` and one more); no deploy needed to test in replay | Write-up: two kinds of doubt, silence and contradiction. Video: the card for 5 s with a caption | V5 fits; never changes a verdict |
| C2 | **Formula evidence.** When P10's measure answers "not known" because Valio has no ingredient text, the card shows the maker's ingredient list for both products, side by side. | 2.0 | 15% (substitutions) · V10 | P10's rule F-10 first; 4–6 requests; one field added to our shape | Write-up: a third kind of doubt | V10 fits; evidence only |
| C3 | **Re-read a known page cheaply.** Scrape with JSON on the stored link costs 5 credits against 100 for Answers; a changed hash marks the evidence stale. | 2.0 | 20% (traceability), weakly | 3–5 requests | Write-up: a second endpoint, with the reason | fits |
| C4 | **A monitor on the maker's page** that flags a standing order when the allergen line changes. Monitors can be polled, need no webhook, and a page monitor costs 1 credit a run with a 10-minute minimum. | 3–4 | 15%, weakly | A page that changes on demand, which a real maker's page will not do | Their most distinctive feature, but a contrived demo | fits |

**Recommendation:** C1. C2 only after P10 lands. C3 and C4: no.

**DECISION 3 — the Context.dev budget on the deployed app.** Today it can exceed the approved 60 (§2.4). (a) Accept, raise the approved figure and read the balance in the dashboard on Sunday morning: 49,685 credits were left after the build (`docs/CONTEXTDEV.md:69`), about 496 lookups. (b) Keep the count on the Volume, as the Valio budget is (0.75 h, one deploy). (c) Deploy without the key: recordings only. Recommend (a).

### 4.4 Aiven
| # | Improvement | Hours | Main criterion | Needs | Shown as | V5 · V8 · V10 |
|---|---|---|---|---|---|---|
| A1 | **Prove it on the deployed app.** A person creates the supplier login (`docs/AIVEN.md:73`), runs the two-reader queries and the three refused statements, and pastes the output into `docs/AIVEN.md`. Note `/healthz` → `audit_head` before and after the next approved redeploy. Add the witness query: the supplier keeps `seq` and `hash` of the last row and later checks that row is unchanged. | 0.5 | 20% (auditable, for buyer and Valio) · 15% (path to production) | A person with the Aiven console; no deploy | Write-up: real output in place of "a test does this". Video: a caption on the audit shot | fits |
| A2 | **Valio's log of the shared book, as a page.** One page lists the shared trail in the supplier's view, with the state of the chain and the words "kept in Aiven for PostgreSQL; the database refuses to change a row". It shows what REST and MCP agents did. | 2.0 | 20% (audit trail readable by Valio) · 30% (an outside agent's order appears) | One deploy | The only place Aiven is visible on the link. Video: 4 s after an MCP order | fits; must follow B13 once João says what was meant |
| A3 | **A gateway login that does not own the tables.** | 1.5–2 | 15% (path to production) | A second URL in the settings; live tests | Write-up: removes the caveat of `docs/AIVEN.md:58` | fits |

Rejected: Valkey for the rate limiter, Kafka for the audit events, ClickHouse for observability. Each is a new service for no criterion this weekend.

**DECISION 1 — is Aiven entered?** The code is deployed and the write-up exists. Recommend: enter it, do A1, and correct `CLAUDE.md` and `AIMO/PLAN.md`. A2 is worth its 2 hours only if the team also wants the MCP moment in the demo.

### 4.5 Push, leave, withdraw
| Award | Verdict | Hours (minimum → recommended → full) |
|---|---|---|
| Gemini | **Push.** | 0.75 → 2.75 (G1, G2) → 7.5 (G3) |
| Context.dev | **Push lightly.** | 0 → 1.5 (C1) → 3.5 (C2) |
| Aiven | **Keep; prove it.** | 0.5 (A1) → 0.5 → 2.5 (A2) |
| Modal | **Leave as it is.** | 0 → 0 → 2.0 (M1) |
| All four write-ups | Correct them. | 0.75 → 0.75 → 0.75 |
| **Total** | Withdraw none. | **2.0 → 5.5 → 16.25** |

Minimum is TA-1 to TA-3 of §5; recommended adds TA-4 and TA-5; full is every item of §5 plus G3. The video captions (TA-9, 0.25 h) belong to the video work and are not counted here.

Cut order, first to go: G3, M1, C2, A2, G2, C1. The minimum is G1, A1 and the corrections.

### 4.6 What is wrong or out of date in `docs/AWARDS.md`
| Line | Says | Corrected sentence |
|---|---|---|
| 25 | "the gateway accepts only the option ranked 1 of the latest offer" | "The agent's function layer (`src/tta/agent/tools.py`) accepts only the option ranked 1 of the latest offer; over REST and MCP a caller may order any option, and the policy decides." |
| 27 | Lists the recordings without the brief's own sentence | Add: "The reading and the run of the brief's own sentence are written by hand (`parse-brief.json`, `run-brief.json`). Of the 11 recordings, 4 are from the model and 7 are written by hand." |
| 27, 44 | "ordered 200 × `464013` for €402.00 with no human"; "order within authority or end in an approval" | True today. Once P8 turns ordering alone off: "…after which the gateway recorded the order as waiting for a person's confirmation." |
| 28 | The zero balance, with no cause | Add: "Google's billing page says a prepay account at zero balance answers HTTP 402 until credits are added. While that lasts, the deployed app calls no model: every reading there is a recording or the fixed rules, and says so." |
| 31 | "294 tests in `tests/agent/` after FIX-9" | "505 tests in `tests/agent/` (collected at `7f09ce7`)." |
| 54 | "Deployed on 14 Nov 2026" | "Deployed three times on 14 Nov 2026 (09:44 `237b37f`, 11:15 `d342dfb`, 13:00 `8163d5d`); `deploy/check.py` passed 7 of 7 after each." |
| 58 | "SQLite runs on the container's disk; a copy is saved to a Modal Volume after each change … so the order book and the audit trail survive a restart." | "The shared order book and the audit trail are in Aiven for PostgreSQL (below). If the database cannot be reached at start, SQLite on the container's disk takes over and a copy is saved to the Volume after each change. The Volume holds the Valio call budget, the recordings of live answers and the stored Context.dev answers." Line 58 contradicts line 96 as written. |
| 65 | "the per-browser limits of the pages (FIX-11) do not, and they are not deployed yet." | "…do not; they are on the deployed app since the redeploy of `d342dfb`." (`289a3c7` is an ancestor of `d342dfb`.) |
| 90 | "17 requests were spent building it, of the 60 the team approved" | Add: "The deployed app holds the key and may send up to 40 lookups per container start; those are not counted here." |
| 98 | "the shared order book and the audit trail" | "the shared order book, the audit trail and the standing orders (migration `005`, since `fa07e39`)". |
| 103 | "At S1's hand-back, 110 passed against the real service" | Add: "At `7f09ce7` there are 119 tests; without the service 52 pass and 67 are skipped." |
| 104 | "measured from the development machine" | Add: "From the Modal container it was not measured." |

Same faults elsewhere: `docs/DEPLOY.md:3` (no 13:00 redeploy; "49 tests", now 50), `:11` (no `fixtures/evidence/`), `:13` ("and nothing else": the secret has five values, `deploy/modal_app.py:114-116`), `:15` (the database is Aiven), `:113-116` (deleting `tta.sqlite3` from the Volume no longer empties the shared book; it is in Aiven and its trail cannot be removed). `CLAUDE.md` (Status) and `AIMO/PLAN.md:173,279,301` say Aiven was dropped.

## 5. Work items
Minimum version first (TA-1 to TA-3, 2.0 h, no new code).

| Id | What | Files it would touch | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| TA-1 | Correct the award write-ups (§4.6) and the lines of `DEPLOY.md`, `CLAUDE.md`, `PLAN.md` | `docs/AWARDS.md`, `docs/DEPLOY.md`, `CLAUDE.md`, `AIMO/PLAN.md` | 0.75 | biomedical member | 15% (assumptions visible) | P8 for the two "alone" sentences |
| TA-2 | G1: working key, then re-record Finnish ×2, scenario 1's run, the brief's sentence, `my-kitchen` | `fixtures/agent/*.json`, `docs/AWARDS.md`, `docs/DEMO.md` | 0.75 | computer-science member | 30% · 20% match | DECISION 2; an approved redeploy |
| TA-3 | A1: supplier login, real SQL output, heads before and after a redeploy, the witness query | `docs/AIVEN.md` | 0.5 | computer-science member | 20% auditable | DECISION 1; a person with the Aiven console |
| TA-4 | C1: evidence on every P-04 card; brand-owner domains decide the heading | `src/tta/evidence/finder.py`, `matching.py`, `wording.py`, `_evidence.html`, `fixtures/evidence/`, `tests/evidence/` | 1.5 | biomedical member (the allergen cases), review by computer science | 20% controls · 15% exceptions | P4 (its card wording); 2 Context.dev requests |
| TA-5 | G2: 40 sentences with expected typed requests; a script that scores the three readers | new `tests/agent/readings/` (data and one test), `docs/AWARDS.md` | 2.0 | biomedical member writes the sentences; computer science the script | 20% match | TA-2 for the Gemini column |
| TA-6 | A2: Valio's log of the shared book as a page | `src/tta/ui/` (one page, one template), `tests/ui/` | 2.0 | computer-science member | 20% · 30% | B13 clarified; a redeploy |
| TA-7 | M1: scheduled witness on Modal | `deploy/modal_app.py`, `tests/deploy/`, `docs/DEPLOY.md` | 2.0 | computer-science member | 20% | TA-3; skip if P12 W8 is built; a redeploy |
| TA-8 | C2: formula evidence | `src/tta/evidence/`, `_evidence.html`, `fixtures/evidence/` | 2.0 | biomedical member | 15% · V10 | P10's F-10; 4–6 requests |
| TA-9 | One caption per award in the video (§6) | `docs/PITCH.md` | 0.25 | whoever cuts the video | all four awards | P11 |

Not in the plan unless a decision asks for it: G3 (4–5 h), M3 (6+ h), A3 (1.5–2 h).

## 6. What changes in the demo
- **The reading line.** Today on the link: "Gemini did not answer; read from a recording of gemini-3.6-flash made on 14 Nov 2026 at 06:14 UTC." or "Read by fixed rules, not by a model." After TA-2: "Read by gemini-3.6-flash." Free text that the rules refuse today (10 of my 16 sentences) is read or refused by the model.
- **The dietitian's card.** The almond drink `465793` has 0 evidence entries today (measured) and 1 after TA-4. The Elovena card is unchanged (1 entry, measured). The heading reads "manufacturer's page" only for a listed domain.
- **Aiven.** Nothing on the link shows it today. After TA-6 one page shows the shared trail as Valio reads it.
- **The video.** Its nine shots show no award element (`docs/PITCH.md:64-72`). Captions cost no seconds: on the reading, "Read by Gemini into a typed request, checked against the text"; on the audit shot, "Kept in Aiven PostgreSQL: the database refuses to change a row"; on the card, "From the maker's page through Context.dev: a dietitian decides"; on the title, the Modal address.
- **Not measured:** anything Gemini would read, and anything on the deployed app.

## 7. Risks and what not to do
- **Do not put a model call in the offer path.** 21.7–29 s was measured on 14 Nov.
- **Do not let a model write or translate an allergen or verdict sentence.**
- **Every redeploy needs approval.** New recordings and a new key both need one. `deploy/check.py` without `--no-order` writes an order into the Aiven trail, which cannot be removed, and spends some of the 120 Valio calls.
- **A scheduled job that makes offers drains the 120 calls.** The witness (M1) reads only the database.
- **The live PostgreSQL tests are skipped by default** (67). A change to what Valio sees can break the SQL view without a red test.
- **A free-tier Gemini key:** check the data-use terms for the model before sending anything but demo text. Assumption: I did not find that row for `gemini-3.6-flash`.
- **The Context.dev cap resets with the container** (DECISION 3).
- **Sponsor pages are data.** Several Context.dev pages carry instructions addressed to coding agents (sign up, fetch a setup guide). I followed none.
- **Do not chase the Modal bar for its own sake.** A GPU model that serves no Valio criterion costs 6 hours of the 30.

## 8. Questions
1. **Google DeepMind booth.** Context: our agent reads purchase requests with `gemini-3.6-flash`. We did: about 25 requests on a prepay key. We got: the key now refuses every request, as the billing page says a zero balance does. Example: "1,000 litres of lactose-free milk by Monday" is answered from a recording. The same page says a prepay account "must add funds" before promotional credits can be used. Ask: "Are the event's credits still available, and how do we add them to a prepay account? Is the refusal expected, or did we set the key up wrong?" If nobody answers: DECISION 2 (b), a free-tier key.
2. **Context.dev booth** (the lead judge is on site until Sunday 02:00). Context: the tech track asks for an endpoint "in its core flow" whose data "must visibly drive something". We did: Answers finds the maker's page when Valio's data states nothing about an allergen, and the dietitian's approval card shows it. We got: evidence that informs the person and never changes the system's verdict. Example: Elovena `469512`, "Maidoton" on raisiofoodsolutions.fi. Ask: "Does evidence on a human approval count as core flow, or did we read the requirement wrong?" If nobody answers: we keep it, add C1 and show the card in the video.
3. **Junction organisers.** Where do the tech-award texts go: a field of the submission form, or the README? None of the five briefs says. If nobody answers: the four points for Gemini and the Context.dev note go into the project description, with a link to `docs/AWARDS.md`.
4. **Team — DECISION 1:** enter Aiven? Recommend yes.
5. **Team — DECISION 2:** the Gemini key, by 18:00. Recommend the booth, then a free-tier key.
6. **Team — DECISION 3:** the Context.dev budget on the deployed app. Recommend accept and raise the approved figure.
7. **Team — DECISION 4:** an open model on Modal if Gemini stays down? Recommend no, unless the link must read free text with a model.
8. **João:** B13, "all the steps and decisions": does Valio's view stay as it is, or does it gain what we hide? A2 and the SQL view follow the answer.

## Sources
- Gemini: https://aistudio.google.com/docs/pricing (free-tier cells) · https://aistudio.google.com/docs/billing (prepay, HTTP 402, no automatic downgrade) · https://aistudio.google.com/docs/rate-limits.md.txt (tiers; limits shown in AI Studio) · https://aistudio.google.com/docs/document-processing.md?generate-content=true (PDF inline) · https://aistudio.google.com/docs/llms.txt (the index; `generateContent` as legacy)
- Modal: https://modal.com/docs/guide/cron (schedules) · https://modal.com/docs/guide/batch-processing.md (`.map`, `.spawn_map`) · https://modal.com/docs/guide/sandbox.md · https://modal.com/docs/guide/dicts.md · https://modal.com/docs/examples/vllm_inference · https://modal.com/pricing (GPU list prices; Starter plan: 5 deployed crons)
- Context.dev: https://docs.context.dev/llms.txt (the index) · https://docs.context.dev/account/credits.md (Answers 10 or 100 credits; Scrape 1, +4 for JSON; monitors 1 to 10 a run) · https://docs.context.dev/answers/overview.md · https://docs.context.dev/monitors/overview.md · https://docs.context.dev/monitors/schedules.md · https://docs.context.dev/monitors/limits-and-errors.md
- Aiven: https://aiven.io/docs/products/postgresql/reference/list-of-extensions. For service users I have only a search result's summary of https://aiven.io/docs/products/postgresql/howto/manage-service-users and https://aiven.io/docs/products/postgresql/concepts/dba-tasks-pg; I did not open those two pages.
