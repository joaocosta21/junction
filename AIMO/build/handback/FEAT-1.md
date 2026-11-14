# FEAT-1 — partly done

Everything the task asks for is built and tested. Two display items need one-line edits in files owned by other tasks (see Not done).

## Built
- `src/tta/policy/custom.py` (new): `profile_in_force(profile)` context manager plus `custom_profile(id)`. A profile set up on a page is in force only inside the `with` block, in that thread of control. Every `RulePolicyEngine` of the process finds it there, including the agent package's own engine that the parser uses.
- `src/tta/policy/engine.py`: `get_profile` checks the profile files first, then the profile in force. A profile in force never shadows a file. New `check_custom_profile(data)` runs the same checks as a profile file and refuses an id that a profile file already uses. New read-only `access_rules` property (F-06), used to list it on the page. `profile_ids()` still lists the files only.
- `src/tta/policy/profiles.py`: the checks of `load_profile` moved into `check_profile(data, source, fixed_rule_ids)`, shared by files and pages. `load_profile` keeps the file-name check. Behaviour is unchanged, except that when a file has both bad exclusion codes and an id that does not match its name, the exclusion problem is now reported first.
- `src/tta/policy/__init__.py`: exports `profile_in_force`.
- `src/tta/api/sandbox.py`:
  - `KITCHEN_PROFILE_ID = "my-kitchen"`; `KITCHEN_AGENT` ("My kitchen agent", `agent:my-kitchen`).
  - Three approver identities bound to `my-kitchen` (`human:my-kitchen-purchasing`, `-finance`, `-dietitian`), named after the hotel's demo approvers (Hanna, Mikko, Leena). The profile's `approver_roles` lists them.
  - `kitchen_profile()`: the page's checks, then `check_custom_profile`, then the bounds (limits 0 to €100,000; at most 10 exclusions; a name of 1 to 60 characters). The gateway sets `profile_id`, `approver_roles`, `description` and `illustrative`, and a form that sends one is refused.
  - `Kitchen`: a thread-safe holder of one book's profile. It starts as a copy of `hotel-kitchen`; `start_from` copies `hotel-kitchen` or `allergy-ward`, and `set_up` saves the visitor's settings.
  - `ProfileInForce`: wraps the book's `Gateway` so that every call made on `book.service` runs with that book's kitchen in force.
  - `Sandbox` gets a `kitchen` field (default factory) and wraps `service` in `__post_init__`. The constructor in `wiring.py` is unchanged.
- `src/tta/ui/kitchen_page.py` (new):
  - `GET /kitchen`; `POST /kitchen` reads every form field, so an unknown or fixed-rule field is refused by name, never dropped; `POST /kitchen/start-from`. All three check CSRF.
  - Each setting is shown with its P-rule sentence in the kitchen's own values, taken from `describe_authority`. Also shown: the summary sentences, the policy hash in force, and F-01 to F-08 under "Always, whatever you set".
  - A refused form returns 422 with one problem per field and changes nothing.
- `src/tta/ui/templates/kitchen.html` (new): the form, the rule sentences, the fixed rules and the copy buttons. It uses only existing CSS classes.
- `src/tta/ui/routes.py`: three added lines and one docstring line. The kitchen identities are added after the demo-identity check, so "My kitchen agent" appears in the "who is asking" selector and the three My kitchen approvers appear in the approvals selector. The route `/kitchen` is registered.
- `docs/DEMO.md`: a section appended at the end, "Your kitchen: the buyer sets what its agent may decide alone".
- Tests:
  - `tests/policy/test_custom_profile.py`: 12 tests.
  - `tests/api/test_sandbox_profile.py`: 19 tests.
  - `tests/ui/test_kitchen_page.py`: 23 tests.

## Tests
```
COVERAGE_FILE=<scratch>/.cov .venv/bin/python -m pytest tests/ui tests/api tests/policy tests/e2e -q -p no:cacheprovider
........................................................................ [ 97%]
.............................                                            [100%]
1037 passed in 98.86s (0:01:38)
```
Coverage, from the kitchen, sandbox and policy tests: `tta.ui.kitchen_page` 100%, `tta.api.sandbox` 99%, `tta.policy.custom` 100%, `tta.policy.engine` 100%, `tta.policy.profiles` 100%. `ruff check` passes on every file I touched.

Checked by hand with the real agent package and no Gemini key, using a scratch script that is not in the repo. Running scenario 1 as My kitchen agent:
- at €3,000 per order the result is `ORDERED` / `AUTO`;
- at €750 the result is `PENDING_APPROVAL` by P-01, plus P-02, because the first €2,580.64 already counts in today's €3,000.

Both runs say "The buyer agent could not run: This sentence was recorded for another buyer profile …" and then use the example's typed request.

## Assumptions
- My kitchen starts as a copy of `hotel-kitchen` (display name "My kitchen") instead of being empty. The request page asks every agent in the selector for its authority, so `my-kitchen` must always resolve, also in the blank book.
- An `Identity` binds an approver to one profile, so the hotel's demo approvers cannot decide `my-kitchen` approvals as they are. Three approver identities bound to `my-kitchen` carry the same people's names; on the approvals page they read "Demo approver Hanna, My kitchen", and so on.
- The profile in force is passed through a context variable, not an argument. The services look profiles up by the caller's id, `wiring.py` (S1) builds every sandbox over the shared engine, and the agent parser has its own engine (`tta.agent.profile_strictness`, T18). The context variable is set only around calls made on a sandbox's service, so REST and MCP never see a custom profile.
- An approval of a `my-kitchen` order is re-checked against the kitchen as it stands at approval time, as it would be after a profile file changed.
- The bounds (€100,000, 10 exclusions, a 60-character name) belong to the page's form. They are not added to the profile-file checks, so the profile files are unaffected.
- The minimum share is entered as a percentage (0 to 100) on the page and stored as the contract's ratio.
- `require_confirmed` drives no P rule. The page says it shapes the offer itself.
- The general statement `X99` is not offered as an allergen to exclude, matching the profile-file check.

## Contract changes needed
- `Identity.profile_id` (common.py): an approver who holds roles for more than one buyer profile would let the hotel's own `human:hotel-*` identities decide `my-kitchen` approvals, instead of the three extra identities. This is not needed for the demo.

## Not done
- **No nav link to `/kitchen`.** `templates/base.html` is not mine. It needs one line in the `<nav>`: `<a href="/kitchen"{% if path == "/kitchen" %} aria-current="page"{% endif %}>Your kitchen</a>`. The demo section says to type the address for now.
- **The result block of a run does not show the profile's summary sentence or the policy hash.** `templates/_result.html` and `request_page.py` belong to T18. What the run shows now:
  - the result names profile `my-kitchen`, and the selector card shows the kitchen's limits;
  - the order record `/orders/{id}` shows "Policy and profile in force: sha256:…" and its audit trail names `my-kitchen` (tested);
  - `/kitchen` shows the summary sentences and the hash.

  To finish it, `request_page._result` would pass `book.service.get_authority(asker)`, and `_result.html` would print `authority.summary[0]` and `authority.policy_hash`.
- **Without a Gemini key, a run as My kitchen agent shows "The buyer agent could not run: This sentence was recorded for another buyer profile …"** before it uses the example's typed request. The recordings in `fixtures/agent/` are for `hotel-kitchen` and `allergy-ward` (T18). A `run-scenario-1` recording for `my-kitchen` would remove the note. The verdicts are the same either way.

## Questions written
0
