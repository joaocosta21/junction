# Oxylabs — "Best Agentic Use Case of Oxylabs Web API" (tech track)

Design your project around the Oxylabs Web API: use live search and scraping to verify and inform your AI agent with what is true on the web **right now**.

> **Stackable:** "Utilize the Oxylabs Web API in the AI agent or product you are building **for your main challenge**."

## Framing
AI models are brilliant but can be out of date. The moment an agent needs today's price, this morning's regulation, or a page hidden behind JavaScript and bot checks, it either guesses or fails.

## The ask
Make the project **act on what is true on the web right now**. Live web data lets a solution check facts, track changes, compare offers and ground answers in **current, cited sources** instead of stale training data.

**The solution must use the Oxylabs Web API at runtime to find and read its information: search to find, scrape to read.** Form is open — chat agent, monitoring tool, voice assistant.

**Show that it gets the answer right today and can prove where it came from.**

## Minimum requirements
- **The demo makes at least one live Web API call (`/search` or `/scrape`) at runtime.** Pre-downloaded data alone does not count.
- **The solution shows the source URLs behind what it states or decides.**

## What to submit
The **same GitHub repository and demo as the main challenge**, plus a short note on which Web API endpoints were used and why.

## The technology
A REST API with **two endpoints**:
- **`/search`** — finds the right pages on the live web, ranked results (title, snippet, URL), **localised to any country**
- **`/scrape`** — reads any public page, returns **Markdown, HTML, structured JSON or a screenshot**

Handles **JavaScript rendering, bot challenges, proxies and geo-targeting** — one HTTP call gives clean data ready for code or an LLM.

**Key capabilities:**
- Read any public page as clean Markdown, **sized for an LLM context window**
- **AI Parsing** — extract structured JSON from any page by describing the fields in a prompt
- **50+ dedicated scrapers** with parsed fields: Search, Maps, Shopping, Trends, Amazon, YouTube subtitles and metadata, eBay, Walmart and more
- **Query ChatGPT, Gemini, Perplexity and Google AI Mode and get their answers with cited sources**
- Plug into Claude Code, Cursor or your own agent via **MCP server or agent skills**

## ⚠️ Getting started — read the billing step carefully
1. Create a free account at https://dashboard.oxylabs.io
2. **Buy the Flexible plan ($500). Use code `JUNCTION2026` at checkout for a full first-month discount.**
   **→ Remember to CANCEL the subscription after the challenge to avoid being charged monthly.**
3. **+ Add product instance** → choose **Web API** → create → copy the API key
4. `export OXYLABS_WEB_API_KEY=your_api_key_here`
5. Follow https://developers.oxylabs.io/get-started/quick-start-web-api

**Setup:** any OS with a terminal. Python 3.10+ with `requests`, or Node.js 18+ (built-in fetch). **No SDK to install.** Optional: `uv` for the MCP server, Node.js for agent skills. Bring your own LLM key.

## Inspiration (their suggestions)
Think of users whose decisions go wrong when information is stale: a shopper, a small business owner, a journalist, a compliance officer, a job seeker.
- **One market, different prices** — compare the same product/service across European countries using geo-targeted search and commerce scrapers
- **Fact-checker that reads the source** — verify a claim by reading full pages, not snippets; return a verdict with citations
- **What does AI say about you?** — compare ChatGPT / Gemini / Perplexity / Google AI Mode answers against what the web says
- **Watchers for small teams** — track regulations, tenders, grants or competitor pages and explain what changed and why it matters

## Contact
Justas Kašėta (technical contact) — justas.kaseta@oxylabs.io

## Implications for how we build
- **Eighth stackable award.** Third one in the live-web category alongside **Exa** and **Context.dev** — all three do search + scrape, so realistically we pick one as the primary and could technically call a second.
- **The billing step is a trap worth flagging:** this is the only brief requiring us to *buy* a $500 plan, discounted to zero for the first month by the code. **If we don't cancel, we get charged $500/month.** Set a reminder the moment we sign up.
- **Geo-targeting and the "query ChatGPT/Gemini/Perplexity + compare to the web" endpoint are the capabilities the other two don't have.** That second one is genuinely unusual — it enables "what do the AI assistants say vs. what's actually true", which maps directly onto the **Hostinger** propaganda challenge and onto fact-checking generally.
- **"Shows the source URLs behind what it states" overlaps with requirements we already have** from Exa (clear sources), Cala (sourced data), MariaDB (source-cited answers), AstraZeneca (clearly show sources supporting every claim). Provenance display is a recurring demand across this event — building it once serves several entries.
- **Must be a live runtime call in the demo** — no cached data. That means internet dependency on stage; have a fallback plan if venue wifi is bad.
