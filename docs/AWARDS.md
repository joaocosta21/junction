# Tech award write-ups

Write-ups for the tech awards next to the Valio Aimo challenge: **Google DeepMind — Best Use of Gemini API**, **Best Use of Modal** and **Context.dev**, and a section on **Aiven for PostgreSQL**, which is being added today. Which awards are entered is the team's decision on the submission form.

Everything below is what exists in the repository and passes its tests. Where something is partly done or still being added, it says so.

---

## Google DeepMind — Best Use of Gemini API

The brief asks the write-up to explain four things. Each is answered below, in the brief's order.

### 1. What problem we are solving, and why it matters

Food-service buyers will soon send purchasing agents instead of clicking through a webshop. Valio Aimo serves more than 20,000 professional kitchens (challenge brief). Its challenge asks how a wholesaler can let such agents find products, get fixed prices and order, while it stays clear what the agent may decide alone and what a human must sign. In the brief's words, it is about how a wholesaler "can be safely and openly readable by autonomous agents – before that interface gets defined by someone else's platform."

We built that interface: a gateway over Valio Aimo's mock API, with REST and MCP surfaces. Gemini is the buyer's agent that uses it. It reads a buyer's sentence such as "1,000 litres of lactose-free milk by Monday" and then buys through the gateway's own functions. Every offer says, claim by claim, what Valio's data confirms, and every order goes through a policy that decides whether the agent may place it alone.

### 2. How we integrated the Gemini API

- **Model and API.** `gemini-3.6-flash` through the official `google-genai` SDK (3.3.0), calling `generateContent` on the stable API version `v1` (`src/tta/agent/gemini.py`). We moved to `generateContent` on 14 Nov because the Interactions endpoint answered 503 to every request with our key. `gemini-3.8-flash` answered 504 to every request of the live check, so `gemini-3.6-flash` is the default; `TTA_GEMINI_MODEL` overrides it.
- **Reading the request: structured output.** The buyer's text goes to the model with `response_mime_type` `application/json` and a JSON Schema (`response_json_schema`) that mirrors our typed purchase request (`src/tta/agent/schema.py`). Every field is required, and `null` means "the text does not say". The instruction carries a 14-day calendar, the 30 product-type keys of our table, the catalog's 21 claim codes and the GS1 allergen codes (`src/tta/agent/prompts.py`). Our parser then checks the answer again (`src/tta/agent/parser.py`). It refuses a product type outside the table, an unknown claim or allergen code, a product id that is not in the text, and a date before today. When the text gives no quantity, unit or allergen strictness, the answer is `invalid-request` naming the missing field. The model is never asked to guess.
- **Every reading checked against the text** (task FIX-9, `src/tta/agent/textcheck.py`). Before the typed request is built, the model's quantity, unit, needed-by date, exclusions, confirmed-only and product ids are compared with what the text says. A disagreement is asked once more, then refused as `invalid-request` naming the field; nothing is corrected silently. Every reading says who read it ("Read by gemini-3.6-flash.", or a recording, or an answer written by hand), on the page and in the headers `TTA-Read-By` and `TTA-Reading-Source`.
- **The buyer agent: function calling.** Four function declarations: `get_authority`, `create_offer`, `place_order` and `get_order` (`src/tta/agent/tools.py`). `place_order` takes an option id and nothing else, and the gateway accepts only the option ranked 1 of the latest offer, with at most two offers per run (FIX-9). Automatic function calling is off, so every function call is made by our runner, and one request is one model call. The whole history is sent on every turn with the model's own content unchanged, so its thought signatures come back where they were received (`src/tta/agent/contents.py`). Thinking level `low`. A run takes at most 8 steps (`src/tta/agent/runner.py`).
- **Where it shows.** `POST /v1/requests/parse` and `POST /v1/agent/run`, and the request page of the demo, which shows each step the agent took with its arguments and answer.
- **Recorded from the model, 14 Nov 2026** (`fixtures/agent/`): the reading of scenario 1 (product type `milk`, claim `FREE_FROM_LACTOSE`, 1,000 L, needed by 16 Nov 2026); the reading of scenario 2 (`plant_drink`, 200 L, milk `AM` and gluten `AW` excluded, confirmed data only, needed by 16 Nov); the run of scenario 2 (authority → create offer → place order of option 1, after which the gateway ordered 200 × `464013` for €402.00 with no human); and the refusal of "Some milk for Monday", which gives no quantity. The run of scenario 1 is a hand-written recording, by plan.
- **When Gemini is down.** Without a key, or when Gemini cannot be reached, a sentence that has a recording is answered from it, and the report says so in its first sentence (`src/tta/agent/fallback.py`). A sentence with no recording answers `supplier-unavailable`. A request is tried at most twice; after that the outage is remembered for 120 s and no request is sent (`src/tta/agent/outage.py`).
- **Being added today (task T18):** a photo of a handwritten order list, read in two visible steps (Gemini transcribes the image into text, shown to the person; then the same parser and text check read that text, `POST /v1/requests/read-image`), and orders in Finnish ("1000 litraa laktoositonta maitoa maanantaiksi") that read to the same typed requests as the English scenarios. <!-- check: T18 -->
- **Tests.** 294 tests in `tests/agent/` after FIX-9 (`AIMO/build/handback/FIX-9.md`) run the real SDK over a mock HTTP transport; no test calls Gemini.

### 3. What makes our use of Gemini innovative or technically impressive

- **The model proposes; the gateway decides.** Gemini reads language and chooses the next call. It never sets a price, a quantity, an allergen status or a verdict: deterministic, tested code does, and the audit trail records which rule applied. That split is what lets a wholesaler trust an agent it did not build.
- **A function surface the model cannot misuse.** The model can name only an option of the offer the gateway built for the request it read. It cannot invent a product, a quantity or a price, and it cannot approve its own order: the approval routes refuse agent tokens. The agent's report is built from the gateway's own sentences; the model's closing words are discarded.
- **Precision by refusal.** The schema makes "the text does not say" an explicit `null`, and the parser turns it into a named missing field. "Some milk for Monday" is refused for its missing quantity rather than filled with a guess. This serves the challenge's 20% criterion: "how precisely the agent matches what the buyer actually asked for".
- **Supplier text stays data.** Product names and other text from the product file or the API reach the model only as function results, and the instruction tells it to read them as data, never as instructions. The pasted request is treated the same way.
- **One agent among many.** Gemini calls the same service functions that REST and MCP expose. The Gemini agent is therefore a working proof that the open interface is enough for an autonomous buyer.

### 4. Why Gemini is an important part of the solution

- It turns a buyer's own words into the typed request the gateway needs: product type, claims, allergen exclusions, quantity, unit and date. Without it, a buyer must fill that request by hand.
- It shows the whole flow the challenge scores at 30%, "a full request → lookup → order/approval flow", driven by an autonomous agent: read the authority, get the offer, order within authority or end in an approval.
- Structured output and function calling are the two Gemini capabilities the design rests on: one fixes the model's output to our contract, the other keeps every action inside the gateway's functions.
- The guardrails do not depend on the model. If Gemini misreads a request, the offer shows how the request was read, and the policy still applies. That is why a model can be given this role at all.

**Honest notes.** Gemini was slow on 14 Nov: 21.7 s for a one-word answer and 29 s to read scenario 1. With a key set and Gemini timing out, the first sentence can wait about 60 s before its recording answers; the next ones answer at once for 120 s (FIX-9). A whole agent run has no deadline yet, and the model's output length has no cap (`AIMO/build/handback/T10-followup.md`).

---

## Best Use of Modal

**What Modal powers: the public demo of the gateway, live at https://joaocostared--trusted-trade-agents.us-east.modal.run.** Deployed on 14 Nov 2026 with `modal deploy deploy/modal_app.py`; the checks of `deploy/check.py` passed right after (health, pages, scenario 2 ordered by the agent on live Valio data, the audit chain, MCP).

What the deployment does (`deploy/modal_app.py`, `docs/DEPLOY.md`):
- One image with the package, the product file, the two CSV files and the recorded fixtures; the FastAPI app served as an ASGI web endpoint with a public URL. No Dockerfile.
- One container at most, scaling to zero after 10 idle minutes. SQLite runs on the container's disk; a copy is saved to a Modal Volume after each change and put back at start, so the order book and the audit trail survive a restart. The Volume also holds the call budget and the recordings of live answers.
- `TTA_ENV=demo` (only the public demo identities) and `TTA_MODE=live`, falling back to the recorded capture, labelled, when the mock cannot be reached or the budget runs low. The deployed app may make at most 120 calls to the Valio mock.
- Only the values the app uses reach Modal, as a Modal Secret built from the local environment at deploy time with `modal.Secret.from_dict`: the Valio API key and base URL, and the Gemini key. Never the whole `.env`. Since `cf6681f` the secret also carries the database URL and the Context.dev key, and the image the evidence recordings; both take effect at the final redeploy. <!-- check: S1 -->
- `docs/DEPLOY.md` gives the commands to deploy, check, redeploy and stop.

**What it does not do.** The Modal brief asks for heavy lifting: an open model on a GPU, agent code in Sandboxes, fine-tuning, or a fan-out batch job. We do none of these. Modal hosts the gateway, keeps its secrets and holds its data on a Volume. The model runs on Google's API. By the brief's own bar this is a light use of Modal; we use it because the judges need a link they can open, and it is the step from laptop to a public URL.

**Not yet checked on Modal.** Which client address the app sees behind Modal's proxy. The per-address limits depend on it (question FIX8-1 in `AIMO/BOOTH-QUESTIONS.md`); the per-browser limits of the pages (FIX-11) do not, and they are not deployed yet.

---

## Context.dev — web evidence where Valio's allergen data says nothing

**Status:** built and committed (task S2, `7abb44e`), wired into the shared order book and every page's own book (`f3286e1`); the key and the recordings are in the deploy (`cf6681f`). It reaches the deployed app at the final redeploy. Details: `docs/CONTEXTDEV.md`.

**The problem it serves.** 46.2% of Valio Aimo's 17,546 products state nothing about allergens (30.6% of food products; whole catalog, `AIMO/FINDINGS.md` §3). The gateway reads "no statement" as unknown, never safe. When a buyer excludes an allergen under the strict rule, rule P-04 sends such a product to the dietitian, who until now saw only "Valio's data says nothing".

**Which endpoint, and why.** Answers, `POST https://api.context.dev/v1/web/answers`, one request per product (`src/tta/evidence/answers.py`).
- One request finds the manufacturer's product page, reads it, and returns `json_content` in our own shape (`page_found`, `source_url`, `page_title`, `product_name_on_page`, `contains`, `may_contain`, `free_from`) together with `sources`, the pages it read. Search plus Scrape was not needed: the source URL is a field of our shape, and the gateway accepts it only if it is also in `sources`.
- Mode `ultra`: on the first product, `fast` returned a different product's page. Deadline 40 s with `behavior: "fail"`, so a partial answer is never taken as evidence.
- Only the product's English name, Finnish name and brand are sent. Nothing about the buyer: no profile, exclusion, quantity, date, price or product id.
- Before anything is shown, the gateway checks the link (plain `http(s)`, listed in `sources`), that the page names this product and its brand, and cleans and bounds the text. It stores a SHA-256 hash of the answer, and one answer per product, so a product is paid for once.

**What it visibly drives: the dietitian's approval card.** First on the card, above "Why a human is needed", under **"Found on the manufacturer's page — not Valio data"**: what the page says the product contains, may contain and is free from, with the link, the page title and the retrieval time. The same evidence is in the approval's reasons, in `GET /v1/approvals` (`evidence[]`), and in the audit trail as one `tta.v1.evidence.attached` event with the URL and the hash (the supplier's view carries only the product id and whether evidence was found).

**The demo moment** (replay, recorded answer). The hotel kitchen asks for 100 L of Elovena barista oat drink `469512` by Monday, without milk: €208.00, within its €750 limit. The product states oats and nothing about milk, so P-04 alone sends it to the dietitian. The card shows Raisio's food-service page for the product, which says *Maidoton* ("milk-free"). On the pages this needs the typed request of `docs/CONTEXTDEV.md`, or the fourth example button being added (task T18). <!-- check: T18 -->

**Honest notes.**
- **It never changes a verdict.** The allergen claim stays `UNKNOWN`, the order stays with the dietitian, and nothing found on the web can make an order go through without that human. Evidence informs the person who signs; it is not Valio's data and is never presented as such.
- It is looked up only when P-04 fired and an excluded allergen is not stated or undeclared; a "may contain" or an oats-for-gluten case gets none.
- The lookup runs when the approval is created, synchronously: a product that is neither stored nor recorded can hold that order book for up to 40 s, once.
- The gateway checks that the brand appears in the page's name, title or host, not who owns the domain.
- Recordings exist for 5 products (`fixtures/evidence/`), so the demo shows the same card without a key. 17 requests were spent building it, of the 60 the team approved (1,315 credits).

---

## Aiven for PostgreSQL — the order book and an audit trail the database itself guards

<!-- check: S1 -->
**Status: being added.** Committed (task S1, `67f3b00`) and green against the real Aiven service; the database URL is in the deploy secret (`cf6681f`), so it reaches the deployed app at the final redeploy. One item is still open: `/healthz` does not yet name the fall-back reason. Details and the SQL for each claim: `docs/AIVEN.md`.

- **What it is.** With `DATABASE_URL` set, the shared order book and the audit trail live in Aiven for PostgreSQL (server 18.7, psycopg 3.3.9), behind the same `Store` port as SQLite (`src/tta/store/postgres.py`). The pages' own books stay in memory.
- **History that survives a redeploy.** An order or an event is in the managed database once its transaction commits; a second gateway on the same database finds the order, the chain intact and the same audit head (`tests/store_pg/test_flow_on_postgres.py`).
- **History the gateway cannot rewrite.** Triggers refuse every `UPDATE`, `DELETE` and `TRUNCATE` of an audit event, and an insert that does not follow the chain's head or repeats an id, for the gateway's own login as for any other (`src/tta/store/sql/002_audit_append_only.sql`).
- **Valio's view in SQL.** A view `audit_supplier` mirrors the supplier's reader view, and a role that can read only that view (`003_reader_views.sql`, `004_supplier_role.sql`).
- **Fall-back.** If the database cannot be reached at start, the gateway starts on SQLite and logs a warning.
- **Tests.** 110 passed and 1 expected failure (the `/healthz` reason) against the real service; without the service the live tests are skipped.
- **Honest notes.** An offer takes 0.65–0.72 s on PostgreSQL against 0.02–0.03 s on SQLite, measured from the development machine. The gateway connects as the service's admin login, which owns the tables and could drop a trigger; a runtime login without that right is the next step. `sslmode=require` encrypts the connection but does not check the server's certificate.

