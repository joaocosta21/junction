# NVIDIA — "Best Use of Nemotron"

Build a project powered by NVIDIA Nemotron that solves a real problem through reasoning, tool use, or coordinated workflows. **Applies to: any track.**

## The ask
Build a project where **Nemotron plays a meaningful role in doing real work**. Use it alone or alongside other models, tools and data sources, to solve a problem for a **clear audience**. Nemotron must contribute directly to core functionality, and **the demo should make that contribution visible**. Otherwise open-ended: choose the problem, design the workflow.

## Minimum requirements
- **Use NVIDIA Nemotron 3.5 Super VL in the working solution.**
- **Demonstrate its contribution to the project's core functionality.**
- **Submit a short written explanation** (as text in the submission form) identifying: the model used, what it does, why it matters, and **how you improved its outputs**.

## The technology — Nemotron 3.5 Super VL
NVIDIA's newest open model:
- **120B parameters, but only ~12B active per token** (MoE) — fast for its size
- **Reads text, images, documents and video in a single workflow**
- So one model can look at a screenshot, read a PDF, watch a clip, call a tool, and write code to act on it

## Judging criteria
- **Meaningful Nemotron usage** — Nemotron is central to the project's value; the team clearly explains what it does and why it matters
- **Technical execution** — the demo works reliably, with thoughtful choices around architecture, data flow, tool use, latency or error handling
- **Quality of AI output** — outputs are useful, relevant and grounded where appropriate; **the team demonstrates efforts to improve quality through prompting, evaluation, or feedback loops**
- **Creativity and differentiation** — Nemotron used thoughtfully or inventively, with a distinct approach

## Prizes
**2 winners, each receiving 1× RTX 5080.**

## Getting started — and the rate limits that matter
- **NVIDIA Build** — free hosted APIs. **OpenAI-compatible**, base URL `https://integrate.api.nvidia.com/v1` (e.g. model `nvidia/nemotron-3.5-lightning-30b-a3b`).
  - **Free tier is rate-limited — reportedly ~40 requests/minute per key.** Agent loops need **retries with backoff**, and **each teammate should use their own key**.
- **OpenRouter** — serverless, unified API across providers.
  - **Free variants (`:free`) capped at 20 req/min and 50 req/day** — or 1,000/day once the account has bought ≥10 credits.
- **Hugging Face** — open weights for local runs, fine-tuning, or deployment on Brev.

## Contacts and support
- Support: NVIDIA Discord channel and the NVIDIA table
- Main contact: **Elliot Winch**, Community Program Manager EMEA — ewinch@nvidia.com
- Mentors attending: **Maxime Pariente**, **Ryan Reese**
- Judges: NVIDIA team

## Implications for how we build
- **Third stackable challenge** (with Gemini and Gemma) — "applies to any track" is stated outright, so it attaches to a partner-challenge build.
- **The rate limits are the real constraint and they're published.** 50 requests/day on OpenRouter free is nothing for an agent loop; ~40/min on NVIDIA Build is workable but needs backoff. **Get one key per teammate on NVIDIA Build early.** A demo that dies on rate limits in front of judges fails "technical execution" directly.
- **"How you improved its outputs" is a required submission field** and appears again in the judging criteria. Keep a record of prompting iterations / evals as we go — this is cheap to do live and expensive to reconstruct Sunday morning.
- **Native video + document + image in one model is the distinctive capability.** A text-only use of Nemotron has no story against teams exploiting the VL part. This makes it a strong technical fit for:
  - **Stoa** (construction drawings — documents and images, needs visual grounding)
  - **AstraZeneca** (Finnish-language PDFs: strategy and roadmap documents)
  - **Hostinger** (multimodal content analysis for propaganda detection)
- Note the model naming inconsistency in the brief: it requires **Nemotron 3.5 Super VL** but the example API string is `nemotron-3.5-lightning-30b-a3b`. Confirm the exact model ID at their table before building against it.
