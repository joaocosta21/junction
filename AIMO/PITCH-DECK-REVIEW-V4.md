# Pitch deck v4 — review

`AIMO/Trusted_Trade_Agents_Junction_Pitch_v4.pptx` (saved Sun 15 Nov 02:33): 14 pages. Pages 1 to 11 are the five-minute pitch (footers "01 / 09" to "09 / 09" on pages 2 to 10); pages 12 to 14 are one page per tech challenge. Reviewed against the working tree at commit `ba3f3f6`, which had 43 uncommitted files while three lanes were still editing. Nothing but this file was written.

- **[M]** = measured by me on my own server from that working tree (replay, no key, demo clock Thu 12 Nov 14:15, port 8025), through the `/shop` routes or REST. No outside service and not the public link.
- "Log hh:mm" = an entry of `AIMO/build/replan/STATUS.md`. `file:line` = the working tree.
- João's rule for slides is applied to every replacement: no "limits" or "limitations" for what the demo does not do; the words are **Assumptions** and **Next steps**. The word "limit" stays only where it is a buyer's spend limit (the €750).

## 1. Verdict

1. **Not as it is, but it is close: about twenty minutes of text edits.** v4 took nearly everything of the first review; the pitch pages no longer describe Saturday's product.
2. **130 statements: 109 correct, 5 outdated, 10 wrong, 3 cannot be shown, 3 not verified.** Pitch pages 1 to 11: 89 correct of 100. Tech pages 12 to 14: 20 correct of 30.
3. **What blocks the export:** the 1,000 L answer on page 5 is one option short and one log entry short; two claims say more than we can show ("an agent can never approve" with no qualifier, "no manual check needed"); the demo link opens the old first page, not `/shop`; and the Modal and Aiven pages state three things that are not true of what is deployed.

## 2. Must change before submitting (most important first)

| # | Page | It says (exact) | What is wrong | Replacement, ready to paste |
|---|---|---|---|---|
| 1 | 5, box 3, small text | "565 L missing. Alternative: the full 1,000 L for €1,010.00, quantity not confirmed by Valio Aimo." | Since 02:03 the answer has three options [M]. The third fills the 1,000 L from confirmed stock with a named substitute, and a person confirms it | "Two more options, for a person to choose: the full 1,000 L for €1,010.00, quantity not confirmed; or 1,000 L from confirmed stock for €2,580.64, with 565 L of lactose-free coffee milk named as a substitute." |
| 2 | 5, log strip | "THE LOG  ·  10 events, one sentence each" | [M] 11 events: the rules are now checked for three options | "THE LOG · 11 events, one sentence each" |
| 3 | 7, bottom strip | "An agent can never approve an order: its token is refused and the attempt is logged." | True over REST and MCP [M]. The demo page has no login, and says so; the claim needs the qualifier (decision B62) | "Over REST and MCP an agent's token can never approve an order: it is refused, and the attempt is logged." |
| 4 | 7, bottom strip | "Above the buyer's limit, a person confirms: 302 L (€748.96) the agent orders, 303 L (€751.44) waits for Hanna." | Figures right [M]. The 302 L is ordered by the agent only with ordering alone switched on, which the sentence before says is off | "With ordering alone switched on: 302 L (€748.96) the agent orders, 303 L (€751.44) waits for Hanna, because of her €750 limit." |
| 5 | 8, step 3 | "The agent checks prices and stock itself: every offer is signed, no manual check needed." | The signature is the gateway's, with a demo key: it shows who answered, not that the stock is there. On the same page the quantity is "NOT KNOWN" and a person decides | "Every offer says, statement by statement, what Valio Aimo's data confirms, and is signed by the gateway: the agent checks both by itself." |
| 6 | 11 | "Demo: joaocostared--trusted-trade-agents.us-east.modal.run" | [M] the root address opens the older page ("Ask the wholesaler as a buyer's agent"), not the shop | "Demo: joaocostared--trusted-trade-agents.us-east.modal.run/shop" |
| 7 | 7, row 02, "NEEDS A PERSON" | "A substitute that loses a dietary claim, does not keep the recipe, or is a last resort" | Since 02:13 the rule is wider: every substitute not judged like for like goes to a person (`src/tta/policy/rules.yaml:436`–`447`; [M] the third option of the 1,000 L answer fires it) | "Any substitute that is not a like-for-like replacement; at the ward and the school, the dietitian" |
| 8 | 9, sub-line | "Suggestions for the buyer, and a back office for Valio Aimo, both read from the same log." | Suggestions come from the customer's order history [M: "From a synthetic order history"]; only the back office is counted from the log | "Suggestions for the buyer from its own order history, and a back office for Valio Aimo counted from its view of the log." |
| 9 | 14, item 04 | "A script checks the published link with 9 checks, from service health to an offer and MCP; all passed after the deploys of 14 Nov" | On 14 Nov the script had 7 checks and all 7 passed (`docs/AWARDS.md:47`). Today it has 10 (`deploy/check.py:247`–`273`), not yet run against the link | "A script checks the published link after every deploy, from service health to an offer, an order, the log and MCP: all 7 of its checks passed on 14 Nov; it has 10 today, run again after tonight's deploy" |
| 10 | 14, item 03; 13, item 05 | "The container scales to zero, so a quiet gateway costs almost nothing: a credible path to production" · "The log and the shared order book outlive the container: Modal scales to zero, the data stays in Aiven" | For the review day one container is kept running (`deploy/modal_app.py:81`, log 02:24). And the demo page keeps its order books in memory, not in Aiven (`docs/AWARDS.md:41`) | 14: "One container, kept running for the review day; one setting takes it back to scale-to-zero, where a quiet gateway costs almost nothing" · 13: "The log and the order book of REST and MCP callers outlive the container: the data stays in Aiven" |
| 11 | 13, item 04 and the "2 views" tile | "A read-only role for Valio Aimo, allowed to read that view and nothing else" · "separated by the database, not by the application" | The role exists without a login and was shown with a test login only; the view's current SQL has not been run on PostgreSQL (`docs/AIVEN.md:14`–`16`). Through the gateway, both views come from the application | Item 04: "A read-only database role that can read that view and nothing else: run on Aiven on 14 Nov with a test login. Next step: Valio Aimo's own login" · Tile: "of one audit log: the buyer's and Valio Aimo's, kept apart in the database as well as in the application" |
| 12 | 14, bottom strip | "Honest limit: today Modal hosts the gateway. No model is served on a GPU yet, and no Sandboxes or fine-tuning." | The fact is right. João's rule: no "limit"; an assumption and a next step | "Assumption: today Modal hosts the gateway, and no model runs. Next step: the optional reader as an open model on a Modal GPU; its deploy file is written (`deploy/agent_model.py`)." |
| 13 | 12, item 01 and headline | "returns seven allergen fields" · "Context.dev: the maker's page fills the allergen gap" | Seven fields, three of them allergen lists (contains, may contain, free from; `docs/CONTEXTDEV.md:10`). And the page fills nothing: item 05 of the same page says it changes no verdict | Item 01: "…finds the manufacturer's page and returns seven fields: its name, title and address, and what it says the product contains, may contain and is free from" · Headline: "Context.dev: the maker's page, beside the allergen question" |
| 14 | 4, sub-line and school card | "The live demo uses the hotel." · "A school" | The deck's own live plan (page 5 notes) ends at the ward. The school has a name in the demo: Kilo School (`src/tta/policy/profiles/school-kitchen.yaml:13`) | "The live demo uses the hotel, then the ward." · "Kilo School" |
| 15 | 10, labels | "TODAY, AND SAID ON THE PAGES" · "A CREDIBLE PATH FORWARD" | Correct. Use the criterion's own words, and give each next step its reason | Section 3, page 10: the full wording |
| 16 | 5, notes (live steps) | "1:05–1:30 … 435 confirmed, 565 not" · "the log, 10 events" | The steps start at 1:05 inside a block headed 1:10; three options and 11 events now | Section 4, "The plan" |
| 17 | 1, notes | "We're ⟨team name⟩" | Placeholder | The team's name |
| 18 | all | — | Pages 2 to 10 and 12 to 14 ask for the font Inter, and v4 does not carry it (the first deck did) | Export the PDF on the machine the deck was made on, then look at every page of the PDF |

**From the first review's table 1b, not taken by v4:** only the `/shop` in the demo link (row 6) and the team's name (row 17). Everything else was taken, or its slide was removed.

## 3. Page by page: what is not correct

**Page 1 (title).** All correct. The three sponsor logos match what is entered (`docs/AWARDS.md:3`).

**Page 2 (the problem).** All correct. Valio Aimo's sentence is verbatim (`AIMO/CHALLENGE.md:30`).

**Page 3 (the solution).** All correct, notes included ("over REST and MCP an agent's token can never approve").

**Page 4 (the four customers).**

| Text | Verdict | True now, and where |
|---|---|---|
| "The live demo uses the hotel." | WRONG | Against the deck's own notes: the fourth live step is City Hospital, Ward 4 |

Correct, but reword: "A school" → "Kilo School". The four cards' facts match the profiles (`src/tta/policy/profiles/*.yaml`: €500, €250, €750, 90%).

**Page 5 (the demo, end to end).**

| Text | Verdict | True now, and where |
|---|---|---|
| "565 L missing. Alternative: the full 1,000 L for €1,010.00, quantity not confirmed by Valio Aimo." | OUTDATED (log 02:03) | [M] three options: 435 L confirmed, €1,083.39 (P-01, P-03); 1,000 × `464306`, €1,010.00, quantity not confirmed (F-01, P-01); "Alternative: confirmed stock, completed with a substitute": 384 × `469363` + 51 × `462775` + 565 × `463380` (Arla Cafè milk 1 L UHT lactose free), €2,580.64 (F-12, P-01). All three need the purchasing manager |
| "THE LOG  ·  10 events, one sentence each" | OUTDATED (same change) | [M] 11 events for the buyer and 11 for Valio Aimo; "the chain they belong to verifies" for both |
| Notes: "…435 confirmed, 565 not…" · "the log, 10 events" · stamps "1:10–2:40" against "1:05–1:30" | OUTDATED | As above; section 4 has the steps retimed |

Everything else on the page holds [M]: read by fixed rules; 26 products looked up, 2 left out (a portion pack, one that cannot be delivered); P-01 and P-03; "Ordered for €1,083.39 net with approval by Hanna Laine, Harbourside Hotel".

**Page 6 (precision).** All correct [M, through the page's own read route]: the two questions are word for word; "Arla" and "whipping" are kept as terms the product must carry.

**Page 7 (alone, with approval, or never).**

| Text | Verdict | True now, and where |
|---|---|---|
| "A substitute that loses a dietary claim, does not keep the recipe, or is a last resort" | OUTDATED (log 02:13) | F-12, "A substitute is not a like-for-like replacement", fires on every such substitute (`rules.yaml:436`–`447`); at the ward and the school the dietitian is asked (log 02:13; not measured by me) |
| "An agent can never approve an order: its token is refused and the attempt is logged." | WRONG without its qualifier | [M] over REST: 403 "An agent cannot approve or reject an order (F-06)…", and the log: "The agent tried to decide approval … and was refused". The page itself says "Demo, no login: you are acting as Hanna Laine" (`src/tta/ui/static/shop/js/main.js:204`) |

Correct, but reword: the 302 L / 303 L sentence (row 4 above). [M] today: "The agent placed this order alone for €748.96 net. That was allowed: ordering alone is switched on for Harbourside Hotel; the total of €748.96 is within the €750 limit per order; …" and 303 L, €751.44, waits (P-01). "26 of 26" holds [M, through the page's routes as the ward].

**Page 8 (how any company can connect).**

| Text | Verdict | True now, and where |
|---|---|---|
| "The agent checks prices and stock itself: every offer is signed, no manual check needed." | WRONG | [M] the proof is the gateway's ("demo_key": true); `/healthz` says "offers and orders are signed with a demo key that changes at every start". 22 of the 26 milks looked up have a quantity Valio Aimo does not confirm (the €1,010.00 alternative and 21 in no option), and each needs a person |
| Notes: "every offer is signed, so the agent can check prices and stock without a manual check" | WRONG | The same. Say: "every offer says what is confirmed and what is not, and is signed by the gateway, so the agent can check both by itself" |
| "Any agent works: two open, documented interfaces (REST and MCP), the same for everyone." | NOT VERIFIED | The interfaces are there [M: OpenAPI 3.1.0 with 27 paths, 13 MCP tools]. No agent other than ours has been connected (`docs/STANDARDS.md:104`) |

The five statements of product `464306` are right word for word [M]; "Finland" is the data's "FI".

**Page 9 (value).**

| Text | Verdict | True now, and where |
|---|---|---|
| "…both read from the same log." | WRONG | Row 8 above |

The three quoted suggestions hold [M]: the forgotten item (€33.10; €248.00 → €281.10), Valio Aimo's own suggestion (shown at Kallio Bakery: €1.48 a litre instead of €2.88, €42.00 less), the reorder prompt (the quote is a shortened form of the page's sentence).

**Page 10 (assumptions and next steps).** All correct. Wording to change, by João's rule and to show the criterion's three parts ("clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps"):

- **Title:** keep "Assumptions and next steps". Kicker: "ASSUMPTIONS · TECHNICAL CHOICES · NEXT STEPS".
- **Left block, label "ASSUMPTIONS, STATED ON THE PAGES":**
  "Data: a recording of Valio Aimo's test API (1,163 products, Sat 14 Nov), at a clock we chose. Live mode asks the API per request." · "Customers, people, spend limit values and order history: ours, synthetic." · "The order step is ours by design: “ordered” is a record in our order book." · "Signatures are the gateway's, with a demo key." · "The demo page has no login: it says who you act as."
- **Right block, new label "TECHNICAL CHOICES":**
  "Fixed rules read the request, no model: every reading repeats and can be checked." · "Rules are data, not code: a buyer's profile sets values and cannot switch a fixed rule off." · "Open standards only: OpenAPI 3.1, JSON Schema, MCP, Ed25519 signatures."
- **Label "NEXT STEPS"** (in place of "A CREDIBLE PATH FORWARD"), the five circles, each with what it stands on:
  - "01 Signed claims — Valio Aimo signs its own price, stock and origin. The gateway already signs every offer and states five things per line."
  - "02 Real identity — people and agents sign in with their own accounts. Every identity is already one token tied to one customer and its roles."
  - "03 Real orders — an order message Valio Aimo's systems can take (Peppol BIS Ordering). The order record already holds the lines, the fixed prices and what they relied on."
  - "04 Witnessed audit — orders tied to their log entries; buyer and Valio Aimo each keep the head of the log. The log is already chained and names a changed entry."
  - "05 Real rules — customers' own spend limits and approvers, and a nutrition standard for schools and hospitals. The dietitian already decides every substitute whose formula differs."
- **One line under the circles:** "Then: new and seasonal products marked in the data · recipes around a seasonal ingredient · a scheduler for standing orders · a price limit read from the sentence · Finnish."
- Where each "already" is verified: signatures and five statements [M]; one token, one customer (`src/tta/api/demo_tokens.yaml`, log 02:24); the order record [M: "this record holds everything a supplier order message would need"]; a changed entry named (checks CK1 and CK4, `REVIEW.md`); the dietitian on formula (log 02:13, not measured by me).

**Page 11 (closing).**

| Text | Verdict | True now, and where |
|---|---|---|
| "Demo: joaocostared--trusted-trade-agents.us-east.modal.run   ·   Code: github.com/joaocosta21/junction" | NOT VERIFIED | Not called. [M] locally the root is the older request page; the demo is `/shop`. The code is on branch `replan-build` (log 00:37); whether the repository is public I cannot see |

**Page 12 (Context.dev).**

| Text | Verdict | True now, and where |
|---|---|---|
| "Context.dev: the maker's page fills the allergen gap" | WRONG | It fills nothing: "The allergen claim stays `UNKNOWN`" (`docs/CONTEXTDEV.md`, "Why it sits in the approval step") |
| "…returns seven allergen fields" | WRONG | Seven fields, three of them allergen lists |

Correct, but reword: "(sample of 25 requests)" → "(13 recorded answers, from 25 requests sent)": 13 files in `fixtures/evidence/` [counted]; 9 kept and 4 dropped is `docs/CONTEXTDEV.md:115`, not re-run by me. "contains almond; may contain nuts" is a translation: the recorded page says "manteli" and "pähkinöistä (ei maapähkinästä)"; add "(translated)".

**Page 13 (Aiven).**

| Text | Verdict | True now, and where |
|---|---|---|
| "2 views … separated by the database, not by the application" | CANNOT BE SHOWN | Row 11 above |
| "A read-only role for Valio Aimo, allowed to read that view and nothing else" | CANNOT BE SHOWN | "The role exists without a login; “Valio Aimo reads its own view” has been shown by a test login only" (`docs/AIVEN.md:16`) |
| Notes: "…through a read-only role. And the log outlives the container: Modal scales to zero…" | CANNOT BE SHOWN | The same two points |
| "The log and the shared order book outlive the container: Modal scales to zero, the data stays in Aiven" | WRONG as a general statement | Row 10 above. What a jury does on `/shop` is not in Aiven |

"20 tests pin the stored hashes" is right (20 collected). "Ran on 14 Nov … connected, no fall-back" is `docs/AWARDS.md:30`; whether tonight's deploy runs on Aiven I could not see.

**Page 14 (Modal).**

| Text | Verdict | True now, and where |
|---|---|---|
| "The container scales to zero, so a quiet gateway costs almost nothing…" | OUTDATED (log 02:24, decision B55) | `MIN_CONTAINERS = 1  # was 0` (`deploy/modal_app.py:81`) |
| "…with 9 checks…; all passed after the deploys of 14 Nov" | WRONG | 7 then; 10 today, not yet run on the link |
| Notes: "…the container scales to zero… A script runs 9 checks on the published link." | WRONG | The same two |
| "anyone at Valio Aimo can redeploy it with one command" | NOT VERIFIED | One command deploys it for whoever holds a Modal account and the secret values; nobody outside the team has done it. Say: "one command redeploys it" |

**Layout, as rendered by LibreOffice.** No card runs past a margin any more. Page 10: the last step's text box ends at 12.85 in, 0.27 in past the other pages' right edge, and its text comes close to the slide's edge. Pages 1 and 11 still use other fonts (Calibri, Arial) and no footer, as in the first deck. The hotel's card on page 4 carries the letter "O".

## 4. Missing

### What the five minutes still do not show, by criterion

| Criterion | In v4 | Still missing, and the line that adds it |
|---|---|---|
| **30%** end-to-end demo | Page 5 and the live part | The third option (row 1). On page 5's source line, nothing else |
| **20%** precision | Page 6 | The measured figure, under the table: "109 test sentences: 55 read, 54 asked about, 0 read wrong." (`docs/READING-TABLE.md:10`, log 01:47) |
| **20%** autonomy and controls | Page 7 | That an order placed by the agent says why it was allowed, and that changing a setting is itself logged. One line on page 7: "An order the agent places alone states why it was allowed; every change of a buyer's settings is in the log." ([M] the 302 L sentence; settings: log 02:24, not measured by me) |
| **15%** exceptions | Page 7 | The best example we now have of a substitution handled well is the third option: say it on page 7, row 02, "THE AGENT, ALONE": "Ranks them, and completes a partial delivery with a named substitute for a person to accept" |
| **15%** openness | Pages 8 and 10 | **The standards by name: v4 says only "REST and MCP".** One line at the foot of page 8's right panel: "OpenAPI 3.1 · JSON Schema · MCP, 13 tools, none approves · problem details (RFC 9457) · Ed25519 signatures · /llms.txt" [M: 3.1.0, 27 paths, 98 schemas, 13 tools]. And the three-part wording of page 10 above |
| The brief's first core item, "search for and retrieve what's available and at what price" | Not on the deck | Page 8, step 1 or 2: "Search answers with the price, the stock and the five statements of each product." [M: `POST /v1/products/search?price_and_availability=true`] |
| Valio Aimo's gain | Page 9, in general words | The number: on page 9's right panel, under "Sales that could not be made": "“565 L asked for could not be covered by confirmed stock of the product asked for: about €1,407 at offered prices.”" [M] |

### The moments of the first review's section 1a

| Moment | In v4? |
|---|---|
| 1 · 435 confirmed, the rest not | Yes: page 5 and live step 1. Add the third option to what is said |
| 2 · Lactose-free is not milk-free (26 of 26) | Yes: page 7, and live step 4 |
| 3 · The sale Valio Aimo did not make (565 L, about €1,407) | Live step 3 only. The figure is on no page: add it to page 9 |
| 4 · 302 L / 303 L | Yes, as a sentence on page 7 (not a picture) |
| 5 · The agent tries to approve its own order | Yes, as a sentence on page 7; qualify it (row 3) |
| 6 · Break the signature | No. It would back page 8, step 3, better than the claim there. Keep it for the questions |
| 7 · A stock assistant over MCP | No, and still tried by nobody |
| 8 · The forgotten item | Yes: page 9 |
| 9 · A cake becomes an order | No. For the questions |
| 10 · A changed log entry is named | No. For the questions |
| Opening and closing lines | In the notes of pages 1 and 11. Page 11 itself still shows the older closing, which is fine |

New since then and worth one spoken sentence on page 9: a standing order renewed on `/shop` at 290 L "against a median of 100 L over the last 6 renewals" goes to Hanna, €719.20 (log 02:06; my own call to that route did not go through, so this is the lane's measurement, not mine).

### The plan: v4's own pages, 300 seconds

v4's notes already sum to 300. Two changes: page 7 gives 5 seconds to page 10, which carries a whole criterion; and the live steps are retimed to fit their 90 seconds.

| Page | From–to | Seconds | Note |
|---|---|---|---|
| 1 Title | 0:00–0:10 | 10 | The opening line |
| 2 The problem | 0:10–0:30 | 20 | |
| 3 The solution | 0:30–0:50 | 20 | |
| 4 The four customers | 0:50–1:00 | 10 | |
| 5 The demo, end to end | 1:00–1:10 | 10 | |
| Live on `/shop` | 1:10–2:40 | 90 | 1:10–1:35 the 1,000 L sentence: "435 litres of the milk you asked for; the rest only unconfirmed, or as a named substitute: a person chooses." · 1:35–1:55 "Confirm order", the log (11 events), Valio Aimo's view · 1:55–2:15 the back office: 565 L, about €1,407 · 2:15–2:40 Ward 4: 26 of 26 refused |
| 6 Precision | 2:40–3:00 | 20 | |
| 7 Alone, with approval, or never | 3:00–3:45 | 45 | was 50 |
| 8 How any company can connect | 3:45–4:10 | 25 | |
| 9 Value | 4:10–4:25 | 15 | |
| 10 Assumptions and next steps | 4:25–4:50 | 25 | was 20 |
| 11 Closing | 4:50–5:00 | 10 | The closing line |
| **Total** | | **300** | Pages 12 to 14 are outside the five minutes |

The back office comes before the ward, as in v4's notes: the page counts everything done in that browser.

## 5. What could not be verified

- **The public link**: not called. The demo address, the checks on it and whether it runs on Aiven depend on tonight's deploy.
- **The final commit**: I measured a working tree that three lanes were still changing. Run the 1,000 L sentence once on the final commit and compare page 5 with it; a price bound on substitutes and "same brand first" (decisions B68, B70) are being built and are claimed nowhere in v4.
- **How v4 looks in PowerPoint or Google Slides**: seen only through LibreOffice, without Inter.
- **`/shop` in a browser**: I drove its routes, not the page.
- **From the log, not measured by me**: the dietitian deciding a substitute whose formula differs (02:13); settings changes in the log (02:24); the standing order at 290 L (02:06).
- **From documents only**: everything on pages 12 to 14 about what ran on Context.dev, Aiven and Modal (`docs/AWARDS.md`, `docs/AIVEN.md`, `docs/CONTEXTDEV.md`), including "9 of 13" on today's matcher.
- **Whether the repository is public**, and which branch the form points at.
