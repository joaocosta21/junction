# Valio Aimo — "Trusted Trade Agents"

How can a food-service wholesaler let **autonomous purchasing agents** place an order — finding products, comparing offers and getting the right approval in a fraction of the time it takes today — **without exposing real systems, confidential data or the marketplace roadmap**?

Sections marked **verbatim** are copied from the Junction platform challenge page. Everything else is our summary.

## Context (our summary)
Valio Aimo serves **20,000+ professional kitchens**, 25,000 product names from 700 suppliers. Part of Valio (€2.4B revenue, 60 export markets, carbon-neutral milk by 2035). They're planning a digital B2B marketplace.

As ordering shifts from people clicking a catalog to **AI agents making autonomous purchasing decisions**, the question of what agents can see, decide and be trusted with becomes *"existential for data ownership, trust, and who owns the customer relationship."*

**Scope:** for Junction they are **mocking today's webshop and backend**, not the marketplace. Prototype **the interface and operating model** that would let an external purchasing agent interact with Valio Aimo's systems, **built on open, verifiable standards rather than a single platform's black box**.

## Core — the solution must enable (verbatim)
- **Product, price & availability lookup:** a structured way for an external agent to search for and retrieve what's available and at what price.
- **Requesting price & availability, then placing an order:** a defined interaction for moving from inquiry to commitment, based on fixed prices rather than a negotiated quote.
- **Permission & human-approval management:** what the agent may decide on its own, and what must go to a human for sign-off.

## Optional – open directions (not required to win) (verbatim)
- **Delivery time & sustainability comparison:** not just price, but delivery reliability and the certificates/sustainability labels already shown in the webshop. (Category-level carbon-footprint ranges are a stretch goal.)
- **Substitution and other exception handling:** what happens when the exact request can't be met. (Last year's Zero-Fail Logistics challenge covered failed deliveries in depth, so this isn't scored as core.)
- **Traceability and explainability:** a human-readable record of what the agent did and why.

## Example request (verbatim)
> "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on price and availability."

A hotel chain's agent sends this request. Your solution returns products, prices and availability in structured form; the agent places the order within its authority or sends it to a human for approval.

## Impact (verbatim)
This is not about replacing today's e-commerce UI with a chatbot. It is about defining how a European food-service wholesaler can be safely and openly readable by autonomous agents – before that interface gets defined by someone else's platform.

## Insight (verbatim)

### Problems we'd love to see tackled
- **Trust protocol:** the minimum data/verification standard for an external agent to trust Valio Aimo's claims on stock, price and origin without a manual check.
- **Guardrails model:** which decisions require human sign-off (spend threshold, substitutions outside stated preferences) vs. fully autonomous.
- **Response logic:** how an agent handles partial availability and substitution ranking ("good-better-best") within Valio Aimo's own assortment.
- **Audit trail:** a usable, human-readable log of an agent's purchasing decisions, for both buyer and Valio Aimo.

### Example scenarios to spark ideas
- **Need → recipe → order:** a chef plans next week's menu around a seasonal ingredient. The agent suggests recipes, works out what's missing from stock, and places the order.
- **Last-minute event:** an unexpected booking for tomorrow. The agent identifies what the recipes require, flags what can't be sourced in time, and proposes substitutions through recipe logic rather than a simple SKU swap.
- **Supplier stock-out:** a key product runs out mid-week. The agent proposes a recipe-compatible substitute before the kitchen notices the gap, and explains the trade-off.
- **Proactive selling agent:** Valio Aimo's own agent spots a new or seasonal product and proactively suggests it to the buyer's agent.
- **Allergen-safe substitution under pressure:** in a school or hospital kitchen, a substitution must still satisfy strict allergen and nutrition rules.
- **Standing order drift detection:** the agent learns a kitchen's recurring weekly order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it.

**Scope note:** we are mocking a structured data/API interface. Whether Valio Aimo's production interface eventually becomes a traditional API, an MCP-style agentic interface or a full service agent of its own is outside the scope of this challenge.

## Resources — what we'll bring (verbatim)
- Synthetic product catalog, simulated suppliers and mock APIs mimicking Valio Aimo's webshop/backend systems, built on realistic data: prices, availability behaviour, delivery lead times, and sustainability certificates/labels (category-level carbon-footprint ranges as a stretch goal).
- No real-time, live or confidential data or systems – everything you build against is synthetic.
- Mentoring on AI agents, wholesale trading rules, exception handling and data governance, plus coaching on which background data and rules are essential.
- Preferred tech: AI agents (agentic/tool-use frameworks), open data/interop standards, recommendation logic, optional verifiable-credential or trust-layer approaches. Agentic payment standards (e.g. x402, Nevermined) are relevant context but not required.

*(Our notes, not verbatim.)*

**Resource portal:** https://junction26.valioaimo.fi/ — contains downloadable datasets, API documentation and mock-backend access instructions.

> **Credentials (portal password + API key) are in the Junction app challenge page and were provided with the brief. They are deliberately NOT recorded in this public repo** — keep them in a local `.env` that is gitignored. Webshop test accounts to be shared separately.

## Judging criteria (verbatim)

| Weight | Criterion | Their wording |
|---|---|---|
| **30%** | Working end-to-end demo | The solution runs through a full request → lookup → order/approval flow in the mocked environment, not just isolated pieces. |
| **20%** | Solving the problem and user need | how Precisely the agent matches what the buyer actually asked for, with the least manual correction needed. |
| **20%** | Autonomy and controls | Quality of the guardrails design. What the agent can decide alone, what needs human sign-off, and how decisions are logged and auditable. |
| **15%** | Robustness to exception situations | Handling of partial availability, substitutions and delivery constraints beyond the happy path. |
| **15%** | Openness and credible path toward production | Open, documented standards rather than a proprietary format, clear visibility of assumptions, well-justified technical choices, and a credible view of next development steps |

## Mentors
- **Marketplace/Commercial:** Hanna Forsström, Pirjo Kaartinen
- **Online Sales:** Minni Ruhtinas
- **IT/Tech integrations & Data governance:** Tommi Nurmi-Aro, Ville Takanen, Riku Tapper

## How we read it
- **The deliverable is the three core capabilities working as one flow**, not an order endpoint: structured lookup, a defined inquiry → commitment interaction at fixed prices, and a permission model with human sign-off. The mock has no order endpoint; the order step is ours to define.
- **"Availability behaviour" and "delivery lead times" are part of what they bring.** Unknown stock, passed order cut-offs and products that cannot be delivered are the realistic conditions the agent must handle and explain, which is exactly what the 15% robustness criterion names: "partial availability, substitutions and delivery constraints beyond the happy path".
- **Substitution is optional in the brief but scored in the rubric** (15% robustness). We build for the rubric.
- **Not a chatbot.** The thing being judged is a typed interface and an operating model that any agent can use; a working agent demonstrates it.
- **"Open, documented standards rather than a proprietary format"** (15%) points at OpenAPI, MCP and public code lists such as GS1, with our assumptions written down.
- **The four "problems we'd love to see tackled" map onto the rubric:** trust protocol and response logic → problem fit and robustness; guardrails model and audit trail → autonomy and controls.
