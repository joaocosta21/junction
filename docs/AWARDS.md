# Tech award write-ups

We enter two tech awards on top of the Valio Aimo challenge: **Google DeepMind — Best Use of Gemini API** and **Best Use of Modal**. The stretch entries for Aiven and Context.dev were not built, so they are not entered.

Everything below is what exists in the repository and passes its tests. Where something is partly done, it says so.

---

## Google DeepMind — Best Use of Gemini API

The brief asks the write-up to explain four things. Each is answered below, in the brief's order.

### 1. What problem we are solving, and why it matters

Food-service buyers will soon send purchasing agents instead of clicking through a webshop. Valio Aimo serves more than 20,000 professional kitchens (challenge brief). Its challenge asks how a wholesaler can let such agents find products, get fixed prices and order, while it stays clear what the agent may decide alone and what a human must sign. In the brief's words, it is about how a wholesaler "can be safely and openly readable by autonomous agents – before that interface gets defined by someone else's platform."

We built that interface: a gateway over Valio Aimo's mock API, with REST and MCP surfaces. Gemini is the buyer's agent that uses it. It reads a buyer's sentence such as "1,000 litres of lactose-free milk by Monday" and then buys through the gateway's own functions. Every offer says, claim by claim, what Valio's data confirms, and every order goes through a policy that decides whether the agent may place it alone.

### 2. How we integrated the Gemini API

- **Model and API.** `gemini-3.6-flash` through the official `google-genai` SDK (3.3.0), calling `generateContent` on the stable API version `v1` (`src/tta/agent/gemini.py`). We moved to `generateContent` on 14 Nov because the Interactions endpoint answered 503 to every request with our key. `gemini-3.8-flash` answered 504 to every request of the live check, so `gemini-3.6-flash` is the default; `TTA_GEMINI_MODEL` overrides it.
- **Reading the request: structured output.** The buyer's text goes to the model with `response_mime_type` `application/json` and a JSON Schema (`response_json_schema`) that mirrors our typed purchase request (`src/tta/agent/schema.py`). Every field is required, and `null` means "the text does not say". The instruction carries a 14-day calendar, the 30 product-type keys of our table, the catalog's 21 claim codes and the GS1 allergen codes (`src/tta/agent/prompts.py`). Our parser then checks the answer again (`src/tta/agent/parser.py`). It refuses a product type outside the table, an unknown claim or allergen code, a product id that is not in the text, and a date before today. When the text gives no quantity, unit or allergen strictness, the answer is `invalid-request` naming the missing field. The model is never asked to guess.
- **The buyer agent: function calling.** Four function declarations: `get_authority`, `create_offer`, `place_order` and `get_order` (`src/tta/agent/tools.py`). `place_order` takes an option id and nothing else. Automatic function calling is off, so every function call is made by our runner, and one request is one model call. The whole history is sent on every turn with the model's own content unchanged, so its thought signatures come back where they were received (`src/tta/agent/contents.py`). Thinking level `low`. A run takes at most 8 steps (`src/tta/agent/runner.py`).
- **Where it shows.** `POST /v1/requests/parse` and `POST /v1/agent/run`, and the request page of the demo, which shows each step the agent took with its arguments and answer.
- **Recorded from the model, 14 Nov 2026** (`fixtures/agent/`): the reading of scenario 1 (product type `milk`, claim `FREE_FROM_LACTOSE`, 1,000 L, needed by 16 Nov 2026); the reading of scenario 2 (`plant_drink`, 200 L, milk `AM` and gluten `AW` excluded, confirmed data only, needed by 16 Nov); the run of scenario 2 (authority → create offer → place order of option 1, after which the gateway ordered 200 × `464013` for €402.00 with no human); and the refusal of "Some milk for Monday", which gives no quantity. The run of scenario 1 is a hand-written recording, by plan.
- **When Gemini is down.** Without a key, or when Gemini cannot be reached, a sentence that has a recording is answered from it, and the report says so in its first sentence (`src/tta/agent/fallback.py`). A sentence with no recording answers `supplier-unavailable`.
- **Tests.** 148 tests in `tests/agent/` run the real SDK over a mock HTTP transport; no test calls Gemini.

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

**Honest notes.** Gemini was slow on 14 Nov: 21.7 s for a one-word answer and 29 s to read scenario 1. With a key set and Gemini timing out, a sentence can wait about 90 s before its recording answers. A whole agent run has no deadline yet, and the model's output length has no cap (`AIMO/build/handback/T10-followup.md`).

---

## Best Use of Modal

<!-- check: every claim in this section depends on deploy/ and docs/DEPLOY.md (T14), which did not exist when this was written; deploy/ was empty. Confirm each line against them, and replace "prepared" with the URL only if AIMO/build/STATUS.md says T14 is done and deployed. -->

**What Modal powers: the public demo of the gateway. The deployment is prepared, not live.** The orchestrator deploys once, after the final review.

What the deployment is set up to do, from the deployment task (`AIMO/build/tasks/T14-deploy.md`):
- `deploy/modal_app.py` builds an image with the package, the product file and the recorded fixtures, and serves the FastAPI app as an ASGI web endpoint with a public URL. <!-- check: deploy/modal_app.py -->
- One container at a time, because the order book and the audit trail are in SQLite; a Modal Volume holds `var/`. <!-- check: deploy/modal_app.py -->
- `TTA_ENV=demo`: only the demo identities are accepted. Live mode, falling back to the recorded capture, labelled, when the mock cannot be reached or the call budget runs low. <!-- check: deploy/modal_app.py -->
- Only the values the app uses reach Modal, as a Modal Secret built from the local environment at deploy time: the Valio API key and base URL, and the Gemini key. Never the whole `.env`. <!-- check: docs/DEPLOY.md -->
- `docs/DEPLOY.md` gives the commands to deploy, check and roll back. <!-- check: docs/DEPLOY.md -->

**What it does not do.** The Modal brief asks for heavy lifting: an open model on a GPU, agent code in Sandboxes, fine-tuning, or a fan-out batch job. We do none of these. Modal hosts the gateway, keeps its secrets and holds its data on a Volume. The model runs on Google's API. By the brief's own bar this is a light use of Modal; we use it because the judges need a link they can open, and it is the step from laptop to a public URL.

**Not yet checked on Modal.** Which client address the app sees behind Modal's proxy. The per-visitor rate limit depends on it (question FIX8-1 in `AIMO/BOOTH-QUESTIONS.md`).
