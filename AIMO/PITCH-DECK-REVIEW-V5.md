# Pitch deck v5 — review

`AIMO/Trusted_Trade_Agents_Junction_Pitch_v5.pptx` (saved Sun 15 Nov 03:00, 14 pages), against my v4 review with its section 0, and against the working tree at `e6d92b9` (33 uncommitted files while lanes edit `src/tta/agent` and others). **[M]** = measured on my own server from that tree: replay, demo clock, **no model key**, port 8025. Only this file was written.

## 1. Verdict

**Ready to export: no. One line is wrong, one check is open, one decision is open. Each is a minute's work; everything else is right.**

135 statements: **126 correct, 2 wrong, 7 not verified**, none outdated, none that cannot be shown. Every figure on the pages was measured again today and holds: 26 products looked up, 2 left out; 435 L, €1,083.39; €1,010.00; €2,580.64; 11 log entries for buyer and for Valio Aimo; 302 L €748.96 by the agent and 303 L €751.44 to a person; 26 of 26 at the ward; €33.10, €248.00 → €281.10; €1.48 against €2.88, €42.00 less; OpenAPI 3.1 with 27 paths, 13 MCP tools; the agent's token refused with 403 and the attempt in the log.

## 2. Must change

| # | Page | It says (exact) | What is wrong | Replacement |
|---|---|---|---|---|
| 1 | 6, bottom strip (and its notes: "On 109 test sentences: 55 read, 54 asked about, none read wrong.") | "A model reads, the gateway checks the reading against the text, fixed rules decide. 109 test sentences: 55 read, 54 asked about, 0 read wrong." | The 109 sentences were read by the fixed rules with no model called (`docs/READING-TABLE.md`: "No model was called. Every row is the work of the fixed rules"). After "A model reads", the figure reads as the model's score | "A model reads, the gateway checks the reading against the text, fixed rules decide. The fixed rules alone, on 109 test sentences: 55 read, 54 asked about, 0 read wrong." Notes: "The fixed rules alone, on 109 test sentences: …". **If the price-limit lane lands before export,** the table changes: its uncommitted version reads 126 sentences, 67 read, 59 asked about, 0 read wrong; take the three numbers from line 10 of `docs/READING-TABLE.md` at the final commit |
| 2 | 6, rows 2 and 3 | "“Is it 1,000 or 1? Write 1000 for the first, or 1 for the second.”" · "“Is ‘milk chocolate’ the product? The rules would read plain milk.”" | **A check, not yet a change.** Both are word for word what the fixed rules answer [M, no key]. The deck now says a model reads first, and with the Gemini reader those two questions are not asked before the model (`src/tta/agent/__init__.py:129`: the live reader is built without the stricter checks; they are on for the open-model reader only, `:111`). What the gateway answers to these two sentences with the model on, nobody has shown me, and I may not use a key | Type both sentences once on the server that has the key. Both asked about: change nothing. Either one read instead: put "(when the fixed rules read)" after "THE GATEWAY ANSWERS", and do not type that row on stage |
| 3 | 14, bottom strip (and its notes: "Today the model that reads sentences is Gemini over its API") | "Assumption: today Modal hosts the gateway; the model that reads sentences is Gemini, asked over its API. Next step: the reader as an open model on a Modal GPU; its deploy file is written." | **A decision for João.** This is section 0.1's own text, taken exactly. It also names the model, which your brief to me says no slide should, and section 0.1 says not to state that the public demo uses Gemini | If the decision is "no slide names the model": "Assumption: today Modal hosts the gateway; the model that reads sentences is asked over an API. Next step: the reader as an open model on a Modal GPU; its deploy file is written." Notes: "Today the model that reads sentences is asked over an API; next, an open model on a Modal GPU." |

**Price limit read from the sentence** (page 10, last line: "… · a scheduler for standing orders · a price limit read from the sentence"). It is still uncommitted (`src/tta/agent/budget.py` is untracked), so v5 is right as it stands. If it lands before export: delete "· a price limit read from the sentence" from that line, and add to page 6, as a fifth row or in the strip: "A price named in the sentence is applied as a spend limit for that request."

### Taken or not

| From | Status in v5 |
|---|---|
| v4 rows 1 to 11, 13, 14, 15, 16 | **Taken**, each as written (row 1 in section 0.2's "barista milk" wording; row 7 with section 0.3's dearer substitute; row 14 also gives the ward a "W" and the hotel an "H") |
| v4 row 12 (page 14 strip) | Taken in section 0.1's wording; see row 3 above |
| v4 row 17 (notes, page 1: "We're ⟨team name⟩") | **Not taken.** Notes only; it does not reach the PDF. Say the name |
| v4 row 18 (the font) | Cannot be taken in the file: v5 still asks for Inter and does not carry it. Export on the machine it was made on and look at the PDF |
| Section 0.1 (a model and the rules) | **Taken**: pages 3, 5, 6 and 10 and the notes; "no model" appears nowhere; the rate-limit caution is in page 5's notes |
| Section 0.2 ("barista milk") | **Taken** on page 5. Page 6 still quotes the gateway's own "Coffee milk was left out…": section 3 |
| Section 0.3 (two guardrails) | **Taken** on page 7, and both hold [M]: the hotel's substitute `475224` "costs €37.00 more than the product you asked for (27% more): a person decides"; for Oatly Oat Drink Whole `470889` at the bakery, Oatly iKaffe `464320` ranks first, ahead of Oatly No Sugars |
| Section 0.4 (page 10) | **Taken**, with the price limit in the last line, as 0.4 says while it is not built |
| v4 "missing": standards by name; search with price and stock; the 109 figure | **Taken** on pages 8 and 6 (the figure needs row 1) |
| v4 "missing": "565 L, about €1,407" on page 9; the two control lines on page 7 | Not taken. Not needed for export: the figure is said in the live part |

## 3. New in v5: wrong, or reads badly; layout

- **Wrong:** only row 1 above.
- **Reads badly, page 6, row 1:** "And in the offer: “Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk.”" The quote is exact [M], but the page before now calls the same product "barista milk" and offers it as a named substitute, so "left out" one page later looks like a contradiction. Suggested: "“Read as: 1,000 L of milk, claim lactose-free, needed by Monday 16 Nov.” Milk made for coffee is never passed off as milk: it appears only as a named substitute."
- **Reads badly, page 5, box 3:** the two further options are six lines of the smallest type on the deck. Legible in the PDF; on a projector, say them.
- **Layout, as rendered by LibreOffice, all 14 pages looked at:** nothing overflows a card or the slide. Page 10: the last next step's text box ends at 12.85 in, past the 12.58 in the other pages keep, and its text comes close to the right edge. Pages 1 and 11 keep their other fonts (Calibri, Arial), as before.

## 4. The five minutes

- **The notes sum to 300 seconds:** 10 · 20 · 20 · 10 · 10 · live 90 · 20 · 50 · 25 · 15 · 20 · 10. The live steps sum to their 90: 25 · 20 · 20 · 25. Pages 12 to 14 are outside.
- **The three live moments are all there, and all hold [M]:** 1:10 the 1,000 L sentence (435 L, and two more options for a person); 1:55 the back office ("565 L asked for could not be covered by confirmed stock of the product asked for: about €1,407 at offered prices."); 2:15 Ward 4 (26 checked, 26 left out). The back office is before the ward, as it must be.
- **One condition for the live part.** Page 5 says "A model reads it". Started without the key, the page says "Read by fixed rules, not by a model: no Gemini key is set." [M]. So the laptop's server runs with the key, with a few seconds between requests, as the notes say.

## 5. Not verified

- **Anything with the model on.** I measured without a key. That a model reads the brief's sentence, that a wrong reading is refused and that the rules take over is the build's own measurement (`README.md:42`–`44`), not mine; so are row 2 above, and "today through the model reader" for Finnish and Swedish on page 10.
- **The public link:** not called. Whether it answers `/shop` and whether it runs with the model depend on tonight's deploy; the demo address on page 11 and "the demo link" on page 14 are unverified until then.
- **"Any agent"** (page 8's notes: "It works with any agent"): no agent other than ours has been connected.
- **Pages 12 to 14:** what ran on Context.dev, Aiven and Modal is from `docs/`, not re-run.
- **The final commit:** the tree was still moving; `docs/READING-TABLE.md` is one of the files that will change (row 1).
- **PowerPoint or Google Slides:** seen only through LibreOffice, without Inter.

## Pages 12 to 14 (the technology partners): what to change, Sun 15 Nov

From three checks, each by an agent acting as that partner's judge, against the deck v5 saved at 03:00. "Must" is a fact that is wrong or stale today; "better" raises the score. Replacements are about as long as the originals.

### Page 12, Context.dev

| Box | Now | Put instead | |
|---|---|---|---|
| Title | "Context.dev: the maker's page, beside the allergen question" | "Context.dev: the product's web page, beside an allergen doubt" | Must |
| Subtitle | "…the approver sees the manufacturer's own page." | "When Valio Aimo's data does not rule out an excluded allergen, the person who decides sees the product's web page." | Must |
| Figure | "9 of 13" | "30 of 92" | Must |
| Under the figure | "manufacturer pages accepted as evidence; 4 rejected… (13 recorded answers, from 25 requests sent)" | "products asked show a web page as evidence; 39 pages rejected, each with its reason; 23 had no page (92 recorded answers)" | Must |
| 01 | "…finds the manufacturer's page and returns seven fields…" | "One endpoint, Answers (POST /v1/web/answers): one request per product looks for its web page and fills our own schema of seven fields: page found, address, title, product name, contains, may contain, free from" | Must (the phrase) |
| 02 | "We send only the product name (English and Finnish) and the brand: nothing about the customer" | "Called in the approval step of an order, only for a product with an allergen doubt. We send its English and Finnish names and its brand: nothing about the buyer" | Better |
| 05 | "A page can add a doubt, never remove one: no verdict changes, the person decides" | "A page can add a doubt, never remove one: the person decides. Each answer is stored once per product, so no request is paid for twice" | Better |
| Strip | "Real example: … Sample figures, not the whole catalog." | "Example: Alpro's barista almond drink, alpro.com: “contains almond; may contain nuts” (translated). The demo link replays 92 recorded answers: a sample." | Better |

### Page 13, Aiven

| Box | Now | Put instead | |
|---|---|---|---|
| Strip | "Ran on 14 Nov: the public link on Aiven, “connected, no fall-back”. 20 tests pin…" | "On the public link, /healthz names the store and the trail's head. Assumptions: the shop page keeps each browser's orders in memory; the gateway's login owns the audit table. Next step: a gateway login that does not." | Must (the link never says the quoted words) |
| 01 | "Aiven for PostgreSQL refuses to change or delete an audit event: triggers fire for every login, even the gateway's own" | "Triggers in Aiven for PostgreSQL refuse UPDATE and DELETE of an audit event, for the gateway's own login too: tried on the live trail on 15 Nov, refused with our error TA001" | Better |
| 04 | "…run on Aiven on 14 Nov with a test login. Next step: Valio Aimo's own login" | "A role with one grant and no login: on the live trail on 15 Nov it read that view and was refused the audit table, the buyer's view and the orders. Next step: Valio Aimo's own login" | Better |
| Figure and caption | "2 views" · "of one audit log: the buyer's and Valio Aimo's…" | "68 of 68" · "tests passed against the live Aiven service on 15 Nov, each in a schema of its own: the triggers, both views, the role, a whole order flow" | Better |
| The ask | "An Aiven service as a significant part of the project, and showing what it makes possible." | "One Aiven service as a meaningful part of the project, and a demonstration of what it enables." | Better (their words) |

Do not put counts of the live trail on the page ("33 events", "26 of 33"): they change with every check of the link.

### Page 14, Modal

| Box | Now | Put instead | |
|---|---|---|---|
| Strip | "…the model that reads sentences is Gemini, asked over its API. Next step: the reader as an open model on a Modal GPU; its deploy file is written." | "Assumption: today Modal hosts the gateway; on the demo link sentences are read by fixed rules, and the model reader is an option that is off there. Next step: the reader as an open model on a Modal GPU; its deploy file is written." | Must (no text names the model or says one runs on the demo link) |
| 05 | "Built next, not yet run on Modal: reading up to 40 manufacturer pages in parallel, and an hourly witness of the audit log" | "Ran on 15 Nov: one batch fan-out, 76 product-page lookups mapped over up to 40 CPU containers, done in 58 seconds. Built, not yet run on Modal: an hourly witness of the audit log" | Must (it ran) |
| 04 | "…all 7 checks passed on 14 Nov; 10 today" | "…five deploys, all 10 checks passed after the last, on 15 Nov" | Must |
| 03 | "…where a quiet gateway costs almost nothing" | "One container, kept running for the review day (1 core, 4,096 MiB; 553 MiB measured after start); one constant takes it back to scale-to-zero" | Better (the cost was never measured) |
| 01 | "The entire gateway is hosted on Modal: REST, MCP and the pages…" | "The whole gateway is one Modal web endpoint: REST, MCP (13 tools for agents) and the pages, behind one public address, the demo link" | Better |

Order of the five points, better: hosting, the batch that ran, plain Python, the checks, one container. The speaker notes of page 14 name the model too: they matter only if the deck is uploaded as .pptx or exported with notes.

### Other pages

- Page 6: "109 test sentences: 55 read, 54 asked about" is now 126 sentences: 67 read, 59 asked about, 0 read wrong.
- Pages 3, 5, 6 and 10 say a model reads the sentence. That stays (João's decision): it must read as an option, since the demo link and the video run on fixed rules, and no page names the model.
