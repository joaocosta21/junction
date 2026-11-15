# Pitch script (spoken), three minutes — Sun 15 Nov

Your slide timings, kept as they were. The four corrections are in; three of the four additions fit by replacing weaker lines word for word (the 302 / 303 litres line does not fit and is left out). About the same number of spoken words as your version.

### Slide 1 — Introduction | 0:00–0:10

What happens when an AI is asked to buy a thousand litres of lactose-free milk?

**The real question is: can we trust its decision?**

That's why we built **Trusted Trade Agents**.

### Slide 2 — The Problem | 0:10–0:25

Meet Hanna, purchasing manager at a hotel.

Her agent must find the right products, confirm stock and delivery, and respect her limits.

**Finding products is easy. Trusting an agent to buy them isn't.**

### Slide 3 — Our Solution | 0:25–0:45

Trusted Trade Agents is an **open gateway between purchasing agents and Valio Aimo**.

It checks prices, quantities, delivery dates, allergens, and origin against Valio Aimo's data. Then it ranks options, applies each buyer's rules, and logs every decision.

**A model can interpret the request. Rules make every decision.**

### Slide 4 — Demo Customers | 0:45–0:50

Four illustrative buyers, each with different rules.

**Let's follow Hanna's hotel.**

### Slide 5 — Working End-to-End Demo | 0:50–1:53

*Start the live demonstration.*

Hanna requests **1,000 litres of lactose-free milk by Monday**.

The gateway checks 26 matching products, but only **435 litres are confirmed**.

It invents nothing. The rest is offered two ways, clearly labelled: **cheaper but unconfirmed, or fully confirmed with a barista milk as a named substitute**.

The confirmed offer costs **€1,083.39**, above the hotel's €750 limit.

**So the agent requests human approval.**

*Show Hanna confirming the order.*

Hanna approves, and the order is recorded.

*Open the audit trail and supplier view.*

Every decision is documented, with separate views for the buyer and Valio Aimo.

**Request, lookup, offer, approval, order: end to end.**

### Slide 6 — Precision | 1:53–2:03

**It orders what was asked, or it asks.**

Ambiguous quantities trigger a question, and a price in the sentence is applied: "under €400" sends a €496 order to a person.

### Slide 7 — Guardrails and Exceptions | 2:03–2:20

Every decision is **AUTO, APPROVAL, or BLOCK**.

It handles partial stock, unconfirmed availability, substitutes and delivery dates.

A milk-allergy ward asking for lactose-free milk gets twenty-six refusals: **lactose-free is still milk.**

**And through the agent interface, an agent can never approve its own order.**

### Slide 8 — Open Integration | 2:20–2:32

Every offer identifies what is **confirmed and what remains unknown**.

Any agent that speaks REST or MCP can connect.

**No proprietary integration is required.**

### Slide 9 — Impact | 2:32–2:42

For buyers: **less manual work and more reliable purchasing**.

For Valio Aimo: visibility into what agents buy, and what it could not sell: **565 litres, about fourteen hundred euros, because its own data did not confirm the stock.**

### Slide 10 — Implementation and Next Steps | 2:42–2:52

Our prototype already works with Valio Aimo's recorded test data.

Next, we need **real customer authentication, purchasing policies, and supplier order integration** to move toward production.

### Slide 11 — Closing | 2:52–3:00

**The future of AI purchasing isn't an agent that buys everything.**

**It's an agent that knows when to act — and when to ask.**

Thank you.
