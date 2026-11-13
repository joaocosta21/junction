# Recommendation — challenge choice and tech-award pairing

Based on three independent analyses of all 22 briefs against our team (3 biomedical engineers + 1 CS, ~30h). **All three independently ranked Aalto first.**

## Primary: Aalto — "Beyond the Clinic"

### Why
1. **Smallest qualified field** — est. 15–25 teams of ~500. Depression/TMS/closed-loop neuromodulation filters out generalists.
2. **The judges' scoring bottleneck is our expertise.** Judged by the Ilmoniemi/Lioumis neuroscience lab. They will probe what HRV tracks, what a phone accelerometer can infer, why baselines matter. Unbuyable in 30h by a software team.
3. **Best peer-review hook on the board** — and peer review is the only route to the €10k top 5. "Depression returns after hospital treatment and there's nothing between visits" needs no explanation.

The only challenge where domain edge + small field + peer legibility align.

### What everyone else will build
A mood check-in app with meditation audio and a line chart. Not closed-loop. Their brief states **"sense how someone is doing → respond with something that helps → learn what works best for that person"** twice — that is the spec, and it's where generalists hand-wave.

### 30-hour scope
- Ingest phone-derived or open HRV/actigraphy signals (brief: *"a laptop and a phone are enough"*)
- Per-person deviation-from-baseline state estimate
- Bandit-style selector over 2–3 sensory interventions
- Clinician triage view
- **Personalisation demonstrated on simulated response data — stated openly.** Neuroscience judges respect a declared limitation and punish an overclaim.
- **Explicit escalation path** for bad signals. Judges from a clinical lab will check for it.

### Risks
- **No published rubric and no cash prize named** → ask at their booth what they weight, Friday.
- Don't let UI polish eat the weekend. The loop is the product.
- Vulnerable population: avoid implying diagnostic capability.

## Runner-up: MariaDB SVT track
Highest win-probability-per-hour on the list. The sponsor pre-announced where the crowd goes (*"RAG track, recommended for most teams"*) and where credit lies (*"SVT or both will be recognised for the added technical ambition"*). Edit-war / bias-drift detection over revision history is **statistical change detection over time series** — our skill set — on starter repos with near-zero setup. Won't reach top 5; likely wins its track. ~3–8 serious SVT entries expected.

## The trap: AstraZeneca
Rubric is ideal for us (30% actionability + 25% insight + 20% data quality = 75% domain reasoning; only 15% execution). But three independent ways to lose:
1. Key documents are in **Finnish**; we have no Finnish speaker
2. **Mentors mostly available Friday 18:00 only**; one person Saturday
3. **Judging Sunday 14:00** may collide with peer review (10:30–14:00)

Peer-review ceiling near zero (Finnish health-policy context is illegible to a tired international hacker). Take only if we secure a Finnish-speaking contact Friday night.

## Drop: Hostinger
Currently listed as our main challenge. Worst fit on the board:
- **Most crowded track at the event** (est. 70–110 teams) — free VPS + credits + domain draw everyone
- Our biomedical edge is **irrelevant** to it
- Hard deploy requirement spends our scarcest resource (one CS engineer) on infrastructure
- A precision/FPR table is right for the partner and the *worst* answer for a tired peer reviewer

## Also cannot win
- **Stoa** — CV/CAD engineering we don't have; hardest brief collected; no rubric
- **Bahn** — needs an optimiser iterating from Friday 19:30, and its Sunday 08:00 final (07:30 cutoff) collides with our submission morning
- **Tieto**, **Espoo** — three of four members would be passengers; deliverables are documents with near-zero peer appeal
- **Cala** — richest prize, but 50% of score is execution + originality in VC/founder domain none of us know

## Tech-award pairing

**Reality check:** proposed bundles totalling 26–33 incremental hours do not fit a 30-hour total (~20h of build time). Realistic: **2–3 awards.**

### Recommended for an Aalto build (~10h, 3 awards)
| Award | Work | Hours | Double duty |
|---|---|---|---|
| **Modal** | `modal deploy` → public demo URL | 2–3 | We need the URL anyway |
| **Aiven** | ClickHouse decision log, surfaced in UI | 4–5 | **Doubles as Aalto's clinician triage view** |
| **Gemini** | Multimodal affect reading (voice/audio in) | 3–4 | Must be a Gemini-specific capability, not a chat wrapper |

### Skip for this build
- **Cloudinary** — separate form required; only pays off if visual media is central
- **Oxylabs / Context.dev / Exa** — no web-data layer in Aalto; all three are substitutes anyway
- **Nemotron** — its VL edge needs documents/images to be differentiated
- **Gemma properly** — 8–14h fine-tune; too expensive. (An API-only Gemma call has no story.)

### Judgment call: Atech / Arduino
5–8h for a physical device. **Upside:** a working device on the table is far more memorable in peer review than a web app when ~500 teams pitch software. **Downside:** highest-variance hour spend; kits are first-come and returned after demos. **Decide Saturday morning, not now** — but look at the kits tonight (5th floor hardware lab; Arduino UNO Q includes USB camera + Modulino sensors).

## Build-first components (pay into everything)
1. **Provenance / source-URL display (3–4h)** — satisfies a stated requirement in 7+ briefs. Lower priority for Aalto specifically, high if we pivot.
2. **Decision/eval log surfaced in UI (4–6h)** — satisfies Aiven + Nemotron's required "how you improved outputs" field + the explainability criterion of nearly every partner challenge. **For Aalto this IS the clinician view.**

## Open items to verify Friday night
- [ ] **Can one project enter multiple MAIN challenges?** Rules say "at least one"; form says "Challenge" singular. If multiple → Aalto + MariaDB-SVT is a strong double. **Ask info desk / Discord.**
- [ ] Ask Aalto booth what they actually weight (no published rubric)
- [ ] Confirm AstraZeneca's Sunday 14:00 judging vs peer review window — only if AZ is still live
- [ ] Claim credits: Modal ($100 × 4, code `VVX-2QX-8HW`), Verda (€200), Gemini (capped at 400 teams), Claude, OpenAI
- [ ] Check 5th-floor hardware lab stock
- [ ] Confirm all four of us are 18+ (required for Google accounts)

## The structural insight worth remembering
**The challenges where a specialist can win the partner prize are mostly the ones that cannot win top 5, and vice versa.** Pick which prize we're playing for deliberately. Trying for both produces a project neither rigorous enough for the partner nor legible enough for the peers.

**Aalto is the exception** — it is the one place where the same artifact can plausibly do both.
