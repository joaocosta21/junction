# FALLBACK-1 — questions

For the team.

**Context:** The task says "gluten-free → FREE_FROM_GLUTEN (claim)". The text check (`agent/textcheck.py`) and the model's instruction (rule 6) both read "gluten-free" as the exclusion of gluten (AW), and the text check refuses any reading that leaves that exclusion out.
**We did:** The rule-based reader reads "gluten-free" as both: the claim FREE_FROM_GLUTEN and the exclusion AW.
**We got:** "30 kg gluten-free bread" reads, through the rules, as bread with claim FREE_FROM_GLUTEN and exclusion AW. The model's instruction (rule 6) asks Gemini for the exclusion only; we did not check live what Gemini gives for this sentence. So the rules offer only bread that carries the claim, while a model reading that follows rule 6 accepts any bread that declares no gluten.
**Example to show:** `POST /v1/requests/parse` with no key, as `agent_ward`, text "30 kg gluten-free bread, most reliable": `required_claims: ["FREE_FROM_GLUTEN"]`, `exclude_allergens: ["AW"]`.
**Ask:** "Should the rules drop the claim and match the model (exclusion only), or should the model's instruction add the claim? Is that expected, or did we get something wrong?"
**If no answer, we build:** we keep both: the rules' reading is stricter, never looser, than the model's.

For the team.

**Context:** The fallback (recording, then rules) runs only when Gemini cannot be reached (a time-out, 408, 429 or a 5xx) or when no key is set. A refusal (400 to 404) is still answered as `supplier-unavailable`, as FIX-9 decided.
**We did:** We kept that rule.
**We got:** If the deployed key is revoked or rejected (403 or 400 "API key not valid"), every sentence with no recording still gets a 503. The rules would read it.
**Example to show:** `tests/agent/test_fallback.py::test_a_refusal_is_not_read_by_the_rules`.
**Ask:** "With the key on a zero balance, should a 403 or 400 also fall back to the recording and the rules? Is that expected, or did we get something wrong?"
**If no answer, we build:** nothing more: a refusal stays a 503, as now.
