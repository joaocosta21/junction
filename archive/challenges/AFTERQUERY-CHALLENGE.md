# AfterQuery — "Break the Agent"

Build a reinforcement learning environment that challenges today's best AI agents, demonstrate real failure modes, and show that its rewards reflect real progress.

## Framing
Frontier AI systems solve hard problems but still struggle in novel situations, from everyday use cases to niche technical workflows. The question: **what should AI agents be able to do that they still struggle with today?**

AfterQuery builds environments for training and testing agents. The work: choose a problem worth learning, define an action and observation space, and define a reward function that defines success.

## The ask
- Choose a setting and build an environment an agent can interact with — a game, a scientific simulation, a software task, a real-world process, or something else. **Explain why you chose it and what an agent could learn there.**
- Environment needs a **clear goal, actions the agent can take, and a reward you can check**.
- **Run a frontier agent in it and compare against a stronger reference run your team can demonstrate and reproduce.**
- **Show where the agent falls short and why.** The difficulty must come from the decisions it needs to make, with access to the information and tools needed to succeed.
- Judges will actively hunt for **reward hacking** — shortcuts that earn a high score without completing the task.

**Optional stretch / tiebreaker:** train a smaller model on experience from the environment and show whether it improves.

## Judging rubric (100 p)
| Weight | Criterion | Full points | Zero points |
|---|---|---|---|
| **30** | **The gap** | Frontier agent consistently scores below a stronger reference run the team demonstrates; both reproduce across repeated runs | No measurable gap, or the gap can't be reproduced/checked against a demonstrated reference run |
| **30** | **Meaningful difficulty** | You can explain the agent's main mistakes and connect them to decisions in the task; needed information and tools are available to it | Gap comes from unfairly withheld info, trick wording, impossible timing, or broken tools |
| **25** | **Reward integrity** | Reward measures real success and holds up to exploit attempts; doing nothing or stopping early earns little/no credit; playing well remains the best way to score | An exploit, loophole, or task-avoiding strategy scores better than successful play |
| **15** | **Craft** | Rules and behavior make sense for the setting; judges run the evaluation from your README **with one command** and reproduce your reported results | Environment only works in your demo, or judges can't reproduce the evaluation |

## How judging runs
- **10-minute demo** per team.
- Judges then **rerun the evaluation with the standard harness**: your reference run, **three agent runs**, a **do-nothing baseline**, and a **stop-early baseline**.
- They spend **15 minutes looking for reward exploits**.
- Scores are based on these runs — not on the demo.
- **Tiebreaker:** a team showing a smaller model improving after training on environment experience.

## Prizes
€3,000 / €1,500 / €500 cash for top three. Winning team members can go straight to the final stage of AfterQuery's interview process — a work trial with the environments team. Finalists get AfterQuery gear.

## Starting points (prompts, not requirements)
- Planning several steps ahead
- Exploring an unfamiliar system
- Using tools
- Managing limited resources
- Adapting when new information arrives

A small environment with a well-chosen challenge can be enough. Think about what better play looks like, how you'd measure it, and whether an agent could increase its score without getting better at the task.

## Resources provided
- **Harbor + OpenCode** — open-source agent harness connecting to your environment **over MCP**
- Scoring skeleton
- Frontier model API credits per team for benchmarking across the 48 hours
- Starter kit: harness documentation and the judging rubric
- On-site mentors: **Daksh Raghuwanshi** and **Ved Vedere** (AfterQuery environments team) — environment design reviews and reward testing

## Implications for how we build
- **The rubric is unusually explicit and mechanical — build directly to it.** 60 of 100 points sit on (a) a reproducible measurable gap and (b) explaining the agent's mistakes. Those are deliverables, not side effects.
- **Judges rerun everything themselves.** One-command reproducibility from the README isn't polish, it's 15 points plus the precondition for the 30-point gap score. Our own demo doesn't score.
- **We must build the baselines ourselves**: do-nothing and stop-early must provably earn near-zero, or reward integrity collapses. Red-team our own reward before judges get 15 minutes at it.
- **The reference run is ours to produce and defend** — a scripted/human-played strong policy that beats the frontier agent. Without it, the gap score is zero.
- Environment connects over MCP to a provided harness, so the integration surface is fixed and known early.
