# MariaDB — "Wikipedia Through Time"

Build the tools Wikipedia is missing, powered by MariaDB's vector search (RAG) and system-versioned tables.

## Framing
MariaDB is the open-source database storing and serving Wikipedia. Yet much of Wikipedia's potential is untapped: **search is still largely keyword-based**, and **the full edit history behind every article — a record of how human knowledge evolves — is rarely explored.** AI and modern database features now make it possible to ask Wikipedia questions in plain language and to travel back in time through its content.

## The ask
**Build a tool for Wikipedia that doesn't exist yet, or exists but is badly underused, with MariaDB at the core of the stack.** Pick a track matching your ambition.

### RAG track *(recommended for most teams)*
Use **MariaDB's native vector search** to build retrieval-augmented generation that lets people ask questions of Wikipedia and get **grounded, source-cited answers** — e.g. a research assistant for the history of Finland.

### SVT track *(advanced teams)*
Use **MariaDB system-versioned tables** to query how knowledge changes over time — e.g. showing what an article said on any given date, surfacing **edit wars**, or tracing how the story of a historical event has been rewritten.

### Both *(very advanced)*
Combine them — e.g. a RAG assistant answering *"what did Wikipedia say about this in 2015, and what has changed since?"*

## Judging criteria
Looking for the **most useful and original tool for Wikipedia built on MariaDB**. Judges focus on:
- **Effective and creative use of MariaDB RAG and/or system-versioned tables**
- **Technical execution and scalability across the provided datasets**
- **Real-world usefulness for Wikipedia readers or editors**
- **Design and demo quality**

**Teams taking the SVT track, or combining both, will be recognised for the added technical ambition.**

## Insights and focus areas
- **LLMs have a world view from their training data — which may differ from Wikipedia's NPOV (Neutral Point of View).**
- **Two user groups:** Wikipedia **readers**, or active **Wikipedians who edit articles**. Choose either or both.
- They'd love tools making Wikipedia's knowledge easier to **digest, verify and trust**: source-grounded Q&A, fact-checking assistants, **detecting gaps and weak spots in article coverage**. **Comparing the same article between languages can reveal surprising insights.**
- On the SVT side, especially excited by **"time-travel" tools**: point-in-time views, change visualisations, **edit wars or bias detection**, edit-history analytics.

## Data and resources
- **MariaDB Server** (open source) with native vector search — RAG track
- **MariaDB system-versioned tables** — SVT track
- **Three datasets (small, medium, large)** from **Finnish Wikipedia articles on the history of Finland** — prototype fast, then prove the tool scales
- Starter docs and examples:
  - https://github.com/MariaDB/mariadb-wikipedia-datasets
  - https://github.com/MariaDB/mariadb-vector-wikipedia-rag
  - https://github.com/MariaDB/mariadb-system-versioning-wikipedia
- Free to pair MariaDB with **any LLM, embedding model or frontend framework**

**Source articles are in Finnish**, so a **multilingual embedding model is recommended** for the RAG track — but **no Finnish language skills are needed to compete**.

## Mentors
MariaDB mentors with hands-on expertise in MariaDB Vector and RAG pipelines, system-versioned (temporal) tables, and large-scale Wikipedia data. Available throughout for data modelling, query design and scaling.
- **Kaj Arnö** — MariaDB Foundation, Executive Chairman
- **Robert Silén** — MariaDB Foundation, AI Lead

MariaDB was born in Finland, created by Michael "Monty" Widenius, original author of MySQL.

## Prizes
- **1st** — €1,000 cash + €1,000 UpCloud credits + **MariaDB certification for every team member** (5 vouchers at learn.mariadb.com, ~750 USD value)
- **2nd** — €500 cash
- **3rd** — €250 cash
- All winning teams credited in a blog post on mariadb.org

## Implications for how we build
- **The SVT track is explicitly under-subscribed and explicitly rewarded.** They recommend RAG "for most teams" and say SVT or both earns recognition for added ambition. Most teams will build a Wikipedia RAG chatbot — which is 2023's canonical demo and hard to make original. **Edit-history analysis is the differentiated play.**
- **"Edit wars" and bias detection over time is the most interesting thing in the brief** — it's a real unsolved need for Wikipedians, it's genuinely hard, and it uses the database feature nobody else will touch.
- **The NPOV-vs-LLM-worldview note is a hint**, not trivia: a tool that surfaces where an LLM's answer diverges from what Wikipedia actually says would engage it directly.
- **Scalability across small/medium/large datasets is a stated criterion** — demo on all three sizes, don't just run the small one.
- Finnish source text means a multilingual embedding model is a setup decision to get right early; cross-language article comparison is suggested as a source of insight.
- Starter repos exist for all three paths, so integration cost is low and well-documented — the lowest-friction technical setup of the briefs collected, after Exa and Context.dev.
