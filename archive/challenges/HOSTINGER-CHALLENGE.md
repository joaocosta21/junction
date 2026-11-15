# Hostinger — "Decode the Noise" (our main challenge)

Build an AI-powered tool that detects propaganda, bots and bad actors online — and deploy it live on Hostinger's infrastructure.

## The ask
Analyse text, social content or web-traffic patterns to detect coordinated propaganda, bot-driven amplification or bad-actor behaviour. Form is open: an API, a dashboard, a classifier with an explainable verdict, or a monitoring service for site owners.

## Hard requirement
**Deployed and running live on Hostinger infrastructure by the end of the hackathon, with a public URL the judges can open.**

## What they explicitly value
- **Strength and honesty of the detection logic over front-end polish.**
- **How we handle false positives.**
- **Transparent and measurable: show precision and false-positive rate**, not just a happy-path demo.

## Directions (pick one or combine)
1. **Spot the swarm** — coordinated inauthentic behaviour (bot networks, astroturfing, brigading) from posting timing, account similarity, text reuse and amplification patterns — not from any single post.
2. **Name the technique** — classify manipulation techniques in text (loaded language, fear appeals, whataboutism, fabricated authority) and explain the verdict in plain language, so a reader learns *why* it's propaganda.
3. **Clean the traffic** — separate malicious bots, scrapers and credential-stuffing from real visitors in web-server logs; give site owners an actionable view.
4. **Trust the source** — score page/account provenance (domain age, cloned content, AI-generated text, link networks).

## Resources provided
- **Hostinger VPS (KVM 2)** per team, free 1 month — 2 vCPU, 8 GB RAM, 100 GB NVMe, 8 TB bandwidth, full root, Docker, free domain. One-click templates for Ollama, n8n, Node.js, Python.
- **Hostinger AI Router credits** — one API key, shared credit balance, 150+ models (Anthropic, OpenAI, DeepSeek, Mistral, xAI). OpenAI- and Anthropic-SDK compatible.
- **Hostinger AI Builder**, 1-month plan — front end / dashboard / landing page.
- **Hostinger Connector, API and CLI** — connect Claude Code / Cursor / VS Code or any MCP client to deploy and manage the server from the editor.
  - Docs: https://docs.hostinger.com/hostinger-connector
  - API reference: https://developers.hostinger.com
  - Open-source MCP server: https://github.com/hostinger/api-mcp-server
- On-site mentors at the Hostinger booth: Minijus Savickas (VPS Product), Emilis Strimaitis (Innovations, AI agents). Dedicated help channel all weekend.

Any language, framework or model (open-source or hosted) is allowed, as long as the final product runs on Hostinger.

## Extra
Talk: "Vibe Coding Solved Building. Now Comes the Hard Part" — Saturday 13:00, on shipping, securing and running code in the real world. Promising teams get a path to continue with Hostinger's engineering team after the event.

## Implications for how we build
- Deployment to the Hostinger VPS is not a last-minute step; get a hello-world live early so the public URL exists from day one.
- We need a **labelled evaluation set** and reported precision / false-positive numbers. Budget time for this — it's an explicit scoring criterion, and most teams will skip it.
- Explainability is scored. Every verdict should carry a plain-language reason.
