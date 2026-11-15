# City of Espoo — "Rethinking Recruitment"

How can recruitment and matchmaking events organised by the City of Espoo help companies and talent relevantly find and connect with each other, **despite AI-generated job search materials and AI-assisted recruitment processes becoming common**?

## Framing
Finding the right talent is increasingly difficult, especially in fast-changing industries and international recruitment. Talented professionals struggle to communicate what they can actually contribute; companies struggle to articulate what they really need.

Espoo organises recruitment and matchmaking events (online, in person, hybrid). Despite strong event-organising capability, facilitating the *right* matches remains hard. The opportunity: rethink how talent, skills, needs and opportunities are **identified, described, communicated and matched**.

**The core tension:** AI-generated application materials meet AI-assisted screening, so "both sides are increasingly interacting through machine-generated interpretations rather than genuine understanding."

## The ask
Imagine and prototype new ways to help companies and talent find **more relevant, efficient and meaningful connections** at these events. May focus on any stage — **before, during or after** an event — or the whole process: registering, attending, following up.

## Recurring problems they listed
- **Companies are hard to engage.** They don't see a public-sector organisation as a relevant pipeline source, assume the city's jobseeker pool has no suitable candidates, and question quality because the service is free.
- Participating companies **struggle to describe actual talent/service needs clearly and early enough** — often only just before the event day.
- Organisers get **many applications but limited ability to understand applicants' real capabilities and potential**, especially for technology-sector skills.
- Companies get **overwhelmed by large volumes of largely irrelevant candidate approaches** during events.
- Professionals find it hard to describe **competencies, transferable skills and value proposition** in a way that attracts recruiters.
- CVs and messages are increasingly AI-generated while employers analyse them with AI — **risk of matching on synthetic representations rather than genuine capabilities**.
- Online event platform matching functionality is **perceived as cumbersome**.
- The platform **may crash** when people log in simultaneously at event start.
- **International recruitment** adds complexity: authority compliance, language, culture, relocation, onboarding support.

**What they want:** "stronger signal and less noise" throughout registering and attending — helping both sides focus on the most relevant opportunities and conversations.

## Hard constraints
- **No automated profiling or automated decision-making about individuals without human involvement.**
- **Use synthetic data.**
- **Minimise personal data processing** and demonstrate how privacy would be protected in real deployment, **in compliance with the EU AI Act**.
- **Avoid reinforcing bias** or systematically disadvantaging people by nationality, language, educational background, career path or other characteristics unrelated to the opportunity.

## Judging criteria
They welcome solutions improving **matching, discovery and communication** between companies and talent. Teams should consider **privacy, transparency, fairness and inclusion**. Solutions should avoid unnecessary personal data processing and must not rely on automated decision-making about individuals.

*(No numeric weights published — criteria are stated qualitatively.)*

## Prizes
- **Winner: €1,500 cash** + an exclusive opportunity to present to Espoo's business development and innovation leaders **and the national network of cities working on talent attraction and retention**.
- Second: **€1,000**. Third: **€500**.
- Runner-ups: Espoo swag, featured on the city's channels, plus a presentation to the cities of Helsinki and Vantaa.

## Resources provided
- Access to subject-matter experts in companies, talent attraction, international recruitment and event organising
- **Example scenarios and user journeys based on real matchmaking events**
- Feedback on concepts from organiser, company and talent perspectives
- Guidance on responsible AI, privacy and public-sector considerations

**Mentors:** City of Espoo International Working Life Services team and Business Services team — on site and on Discord.
**Main contact:** Melissa Arni-Hardén, Client Relations Manager & International Working Life Services team lead.

### Suggested open data / APIs (not required)
- Job portals: Duunitori, The Hub, Work in Finland open jobs, Job Market Finland
- Event platforms: Tavata, Brella
- **ESCO** — European Skills/Competences, Qualifications and Occupations
- National Forum for Skills Anticipation
- Suomi.fi PTV Open API
- Business Espoo / Espoo recruitment assistance

Teams aren't expected to use any specific technology or dataset — "the focus should remain on solving the underlying problem rather than implementing a predefined technical solution."

## Implications for how we build
- **The AI-vs-AI framing is the heart of the brief, and most teams will miss it.** The obvious build is "better matching algorithm" — but they're telling you the inputs themselves are synthetic and untrustworthy. A solution that elicits *verifiable* signal (demonstrated skill, structured conversation, work sample) rather than scoring documents engages the actual problem.
- **"No automated decision-making about individuals" rules out the default design.** Ranking candidates for recruiters is exactly what's prohibited without human involvement. Design for human decision support, not a scoring engine.
- **EU AI Act compliance is an explicit requirement** — recruitment is a designated high-risk use case under the Act, which is precisely why they flag it. Being able to say which obligations apply and how the design respects them is a differentiator here, not boilerplate.
- **ESCO is the lever for the "can't describe transferable skills" problem** — a standard competency taxonomy lets you map a messy self-description onto comparable structured skills without inventing a scoring model.
- The "companies provide needs too late" and "platform crashes at login" problems are real but unglamorous; solving the *engagement* problem (why companies don't show up) is a less crowded angle than the matching problem.
- Non-cash upside is notable: presentation to Espoo leadership plus the national city network, and to Helsinki and Vantaa.
