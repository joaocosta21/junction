"""Fixed rules, buyer profiles and the policy engine (SPEC section 7).

What the buyer's agent may decide alone, what needs a human, and what can never be ordered. The rules
are data (`rules.yaml`), the limits of each buyer are data (`profiles/*.yaml`), and the engine that
reads them is deterministic: no model takes part in a verdict.

The design is Gabriela's, from her work of Friday 13 Nov in `AIMO/policy/` (branch `bio2`):
`policy.yaml`, `policy_check.py` and `test_policy_file.py`. Kept from it: every fact a rule may read is
declared; rules are declarative (`when`, verdict, approver role, message, justification); the most
severe verdict wins; a missing fact never passes; and the hash of the policy in force is carried by
every decision. Her spend limits of 750 and 3,000 and her minimum fill ratio of 0.9 are the values of
the `hotel-kitchen` profile.
"""

from tta.policy.engine import RulePolicyEngine
from tta.policy.errors import PolicyLoadError
from tta.policy.loading import PROFILES_DIR, RULES_PATH, load_rulebook, parse_rulebook
from tta.policy.profiles import load_profile, load_profiles

__all__ = [
    "PROFILES_DIR",
    "RULES_PATH",
    "PolicyLoadError",
    "RulePolicyEngine",
    "load_profile",
    "load_profiles",
    "load_rulebook",
    "parse_rulebook",
]
