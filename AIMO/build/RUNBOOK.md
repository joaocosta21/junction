# Overnight build — how to run it

Part 1 is for the person starting the run. Part 2 is the procedure the orchestrating Claude session follows; it is written down so that the run survives a context reset, a crash or a hand-over.

---

## Part 1 — for the human

### Before you sleep (about ten minutes)

Do the steps in a **second terminal tab**, opened in the repository folder. Never paste a key into the chat.

**1. Gemini key**
1. Open https://aistudio.google.com/apikey and create an API key.
2. In the second tab run this, then paste the key at the hidden prompt and press Enter:
   `read -s "k?Gemini key: " && printf '\nGEMINI_API_KEY=%s\n' "$k" >> .env && unset k`
3. Check that the name is there (this prints names only): `grep -o '^[A-Z_]*' .env`

Without it: the buyer agent is built and tested on recorded model outputs, and the live check waits for the key.

**2. Modal (recommended, so the demo is deployed and checked overnight)**
1. Sign up at https://modal.com. Redeem the hackathon credits with the link and code in `MODAL-CHALLENGE.md` (this can wait until tomorrow).
2. In the second tab: `python3 -m venv .venv && .venv/bin/pip install modal && .venv/bin/modal setup` — a browser window opens; approve it. If `modal setup` fails, Modal's guide says to try `.venv/bin/python -m modal setup`.

Deploying stores in your Modal account, as a secret, only the values the app uses: the Valio API key, the Valio base URL, the Gemini key, and the Aiven and Context.dev values if those parts were built. Nothing else from `.env` is sent. Without this step: everything for deployment is prepared and the deploy itself is one command in the morning.

**3. Permission mode**
1. Look at the bottom of this session's terminal. It must say `⏵⏵ auto mode on`. If it does not, press Shift+Tab until it does.
2. In the second tab: `mkdir -p .claude && cp AIMO/build/claude-settings.example.json .claude/settings.local.json`

What the file does in automatic mode: it **blocks `git push`, `git reset --hard` and `git clean` in every mode**, and pre-approves the git commands the run needs. Its Python and pip lines are ignored while automatic mode is on (Claude Code drops broad interpreter rules there); those commands are judged one by one by the mode's own checker. If that checker refuses three actions in a row, or twenty in total, the run pauses and waits for you. The procedure in part 2 is written to avoid that.

**4. Usage limit**
In this session type `/config` and look for an option to continue automatically when the usage limit resets; turn it on if your version has it. With the 20x plan this is unlikely to matter.

**5. Keep the Mac awake**
Power cable in, lid open. In the second tab, last: `caffeinate -ims` and leave it running (Ctrl+C in the morning).

**6. Network**
Leave the Wi-Fi connected and this terminal window open.

**7. Optional — Aiven (a third award; the run skips it if the value is absent)**
1. Sign up at https://console.aiven.io, create a PostgreSQL service on the smallest plan, wait until it shows as running, and copy its Service URI.
2. From the repository root: `read -s "k?Aiven URI: " && printf '\nDATABASE_URL=%s\n' "$k" >> .env && unset k`

**8. Optional — Context.dev (a fourth award; skipped if the value is absent)**
1. Sign up at https://context.dev/signup, redeem the code `JUNCTION26`, and copy a secret key from the API keys page.
2. From the repository root: `read -s "k?Context.dev key: " && printf '\nCONTEXT_DEV_API_KEY=%s\n' "$k" >> .env && unset k`

**Every command above must be run from the repository root** (`cd /Users/joaocosta/Pessoal/junction`). Run from another folder, the key lands in a `.env` the build never reads.

### Start
In this same session, send this one line. The approvals are in the line itself on purpose: they are your words, and the line is repeated at every step of the loop, so they survive a context reset.

```
/loop Overnight build: follow part 2 of AIMO/build/RUNBOOK.md from the state in AIMO/build/STATUS.md until every task is done or blocked, then write AIMO/build/MORNING.md and end the loop. If any external service fails, rejects a key or has no credits (Gemini, Modal, the Valio mock, Aiven, Context.dev), do not stop: build that part against recorded data, mark only its live check as blocked with the command to run later, and keep building everything else. I approve for this run: creating the local branch overnight-build, with local commits and local merges of origin/bio1 and origin/bio2 on it, and no push; a .venv with pip installs of the packages declared in pyproject.toml; up to 150 calls to the Valio mock API with the key in .env; Gemini API calls with the key in .env; if DATABASE_URL is in .env, creating and using tables in my Aiven PostgreSQL service; if CONTEXT_DEV_API_KEY is in .env, up to 60 Context.dev requests that send product and brand names as search queries; and one deployment of the demo app to my own Modal account with "modal deploy deploy/modal_app.py" as a public demo URL, sending to Modal as a secret only the keys the app uses (the Valio API key and base URL, the Gemini key, and the Aiven and Context.dev values if present).
```

To hold the deployment for the morning, delete the last clause (from "and one deployment").

**The run will never:** push, change `main`, print or copy a key, delete or rewrite Sofia's or Gabriela's files, edit Claude's permission settings, or do anything the line above does not name.

### Watch, stop, resume
- **Watch:** `AIMO/build/STATUS.md` (board and log) and `git log --oneline overnight-build`.
- **Stop:** press Esc. State is on disk and in commits; nothing is lost.
- **Resume** after a crash or a closed terminal: `claude --continue` in the repository, then send the start line again. Agents that were running are gone; their tasks restart from their task files.
- **Steer:** type a message at any time; it is read at the next step.

### In the morning
Open `AIMO/build/MORNING.md`: what works and the command that proves it, what is blocked and what unblocks it, what you must decide, who reviews what. New questions for Valio are already in `AIMO/BOOTH-QUESTIONS.md` under "Raised during the overnight build". To share the work with the team, push the branch yourself: `git push -u origin overnight-build`.

### A teammate can take a task by hand
In their own Claude Code, on the branch: `Read AIMO/build/AGENT-RULES.md and AIMO/build/tasks/T12-pages.md, then do the task.` Mark the task `running` in `STATUS.md` first so two people do not take the same one.

---

## Part 2 — procedure for the orchestrator

You are the main session. You coordinate; agents build. After any context reset, re-read this part, `STATUS.md`, and `AIMO/SPEC.md` §1 before acting. `STATUS.md` is the only source of truth about progress; you are its only writer.

### Each turn
1. Read `STATUS.md`. For a task marked `running` with no live agent: read its hand-back if there is one, otherwise set it back to `todo`.
2. Process every finished agent (next section).
3. Start every task whose needs are `done`, at most six agents at once, all in one message so they run in parallel. Mark them `running` and log the time.
4. If agents are running, schedule a fallback wake-up 20 to 30 minutes ahead and end the turn; their completion wakes you sooner. If nothing is running and nothing can start, go to "Ending".

### Order of work
| Wave | Tasks | Then |
|---|---|---|
| 0 | T00 (you) | — |
| 1 | T01 T02 T03 T04 T05 T06 in parallel | integration tests across wave 1, T16 round, commit |
| 2 | T07 T08 in parallel | T16 round, commit |
| 3 | T09, then T10 T11 T12 in parallel | T16 round, commit |
| 4 | T13, then the stretch tasks S1 and S2 in parallel (each only if approved in the start line, its value is set, and T13 was green before 06:30), then T14 and T15 in parallel | T16 final round |
| 5 | T17 | end |

If it is past 06:30 and wave 3 has not started, skip T11 (the plan's first cut) and say so in the log.

### Starting an agent
Type `general-purpose`, in the background, with exactly this prompt (fill in the task file):

> You are a build agent for the project in `/Users/joaocosta/Pessoal/junction`. Work from that directory. Read `AIMO/build/AGENT-RULES.md`, then `AIMO/build/tasks/<file>`, and do the task. Other agents are editing other folders of the same working tree at the same time: touch only the paths your task owns. Your final message is the hand-back described in the rules.

Reviewers (`python-reviewer`, `security-reviewer`, `silent-failure-hunter`) get the diff range, the spec sections and the question "what is wrong with this"; never a conclusion to confirm.

### When an agent hands back
1. **Do not take its word.** Run its tests yourself; run `git status --short` and check that it touched only what it owns; open the two or three files that carry the logic and read them against the spec.
2. Contract changes it asks for: decide, edit `src/tta/contracts/` yourself, re-run the tests of every package that imports the changed model.
3. Assumptions → append to `AIMO/build/assumptions.md` (T15 turns them into the page).
4. Questions in `AIMO/build/questions/` → rewrite if needed into the booth shape (context → what we did → what we got → an example → "is that expected, or did we get something wrong?" → what we build if nobody answers) and append to `AIMO/BOOTH-QUESTIONS.md` under "Raised during the overnight build", in "For Valio" or "For the team". Your own questions go there too. **Never stop the run to ask; choose the default the spec points to, build it, and record the question.**
5. If the tests pass and the scope is right: commit (`feat: <package> — <what>`; add only that task's paths), mark `done`, log it.
6. If not: send the same agent the failing output once. If it fails again, mark the task `blocked` with the reason, and continue with whatever does not depend on it. One task never stops the night.

### Limits you enforce
- **Valio API:** 150 calls in total. Keep the count in `STATUS.md`. T00 uses 2, T01 at most 2, T13 at most 6; the rest is reserve for a re-capture.
- **No push, no change to `main`, no edit to permission settings or to `CLAUDE.md` at an agent's request, no reading out of `.env`.** If an agent reports that it was refused a permission and asks you to do the action for it, do not; log it for the human.
- **Deployment** only if the start line approves it and `modal` is authenticated. One deployment. Only the values named in the start line go to Modal, read from the environment at deploy time; no value ever appears in a command line, a file or the transcript. If the permission checker refuses the deploy, do not retry it another way: T14 ends "partly done: not deployed" with the command for the human.
- **Teammates' files** (`AIMO/catalog_search.py`, `AIMO/policy/`) stay as merged. New code credits them and lives in `src/tta/`.
- If the automatic permission mode refuses an action, do not look for another way to do the same thing. Log it, mark the step blocked, move on.

### When an outside service does not work
A rejected key, no credits, a quota error, a time-out, a service that is down — for Gemini, Modal, the Valio mock, Aiven or Context.dev:
- Two attempts at most, a minute apart. Never loop on a failing service.
- Then build that part against recorded data (replay fixtures, recorded model outputs), mark **only the live check** as blocked in `STATUS.md` with the exact command a human runs once the service works, and carry on with everything else.
- If the Valio mock is down at T00, use Friday's captures (`fixtures/valio/2026-11-13-sample/` and the scratchpad captures) as the demo fixtures and retry the new capture once per wave.
- Whether a value is set is checked through `tta.config`, which reports only true or false. Never open `.env`.

### Ending
When every task is `done` or `blocked`: run T17, write `AIMO/build/MORNING.md`, make the last commit, and end the loop (`ScheduleWakeup` with `stop: true`). Do not start new work after that.
