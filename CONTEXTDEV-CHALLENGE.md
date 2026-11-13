# Context.dev — "The Web Is Your Real-Time Database"

Build a product that reacts to the live web.

## Framing
Most software runs on stale data and can't see the internet as it is right now. **Context.dev turns any website, company, person or news story into clean, structured data with one API call.**

Every industry runs on information sitting on the open web, spread across millions of pages in different formats, going out of date overnight. Analysts still copy-paste prices, check supplier sites by hand and read the news to catch risks. Fact-checkers can't keep up. Software still greets every new customer with the same generic screen.

## The ask
**Build a product that turns live web data into decisions, actions or experiences that weren't possible before.**

## Themes they'd love to see
- **Scrape the Economy** — live indicators built from product prices or job listings
- **The Web, Watched** — agents triggered by changes to websites or news
- **Brand in a Box** — apps that brand themselves from a sign-up email
- **Truth at Internet Speed** — fact-checking with sources

**Wild / creative / ambitious ideas outside these themes are "extremely welcome."**

## Examples for inspiration
- **GPU Rental Prices** — compare GPU rental prices across cloud providers
- **Yapper Leaderboard** — rank founders and startups by their activity on X
- **cve.now** — monitor newly disclosed security vulnerabilities
- **Ferndesk** — personalise onboarding with company data and brand assets

## Resources provided
- **50,000 free API credits per team, non-expiring.** Sign up at https://context.dev/signup, redeem code **`JUNCTION26`** at https://context.dev/dashboard/redeem-credits
- Quickstart: https://docs.context.dev/quickstart · Full docs: https://docs.context.dev
- **Up to 50 concurrent requests per team**
- API surface:
  - **Web** — search, scrape (markdown, HTML, screenshots, images), crawl, URL mapping, structured extraction, research answers
  - **Entities** — brand data (logos, colours, fonts, style guides), company and people search and enrichment, NAICS/SIC classification
  - **Signals** — news search, **monitors with webhooks for change detection**
  - **Scale** — batch API for thousands of URLs, file parsing for PDFs and documents

## Mentors
Engineers from Context.dev with expertise in web data extraction, LLM agents, search and large-scale data pipelines: **Beer van der Drift (CTO)**, **Yahia Bakour (Founder & CEO)**, **Thomas Oomens (Engineer)**.

**On site:** Friday until 23:00 · Saturday 09:00 → Sunday 02:00 · Sunday from 07:00 to the end. (The broadest mentor coverage of any brief collected.)

Main contact: Beer van der Drift, CTO — beer@context.dev

They'd love to feature standout projects on their social channels.

## Implications for how we build
- **No published judging rubric.** Ask at the booth. Absent one, the brief's own phrase is the bar: something that "wasn't possible before" — novelty of the *application*, not the integration.
- **Heavy overlap with the Exa challenge** (live web data → agent). If both are on the table, the difference is Context.dev's **monitors + webhooks** (push-based change detection) and **brand/entity enrichment**, versus Exa's semantic search depth. A change-triggered agent is natural here and awkward on Exa.
- **The webhook monitors are the most distinctive primitive offered** — a product that *reacts* to a change, rather than answering a question on demand, uses the thing their competitors' APIs don't have, and matches the challenge title directly.
- **50 concurrent requests** is a real ceiling for anything doing broad crawls — design around it rather than discovering it mid-demo.
- Their four themes are published, so expect clustering there; the brief explicitly invites off-theme ideas, which is where differentiation sits.
