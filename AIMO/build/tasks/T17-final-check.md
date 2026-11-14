# T17 — Final check against the problem statement, and the morning report

**Scores on:** all five criteria. This is the check that we built what Valio asked for, not what we assumed.
**Needs:** everything else `done` or `blocked`.

## Step 1 — an independent check (a fresh agent, read-only on `src/`)
Give it `AIMO/CHALLENGE.md`, `AIMO/SPEC.md` and the running app in replay. It must not be told what we think works. It reports:
- for each of the three core requirements, each optional direction, each of the four "problems they'd love tackled" and each judging criterion: the piece that answers it, how it verified that piece by running it, and what is missing;
- the scenarios of SPEC §13 run by HTTP, with the outputs;
- anything in the app that contradicts the brief (for example, anything that behaves like a chatbot, a proprietary format where an open one exists, an undeclared assumption);
- the ten weakest points, ranked by the score they put at risk.

## Step 2 — the orchestrator fixes what is cheap and high in that ranking, through fix tasks, and re-runs the suite.

## Step 3 — `AIMO/build/MORNING.md`
- **What works**, with the command that proves it.
- **How to run it:** replay, live, tests — three commands each.
- **What is blocked and what unblocks it** (a key, a token, a decision).
- **What a human must decide or check**, most important first.
- **Questions raised overnight** (they are already merged into `AIMO/BOOTH-QUESTIONS.md`): the three to ask first.
- **Per person:** what to review on Saturday morning, by package.
- **Numbers:** tests passed, coverage, live API calls used, commits.
- **The deployed URL**, or the commands to deploy.

## Step 4 — update `AIMO/PLAN.md` §5 and §8 to match what exists, commit, and end the loop.
