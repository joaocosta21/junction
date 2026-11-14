# T05 — Policy: fixed rules, buyer profiles, engine

**Scores on:** 20% (autonomy and controls: "what the agent can decide alone, what needs human sign-off") · Core 3.
**Needs:** T00. **Owns:** `src/tta/policy/`, `tests/policy/`.
**Read first:** SPEC §7 · `AIMO/policy/policy.yaml`, `policy_check.py`, `test_policy_file.py` (Gabriela's Friday work: keep its structure — declared facts, declarative rules, most severe verdict wins, missing fact never passes, policy hash — and credit it in the module docstring) · `AIMO/PLAN.md` §5 (what her file must drop) · `tta/contracts/policy.py`.

## Build
- **`rules.yaml`:** the fixed rules F-01 to F-05 and the profile rules P-00 to P-07 of SPEC §7, in the declarative form of Gabriela's file (facts, `when`, verdict, approver role, message template, justification). Drop what the plan supersedes: the contradicted-closing-time setting, the sentinel threshold, the rule that blocks `X99`.
- **Profiles:** `profiles/hotel-kitchen.yaml` and `profiles/allergy-ward.yaml` with the values of SPEC §7, each marked "illustrative". A validated schema. **A profile cannot disable or weaken a fixed rule**; a file that tries is rejected at load.
- **Engine** implementing the `PolicyEngine` port: `evaluate(option, profile, context)` → `PolicyDecision` (verdict, every rule that fired with its sentence and the facts it read, the roles required, the policy hash). Deterministic; no model involved.
- **Facts** are read from the offer option and the order context (today's committed spend). A missing fact fires F-03.
- **Hash:** SHA-256 of the canonical form of the rules plus the profile.
- `describe_authority(profile)` → the plain-language summary returned by `GET /v1/authority`.

## Tests to write first
- Each rule fires and does not fire; the most severe verdict wins; all fired rules are listed.
- A missing fact → `APPROVAL` by F-03, never `AUTO`.
- A profile that sets a fixed rule to off, or omits `allergen_strictness` while listing exclusions → load error.
- Canonical option (net €1,980.77, fill ratio 0.749, `hotel-kitchen`) → `APPROVAL`, rules P-01 and P-03, role purchasing manager.
- The unconfirmed alternative (net €1,010.00) → `APPROVAL` by F-01 and P-01.
- `allergy-ward`, net €428.00, every claim confirmed, fill 1.0 → `AUTO`.
- The same order once the day's spend would pass €1,500 → `APPROVAL` by P-02 (finance).
- The hash is stable across runs and changes when a limit changes.
