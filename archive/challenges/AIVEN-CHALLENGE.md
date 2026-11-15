# Aiven — "Best Use of Aiven" (tech track)

> **Stackable technology award.** Their brief states it outright: *"You can enter this tech challenge alongside your main challenge."*

## The ask
Great ideas need somewhere to run, data they can use, and systems that work together. Aiven is looking for **the most impressive use of Aiven technology: a thoughtful implementation that makes a meaningful difference to the working solution.**

- **Use at least one Aiven service as a meaningful part of the project, and demonstrate what it enables.**
- **Keep your chosen problem, industry and audience** — use Aiven where it helps.
- **Choose the services that fit.** "A well-executed use of one service can be just as impressive as a solution combining several."

## Services available
| Service | Use |
|---|---|
| **Aiven Runtime** | Host the app or agent |
| **Aiven PostgreSQL** | Store data |
| **Aiven Valkey** | Caching |
| **Aiven Kafka** | Process events |
| **Aiven ClickHouse** | Observe the agent |
| **Aiven OpenSearch** | Add search |

## Resources
- **Sign up to Aiven for $50 in free credits**
- Documentation: Aiven docs
- **Runtime templates** for popular open-source frameworks
- **Aiven mentors on site all days** — platform questions and project architecture

## Implications for how we build
- **Fifth stackable award** (with Context.dev-tech, Nemotron, Gemini, Gemma). The brief explicitly blesses stacking, so no ambiguity here.
- **The qualifying bar is low but "meaningful" is the operative word.** Swapping local Postgres for Aiven Postgres technically qualifies and will score nothing. The ones with a real story:
  - **Aiven Runtime** as the deployment target — gives us a public demo URL, which several partner challenges require anyway
  - **ClickHouse for agent observability** — this is the interesting one. An agent that logs its own decisions to ClickHouse and shows them back is a genuine capability, not a hosting swap, and it directly supports challenges that demand explainability (Tieto's evidence trail, AfterQuery's failure-mode analysis, Hostinger's precision metrics)
  - **Kafka** if anything is event-driven (e.g. Context.dev webhook monitors feeding a pipeline)
- **Note the conflict with Hostinger:** that challenge requires deployment on *Hostinger* infrastructure. If we pick Hostinger as the main challenge, Aiven Runtime is out, though managed data services alongside it would still be fine.
- **$50 credits** is modest — fine for a weekend, but don't architect around anything expensive.
- Mentors on site all days, which is broader coverage than most partners.
