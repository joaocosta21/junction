"""What a change of a kitchen's settings leaves in the log, and what it may not do (decision B59; checks C1-6, C4-F2).

Scores on the 20% "autonomy and controls ... how decisions are logged and auditable". Switching "ordering alone" on
is the most important human decision in the system; it is now one `settings.changed` event with who changed what
and each setting before and after (`tta.audit.settings_sentences` words it; Valio Aimo's view shows no value).

And a guard that needs no login. Where the customer's profile names a dietitian of its own (the ward, the school),
the allergen exclusions are hers: a page that acts for the person who orders may add an exclusion and put one
under the strict rule, and may never remove one her profile holds or check it under a weaker rule. Allergens stay
overly cautious: no data means unknown, and no setting of a page makes an allergen question disappear.

Pure functions over buyer profiles, and one that writes the event. `tta.api.sandbox.Kitchen` calls them.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from tta.audit.phrases import MAX_NAME_CHARACTERS, allergen_names, plain
from tta.contracts.audit import Actor, AuditContext, AuditEventType
from tta.contracts.common import AllergenStrictness, ApproverRole, JsonDict
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import AuditSink
from tta.policy.human_approval import has_own

CHANGES_FACT, CUSTOMER_FACT = "changes", "customer_id"
EXCLUSIONS, FORMULA_MODE = "excluded_allergens", "formula_mode"
# The settings a person sets, in the order a sentence says them: ordering alone first. The values are the
# profile's own, as JSON. Two are read as a person means them and not as the form spells them (`said`).
SAID_AS_THEY_ARE = (
    "auto_order_enabled", "max_order_net_eur", "max_daily_net_eur", "min_fill_ratio",
    "substitution_without_approval", "variable_weight", "deposits", "require_confirmed",
    "standing_order_drift_ratio", "max_preference_premium_ratio", "display_name",
)
EXCLUSIONS_STAY = (
    "excluded_allergens: The allergen exclusions of {customer} are set by its dietitian and cannot be removed "
    "here: {names} must stay excluded"
)
STRICT_RULE_STAYS = (
    "allergen_strictness: The allergen rule of {customer} is set by its dietitian and cannot be relaxed here: "
    "{names} must stay under the strict rule"
)


def said(profile: BuyerProfile) -> JsonDict:
    """A profile's settings as a person means them. The allergens kept out are one setting: each excluded code with
    the rule it is checked under, however the form spelled it (one rule for all, or one per code). When a substitute
    must keep the recipe is the mode in force, whichever of the two formula settings says it."""
    dumped = profile.model_dump(mode="json", include=set(SAID_AS_THEY_ARE))
    rules = {code: _rule(profile, code) for code in profile.excluded_allergens}
    return {
        **{name: dumped[name] for name in SAID_AS_THEY_ARE[:4]},
        EXCLUSIONS: rules,
        **{name: dumped[name] for name in SAID_AS_THEY_ARE[4:-1]},
        FORMULA_MODE: profile.formula_mode_in_force.value,
        SAID_AS_THEY_ARE[-1]: dumped[SAID_AS_THEY_ARE[-1]],
    }


def _rule(profile: BuyerProfile, code: str) -> str | None:
    rule = profile.strictness_for(code)
    return rule.value if rule is not None else None


def changes(before: BuyerProfile, after: BuyerProfile) -> tuple[JsonDict, ...]:
    """Each setting that differs, with its value before and after. Empty when a form changes nothing."""
    was, now = said(before), said(after)
    return tuple(
        {"setting": name, "before": was[name], "after": value} for name, value in now.items() if was[name] != value
    )


def has_own_dietitian(profile: BuyerProfile) -> bool:
    """Whether somebody other than the person who orders holds the dietitian's role: the ward and the school.
    At the hotel and the bakery one person holds every role."""
    return has_own(profile, ApproverRole.DIETITIAN)  # the policy's own answer: one reading of who is a second person


def dietitians_refusals(customer: BuyerProfile, wanted: BuyerProfile) -> list[str]:
    """Why `wanted` may not become the settings of this customer: it removes an allergen exclusion the customer's
    dietitian set, or checks one under a weaker rule. One problem per field, each starting with the field's name.
    Empty for a customer with no dietitian of its own, and for settings that only add or tighten."""
    if not has_own_dietitian(customer):
        return []
    kept = [code for code in customer.excluded_allergens if code in wanted.excluded_allergens]
    removed = [code for code in customer.excluded_allergens if code not in kept]
    relaxed = [
        code for code in kept
        if customer.strictness_for(code) is AllergenStrictness.STRICT
        and wanted.strictness_for(code) is not AllergenStrictness.STRICT
    ]
    name = plain(customer.display_name, MAX_NAME_CHARACTERS)
    problems = []
    if removed:
        problems.append(EXCLUSIONS_STAY.format(customer=name, names=allergen_names(removed)))
    if relaxed:
        problems.append(STRICT_RULE_STAYS.format(customer=name, names=allergen_names(relaxed)))
    return problems


def record_change(
    audit: AuditSink, actor: Actor, profile: BuyerProfile, changed: Sequence[JsonDict], customer_id: str | None
) -> None:
    """One `settings.changed` event: who, the profile as it stands after the change, and each changed setting
    before and after. `customer_id` names the customer file the book stands for, when it stands for one."""
    facts: dict[str, Any] = {CHANGES_FACT: list(changed)}
    if customer_id is not None:
        facts[CUSTOMER_FACT] = customer_id
    audit.record(AuditEventType.SETTINGS_CHANGED, actor, AuditContext(profile=profile, facts=facts))
