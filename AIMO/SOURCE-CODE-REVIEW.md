# The "Source Code" link: is the repository ready?

Lane SRC, Sunday 15 Nov 2026, about 04:30. Checked on branch `replan-build` at `d617d5c` to `db3c2b6` (285 commits in all refs). No outside call was made: nothing here was checked on GitHub itself, and `.env` was not read.

**Answer.** The code and the README are ready. The link is not: a visitor lands on `main`, which holds no code and no licence, and 16 commits of tonight are not pushed. Steps 1 to 4 below fix that in about ten minutes.

## 1. Same repository or a new one

**Same repository, made public, with `main` moved to tonight's code.**

- The history is the evidence that the code was written at the event: 285 commits from Fri 13 Nov 19:22 to today, the first code on Fri 13 Nov 22:18. A new repository with one commit loses it.
- Nothing secret is in the history (section 2). What a team might prefer not to show is noise, not harm (section 3).
- The documents cite commit ids and files under `AIMO/build/` in 33 places; a rewritten or filtered history breaks all of them, and `git-filter-repo` is not installed.
- A new repository with the full history pushed to it shows exactly the same content, so it gains nothing.
- One open point decides whether this holds: Valio Aimo's data files are in the history (step 0).

What João does, in order:

| # | What | Command or click | Takes |
|---|---|---|---|
| 0 | Ask Valio Aimo at the booth, before step 4 | "Junction asks for a public, MIT-licensed repository. Ours holds your synthetic product file and recorded mock answers, which the demo needs to start. May they stay public?" | 2 min |
| 1 | Wait for the orchestrator's last commit; the tree must be clean | `git status --short` prints nothing | — |
| 2 | Move the other challenges' briefs out of the first page (section 3) | the three commands of section 3, row A | 1 min |
| 3 | Push tonight's work and move `main` to it (a fast-forward: `origin/main` is an ancestor of `replan-build`) | `git push origin replan-build && git push origin replan-build:main`. If GitHub refuses the second push (a protected branch): Settings → Branches → default branch → `replan-build` | 1 min |
| 4 | Make it public | GitHub → Settings → General → Danger Zone → Change visibility → Public | 1 min |
| 5 | Look as a judge | open `https://github.com/joaocosta21/junction` in a private window: the README starts with "Trusted Trade Agents", the right column says "MIT license", `src/` is there | 1 min |
| 6 | Paste that address in the form's "Source Code" field | — | — |

If Valio says the data may not be public: do not do step 4. Keep the repository private, invite the organisers' GitHub accounts (Settings → Collaborators), and say so in the form. Removing the files is not an option before 10:00: they are in the history, and the gateway does not start without the product file (`SupplierUnavailable`, checked).

Optional, one click each: Settings → General → rename the repository to `trusted-trade-agents` (GitHub redirects the old address); on the repository's front page, "About" → the punchline and the public link as website.

## 2. What must be true before the link goes in the form

| Check | Answer | How it was checked |
|---|---|---|
| MIT `LICENSE` at the top level | yes | Standard MIT text, "Copyright (c) 2026 The project contributors" |
| `license` in `pyproject.toml` | yes | `license = "MIT"`; the OpenAPI document says MIT too |
| No secret in a tracked file | yes, by pattern | See the scan below |
| No secret in the history | yes, by pattern; the real values were not compared | The same scan over every added line of all 285 commits; João's 20-second check below closes it |
| `.env` and `var/` ignored, never committed | yes | `.gitignore` lines 1, 2 and 18; no path named `.env*`, `var/`, `*.key`, `*.pem`, `credentials*` or `*.sqlite` was ever added in any ref |
| A clone runs with the README's command and no key | yes for the code; cannot tell for a fresh `pip install` | The committed tree was extracted to an empty folder (no `.env`, no `var/`) and started with the README's settings: `/healthz` ok, replay, reader `fixed_rules`, `/shop` 200, `/v1/authority` 200 with a demo token; start takes about 10 s. Not run: the install itself. The dependencies carry no versions and there is no lock file |
| Every link in the README resolves | yes | 17 relative links, each a tracked file; every backticked path exists. The one outside address (the public link) was not called |
| The branch a visitor lands on shows tonight's code | **no** | The default branch is `main`. `origin/main` is at `12a40a0`: 45 commits, briefs and data only, a README that reads "# junction", no `src/`, no `LICENSE`, no `pyproject.toml`. `replan-build` is 240 commits ahead of it, and 16 of those are not pushed. Step 3 fixes both |
| The repository is public | cannot tell from here | Step 4 |
| Valio Aimo's data may be public | cannot tell | Step 0. `AIMO/CHALLENGE.md:52` says everything is synthetic and not confidential; the files sit behind an API key |

**The scan.** `git log --all -p` (every added line, 195,549 lines; the 87 MB product file left out), searched for: Google, OpenAI, Anthropic, GitHub, AWS, Slack, Modal and Aiven token shapes; private-key blocks; JSON Web Tokens and the private part of a JWK; connection strings with a password; `Bearer` followed by a long value; `…KEY`, `…SECRET`, `…TOKEN`, `…PASSWORD`, `DATABASE_URL` assigned a value; values after `X-API-Key`, `Authorization` and key-like query parameters; `aivencloud.com` host names; identifiers next to the words key, token, secret, password. The recordings under `fixtures/` were searched for request headers: none is stored. Every hit is a test placeholder (`sentinel-…`, `db.example`, `127.0.0.1`), a `your_api_key_here` in a partner's brief, or a demonstration token that is public by design. The Valio client and the capture script send the key only as a header and refuse to store an answer that repeats it.

**João's check, since I did not read `.env`** (prints each setting's name and a count, never a value; every count must be 0):

```bash
while IFS='=' read -r k v; do v=${v%\"}; v=${v#\"}; [ ${#v} -ge 12 ] && echo "$k: $(git log --all --oneline -S"$v" | wc -l)"; done < .env
```

## 3. What a judge does not need, and what a team may not want public

Moving a file tidies what a visitor sees first; it hides nothing, because the history stays. Nothing below is a secret.

| | What | Why | Command |
|---|---|---|---|
| A | 22 `*-CHALLENGE.md`, `RECOMMENDATION.md`, `RESOURCES.md` at the top level | Other partners' briefs copied from the Junction app, with their contacts (e-mail addresses at `ATECH-CHALLENGE.md:60-62`, `CALA-CHALLENGE.md:42`, `CONTEXTDEV-CHALLENGE.md:42`, `CONTEXTDEV-TECH-CHALLENGE.md:61`, `NVIDIA-CHALLENGE.md:37`, `OXYLABS-CHALLENGE.md:56`; a phone number at `ASTRAZENECA-CHALLENGE.md:68`) and credit codes; our notes on which challenge had the best odds. On GitHub they push the README below 40 file names. Nothing links to them (one code comment names one) | `mkdir -p archive/challenges && git mv *-CHALLENGE.md archive/challenges/ && git mv RECOMMENDATION.md RESOURCES.md archive/` then `git commit -m "chore: the other challenges' briefs and the selection notes moved to archive/"` |
| B | Two superseded decks: `AIMO/Trusted_Trade_Agents_Combined_Junction_Pitch.pptx`, `AIMO/Trusted_Trade_Agents_Junction_Pitch_v4.pptx` | A judge who opens the wrong deck reads claims corrected since. Nothing links to them | `git mv AIMO/Trusted_Trade_Agents_Combined_Junction_Pitch.pptx AIMO/Trusted_Trade_Agents_Junction_Pitch_v4.pptx archive/` (in the same commit) |
| C | `CLAUDE.md` | The working notes for coding agents: the scoring plan, the prize amounts, and the team in lines 90 to 93 (country and degrees, no names). Not harmful; the team's call. Coding agents load it from the top level, so move it only after the last agent has finished | leave it, or last of all: `git mv CLAUDE.md archive/CLAUDE.md` |
| D | `AIMO/build/` (153 files: task files, hand-backs, the board, the decisions) | Leave it. 33 kept files cite it (the README three times), and it is the record of how and when the code was written | none |
| E | `AIMO/build/replan/REVIEW.md` (the security findings with reproductions) | Leave it: it helps the criterion more than it risks. Nine documents cite it as the proof of what was found and decided, which is "clear visibility of assumptions". It hands a visitor no new way to disturb the public demo: the rates per address and for all callers are already in the README and on the served `/assumptions` page; the pages keep one order book per browser; the public link carries no Context.dev key and no model key; changing a stored order needs write access to the database. **But its State column is stale: 32 rows of the Sunday tables still say `todo` although the board says the lanes are done. Bring it up to date before step 4, or a judge reads 32 open findings** | the orchestrator's file |
| F | The booth notes: `AIMO/BOOTH-NOW.md`, `BOOTH-QUESTIONS.md`, `BOOTH-ROUND-2.md`, `OPEN-QUESTIONS.md` | They are the source of every "Valio Aimo said on 14 Nov" in the README and the rules, and seven kept files cite them: leave them. I found no person's name in them (searched by pattern, not read line by line). One answer is quoted bluntly, about how judging works: `AIMO/BOOTH-ROUND-2.md:11`. Read that line and decide | none, or edit that line |
| G | Personal details | No full name, no phone number of ours and no school is in a tracked file. The team's country and degrees: `CLAUDE.md:90-93`. Teammates' first names: `AIMO/PLAN.md` and seven code comments. One teammate's e-mail address: `AIMO/build/replan/C1-human-approval-branch.md:115`. **Three author e-mail addresses (two personal, one of an organisation) are in the commit metadata of all 285 commits** and become public with the repository: tell the two teammates before step 4. List them with `git log --all --format=%ae \| sort -u` | none that keeps the history |
| H | Valio Aimo's data: `valio_aimo_junction26_product_data.json` (87 MB), the schema, the two CSV files, `fixtures/valio/` (recorded answers), and `AIMO/docs/API.md` (their API documentation, which sits behind the portal password) | Redistribution is theirs to allow: step 0. The gateway needs the product file to start and the recordings to answer. `.gitignore` line 7 says of the copies under `AIMO/` "not ours to redistribute" while the same files are tracked at the top level: once Valio has answered, make that comment say what is true | step 0 |
| I | Remote branches `bio1`, `bio2`, `frontend-shop`, `codex/mandatory-human-approval`, `overnight-build` | All merged into `replan-build` (0 commits of their own). They show who built what: leave them | none |

## 4. What changed in `README.md`

An edit for order, not a rewrite: 206 lines and 4,476 words, against 193 and 4,481. A judge now reaches the run command at line 25 (it was line 72) and the four phrases of the criterion right after it.

- **First screen:** three sentences on what it is; the brief's sentence with its three options as a table (435 L confirmed for €1,083.39; 1,000 L for €1,010.00 with a quantity not confirmed; 1,000 L from confirmed stock for €2,580.64 with 565 L of coffee milk named as a substitute), each with the rules that send it to a person; one command to run it, where to click on `/shop`, where an agent starts, and the public link.
- **Four sections under the criterion's own phrases:** "Open, documented standards" (new table: each standard and where to see it), "Assumptions" (moved up, kept), "Technical choices, and why" (new table: the choice, the alternative not taken, the reason; eight rows), "Next steps" (moved up, kept, each as "today … next …").
- **Below a rule, as reference:** the flow, who reads a request, the four customers, the rules, running it in detail, the tests, the datasets, read more, the licence. Their facts are unchanged.
- **Measured again by me** in replay with no key, at both clocks, over REST as the hotel's agent: the three options, their products, totals and rules (option 2 fires F-01 and P-01; the old text named F-01 only); 27 paths, OpenAPI 3.1.0; 98 schemas, each with the 2020-12 `$schema`; 13 MCP tools, none approving; 11 demo identities; problem details on 401 and 403; an agent's token refused at the approval route with 403; the Ed25519 key at `/.well-known/jwks.json`.
- **Corrected:** the note that the deploy "passes the key to the public link when the deploying machine has one" was no longer true: the code sends a model key only with `TTA_DEPLOY_WITH_MODEL=1`. The sentence about the public link now points to the build log, which records the redeploy of 03:35.
- **Removed:** the model's name (twice) and its provider's name; the model reader is described as existing, measured, and off on the public link and for every figure. The setting `GEMINI_API_KEY=` stays in the run command, because it is what keeps the reader off on a machine that has a key. Also removed: the old tail "Hackathon notes / # junction", and lines said twice.
- **Not created:** `docs/OPENNESS.md`. `docs/STANDARDS.md` and `docs/ASSUMPTIONS.md` already hold the depth, and the README points to them.

## 5. Found, and not mine to change

- `AIMO/SUBMISSION.md:79`: the description drafted for the form has the heading "Honest limits", against João's wording rule. If that text went into the form, change the heading there too ("Assumptions").
- The model is still named in `docs/STANDARDS.md`, `docs/DEMO.md`, `docs/AWARDS.md`, `docs/ASSUMPTIONS.md`, `AIMO/SPEC.md` (twice), `AIMO/WALKTHROUGH.md`, `AIMO/COVERAGE.md`, and in the code (`src/tta/agent/gemini.py`, `labels.py`, `fallback.py`).
- `docs/DEPLOY.md:5` still says its code "was not deployed when this was written"; the board says the link was redeployed from `627c732` at 03:35 and passed its 10 checks.
- `AIMO/build/replan/REVIEW.md`: the stale State column (row E above).
- `.gitignore:7`: the comment about redistribution (row H above).
- `pyproject.toml`: no versions on the dependencies and no lock file. `.venv/bin/pip freeze --exclude-editable > requirements.lock` would record what the suite passed with; a new file, so João's decision.
