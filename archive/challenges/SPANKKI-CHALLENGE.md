# S-Pankki (S-Bank) — "Personal Economic Trainer"

Explore how AI can turn personal banking data into a trusted financial coach for everyday life.

## Context
S-Bank is Finland's fourth-largest bank: **3.5 million customers**, and its **S-mobiili** app is used weekly by **one in three Finnish adults**. Banking today stops at statements and transaction lists; they want it conversational, insightful and personalised.

## The ask
Using a **large synthetic transaction dataset modelled on real S-Bank data**, build an AI experience that lets people **chat with their own money** — from simple questions to deeper ones:
- "How much did I spend on taxis last month?"
- "What kind of spender am I?"
- "What is safe for me to spend this week?"
- "How much could I save if I reduced dining out by 20%?"

## The pedagogical angle they value
Everyone's spending falls into **three baskets**:
1. **Mandatory and regular** (e.g. rent)
2. **Mandatory and irregular** (e.g. a broken washing machine)
3. **Everyday spending that slips through your fingers** (e.g. coffees)

**Solutions that help people understand where their money really goes "will go far with us."**

## Design principles stated
- **Think in the spirit of MyData**: let users explore their own data freely, rather than showing fixed charts the bank has picked for them.
- Enhance insights with **open data sources (e.g. Statistics Finland)** for meaningful benchmarks — encouraged, not mandatory.
- Especially interested in conversational AI that:
  - explains financial concepts **in plain language**,
  - simulates **"what if" scenarios**,
  - guides users toward healthier habits, e.g. **safe-to-spend and safe-to-save guidance**.

## Recommended output
**A mobile app, or a web app embeddable in a mobile app — their customers are on mobile.**

## Optional bonus angle (not required)
**Multi-bank view:** under PSD2, customers can let their bank fetch account data from other banks. How could an AI coach use the customer's *full* financial picture? The challenge is fully solvable with the provided data plus open data.

## Why they care
To their knowledge, **no Finnish bank yet lets customers chat with their own financial data** — a first-of-its-kind opportunity in Finnish banking. Ties directly to S-Bank's digital strategy and the S-mobiili vision. S-mobiili is top-rated on both Google Play and the App Store, so a winning idea could reach millions. They see AI as key to improving financial literacy, especially among young adults.

## Resources provided
- Large **synthetic transaction dataset** modelled on the structure of S-Bank data (link given via their challenge page / booth).
- **Mentors:**
  - Carl-Edvard ("Calle") Holmberg — Chief Innovation Officer (**main contact**)
  - Representative from S-Bank IT / AI development
  - Data Scientist (transaction data expert)
  - 1–2 business representatives who own the customer problem

## Implications for how we build
- **Mobile-first is an explicit recommendation**, so a desktop-only dashboard is off-brief. A responsive web app embeddable in mobile satisfies it with less cost than a native build.
- **The three-basket framing is the clearest signal in the brief.** Classifying transactions into mandatory-regular / mandatory-irregular / discretionary leakage, and making that legible, is what they said will score. A generic "chat with your statements" bot ignores the one thing they asked for.
- **MyData framing argues against pre-baked charts** — the interface should let users ask arbitrary questions, not navigate a fixed report.
- Safe-to-spend and what-if simulation require a forecasting model over recurring commitments, not just retrospective aggregation. That's the substantive engineering.
- Synthetic data only — no real customer data, which keeps it clean against Junction's rules and any privacy concern.
- **Note:** the "mandatory and irregular" basket is the hardest and most interesting to detect (rare, lumpy, unpredictable events). Doing that well would differentiate against teams that only split fixed vs. variable.
