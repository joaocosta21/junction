# Pitch script (spoken) — Sun 15 Nov, 04:10

Runs 3:41 at a calm pace; the pitch slot is five minutes. Every figure was measured on the recorded Valio Aimo test data at the demo clock.

### Slide 1 — Introduction | 0:00–0:10

What happens when an AI is asked to buy a thousand litres of lactose-free milk?

**The real question is: can we trust its decision?**

That's why we built **Trusted Trade Agents**.

### Slide 2 — The Problem | 0:10–0:25

Meet Hanna, purchasing manager at a hotel.

Her AI agent must find the right products, confirm availability and delivery, and respect her purchasing limits.

**Finding products is easy. Trusting an agent to buy them isn't.**

### Slide 3 — Our Solution | 0:25–0:47

Trusted Trade Agents is an **open gateway between purchasing agents and Valio Aimo**.

It checks what Valio Aimo's data confirms about prices, quantities, delivery dates, allergens, and origin. Then it ranks options, applies each buyer's rules, and logs every decision.

**A model can interpret the request. Rules check it and make every decision.**

### Slide 4 — Demo Customers | 0:47–0:52

We created four illustrative buyer profiles, each with different purchasing rules.

**Let's follow Hanna's hotel.**

### Slide 5 — Working End-to-End Demo | 0:52–2:00

*Start the live demonstration.*

Hanna requests **1,000 litres of lactose-free milk by Monday**.

The gateway checks 26 matching products, but only **435 litres are confirmed**.

It does not invent availability. 435 litres are confirmed; for the rest it offers two ways, clearly labelled: **cheaper with unconfirmed stock, or fully confirmed with a barista milk as a named substitute**.

The confirmed offer costs **€1,083.39**, exceeding the hotel's €750 purchasing limit and falling below its 90% minimum coverage.

**So the agent requests human approval.**

*Show Hanna confirming the order.*

Hanna approves it, and the order is recorded in our demo system.

*Open the audit trail and supplier view.*

Every decision is documented, with separate views for the buyer and Valio Aimo.

**From request to lookup, offer, approval and order — the entire workflow works end-to-end.**

### Slide 6 — Precision | 2:00–2:17

Our system **matches what the buyer actually asked for**.

Ambiguous quantities trigger clarification, requested brands are preserved, and missing information is never silently guessed.

**Even a price in the sentence is applied: "under €400" sends a €496 order to a person.**

### Slide 7 — Guardrails and Exceptions | 2:17–2:49

Every decision has three possible outcomes: **AUTO, APPROVAL, or BLOCK**.

The system handles partial stock, uncertain availability, unsafe substitutions, and delivery constraints.

A milk-allergy ward asks for lactose-free milk: twenty-six checked, twenty-six refused. **Lactose-free is still milk.**

With ordering alone switched on, the agent orders 302 litres; at 303 it waits for Hanna.

**A substitute introducing an excluded allergen is blocked, and through the agent interface, an agent can never approve its own order.**

### Slide 8 — Open Integration | 2:49–3:01

Every offer identifies what is **confirmed and what remains unknown**.

Through open REST and MCP interfaces, any agent that speaks REST or MCP can connect.

**No proprietary integration is required.**

### Slide 9 — Impact | 3:01–3:21

For buyers, this means **less manual work and more reliable purchasing decisions**.

For Valio Aimo, it provides visibility into purchasing activity, recommendations, and demand that could not be fulfilled.

**Valio Aimo sees the 565 litres too: about fourteen hundred euros it could not sell, because its own data did not confirm the stock.**

### Slide 10 — Implementation and Next Steps | 3:21–3:33

Our prototype already works with Valio Aimo's recorded test data.

Next, we need **real customer authentication, purchasing policies, supplier order integration, and Valio Aimo signing its own offers** to move toward production.

### Slide 11 — Closing | 3:33–3:41

**The future of AI purchasing isn't an agent that buys everything.**

**It's an agent that knows when to act — and when to ask.**

Thank you.
