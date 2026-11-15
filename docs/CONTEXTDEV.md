# Context.dev in the gateway

Which Context.dev endpoint the gateway uses, why, and where its data shows. This is the note the "Best Use of Context.dev" award asks for. Code: `src/tta/evidence/`. Tests: `tests/evidence/` (241 tests; none calls Context.dev). Recorded answers: `fixtures/evidence/` (92 files: 13 of Sat 14 Nov, 79 of Sun 15 Nov).

Checked against the code at commit `c2106fe`, offline; who decides, the rule ids of "The demo moments" and Valio Aimo's view were checked again on Sun 15 Nov 2026 at commit `94b21a5`. The counts of answers shown and rejected are as the matcher reads the 92 files at the final code, commit `b567e5f`. **On Sun 15 Nov 2026, 03:49 to 03:54 Helsinki, 79 more requests were sent to Context.dev** (2 by the recording script, 77 as a fan-out on Modal): see "The 79 answers of 15 Nov". Every figure below was produced by running the code over the recorded answers in replay, unless it says "from the log".

## The note, in short

- **Endpoint:** Answers (`POST https://api.context.dev/v1/web/answers`), one request per product.
- **Why:** one call looks for the product's web page, the manufacturer's own when there is one, and returns our seven fields together with the pages it read. What comes back is called "the manufacturer's page" only on a host we list for the brand; on any other host it is "a web page whose owner was not checked".
- **When:** only when Valio Aimo's data does not rule out an allergen the buyer excludes, and a person must therefore decide: the dietitian at the ward and the school, the person who orders at the hotel and the bakery, which have no dietitian.
- **Sent:** the product's English name, its Finnish name and its brand. Nothing about the buyer.
- **Checked:** the page must be shown to be this product, variant and pack included. A failed or partial answer is not evidence.
- **Stored** once per product, because a cached answer costs the same as a fresh one.
- **Measured (a sample of 92 products, not a catalog figure):** 92 products asked once each; a page came back for 69; 30 are shown as evidence (13 on a host we list as the brand owner's, 17 on a host whose owner was not checked), 39 were rejected with the reason in a sentence, 23 had no page.
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

A page on any other host reads, in the sentence: "A web page whose owner was not checked, “…” on <host> says: …". Of the 30 kept recordings, 13 are on a listed host and 17 are not (wholesalers and importers such as finefoods.fi, hkfoodservice.fi, metrotukku.fi, topfoods.fi), so 17 read with this wording in replay.

**The headings.** The shop's card is headed "Found on the web, not Valio Aimo data", whoever owns the page; the sentence under it says whose page it is. The older `/approvals` page still prints "Found on the manufacturer's page — not Valio data" for every page: there only the sentence tells the two cases apart.

## Stored once per product

One file per product, `<TTA_DATA_DIR>/evidence/<product id>.json`: what was sent, the full answer, the retrieval time. Every 200 answer is stored, a page that did not match and "no page found" included, because asking again would cost the same. A failure (time-out, refusal, no credits) is not stored, so the next approval for that product tries again.

**Lookup order:** stored answer → recording in `fixtures/evidence/` → Context.dev. Without a key the gateway reads stored and recorded answers only and asks nobody; a product with neither gets "no recorded page of this product is stored and no Context.dev key is set, so nothing was looked up".

**The cap.** One gateway sends at most 40 requests (`DEFAULT_MAX_CALLS`). The count is kept on disk in `<TTA_DATA_DIR>/evidence/request-count.json`, so a restarted container goes on from it. The recording script has its own cap per run (`--limit`, default 10). The two recording scripts share a total across runs (`--total-cap`, default 60), counted in `var/evidence/request-count.json` on the machine that runs them. **That file reads 181 on the team's machine and 104 requests were really sent:** a first fan-out of 77 on 15 Nov failed before any request left (see below), and its 77 were counted before sending, as the script is written to do. With 92 recordings the floor of the count is 104, above the default total of 60, so every further run needs `--total-cap` and says "The total is spent" without it, a dry run included.

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

## The 13 recorded answers of 14 Nov

All recorded on Saturday 14 Nov 2026 in mode `ultra`: five at about 10:06 Helsinki, eight between 19:56 and 19:58. Kept or dropped is what the matcher at commit `c2106fe` decided, run offline over the files: **9 kept, 4 dropped** (the same on 15 Nov, read again over the files). This is a sample of 13 products, not a catalog figure.

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

## The 79 answers of 15 Nov

Sent on Sunday 15 Nov 2026 between 03:49 and 03:54 Helsinki, mode `ultra`, 100 credits each by each answer's own `key_metadata` (7,900 credits). The team approved going past the first total of 60 on 14 Nov at 20:51. All figures are of these runs: a sample, not a catalog fact.

**The two demo products that had no page** (`scripts/record_evidence.py --ids 469363 469386 --limit 2`, 17 seconds, one request after the other; the same two the dry run of `--demo-set` lists at the demo clock):

| Product | Page found | Result | What the person reads |
|---|---|---|---|
| `469386` 5 x Arla Lactose- and fatfree milkdrink 1 L Suomi ESL | arla.fi, "Arla Maitoa Suomesta Laktoositon rasvaton maitojuoma Suomi 1 l" | kept | contains Maito; free from Laktoositon. The page does not say "ESL" and the matcher does not ask for it. |
| `469363` Arla Semi skimmed milkdrink 1 L UHT lactose free Suomesta | arla.fi, "Arla Maitoa Suomesta Laktoositon kevytmaitojuoma (UHT) 1 l" | kept (since commit `b567e5f`; rejected before it, see below) | contains Maito; free from laktoositon |

**`469363` was first rejected by a fault of the matcher, corrected in `b567e5f`.** The mark "fat-free" (`src/tta/evidence/matching.py`, `MARKS`) matched the word "skimmed", and so also "Semi skimmed", and the page was rejected with "the product asked for is fat-free; the page does not say fat-free". The page is this product (kevytmaitojuoma is semi-skimmed milk drink; UHT, lactose-free, 1 l, Arla). Since the correction "skimmed" is not read after "semi ", this page is kept, and no other of the 92 recordings reads differently. The fault only rejected a page; it could not show a wrong one. It is why the counts moved from 29 shown and 40 rejected to 30 and 39.

**The fan-out on Modal** (`deploy/evidence_batch.py`): every product of the recording `2026-11-14-demo` whose data holds no allergen statement at all and that had no recorded page: 77 products (79 hold no statement; 2 were recorded on 14 Nov). One call per product, spread over at most 40 containers, each call sending one request.

- A first run of 77 at 03:51 failed in every container before a request left: the batch image lacked PyYAML, which `tta.evidence` imports through `tta.catalog`. 0 answers, 0 credits (the next answer's balance was exactly 100 lower than the one before the run). One line was added to the image's pinned libraries (`pyyaml==6.0.3`, the gateway's own pin).
- Then 1 product (`460394`) to check the corrected image, then the other 76: `.venv/bin/modal run -q deploy/evidence_batch.py --limit 76 --total-cap 181`. **76 answers in 58 seconds from start to exit; 40 containers alive at once, the cap, from second 14 to the end** (counted with `modal container list` about every 2 seconds; 6, 12, 20, 29, then 40). Not measured, an estimate: one after the other, at the 8 to 9 seconds each of the two requests above took, the same 76 take about 11 minutes.

| Of the 77 | Products asked | A page came back | Shown as evidence | Dropped, with the reason | No page |
|---|---|---|---|---|---|
| With a brand in Valio Aimo's data | 36 | 34 | 19 | 15 | 2 |
| Without a brand | 41 | 20 | 0 | 20 | 21 |
| All | 77 | 54 | 19 | 35 | 23 |

- **The 41 products without a brand could not be kept and were asked anyway**, 4,100 credits: the matcher's first check needs a brand, or Valio Aimo's own site for its own label. 23 of them are the "AIMO" own label, for which a page on valioaimo.fi could have counted; one such page came back (`465513`) and was dropped on another check: its name carries the maker's name, Savo-Karjalan Liha Oy, which the product's name does not. They were asked so that the figure covers every product of the capture `2026-11-14-demo` (769 products) with no allergen statement, and so that the fan-out reached its 40 containers. A next run should leave out a product with no brand that is not of the own label.
- Of the 19 kept, 2 are on a host we list as the brand owner's (`463773` on valio.fi, `469288` on oddlygood.com). The other 17 read "A web page whose owner was not checked".
- 2 of the 19 name something under "contains" (`462322`: Kookospähkinä; `469288`: maissia), 5 carry a free-from list (`469288` both), 13 name no allergen in their text. 68 of the 77 products are meat (54, mostly raw beef) or coconut products (14): a page that names no allergen is the expected answer there, and it still leaves Valio Aimo's data silent, so the status stays unknown.
- Several drops of a branded product look like the same product written another way, not another product: "ulkofile" on the page against "ulkofilee" in the catalog (`464814`), "flank steak" against "Flanksteak" (`464115`), "sous vide" added (`466210`), "n." before a weight read as a word (`464370`, `464814`). Words are compared as written, and a false match is treated as worse than a missing page. Nobody checked these pages by hand.

Kept, 19:

| Product (name in Valio Aimo's file) | Page | What the person reads |
|---|---|---|
| `460394` Spice Up! Coconut milk 2900ml | finefoods.fi (owner not checked) | names no allergen in its text |
| `462322` Santa Maria 2900ml Coconut Milk | pauligpro.com (owner not checked) | contains Kookospähkinä |
| `463067` Naturkött 2,8kg Beef Striploin | metrotukku.fi (owner not checked) | names no allergen in its text |
| `463263` Spice Up! Coconut cream 1000ml | finefoods.fi (owner not checked) | names no allergen in its text |
| `463773` Valio clear cake jelly 5 kg | valio.fi (manufacturer's page) | names no allergen in its text |
| `463917` HK Beef Knuckle | hkfoodservice.fi (owner not checked) | free from Gluteeniton, Laktoositon, Maidoton |
| `464217` Spice Up! Coconut cream 165ml | finefoods.fi (owner not checked) | names no allergen in its text |
| `464393` Topfoods beef short loin fresh app. 2kg | topfoods.fi (owner not checked) | names no allergen in its text |
| `464744` Evryday c3kg Beef Chuck roll square cut | pikatukku.valioaimo.fi (owner not checked) | names no allergen in its text |
| `464852` Topfoods beef topside cap off app. 3kg | topfoods.fi (owner not checked) | names no allergen in its text |
| `465421` Familia Beef fillet ~2kg | pnmchipsters.fi (owner not checked) | names no allergen in its text |
| `467009` HK Beef burger minced | hkfoodservice.fi (owner not checked) | free from Gluteeniton, Laktoositon, Maidoton |
| `467039` HK Beef Silverside without membrane | sydanmerkki.fi (owner not checked) | free from Laktoositon, Maidoton, Gluteeniton |
| `467150` Spice Up! Condensed coconut milk 320g | finefoods.fi (owner not checked) | names no allergen in its text |
| `467244` Spice Up! Coconut milk 1000ml | finefoods.fi (owner not checked) | names no allergen in its text |
| `469288` Oddlygood® Easy Whipping 2,5 dl UHT | oddlygood.com (manufacturer's page) | contains maissia; free from gluteeniton, ei sisällä maitoa |
| `469415` Spice Up! Coconut milk 400ml | finefoods.fi (owner not checked) | names no allergen in its text |
| `470057` Tamminen Beef Picanha appr 700 g | hkfoodservice.fi (owner not checked) | free from Gluteeniton, Laktoositon, Maidoton |
| `470182` Familia Grainfed veal topside PAD chilled ~4kg NL | pnmchipsters.fi (owner not checked) | names no allergen in its text |

Dropped though the product has a brand, 15:

| Product | Page found | Dropped because |
|---|---|---|
| `463059` Naturkött Beef Tenderloin ca 1,8kg | norvida.se, "Oxfilé 1,8 kg+, färsk" | the page does not show the brand “Naturkött” |
| `463180` Naturkött Beef Cuberoll ca. 2kg | english.norvida.se, "Entrecôte" | the page does not show the brand “Naturkött” |
| `463746` Peter´s Farm beef short loin fresh app. 2,4kg | topfoods.fi, "PETER’S FARM MAITOVASIKAN ULKOFILEE SISÄLTÄÄ RASVAN JA KALVON N. 2,4 KG" | the page's product name says “MAITOVASIKAN”, which the product asked for does not |
| `464115` Tamminen Rotukarja Beef Flanksteak appr 700 g | tamminen.fi, "Rotukarja naudan flank steak" | the page's product name says “flank”, “steak”, which the product asked for does not |
| `464370` Topfoods rumb heart pad 2kg+ | topfoods.fi, "NAUDAN PAAHTOPAISTI, KALVOTON N. +2 KG" | the page's product name says “N”, which the product asked for does not |
| `464689` Evryday Beef Cube Roll ca. 1,6kg | kespro.com, "Evryday naudan entrecote n. 1,6kg" | the page's product name says “naudan”, “entrecote”, which the product asked for does not |
| `464814` Evryday Beef Striploin c3,5kg | kespro.com, "Evryday Naudan ulkofile n.3,5kg tuore" | the page's product name says “ulkofile”, “n”, “tuore”, which the product asked for does not |
| `465089` Hutten Beef Beef topside PAD chilled ~2kg | huttenbeef.com, "Topside pad" | the page does not show the brand “Hutten Beef” |
| `466210` HK Beef mince browned 3 kg | hkfoodservice.fi, "HK Ruskistettu naudan jauheliha, sous vide (7663)" | the page's product name says “sous”, “vide”, which the product asked for does not |
| `469316` Urtekram Organic Coconut milk Fairtrade BIB 3l | urtekram.fi, "Kookosmaito" | the product asked for is organic; the page does not say organic |
| `469345` Kung Markatta coconutmilk organic 3l | midsonafoodservice.fi, "Kung Markatta Kooksmaito 3l" | the product asked for is organic; the page does not say organic |
| `469380` Urtekram Organic Creamy Coconut milk Fairtrade BIB 3l | urtekram.fi, "Kookosmaito" | the product asked for is organic; the page does not say organic |
| `469426` Well Beef Beef Entrecote n 2 kg | kaivonliha.fi, "Well Beef naudan entrecôte n. 2,5kg" | the page is for the 2.5 kg pack; the product asked for is 2 kg |
| `472243` Oddlygood® Easy Whipping 1 L UHT | valio.fi, "Oddlygood® Easy Whipping" | the product asked for is UHT; the page does not say UHT |
| `473941` Fazer Aito Plant-based Whipping, gluten-free whippable vegetable fat product 1L | fazer.com, "Fazer Aito Kasvipohjainen Vispi 1 L" | the page's product name carries too little of the name of the product asked for |

Dropped because the product has no brand in Valio Aimo's data, 20 (one of them because the answer named no page it read, one on a page name with other words): `462199`, `462314`, `462870`, `462880`, `462892`, `463125`, `463135`, `463147`, `463778`, `465122`, `465331`, `465476`, `465513`, `465538`, `466510`, `467983`, `468359`, `468417`, `468810`, `469118`. No page found, 23: `462416` and `467496` (with a brand), and `462286`, `462309`, `462323`, `463020`, `463071`, `463076`, `463098`, `463105`, `463116`, `463121`, `463771`, `464023`, `464025`, `464037`, `464753`, `464759`, `464788`, `467245`, `468887`, `469867`, `475044`.

**On the public link.** The link was deployed again on 15 Nov from the final code `b567e5f` and carries the 92 recorded answers. The four tests of `tests/evidence` that pinned the 13 files of 14 Nov follow the 92 files since that commit.

## Requests spent

**104 requests in all, 10,400 credits by our count** (25 through 14 Nov, 79 on 15 Nov). The balance was not read on Context.dev's dashboard. Each answer reports a balance; read at the same moment by 40 containers they disagree, and the lowest reported is 45,185, where 48,885 − 7,900 gives 40,985.
- 17 before the evening of 14 Nov: 10 trials by hand, 5 that produced the first recordings, 2 sent by an early test with a fake key and refused with 401 before that test was cut off from the network.
- 8 that evening, sent by the orchestrator with `scripts/record_evidence.py --demo-set`: the demo's products with an allergen doubt and no recorded page. All 8 answered with a page.
- 79 on 15 Nov: above.

No test calls Context.dev: the client tests use `httpx.MockTransport`.

## Assumptions and next steps

- **No lookup is made from the public link itself.** The link carries no Context.dev key by choice (`TTA_DEPLOY_WITH_EVIDENCE_LOOKUPS` is not set: any visitor could then spend credits), so it shows recorded pages only and looks nothing up.
- **It informs a person; it decides nothing.** That is the design. Whether the award's "core flow" requirement counts it is a question for Context.dev's judge.
- **Waiting time.** A lookup runs when an approval is created. A product that is neither stored nor recorded can hold that order for up to 40 seconds, once, when a key is set. *Next:* attach the evidence after the approval is written, as its own audited event.
- **Language.** Matching is by words, untranslated. Only the variant marks are read in both English and Finnish, and they only ever drop a page. In the fan-out of 15 Nov, spellings that differ by a letter or a space dropped several branded meat products (above). *Next:* a product identifier (GTIN) on the page, which needs no words.
- **Whose page.** The host list is ours and unverified (above). *Next:* the team or the brand owners confirm it; an access policy at Context.dev that lists those domains.
- **Freshness.** An answer is kept until its file is deleted. *Next:* a maximum age.
