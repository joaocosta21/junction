# Context.dev in the gateway

Which Context.dev endpoint the gateway uses, why, and where its data shows. This is the note the "Best Use of Context.dev" award asks for. Code: `src/tta/evidence/`. Tests: `tests/evidence/` (241 tests; none calls Context.dev). Recorded answers: `fixtures/evidence/` (13 files).

Checked against the code at commit `c2106fe`, offline; who decides, the rule ids of "The demo moments" and Valio Aimo's view were checked again on Sun 15 Nov 2026 at commit `94b21a5`. Every figure below was produced by running the code over the recorded answers in replay, unless it says "from the log".

## The note, in short

- **Endpoint:** Answers (`POST https://api.context.dev/v1/web/answers`), one request per product.
- **Why:** one call finds the manufacturer's product page and returns our seven fields together with the pages it read.
- **When:** only when Valio Aimo's data does not rule out an allergen the buyer excludes, and a person must therefore decide: the dietitian at the ward and the school, the person who orders at the hotel and the bakery, which have no dietitian.
- **Sent:** the product's English name, its Finnish name and its brand. Nothing about the buyer.
- **Checked:** the page must be shown to be this product, variant and pack included. A failed or partial answer is not evidence.
- **Stored** once per product, because a cached answer costs the same as a fresh one.
- **It never changes a verdict.** A page can add a doubt and never removes one.

## Why it sits in the approval step

In Valio Aimo's catalog, 46.2% of products have no allergen statement at all (30.6% of food products; `AIMO/FINDINGS.md` §3, whole catalog of 17,546 products). The gateway reads "no statement" as unknown, never as safe. When a buyer excludes an allergen, rule P-04 sends a product that does not rule it out to the dietitian (at the hotel and the bakery the person who orders holds that role). Without Context.dev that person has only "Valio Aimo's data states nothing". With it, the approval carries what the manufacturer's page says, with the link, the retrieval time and a hash, under a heading that says it is not Valio Aimo data.

The evidence only informs the person who signs. The allergen claim stays `UNKNOWN`, the order stays with the person, and nothing found on the web can make an order go through.

**Which lines get evidence:** every line that P-04 sent to a person, whatever the doubt: no statement, "undeclared", "may contain", or a declaration its own ingredient list contradicts (`finder.py`, `doubts`). At most 3 products are looked up for one approval; a fourth gets a sentence that says so.

## Endpoint: Answers

- **Mode `ultra`**, which reads pages (100 credits a request by our log). `fast` answers from search snippets and returned another product's page in the first trial (from the log of 14 Nov).
- **Deadline:** `timeoutOpts: {milliseconds: 40000, behavior: "fail"}`. A partial answer is never taken as evidence. The HTTP client waits 50 seconds.
- **What is sent:** the two names and the brand, inside a fixed instruction. No profile, allergen exclusion, quantity, date, price or product id. Quotation marks and control characters are removed, and each name is limited to 120 characters. Every request is stored with its answer (`fixtures/evidence/*.json`, field `request`), so what was sent can be checked.
- **Our shape (`json_format`):** `page_found`, `source_url`, `page_title`, `product_name_on_page`, `contains`, `may_contain`, `free_from`.
- **Key:** read through `tta.config` (`CONTEXT_DEV_API_KEY`), put in the `Authorization` header when a request is sent, written nowhere else. An error names the HTTP status, never the key or the service's own text.

## What the gateway checks before anything is shown

- **The answer.** Status 200; `success: false` is refused; so is `partial: true`.
- **The link.** A plain `http(s)` address with a host, no user name or password, at most 500 characters, and listed in the answer's `sources`.
- **The product** (`src/tta/evidence/matching.py`). A sibling product (another fat level, another variant, another pack) can state other allergens, so a false match is treated as worse than a missing page. A page is kept only when all of these hold, checked in this order:
  1. The brand is in the page's product name, its title or the host name.
  2. What makes a variant is the same on both sides: every percentage ("15%"), the marks lactose-free, low-lactose, fat-free, whole milk, UHT and organic, and the flavour. A lactose mark the page's name leaves out is accepted from the page's own free-from list, and from nowhere else.
  3. A pack size the page names is one the product names ("1 l" and "1000 ml" are the same pack). A page that names no pack is taken as the page of the product in all its packs.
  4. Against the English or the Finnish name, the page adds no word of its own (the brand, pack sizes and "UHT" aside).
  5. It carries at least 60% of that name's words.

  Words are compared as written and are not translated. A dropped page gives the approver one sentence with the reason. The word lists are ours, written from the 13 recorded pages.
- **The text.** Control and format characters are removed. A title or name is cut at 200 characters; a term longer than 80 characters is dropped, not cut; at most 20 terms per list. The text is escaped on the page and is never given to a model.
- **The hash.** SHA-256 over the JSON of the answer's content as received. The audit event carries it.

## What a page can do, and what it cannot

For each allergen the order excludes, the sentence puts Valio Aimo's data beside the page: the page says it contains it, may contain it, is free from it, does not name it, or uses words that could not be matched (`src/tta/evidence/alignment.py`). A word no table reads is never guessed.

- A page that names an excluded allergen **adds a reason** for the person who signs: "The page names tree nuts (AN), which this order excludes: check the product before approving. What a page says can add a doubt and never removes one."
- "Free from" on a page **never makes a product safe**. The status, the finding and the verdict stay as they were.

## Whose page it is

"The manufacturer's page" is said only when the page's host is one we list for the product's brand, or a subdomain of it. **The list is ours and unverified:** no registry was consulted, and the team has not confirmed it (`AIMO/build/replan/DECISIONS.md`, C6).

| Brand word | Hosts taken as the brand owner's |
|---|---|
| elovena | `elovena.fi`, `raisiofoodsolutions.fi` |
| oddlygood | `oddlygood.com` |
| fazer | `fazer.com` |
| valio | `valio.fi`, `valio.com` |
| arla | `arla.fi`, `arla.com`, `arlapro.com` |
| alpro | `alpro.com` |

A page on any other host reads, in the sentence: "A web page whose owner was not checked, “…” on <host> says: …". All 9 kept recordings are on a listed host, so this wording does not appear in replay.

**The headings.** The shop's card is headed "Found on the web, not Valio Aimo data", whoever owns the page; the sentence under it says whose page it is. The older `/approvals` page still prints "Found on the manufacturer's page — not Valio data" for every page: there only the sentence tells the two cases apart.

## Stored once per product

One file per product, `<TTA_DATA_DIR>/evidence/<product id>.json`: what was sent, the full answer, the retrieval time. Every 200 answer is stored, a page that did not match and "no page found" included, because asking again would cost the same. A failure (time-out, refusal, no credits) is not stored, so the next approval for that product tries again.

**Lookup order:** stored answer → recording in `fixtures/evidence/` → Context.dev. Without a key the gateway reads stored and recorded answers only and asks nobody; a product with neither gets "no recorded page of this product is stored and no Context.dev key is set, so nothing was looked up".

**The cap.** One gateway sends at most 40 requests (`DEFAULT_MAX_CALLS`). The count is kept on disk in `<TTA_DATA_DIR>/evidence/request-count.json`, so a restarted container goes on from it. No such file exists in this repository's data folder: the gateway itself has sent no request from this machine since the count was added. The recording script has its own cap per run (`--limit`, default 10).

## Where it shows

| Surface | What appears |
|---|---|
| Approval reasons | After P-04's own sentence: "Web evidence for product 469512 is attached for the dietitian, and it is not Valio Aimo's data: … It changes no verdict: a human decides." |
| The shop page, on the result (`/shop`, `GET /shop/api/evidence`) | Where the person who orders decides the allergen question on the result itself (the hotel, the bakery), the recorded page shows beside the question, before any approval exists. Recordings only: nobody is asked and nothing is stored. |
| The shop's approval card (`/shop`) | Above the reasons, under "Found on the web, not Valio Aimo data": the entries, then "Read from the web through Context.dev. Valio Aimo's data still states nothing about this allergen, so it stays unknown: this changes no status and no decision, and the person approving decides." |
| The older `/approvals` page | First on the card, under "Found on the manufacturer's page — not Valio data". |
| `GET /v1/approvals` | `evidence[]` on each approval (`tta.contracts.order.Evidence`): `product_id`, `found`, `source_url`, `page_title`, `product_name_on_page`, `contains`, `may_contain`, `free_from`, `retrieved_at`, `content_hash`, `sentence`. |
| Audit trail | An `evidence.attached` event, right after the approval is requested. The buyer's view carries the link and the hash. Valio Aimo's view says only that evidence from outside its data was attached to an approval; the product is not named there, because it is the product rule P-04 fired on. |

## The demo moments (replay, recorded answers)

First run at commit `c2106fe` through the REST routes as the hotel's agent, at both clocks. Run again on Sun 15 Nov 2026 at 02:35, at the demo clock (Thu 12 Nov 2026 14:15), as the hotel through the shop's routes; the first options below are from that run. At the hotel the person who orders, Hanna Laine, holds the dietitian's role, so "to the dietitian" means her there. Where a dietitian is a second person, the same card is hers: at Kilo School "20 litres of almond drink by Monday" sends `465793` to Riikka Mäkelä with the alpro.com page of moment 1 (`docs/DEMO.md`, scenario 4b).

**1. A page that adds a doubt.** 10 L of Alpro Barista almond drink (`465793`), tree nuts excluded, strict.
- First option, "Alternative: a substitute a person must judge": a substitute that rules tree nuts out, 10 × `473424`, €23.60. It goes to a person under fixed rule F-12 (a substitute that is not a like-for-like replacement: a rice drink for an almond barista drink).
- Second option, "Alternative: allergen not ruled out": 10 × `465793`, €23.80, to the dietitian's role (P-04).
- Ordering the second option attaches: "The manufacturer's page “Barista Mantelijuoma” on alpro.com says: contains manteli; may contain pähkinöistä (ei maapähkinästä); free from laktoositon, Maidoton, Gluteeniton. Asked about tree nuts (AN): Valio Aimo's data does not rule it out; the page says it contains it, in its words “manteli”. The page names tree nuts (AN), which this order excludes: check the product before approving. What a page says can add a doubt and never removes one."

**2. A page that says free from, and still decides nothing.** 100 L of Elovena barista oat drink (`469512`), milk excluded, strict.
- First option: a substitute that rules milk out, 100 × `473424`, €236.00, to a person under F-12.
- Second option, "Alternative: allergen not ruled out": 100 × `469512`, €208.00, to the dietitian's role (P-04).
- Ordering the second option attaches: "… Asked about milk (AM): Valio Aimo's data states nothing; the page says free from, in its words “Maidoton”." The order still waits for a person.

```sh
curl -s -X POST $BASE/v1/offers -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Content-Type: application/json" \
  -d '{"needed_by":"2026-11-16","lines":[{"text":"10 L of product 465793","product_ids":["465793"],"quantity":10,"unit":"L","exclude_allergens":["AN"],"allergen_strictness":"STRICT"}]}'
curl -s -X POST $BASE/v1/orders -H "Authorization: Bearer demo-agent-hotel-kitchen" -H "Idempotency-Key: evidence-demo-1" \
  -H "Content-Type: application/json" -d '{"offer_id":"<offer_id>","option_id":"opt_2"}'      # → PENDING_APPROVAL, the dietitian's role
curl -s "$BASE/v1/approvals?status=pending" -H "Authorization: Bearer demo-approver-hotel-purchasing"  # → evidence[] (Hanna holds every role at the hotel)
curl -s "$BASE/v1/audit?order_id=<order_id>" -H "Authorization: Bearer demo-agent-hotel-kitchen"      # → evidence.attached
```

## The 13 recorded answers

All recorded on Saturday 14 Nov 2026 in mode `ultra`: five at about 10:06 Helsinki, eight between 19:56 and 19:58. Kept or dropped is what the matcher at commit `c2106fe` decided, run offline over the files: **9 kept, 4 dropped** (not run again on 15 Nov). This is a sample of 13 products, not a catalog figure.

| Product (name in Valio Aimo's file) | Page found | Result | What the approver reads |
|---|---|---|---|
| `463047` Arla whole milk 1 L, low lactose, UHT | arla.fi | kept | contains Maito; free from Vähälaktoosinen |
| `463975` Arla Pro Ruoka 1 L 15% lactose free vegetable mix, UHT | arlapro.com | kept | contains maito; free from laktoositon |
| `464401` Valio Eila skimmed milk drink 1 l, lactose free | valio.fi | kept | free from laktoositon, laktoosittomaan ruokavalioon |
| `465793` Alpro Barista almond drink 1 L | alpro.com | kept | contains manteli; may contain pähkinöistä (ei maapähkinästä); free from laktoositon, Maidoton, Gluteeniton |
| `468465` Oddlygood oat drink 1 l UHT gluten free | oddlygood.com | kept | contains gluteeniton kaura; free from gluteeniton, ei sisällä maitoa |
| `469162` Valio cooking cream alternative 15% 1 l, lactose free | valio.fi | kept | contains maito; free from laktoositon |
| `469512` Elovena 1 l oat drink barista | raisiofoodsolutions.fi | kept | contains KAURA; free from Gluteeniton, Laktoositon, Maidoton, Kananmunaton |
| `473609` Oddlygood Barista oat drink 1 l UHT gluten free | oddlygood.com | kept | contains Gluteeniton kaura; free from Gluteeniton |
| `475224` Fazer Aito Professional Barista oat drink, gluten-free 1 L UHT | fazer.com | kept | the page names no allergen in its text |
| `462775` Arla milk drink 1 L lactose free, fat free, **UHT** | arla.fi, "Arla Maitoa Suomesta Laktoositon rasvaton maitojuoma Suomi 1 l" | **dropped** | "the product asked for is UHT; the page does not say UHT" (it reads as the chilled product) |
| `464517` AIMO natural yogurt 5 kg **2%** lactose free (Valio Aimo's own label) | valioaimo.fi, "Valio A+™ luonnonjogurtti maustamaton laktoositon 5 kg" | **dropped** | "the product asked for is 2%; the page's product name states no percentage" |
| `464608` AIMO Turkish yogurt 5 kg 10% lactose free (Valio Aimo's own label) | saarefood.ee, "Saare Turkish yogurt 10%, lactose-free" | **dropped** | "the page's product name says “Saare”, which the product asked for does not" |
| `474864` Oddlygood "almond drink" 1 l (Finnish name: *soijajuoma*, soya drink) | oddlygood.com, "Oddlygood® mantelijuoma 1 l no sugars UHT" | **dropped** | "the page's product name says “mantelijuoma”, which the product asked for does not" |

Two of the dropped pages may well be the same product (`462775` under its retail name; the two AIMO yoghurts under their maker's brand). Nothing shows that they are, so they are not shown. Who makes the AIMO own-label yoghurts is a question for Valio Aimo.

## Requests spent

From the team's log, not re-read on Context.dev's dashboard: **25 requests in all, of the 60 the team approved.**
- 17 before the evening of 14 Nov: 10 trials by hand, 5 that produced the first recordings, 2 sent by an early test with a fake key and refused with 401 before that test was cut off from the network.
- 8 that evening, sent by the orchestrator with `scripts/record_evidence.py --demo-set`: the demo's products with an allergen doubt and no recorded page. All 8 answered with a page.

No test calls Context.dev: the client tests use `httpx.MockTransport`.

## Still to run

- **The batch on Modal** (`deploy/evidence_batch.py`): the same request for many products at once, at most 40 at a time. Only its offline dry run and its tests with a stand-in sender exist.
- **The public link does not have the 8 recordings of 14 Nov evening or the stricter matcher** until someone redeploys (`docs/DEPLOY.md`, "To run"); at 00:30 on 15 Nov it still ran Saturday morning's code.

## Assumptions and next steps

- **It informs a person; it decides nothing.** That is the design. Whether the award's "core flow" requirement counts it is a question for Context.dev's judge.
- **Waiting time.** A lookup runs when an approval is created. A product that is neither stored nor recorded can hold that order for up to 40 seconds, once, when a key is set. *Next:* attach the evidence after the approval is written, as its own audited event.
- **Language.** Matching is by words, untranslated. Only the variant marks are read in both English and Finnish, and they only ever drop a page. *Next:* a product identifier (GTIN) on the page, which needs no words.
- **Whose page.** The host list is ours and unverified (above). *Next:* the team or the brand owners confirm it; an access policy at Context.dev that lists those domains.
- **Freshness.** An answer is kept until its file is deleted. *Next:* a maximum age.
