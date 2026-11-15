# Google DeepMind — "Best Use of Gemma"

Awarded to the team demonstrating the most innovative and impactful use of Google's **Gemma open models**.

## The ask
They're looking for:
- **Creative applications**
- **Strong technical execution**
- **Solutions that showcase the potential of open AI models to solve real-world problems**

*(No further problem statement, rubric or deliverable list published — this is an open award like the Gemini challenge.)*

## How to access Gemma
Gemma is Google's family of **open** AI models. Available through several platforms, including Junction 2026 partners:

| Platform | Use |
|---|---|
| **Featherless AI** | Hosted Gemma models through an API |
| **Modal** | Deploy and run Gemma on serverless GPU infrastructure |
| **Verda** | Cloud GPU resources to deploy and run Gemma yourself |
| **Google AI Studio** | Experiment with Gemma in the browser |
| **Hugging Face** | Download Gemma models and integrate them |

Setup instructions in the official Gemma documentation. **Check the Junction Hackerpack for event-specific credits or access instructions.**

## Implications for how we build
- **Second stackable challenge**, like the Gemini one — no problem statement of its own, so it attaches to whatever we build provided Gemma is central.
- **Gemma and Gemini are separate awards.** A project could in principle target both, but the honest version of "best use of Gemma" is a build where running an *open* model matters: self-hosted, fine-tuned, on-device, offline, or cost/privacy-constrained. If Gemini (hosted, frontier) is doing the real work, the Gemma entry is weak.
- **"Potential of open AI models" is the actual bar.** The differentiator for open weights over an API is: fine-tuning on task-specific data, running locally/privately, or deploying at a cost point a frontier API can't match. A build that just calls hosted Gemma through an API instead of hosted Gemini has no story here.
- **This pairs naturally with specific other challenges on our list:**
  - **S-Pankki** — financial data, privacy-sensitive, strong argument for a self-hosted open model
  - **Aalto** — mental-health sensing, same privacy argument, plus on-device
  - **AfterQuery** — their *explicit tiebreaker* is training a smaller model on environment experience; Gemma is the obvious candidate
- **Modal / Verda / Featherless credits** may need separate claiming — check the Hackerpack. Fine-tuning needs GPU access, so secure that before committing to a fine-tune plan.
