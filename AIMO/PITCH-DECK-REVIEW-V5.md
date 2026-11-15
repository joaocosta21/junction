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
