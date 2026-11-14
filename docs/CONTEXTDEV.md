# Context.dev in the gateway

Which Context.dev endpoints the gateway uses, why, and where their data shows up. This is the note the "Best Use of Context.dev" award asks for. Code: `src/tta/evidence/`. Tests: `tests/evidence/`. Recorded answers: `fixtures/evidence/`.

## Why it sits in the approval step

In Valio Aimo's catalog, 46.2% of products have no allergen statement at all (30.6% of food products; `AIMO/FINDINGS.md` §3, whole catalog). The gateway reads "no statement" as unknown, never as safe. When a buyer excludes an allergen under the strict rule, rule P-04 sends such a product to the dietitian. That human sign-off is the core of Valio Aimo's third requirement ("what must go to a human"), and for these products it is the only way an order can go through. Without Context.dev, the dietitian has only "Valio's data says nothing". With it, the approval carries what the manufacturer's own page says, with a link, a retrieval time and a hash, labelled as not Valio data. The evidence is part of the approval record: it appears in the approval's reasons, first on the approval card, in the audit trail, and in `GET /v1/approvals`. It never changes a status or a verdict. The allergen claim stays `UNKNOWN`, the case stays with the human, and nothing found on the web can make an order go through without that human.

## Endpoint: Answers (`POST https://api.context.dev/v1/web/answers`)

- **What it does for us:** it finds the manufacturer's product page, reads it, and returns `json_content` in our own shape together with `sources`, the pages it read. One request does both the search and the extraction.
- **Why Answers, not Search plus Scrape:** the task (`AIMO/build/tasks/S2-contextdev-evidence.md`) says to fall back only if Answers cannot return the source page. It can: the source URL is a field of our shape, and the gateway accepts it only if it also appears in `sources`.
- **Mode `ultra`** (100 credits, up to 50 seconds of research). On our first product, `fast` (10 credits, which answers from search snippets) returned a different Fazer barista drink. `ultra` read the right page.
- **Deadline:** `timeoutOpts: {milliseconds: 40000, behavior: "fail"}`. A partial answer is never taken as evidence, so the gateway asks for a 408 at the deadline rather than `return-partial`. The HTTP client waits 50 seconds.
- **What is sent:** the product's English name, its Finnish name and its brand, inside a fixed instruction. Nothing about the buyer is sent: no profile, allergen exclusion, quantity, date, price or product id. Quotation marks and control characters are removed from the names, and each name is limited to 120 characters. Every request is stored with its answer, so what was sent can be checked (`fixtures/evidence/*.json`, field `request`).
- **Our shape (`json_format`):** `page_found`, `source_url`, `page_title`, `product_name_on_page`, `contains`, `may_contain`, `free_from`.
- **Key:** read through `tta.config` (`CONTEXT_DEV_API_KEY`), placed in the `Authorization` header when a request is sent, and written nowhere else. Errors name the HTTP status, never the key or the service's own message.

## What the gateway checks before anything is shown

- **The output itself.** The status must be 200. `success: false` is refused (Context.dev's brief warns that a 200 can carry a failed output). So is `partial: true`. `json_content` must be an object and `sources` a list.
- **The link.** It must be a plain `http(s)` address with a host and no user name or password, at most 500 characters, and listed in `sources`, which means the research actually read it.
- **The product.** The page's product name must name this product. It may not add a word that neither the English nor the Finnish name carries; pack sizes, the brand and "UHT" are ignored. It must carry at least 60% of the product's own words. The brand must appear in the page's name, its title or the host name. Otherwise the page is dropped and the card says "No evidence was found …: the page found is for another product (…)". Examples: asked for the plain Oddlygood oat drink, Context.dev once returned the Barista drink, which was dropped. The Fazer "(INT)" recipe would also be dropped.
- **The text.** Control and format characters are removed. A title or name is cut at 200 characters. A term longer than 80 characters is dropped rather than cut, and at most 20 terms are kept per list. The text is escaped on the page, never executed, and never given to a model.
- **The hash.** SHA-256 over the canonical JSON of `json_content` exactly as received. The audit event carries it, so a stored answer can be checked against the trail.

## Stored once per product

Context.dev charges the same credits for a cached answer as for a fresh one, so the gateway keeps its own copy: one file per product, `<TTA_DATA_DIR>/evidence/<product id>.json`. It holds what was sent, the full answer and the retrieval time. Every 200 answer is stored, including a page that did not match or "no page found", because asking again would cost the same. A failure (time-out, refusal, no credits) is not stored, so the next approval for that product tries again. Behind the store are the recordings in `fixtures/evidence/`, which are read-only and in the same format, so replay shows the same card on every run. A process sends at most 40 lookups (`DEFAULT_MAX_CALLS`), and one approval looks up at most 3 products.

**Lookup order:** stored answer → recording → Context.dev. Without a key, `build_evidence_finder` returns `None`, the order book attaches nothing, and the gateway works as before.

## Where it shows

| Surface | What appears |
|---|---|
| Approval reasons | After P-04's own sentence: "Web evidence for product 469512 is attached for the dietitian, and it is not Valio Aimo's data: The page "Elovena Kaurajuoma kahviin" on raisiofoodsolutions.fi says: contains KAURA; free from Gluteeniton, Laktoositon, Maidoton, Kananmunaton. It changes no verdict: a human decides." |
| Approval card (`/approvals`) | First on the card, above "Why a human is needed", under the heading **"Found on the manufacturer's page — not Valio data"**: the product name on the page, contains / may contain / free from, and the link, page title and retrieval time. When nothing was found, the card shows one sentence saying why. |
| `GET /v1/approvals` | `evidence[]` on each approval (`tta.contracts.order.Evidence`): `source_url`, `page_title`, `product_name_on_page`, `contains`, `may_contain`, `free_from`, `retrieved_at`, `content_hash`, `sentence`. |
| Audit trail | One `tta.v1.evidence.attached` event per piece of evidence found, right after `approval.requested`, in the same transaction. The buyer's view carries the URL and the hash. The supplier's view carries only the product id and `found`. |

## The demo moment (replay, recorded answer)

The hotel kitchen asks for **100 L of Elovena barista oat drink (`469512`) by Monday, without milk**. Tonight `469512` is confirmed (€2.08, €208.00 for 100 L, within the €750 limit). The product states that it contains oats and states nothing about milk (`AM`). So under the strict rule P-04 sends it to the dietitian, and P-04 is the only rule that fires. Context.dev found Raisio's food-service page for the product, which says *Maidoton* ("milk-free"). The dietitian reads that on the card, next to "Valio's data states nothing", and decides.

```sh
curl -s -X POST $BASE/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" \
  -d '{"needed_by":"2026-11-16","lines":[{"text":"100 litres of Elovena barista oat drink, product 469512, by Monday; no milk","product_ids":["469512"],"quantity":100,"unit":"L","exclude_allergens":["AM"],"allergen_strictness":"STRICT"}]}'
curl -s -X POST $BASE/v1/orders -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Idempotency-Key: s2-demo-1" \
  -H "Content-Type: application/json" -d '{"offer_id":"<offer_id>","option_id":"opt_1"}'      # → PENDING_APPROVAL, dietitian
curl -s "$BASE/v1/approvals?status=pending" -H "Authorization: Bearer demo-approver-hotel-dietitian"   # → evidence[]
curl -s "$BASE/v1/audit?order_id=<order_id>" -H "Authorization: Bearer demo-agent-hotel-kitchen"      # → evidence.attached
```

A second request shows both cases at once: **200 L of Oddlygood oat drink, product `468465`, without milk**. Option 1 is the Elovena drink as a substitute, which goes to the dietitian. Option 2 is `468465` itself, whose quantity is not confirmed, so it needs the purchasing manager and the dietitian. Its recorded page says *ei sisällä maitoa* ("contains no milk").

### Recorded answers (`fixtures/evidence/`, 14 Nov 2026)

| Product | Valio's data | Context.dev found | On the card |
|---|---|---|---|
| `469512` Elovena barista oat drink | oats `GO` contains; nothing on milk | raisiofoodsolutions.fi (Raisio, the brand owner) | contains KAURA; free from Gluteeniton, Laktoositon, Maidoton, Kananmunaton |
| `468465` Oddlygood oat drink 1 l | oats contains; nothing on milk | oddlygood.com/fi | contains gluteeniton kaura; free from gluteeniton, ei sisällä maitoa |
| `473609` Oddlygood Barista oat drink | oats contains; nothing on milk | oddlygood.com/fi | contains Gluteeniton kaura; free from Gluteeniton |
| `475224` Fazer Aito Professional Barista | oats contains, gluten free-from; nothing on milk | fazer.com, the right page | the page names no allergen in its text (Fazer's product details are not in the page text) |
| `474864` Oddlygood "almond drink" | soya `AY` contains; nothing on milk | Oddlygood's almond-drink page ("mantelijuoma") | **dropped**: neither name carries "mantelijuoma". The Finnish name in Valio's file says *soijajuoma* (soya drink) and the product declares soya, so the page is most likely another product |

## Requests spent building this

17 requests in total, out of the 60 the team approved, for 1,315 credits (51,000 → 49,685):

- 10 were trials sent by hand: 9 to Answers (1 `fast`, 8 `ultra`) and 1 Scrape JSON on Fazer's page, which showed that its product details are not in the page text.
- 5 produced the recordings above, sent through the finder itself.
- 2 were sent by an early test with a fake key and refused with 401, before that test was cut off from the network.

No test calls Context.dev now: the client tests use `httpx.MockTransport`, and the factory test refuses any call.

## Limits and next steps

- **Waiting time.** A lookup runs synchronously when an approval is created, inside the order book's in-process lock but outside any database transaction. A product that is neither stored nor recorded can hold that order book for up to 40 seconds, once. *Next:* attach the evidence asynchronously after the approval is written, as its own audited event.
- **Language.** Matching is done by words, and the page's words are not translated. A page in a third language passes only if its words are among the English or Finnish name's words. Pack size is ignored, so the same product in another size matches.
- **Who owns the page.** "Manufacturer's page" is what Context.dev was asked for. The gateway checks that the brand appears in the page's name, title or host, not who owns the domain. *Next:* an access policy (Context.dev `policies`) that lists the brand owners' domains.
- **Freshness.** An answer is kept until its file is deleted. *Next:* a maximum age, with `maxAgeMs` on a re-ask.
