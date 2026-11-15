# Exa — Personal Agent for Tedious Tasks

Build an agent that takes tedious tasks in people's lives off their hands.

## Framing
Everyone has day-to-day pain points requiring hours of digging and research: checking whether a rent increase is legal, finding out which benefits a family qualifies for, which vegan restaurant to pick for an anniversary date. **The answers exist, but they're buried across the web.** Exa is a search engine built for AI — it finds, reads and compares information across the web and returns it as structured data, so the agent can do the digging and the task can be handed off completely.

## The ask
Develop a **personal agent that helps people get stuff done**. It should:
- find what matters across the web,
- work out what needs to happen,
- get the task **as close to done as it can**, leaving final approval to the user if needed.
- **Demo on a real case.**

**Areas of interest:** general tasks — planning special occasions, daily living errands, rent, missed benefits, business information, travel disruption, etc.

## How they judge
- How well the project uses **Exa to get information that could not have come from a model's training data alone**.
- How **useful to a specific group of real people**.
- How **clearly it shows its sources**.
- **Originality.**
- **Whether the demo works on live queries — including ones the judges try themselves.**

## Prizes
Winning team: cash + Exa API credits per member. Two runner-up teams also receive prizes. Every team submitting a working project built on Exa receives API credits to keep building after the event. (Specific amounts were left as placeholders in the brief — confirm at their booth.)

## Resources provided
- **$50 in Exa credits per participant** — code **`EXA50JUNCTION`**, redeem at https://dashboard.exa.ai/billing
- Full API access for the event:
  - **Search API** — fast, balanced and deep research modes
  - **Contents API** — full page text, highlights, summaries, crawling a site's subpages
  - Filter by date, domain and category (news, research papers, companies, people, personal websites)
  - Results as **structured JSON**; retrieve **past versions of web pages**
  - **Websets** — verified lists of people, companies, opportunities
  - **Monitors** — recurring searches
  - **Hosted MCP server**, Python and JavaScript SDKs
- Demo gallery with working examples: https://demos.exa.ai
- Exa engineers on site all event, plus a Discord channel for async advice.

## Implications for how we build
- **"Judges try their own live queries" is the key constraint.** The agent must generalise within its chosen domain, not work on one rehearsed example. Pick a narrow enough task that arbitrary live inputs still land inside the competence boundary.
- **Must demonstrably need Exa.** If a frontier model could answer from training data, it scores poorly. Favour tasks turning on *current, local, or jurisdiction-specific* facts — rent regulations, benefit thresholds, opening hours, live disruption data.
- **Source citation is an explicit criterion**, so provenance should be visible in the UI, not buried.
- "A specific group of real people" rewards picking one concrete audience over a general-purpose assistant.
- Date/domain/category filters and historical page versions are differentiators worth using deliberately rather than just calling plain search.
