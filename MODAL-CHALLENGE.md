# Modal — "Best Use of Modal" (tech track)

Take your Junction project from laptop to production AI on Modal.

> **Explicitly stackable:** *"Best use of Modal is a tech challenge, so you compete in it on top of your main challenge... The same project can enter other tech challenges too."*

## The framing — and it's accurate
*"Every Junction team is building with AI, and most hit the same wall: the model runs on a laptop, but too slowly, not on a GPU, and not behind a URL the judges can open."*

## The ask
Use Modal to power the project you're already building:
- **Serve an open model on a GPU**
- **Run your agent's code in secure Sandboxes**
- **Fine-tune a model on your own data**
- **Fan out a big batch job**

All in plain Python — **no Dockerfiles, Kubernetes or YAML**.

They're looking for **the most ambitious working AI system built on Modal, where Modal does the heavy lifting and the team spends its 48 hours on the problem.**

## Credits — claim these
**$100 in Modal credits per participant** (not per team), valid **one year from redemption**.

Sign up for a Modal account, then redeem at:
**https://modal.fillout.com/t/qMXCmRGseUus?code=VVX-2QX-8HW** using code **`VVX-2QX-8HW`**

## What's available
- **GPUs:** T4, L4, A10, L40S, A100 (40 & 80 GB), RTX PRO 6000, H100, H200, B200, **B300** — billed **per second**, **scaling to zero when idle**
- **Python SDK and CLI** (`pip install modal`); JavaScript and Go SDKs for Sandboxes
- **Sandboxes** — secure, on-demand containers for agents, code interpreters and evals
- **Web endpoints** (FastAPI, WebSockets, WebRTC) with autoscaling and **public URLs**
- **Volumes, Dicts and Queues** for model weights, datasets and shared state
- **Modal Dojo** — open-source library for fine-tuning and RL post-training on Modal GPUs
- **Starter examples:** LLM serving with vLLM and SGLang, speech-to-text, text-to-speech, vision, RAG, agents, RL
- A **Junction starter kit** of ready-to-run examples

Workflow: decorate a function, `modal run` executes it in the cloud in seconds; **`modal deploy` turns it into an autoscaling web endpoint with a public URL ready for the demo.**

## Mentors
Modal engineers and Developer Relations with experience in inference, AI agents, code-execution sandboxes, fine-tuning and RL, and real-time audio/video pipelines. At the Modal booth **throughout the event** and on Junction Discord for debugging.

Main contact: **Filip Makraduli**, Developer Relations Engineer.
Kick-off workshop at the Modal booth, announced on Discord.

## Implications for how we build
- **Seventh stackable award**, and the one that most directly solves a problem we will actually have: **a public URL for the demo.** `modal deploy` gives us that in one command, and several partner challenges require a judge-openable link.
- **$100 per participant, not per team** — a team of four has $400 of GPU time. That's the largest compute allowance of any brief collected.
- **This is the natural partner for the Gemma award.** Gemma needs an open-model story (fine-tuned / self-hosted); Modal provides the GPU and **Modal Dojo** for fine-tuning. Those two awards reinforce each other rather than competing.
- **It's also the natural partner for AfterQuery**, whose published tiebreaker is training a smaller model on environment experience — that's Modal Dojo's exact use case. And **Sandboxes** are built for exactly the "run untrusted LLM-generated code" problem an RL environment has.
- **Conflicts with Hostinger** (must deploy on Hostinger infra) and overlaps with **Aiven Runtime** as a hosting choice — pick one hosting story per project.
- Per-second billing and scale-to-zero mean idle experimentation is cheap; no need to ration carefully within a weekend.
