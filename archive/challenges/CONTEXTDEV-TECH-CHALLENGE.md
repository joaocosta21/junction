# Context.dev — "Best Use of Context.dev: Fully Structured Web" (tech track)

> Separate from their main challenge ("The Web Is Your Real-Time Database", see [CONTEXTDEV-CHALLENGE.md](CONTEXTDEV-CHALLENGE.md)). This one is a **stackable technology award** — plug the API into whatever you're building.

## The ask
Whatever you're building, use the Context.dev API to **extract exactly what you need from the web and nothing more**.

Live web data lets a project check facts against current sources, react when a page or news story changes, brand itself from a customer's email, or enrich a company or person in one call instead of relying on stale data.

**To count, the project must call at least one Context.dev endpoint in its core flow, not just as a side feature.**

## Minimum requirements
- Use **at least one Context.dev API endpoint** in the submitted project.
- **The data from Context.dev must visibly drive something in the demo.**

## What to submit
A **GitHub repository** and a **demo**, plus a **short note on which endpoints were used and why**.

## The technology
Send it a URL, domain, company or search query; get back clean structured data — markdown, JSON, screenshots, logos, colours, company facts, news. No scrapers, proxies or parsers to maintain.

**Key capabilities:**
- **Search and scrape** — pages to markdown, HTML, screenshots or images; crawl and map a whole site
- **Structured extraction** — JSON with your own schema, or researched answers to a question
- **Brand data** — logos, colours, fonts and a style guide from a domain or email
- **Search and enrichment** — companies, people, news
- **Monitors and webhooks** — react when a page or topic changes
- **Batch processing** — thousands of URLs
- **File parsing** — PDFs and documents
- **Social media** — scrape feeds such as TikTok and Instagram

## Getting started
1. Create an account at https://context.dev/signup (coding agents: https://context.dev/auth.md)
2. **Redeem code `JUNCTION26`** → **50,000 API credits per team, no expiry**
3. Copy a secret key from the API keys page
4. Install SDK: `npm install context.dev` or `pip install context.dev`
5. Scrape a first page using the Quickstart

**No credit card needed. No rate limit — max 50 concurrent requests per organisation.** No special hardware; the live web is the dataset.

- MCP server: `https://mcp.context.dev/mcp`
- SDKs: TypeScript/Node, Python, Ruby, Go — or any language over HTTP, or just curl
- Requirements: Node.js 20+ or Python 3.9+ (Ruby 3.2+, Go 1.22+ also supported); internet access
- Optional: `context-dev` CLI, the agent skill, the MCP server, or the Playground for codeless requests
- **There is no starter repository** — start with the Quickstart

## Tips and common pitfalls (from their brief)
- **Check each output's `success` flag.** A 200 response can still contain a failed output.
- **Set `maxAgeMs: 0` when fresh data is needed.** Results are cached up to 3 days by default, and **cached results cost the same credits as fresh ones** — store results in your own app to avoid paying for repeat calls.
- **Crawls, batches and monitors are asynchronous.** Poll the job or receive a webhook; use something like Cloudflare Tunnel for local webhooks.
- **Some sites block automated access.** Teams are responsible for respecting the terms of the sites they use.

## Documentation
- Docs: https://docs.context.dev · API reference: Web scraping API · Credits and pricing
- Guides: Quickstart, Agent quickstart, Recipes
- Live examples: GPU rental price tracker, Yapper leaderboard
- SDKs: https://github.com/context-dot-dev
- Status: https://status.context.dev

## Mentors and support
- **Beer van der Drift** — CTO, **challenge lead and lead judge**, beer@context.dev
- **Yahia Bakour** — Founder & CEO
- **Thomas Oomens** — Engineer

**On site:** Friday until 23:00 · Saturday 09:00 → Sunday 02:00 · Sunday 07:00 → end.

## Implications for how we build
- **Fourth stackable challenge** (with Gemini, Gemma, Nemotron) — and the easiest bar of any of them: one endpoint in the core flow, visibly driving the demo. If our build touches the web at all, this is close to a free second entry.
- **Note the discrepancy with their main brief:** that one said "up to 50 concurrent requests" as a limit; this one says **no rate limit**, only 50 concurrency. This is the more detailed brief, so treat it as authoritative — concurrency, not throughput, is the constraint.
- **Their caching pitfall is a credit trap:** cached results cost full price, so cache in our own app. 50,000 credits is generous but not unlimited.
- **The `success`-flag warning is the kind of thing that breaks a live demo** — handle per-output failure explicitly rather than trusting HTTP 200.
- **Webhooks need a public URL.** If we use monitors, set up Cloudflare Tunnel early; this is a classic Sunday-morning blocker.
- **The CTO is both challenge lead and lead judge**, and is on site essentially the entire event. Talking to him directly is unusually high-value here.
