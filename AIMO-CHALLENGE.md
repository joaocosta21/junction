# Valio Aimo — "Trusted Trade Agents"

How can a food-service wholesaler let **autonomous purchasing agents** place an order — finding products, comparing offers and getting the right approval in a fraction of the time it takes today — **without exposing real systems, confidential data or the marketplace roadmap**?

## Context
Valio Aimo serves **20,000+ professional kitchens**, 25,000 product names from 700 suppliers. Part of Valio (€2.4B revenue, 60 export markets, carbon-neutral milk by 2035). They're planning a digital B2B marketplace.

As ordering shifts from people clicking a catalog to **AI agents making autonomous purchasing decisions**, the question of what agents can see, decide and be trusted with becomes *"existential for data ownership, trust, and who owns the customer relationship."*

**Scope:** for Junction they are **mocking today's webshop and backend**, not the marketplace. Prototype **the interface and operating model** that would let an external purchasing agent interact with Valio Aimo's systems, **built on open, verifiable standards rather than a single platform's black box**.

## Core — the solution MUST enable
1. **Product, price & availability lookup** — a structured way for an external agent to search and retrieve what's available and at what price.
2. **Requesting price & availability, then placing an order** — a defined interaction from inquiry to commitment, **based on fixed prices rather than a negotiated quote**.
3. **Permission & human-approval management** — what the agent may decide on its own, and what must go to a human for sign-off.

## Optional — open directions (not required to win)
- **Delivery time & sustainability comparison** — delivery reliability plus the certificates/sustainability labels already in the webshop. (Category-level carbon-footprint ranges = stretch goal.)
- **Substitution and exception handling** — what happens when the exact request can't be met. *(Explicitly NOT scored as core — last year's Zero-Fail Logistics challenge covered it.)*
- **Traceability and explainability** — a human-readable record of what the agent did and why.

## Example request
> *"I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."*

A hotel chain's agent sends this. The solution returns products, prices and availability in structured form; the agent places the order within its authority or sends it to a human for approval.

## ⚠️ Their explicit anti-pattern
> **"This is not about replacing today's e-commerce UI with a chatbot."**

It is about defining how a European food-service wholesaler can be **safely and openly readable by autonomous agents — before that interface gets defined by someone else's platform.**

## Problems they'd love tackled
- **Trust protocol** — the minimum data/verification standard for an external agent to trust Valio Aimo's claims on stock, price and origin **without a manual check**.
- **Guardrails model** — which decisions need human sign-off (spend threshold, substitutions outside stated preferences) vs. fully autonomous.
- **Response logic** — handling partial availability and substitution ranking ("good-better-best") within their own assortment.
- **Audit trail** — a usable, human-readable log of purchasing decisions, for both buyer and Valio Aimo.

## Example scenarios
- **Need → recipe → order** — chef plans a menu around a seasonal ingredient; agent suggests recipes, works out what's missing, orders.
- **Last-minute event** — agent identifies recipe requirements, flags what can't be sourced in time, proposes substitutions **through recipe logic rather than a simple SKU swap**.
- **Supplier stock-out** — agent proposes a recipe-compatible substitute before the kitchen notices, and explains the trade-off.
- **Proactive selling agent** — Valio Aimo's own agent suggests a seasonal product to the buyer's agent.
- **Allergen-safe substitution under pressure** — school/hospital kitchen; substitution must still satisfy strict allergen and nutrition rules.
- **Standing order drift detection** — agent learns a recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing.

## Resources provided
- **Synthetic product catalog, simulated suppliers and mock APIs** mimicking the webshop/backend: prices, availability behaviour, delivery lead times, sustainability certificates/labels.
- **No real-time, live or confidential data** — everything is synthetic.
- Mentoring on AI agents, wholesale trading rules, exception handling, data governance.
- **Preferred tech:** AI agents (agentic/tool-use frameworks), open data/interop standards, recommendation logic, optional **verifiable-credential or trust-layer** approaches. Agentic payment standards (**x402, Nevermined**) are relevant context but not required.

**Resource portal:** https://junction26.valioaimo.fi/ — contains downloadable datasets, API documentation and mock-backend access instructions.

> **Credentials (portal password + API key) are in the Junction app challenge page and were provided with the brief. They are deliberately NOT recorded in this public repo** — keep them in a local `.env` that is gitignored. Webshop test accounts to be shared separately.

**Scope note:** they are mocking a structured data/API interface. Whether production eventually becomes a traditional API, an MCP-style agentic interface, or a service agent of its own is **outside scope**.

## Mentors
- **Marketplace/Commercial:** Hanna Forsström, Pirjo Kaartinen
- **Online Sales:** Minni Ruhtinas
- **IT/Tech integrations & Data governance:** Tommi Nurmi-Aro, Ville Takanen, Riku Tapper

## Judging and prizes
**No judging rubric published. No cash prize named in the brief.** Ask at their booth.

## Implications for how we build
- **Best-prepared resources of any brief collected** — mock APIs, synthetic catalog, API key and portal handed over upfront. Fastest possible start; no data wrangling before building. That also means **low friction → higher crowding**.
- **The core is an interface and governance design problem, not an ML problem.** Three of the three core requirements are about structured access and approval authority. The differentiator is the **guardrails model and audit trail**, not the agent's cleverness.
- **Their anti-pattern statement is the strongest signal in the brief:** most teams will build a chatbot that orders milk. They have pre-emptively said that isn't it. A team that ships a *specification* — a typed interface, an explicit authority/permission model, a signed audit record — engages the actual question.
- **"Open, verifiable standards rather than a single platform's black box"** points at MCP, verifiable credentials, and open schema work. x402/Nevermined are named as context.
- **No cash prize named and no rubric** — a material downside if optimising for money.
- **No domain edge for our team.** Foodservice wholesale procurement is as far from biomedical engineering as the Cala/VC challenge. Our differentiator is irrelevant here.
- Tech-award stacking is weak: Aiven (data layer) and Modal (hosting) fit; Nemotron/Cloudinary/web-data awards have no natural role since the data is supplied synthetic and local.
