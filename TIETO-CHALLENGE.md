# Tieto — "Earned Trust in AI Code"

How does AI code review keep pace with AI-written code, while humans stay accountable for every change?

## Framing
A PR lands from an agent: 200 lines, your name on the approval. Instead of hunting for problems in the diff, the change opens with its own explanation — what it does, why, what else it touches, and how sure the AI is about each part. You're checking a story and questioning the parts that don't add up.

Background: agent tokens passed human tokens in February 2026 and reached 7.3 trillion by August (OpenRouter data, a16z chart). Reviewing every change by hand doesn't scale, yet engineers need a sound basis to trust AI-reviewed code.

## The ask
Design an **AI code review concept**, then show it works. Define concept, principles, reference implementation and technology considerations across frontend, backend and security.

Challenge the traditional model: is line-by-line review still the right way to ensure quality? Balance **risk, hallucination, transparency, confidence and quality**.

**The result is a reference implementation that illustrates the concept — not a product.**

## What's expected from each team
- Define the concept: what the "PR review" factory should follow.
- State key principles, including how it balances risk, hallucination, transparency, confidence and quality.
- Illustrate it as a reference on **one sample agent-written change with its requirement ID**.
- Show what the AI found, **what it refused to decide, and why**.
- Show how the evidence lets a **named human** accept the change without a full read.
- Name the failure modes seen, and keep a short decisions log.
- Synthetic or cleared sample data only.

## Deliverables
- **Concept card**: recommendation, principles, trade-offs, limits
- **Live walkthrough** showing where the trust comes from
- **Lessons log** and a demo video/presentation

Out of scope: a finished product, model training, vendor selection.

Expected outcome: a concept with explicit trade-offs that humans can trust and be accountable for.

## Their core principle — AI reviews, humans stay accountable
Trust is built on evidence a person can check and own, not on the AI being confident.

How humans build trust they can stand behind:
- A named engineer owns each change and signs off.
- The AI review is **advice with evidence, never the approval itself**.
- Evidence is traceable to a requirement, so the owner can check it quickly.
- Depth of human review follows risk: low-risk changes get light checks, high-risk ones get a full read.
- Humans spot-check the AI reviewer and track what it misses.
- Trust is earned per area from track record, and withdrawn after escapes.

**What the owner signs:** what was checked and by whom/what; what was *not* checked and why; the residual risk they accept.

**What is not accepted:** "the AI said it was fine"; an unowned merge; confidence without evidence; a risk score nobody can explain.

**What major vendors recommend:** route human attention by risk; keep reviews fast and low-noise; review with full repo context and verify findings before posting; measure outcomes (reverts, incidents), not review activity.

## Directions (options, not requirements)
Every option keeps a named human accountable for the outcome.
1. **Generalist reviewer** — one reviewer covering frontend, backend, security and performance. How to train or prompt for that breadth is part of the work.
2. **Classifier** — flag code that genuinely needs human review, and separate it from code that meets the standard.

## Questions judges will ask
- What would make you not trust your own output?
- Who owns the decision?
- How would this scale?

## Resources provided
- Background on what good code means at Tieto: standards, security, quality
- A requirements set: intent, functional and non-functional
- Sample agent-written changes, each with its requirement ID
- Model access via partner credits on the Junction Platform (any partner's models)

## Implications for how we build
- The deliverable is a **concept + reference implementation**, not a product. Judging weight sits on the clarity of the principles and the honesty of the trade-offs.
- **"What it refused to decide, and why"** is an explicit requirement — abstention must be a first-class output, not an afterthought.
- The sign-off artifact (checked / not checked / residual risk accepted, with a named owner) is the centre of the demo.
- Must use their sample agent-written changes and requirement IDs — traceability to a requirement is the mechanism that makes evidence checkable.
