# P14 — Photo in, speech in, speech out: who values them, and what to keep

Written Saturday 14 Nov, 15:05. Measured in replay with no key, each run in a fresh data folder (scripts in the scratch folder `replan/P14/`). Web pages were read on 14 Nov 2026 through the page-reading tool; quotes are as it returned them. Every URL is under "Sources".

## 1. In five lines
1. **Photo in: keep, and fix one thing.** On the page, one click on "Read the photo and run" transcribes, reads, builds the offer and places the order (`src/tta/ui/run.py:176-201`). The lines are shown only on the result. That breaks V8 and the rule "shown before anything is built".
2. **Speech in: do not build.** It scores 0 on Valio's five criteria, the browser's recogniser uses no Gemini, and Gemini audio needs credits our key does not have. A microphone is also what the brief's "chatbot" looks like.
3. **Speech out: do not build.** It scores on no criterion for any of the three audiences.
4. **The photo claim is not real yet.** Its transcription and reading are written by hand (`AIMO/build/handback/T18.md:3-10`). By the code, the deployed link refuses every photo but one file while the key has no credits. The photo is not in the demo script or the video.
5. **Cost:** 2 h minimum (the photo stops after reading), 4 h in full. `AIMO/PLAN.md:246` argues against voice with a sentence that today's Gemini page does not contain; the conclusion stands for other reasons.

## 2. What exists today (verified)
- **Where it is.** On `/`, under the text box and its Run button, above the examples: a file input and the button "Read the photo and run" (`src/tta/ui/templates/index.html:46-51`). REST: `POST /v1/requests/read-image` (`src/tta/api/routes.py:279-298`). No MCP tool reads a photo (`AIMO/build/handback/T18.md:159`).
- **What it does.** The first bytes and the size are checked before any model call (`src/tta/agent/images.py:92-102`, 5 MB). Gemini returns lines held to a schema. The joined lines go to the same parser and text check as typed text (`src/tta/agent/photo.py:113`).
- **Measured, REST, demo photo, hotel:** 200 in 0.002 s. `transcription` = `["Tilaus", "Maito laktoositon 1000 l — ma"]`. Request = 1,000 L `milk`, `FREE_FROM_LACTOSE`, needed by 2026-11-16. Header `TTA-Reading-Source: hand-built`. Sentence: "Read from a photo: transcribed by hand, not by a model, then read from an answer written by hand, not by a model; no model was asked." Orders after the call: 0.
- **Measured, page, demo photo, hotel:** 200 in 0.03 s. One click gives the result page with "Read in the photo", the request, the offer, and "Sent for approval … rule P-01".
- **Measured, the other cases, no key:**
  - the same file with one byte added: 503, "the gateway can read only the 1 recorded demonstration photo(s), and this is not one of them";
  - the demo photo as the allergy ward: 503 (a recording is served only for its profile);
  - a text file sent as an image: 422.
- **What a judge meets on the deployed link** (`8163d5d`, which contains T18's `812de0f`; checked with `git merge-base --is-ancestor`). The control is there. The demo file is not on the page: it is `fixtures/agent/photos/order-list.png` in the repository. The key ran on a zero balance on 14 Nov (`docs/AWARDS.md:28`), a 402 counts as "cannot be reached" (`src/tta/agent/gemini.py:74`), and a photo with no recording is then refused (`src/tta/agent/fallback.py:147-157`). So a judge's own photo is refused. Read from the code; I did not call the deployed app.
- **The demo photo is a rendered stand-in**, not a phone photo (I opened the file: a font on lined paper). Gemini has never read it: 6 requests, all 503 or 504 (`AIMO/build/handback/T18.md:3-6`).
- **Demo script and video.** `docs/DEMO.md` names the photo once, in the note on recordings (line 22). It is not a step. `docs/PITCH.md:38` lists it as an optional beat. The 2:00 shot list (`docs/PITCH.md:62-72`) has no photo.
- **Tests.** 58 test functions in `tests/agent/test_photo.py` (24), `tests/agent/test_images.py` (9), `tests/api/test_read_image.py` (16), `tests/ui/test_photo_page.py` (9); counted with `grep -c`. They cover the same parser and text check, an instruction written in the photo, an upload that is not an image, and nothing written to a log. None calls Gemini. Run by me at 15:03 with no key: 89 passed (550 s, on the loaded machine).
- **Voice.** Nothing is built. The pages have one script, `src/tta/ui/static/app.js` (29 lines). The page policy is `script-src 'self'`, `connect-src 'self'`, and no `media-src` (`src/tta/ui/security.py:39-48`).

## 3. What Valio's answers change
- **V8** ("the final submition should always have the input from the user"). The photo button orders in the same click when no rule asks for a human. Measured with the photo reader replaced by a stub that returns scenario 2's own recorded reading: "Ordered by the agent. The agent placed this order alone for €402.00 net". The demo photo hides this: its €2,580.64 is over the hotel's €750 limit, so it goes to approval. Agent P8 did not run the photo button (`P8-confirm.md:23`); this fills that row.
- **V5** ("if you are not sure you need to flag it to the user to ask for his input"). Handwriting is the least sure input we have. Today the person sees the lines after the offer and the order exist. `docs/AWARDS.md:29` ("shown to the person; then the same parser…") and `index.html:50` ("Two steps you can check") give the order of processing. On the page the person cannot stop between the two steps.
- **The REST route already keeps the rule.** It answers the lines and the typed request and builds nothing. The agent must then send `POST /v1/offers` itself.
- **The mentor's goal** ("attract as many customers as possible"). A kitchen that writes its list on paper would be one more kind of customer. No answer says Valio has such customers. See question Q1.

## 4. Options and recommendation

### 4a. Value for each audience (0 = none, 3 = decides a score)

| | Valio's judges | Gemini award's judges | Peer reviewers (main prize) |
|---|---|---|---|
| **Photo in** | **1.** It touches only "how Precisely the agent matches what the buyer actually asked for, with the least manual correction needed", and only if the lines are shown and checked. The three core items speak of "an external agent", not of paper. | **2 if recorded live, 0 today.** They want "projects that go beyond simply adding an LLM to an application". Lines held to a schema and then checked by code fit that. But Gemini has never read our photo. | **2.** "Innovation: is it new/different" (`CLAUDE.md`'s wording): a handwritten note that becomes a checked order is understood in ten seconds. "Implementation: realistic, viable" fails if their own photo is refused. |
| **Speech in** | **0.** "This is not about replacing today's e-commerce UI with a chatbot." A misheard number raises "manual correction". | **0 with the browser's recogniser** (no Gemini is used). **1 with Gemini audio**: a second multimodal input, the same idea as the photo. | **1.** A second way to fill the same box. It is the input most likely to fail in a hall (my assumption, not measured). |
| **Speech out** | **0.** No criterion names it. The "human-readable record" they ask for is the audit trail, which is text. | **0.** Reading a sentence aloud is "simply adding" a model. | **0.** Not heard at a table in a hall (my assumption). |

**Does speech make us look like a chatbot?** Yes, on stage. The claim "any front end lands on the same typed request and the same rules" is true, and a Valio judge can check it: the typed request and the rule ids are on the screen. One non-typed front end proves it. A second one adds a microphone and no new proof. The strongest proof is already built: another company's agent calling over REST or MCP. So the photo is shown as one more caller, for a few seconds, never as the product. That is the framing a Valio judge would accept.

### 4b. The cheapest honest way to do each (current documentation)

| | Needs | Languages | Network | Hours | What fails live |
|---|---|---|---|---|---|
| **Speech in, browser** (`SpeechRecognition`; in Chrome `webkitSpeechRecognition`) | No key, no credits. A microphone prompt: "Pages hosted on HTTPS do not need to ask repeatedly for permission" [S14]. Code in `app.js` only: the heard text goes into the text box and the person presses Run. | Chrome's own demo lists `fi-FI`, `sv-SE` and `pt-PT` [S5]. | **Yes.** "On some browsers, like Chrome … Your audio is sent to a web service for recognition processing, so it won't work offline." [S1] The audio goes to Google, not to us. | 1.5–2 | Hall noise. Wi-Fi. Firefox: disabled by default. Edge and Opera: not supported. Chrome and Safari: "partial" [S3]. MDN: "not Baseline" [S1]. |
| **Speech in, on the device** (`processLocally = true`) | Chrome 139+ [S4], and a language pack downloaded once [S2]. For Edge the sources disagree: 139+ [S4], or Canary and Dev 150+ behind a flag [S6]. | Finnish not confirmed. Edge's list: en-US, de-DE, it-IT, pt-PT, es-ES, ko-KR [S6]. | No, after the download. | 2–3 | `language-not-supported` when the pack is missing [S2]. |
| **Speech in, Gemini audio** | **Credits.** At a prepaid balance of zero, requests fail with "an HTTP 402 Payment Required error until you add credits", and "Your projects aren't automatically downgraded to the Free Tier" [S9]. Also a recorder in the page (`getUserMedia` "can only be used in secure contexts"; localhost counts [S12]), a new upload route (the 64 KB body limit refuses audio as it refused photos), recordings and tests. | The page gives no language list and does **not** say "English only" [S7]. Finnish speech is unverified either way. | Yes. | 4–6 (my estimate) | Gemini itself: 503, 504 and 402 on 14 Nov; 21.7 s for a one-word answer (`docs/AWARDS.md`, "Honest notes"). |
| **Speech out, browser** (`speechSynthesis`) | No key. "Baseline Widely available" [S15]. A click before `speak()` (Chrome's rule since M71; not re-checked [S13]). | The voices of the machine. | No for local voices (assumption). | 0.5–1 | Not heard. A missing Finnish voice. |
| **Speech out, Gemini** (`gemini-3.8-flash-tts`) | Credits (402 today). `media-src` added to the page policy. | "over 130 languages"; Finnish is listed [S10]. | Yes. | 2–3 | As Gemini audio. |

Notes:
- `gemini-3.6-flash` accepts "Text, Image, Video, Audio, and PDF" [S8]. Audio costs 32 tokens a second, `audio/webm` is accepted, and a request is at most 20 MB [S7].
- The pricing page shows "Free of charge" for `gemini-3.6-flash` on the free tier [S11]. That does not help a project whose prepaid balance is zero [S9]. A key from a project with no billing account would be on the free tier (assumption; not tried, no service was called).
- **Measured: what our reader does with a spoken sentence, no key** (`POST /v1/requests/parse`, hotel). "I need 1000 litres of lactose free milk by Monday", and the same in lower case with "liters", are read by the fixed rules as 1,000 L `milk`, `FREE_FROM_LACTOSE`, 16 Nov. "one thousand litres" and "a thousand litres" answer 503: "milk is named with no quantity in digits and unit". The sixth reading in a minute answers 429 ("at most 5 in 60 seconds").

### 4c. The safety rule, and whether the photo keeps it

| Part of the rule | REST `read-image` | Page "Read the photo and run" |
|---|---|---|
| The text read is shown before anything is built from it | **Yes.** The route builds nothing. | **No.** Lines, offer and order come from one click (`run.py:182`, `194`, `199`). |
| Same reader and same checks as typed text | **Yes** (`photo.py:113`). | **Yes** (the same call). |
| Nothing ordered without the user's confirmation (V8) | **No today:** an agent may order alone within its authority. Closed by P8's item M1 (ordering alone off in both profiles). | **No today.** Measured: €402.00 ordered alone from a photo (stubbed reader). Closed by P8's M1 too: the photo shares `_offer_and_order`. |

So P8's M1 closes the third row with no work here. The first row is this topic's own gap (PV-1). Any voice input would have to pass the same table. The browser version does by construction: it only fills the text box.

### 4d. Recommendation
- **Photo in: KEEP, and fix.** The button stops after reading. The page shows the lines and the typed request, and builds nothing. A second button continues from the reading that was kept, with no second model call.
  - Putting the lines back into the text box is not enough. Measured: "Tilaus / Maito laktoositon 1000 l — ma" typed as the hotel answers 503 with no key. The buyer agent has no run recording for it, and "the fixed rules could not read it either: line 1 names no product type of the table". So the second step must use the kept reading.
- **Speech in: DROP.** If the team still wants it for the peer review, the only version worth its hours is the browser one (1.5–2 h, Chrome, fills the text box). It is the first thing cut.
- **Speech out: DROP.**
- **In the 2:00 video.** Speech: nowhere. Photo: only if PV-3 is done (a real phone photo, read by Gemini live). Then five seconds inside shot 2 (0:08–0:18), caption "Agent, sentence or photo: the same typed request". Otherwise it stays out of the video and on the page, labelled hand-built.
- **The sentence for "is this a chatbot?"** "No: it is a typed interface that any agent calls over OpenAPI or MCP; a sentence or a photo only fills the same typed request, the same rules judge it, and nothing is ordered until a person confirms." (The last part is true once P8's item M1 is in.)

**DECISION D1:** no speech in and no speech out (recommended), or the browser-only speech input after everything Valio asked for is built.
**DECISION D2:** the photo stops after reading (PV-1, 2 h; recommended), or the upload control leaves the page and the photo stays a REST route (0.25 h).
**DECISION D3:** the photo enters the video only if Gemini reads a real photo live. That needs credits (agent P13's topic).

## 5. Work items (minimum version first)

| id | What | Files | Hours | Who | Criterion | Depends on |
|---|---|---|---|---|---|---|
| **PV-1** (minimum) | The photo button stops after reading: lines and typed request shown, nothing built. "These lines are right: build the offer" continues from the kept reading. "No" puts the lines in the text box to be corrected. | `src/tta/ui/run.py`, `src/tta/ui/request_page.py`, `src/tta/ui/templates/index.html`, `src/tta/ui/templates/_result.html`, `tests/ui/test_photo_page.py`, `tests/ui/test_run_unit.py` | 2 | computer-science member | 20% autonomy and controls (V8, V5) · 20% match | P8's M1 (no order alone; `_offer_and_order`, `run.py:190`, is shared) and P8's F1 (the same button wording) |
| PV-2 | One example button, "Photo of a handwritten order list": it shows the demo photo and runs PV-1 on it. The upload control says "Any other photo needs Gemini live." | `src/tta/ui/examples.py`, `src/tta/ui/templates/index.html`, `src/tta/ui/request_page.py`, `src/tta/ui/static/` (the image; `img-src 'self'` allows it), `tests/ui/` | 1 | biomedical member | 30% demo (reachable in one click on the link) · main prize: innovation | PV-1 |
| PV-3 | A real phone photo of a handwritten list replaces the stand-in, recorded from Gemini: `.venv/bin/python -m tta.agent.record --only photo --max-calls 4` (`T18.md:21-23`). At most 4 requests. | `fixtures/agent/photos/order-list.png`, `fixtures/agent/transcribe-photo.json`, `fixtures/agent/parse-photo.json`, two strings in `tests/agent/conftest.py` and `tests/ui/test_photo_page.py` | 0.5 | biomedical member | Gemini award · 20% match | Gemini credits (P13) |
| PV-4 | Documents. `AIMO/PLAN.md:246`: the "English speech only" reason is not on today's page, "1–2 h" is low, and speech is dropped for the reasons of 4a. `docs/AWARDS.md:29` and `index.html:50`: the lines are confirmed before the offer. `docs/PITCH.md` "Likely questions": the chatbot sentence. | those documents and the one template line | 0.5 | any member | 15% openness (visible assumptions) | PV-1 |
| not built | Speech in: browser 1.5–2 h, Gemini audio 4–6 h. Speech out: browser 0.5–1 h, Gemini 2–3 h. | — | 0 | — | none | — |

Cut first: PV-3, then PV-2, then PV-4. If PV-1 is cut too and P8's M1 is in, the photo no longer orders alone, but its lines are still shown after the offer is built: then change the sentence at `index.html:50` (0.1 h), or take the upload control off the page and keep the REST route (0.25 h).

## 6. What changes in the demo
- Today: one click on the photo button ends on "Sent for approval" (the demo photo) or "Ordered by the agent" (a small order).
- After PV-1: the click ends on "Read in the photo: Tilaus / Maito laktoositon 1000 l — ma", the typed request (1,000 L milk, lactose-free, Monday 16 Nov) and one button. The offer of €2,580.64 appears only after the person presses it.
- After PV-3: the sentence changes from "transcribed by hand, not by a model" to "transcribed by gemini-3.6-flash".
- Nothing in the three scenarios changes.

## 7. Risks and what not to do
- Do not show a microphone on stage or in the video. The brief's Impact paragraph was written against that picture.
- Do not claim "Gemini reads handwriting" in the Gemini write-up while the recording is hand-built. `docs/AWARDS.md:30` says so today; keep it until PV-3 is done.
- Do not leave the upload control on the link while every photo but one is refused and no sentence says why.
- Do not spend hours here before V8, V10, V5 and B5 are built. This topic is worth at most 1 of 3 to Valio.
- At the table, five readings a minute per address is the limit (429 measured). Several reviewers behind one address can hit it. Which address the deployed app sees behind Modal is not checked (`docs/AWARDS.md`, Modal section).
- Not tried: whether Chrome's speech service works under our page policy `connect-src 'self'`. I assume the browser's own recogniser is not bound by it.

## 8. Questions
- **For the team:** do Gemini credits arrive before the freeze? PV-3 and D3 depend on it.
- **Q1 for Valio (booth shape).**
  - Context: our gateway takes a typed request from any agent. On the buyer's side we also read a photo of a handwritten order list.
  - What we did: the photo is transcribed, the lines are shown to the person, and the same checks as for typed text apply. Nothing is ordered before the person confirms.
  - What we got: "Maito laktoositon 1000 l — ma" on paper becomes 1,000 L of lactose-free milk for Monday 16 Nov.
  - The ask: "Do your customers' kitchens send you orders written on paper, as photos or by phone today? Is that worth showing, or is it outside what you want to see?"
  - If nobody answers: we keep the photo as a small example of one more caller, and build no voice.

## Sources (read 14 Nov 2026)
- [S1] https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition
- [S2] https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API/Using_the_Web_Speech_API
- [S3] https://caniuse.com/speech-recognition (global usage shown: 88.82%)
- [S4] https://caniuse.com/mdn-api_speechrecognition_processlocally
- [S5] https://raw.githubusercontent.com/GoogleChrome/webplatform-samples/master/webspeechdemo/webspeechdemo.html (the `langs` table of Chrome's demo; it says nothing about quality)
- [S6] https://learn.microsoft.com/en-us/microsoft-edge/web-platform/speech-recognition-api
- [S7] https://aistudio.google.com/docs/audio (`ai.google.dev/gemini-api/docs/audio` redirects here)
- [S8] https://aistudio.google.com/docs/models/gemini-3.6-flash
- [S9] https://aistudio.google.com/docs/billing
- [S10] https://aistudio.google.com/docs/speech-generation
- [S11] https://aistudio.google.com/docs/pricing
- [S12] https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia
- [S13] https://groups.google.com/a/chromium.org/g/blink-dev/c/WsnBm53M4Pc (seen through a search summary only, not opened)
- [S14] https://developer.chrome.com/blog/voice-driven-web-apps-introduction-to-the-web-speech-api
- [S15] https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis ("It's been available across browsers since September 2018.")
