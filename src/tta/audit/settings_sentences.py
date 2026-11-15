"""The sentences of `settings.changed` (decision B59, checks C1-6 and C4-F2).

Switching "ordering alone" on is the most important human decision in the system, and it left no event. Every
change of a buyer's settings is one event now: who changed what, each setting before and after, in a sentence the
buyer reads. Valio Aimo reads that a setting changed and nothing else: limits and allergen exclusions are the
buyer's private settings, so its sentence is one fixed text and its facts are empty.

What the event carries (written by `tta.api.kitchen_log`):
    profile             the buyer profile as it stands after the change
    facts["changes"]    one entry per changed setting: {"setting": name, "before": value, "after": value}, the
                        values as JSON. The allergen exclusions are one setting, `excluded_allergens`, whose value
                        maps each excluded allergen's GS1 code to the rule it is checked under.

A setting or a value this module has no words for is shown as data, never dropped: the facts hold it either way.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

from tta.audit.phrases import (
    ALLERGEN_RULE_WORDS,
    MAX_NAME_CHARACTERS,
    actor_text,
    allergen_names,
    label,
    money,
    percent,
    plain,
    quoted,
)
from tta.audit.scope import Scope
from tta.contracts.audit import Actor, ActorKind, AuditContext
from tta.contracts.policy import BuyerProfile

CHANGES_FACT = "changes"
ORDERING_ALONE, EXCLUSIONS, NAME = "auto_order_enabled", "excluded_allergens", "display_name"
SUPPLIER_SENTENCE = (
    "The buyer changed a setting of its agent. Which setting and its values are the buyer's own and are not shown."
)
NOT_RECORDED = "changed the agent's settings; what changed is not recorded"
ALONE_ON = "switched ordering alone on"
ALONE_ON_LIMITS = ": the agent may order up to {order} an order and {day} a day without asking"
ALONE_OFF = "switched ordering alone off: a person confirms every order"
NOT_SET = "not set"
MONEY_SETTINGS = {"max_order_net_eur": "the limit per order", "max_daily_net_eur": "the limit per day"}
SHARE_SETTINGS = {
    "min_fill_ratio": "the share of a request that must be covered",
    "standing_order_drift_ratio": "how far a standing order may differ from its usual quantity or price",
    "max_preference_premium_ratio": "how much more than the cheapest option a preferred option may cost",
}
SWITCHES = {"require_confirmed": "confirmed stock only"}
CHOICES: Mapping[str, tuple[str, Mapping[str, str]]] = {
    "substitution_without_approval": ("the substitutes the agent may take alone", {
        "NONE": "none", "LISTED_BY_SUPPLIER": "those Valio Aimo lists", "SAME_CATEGORY": "any of the same category",
    }),
    "variable_weight": ("how a product sold by weight is ordered", {
        "APPROVAL": "a person approves it", "AUTO_WITH_CEILING": "the agent orders it, the estimate as a ceiling",
    }),
    "deposits": ("how a product with a deposit is ordered", {
        "APPROVAL": "a person approves it", "NOTE": "the agent orders it and notes the deposit",
    }),
    "formula_mode": ("when a substitute must keep the recipe", {
        "ALWAYS": "always", "LEARN": "where this buyer's past orders show it matters",
        "WHEN_ASKED": "only when the request says so",
    }),
}
ALLERGEN_RULES = {rule.value: words for rule, words in ALLERGEN_RULE_WORDS.items()}


def _who(actor: Actor) -> str:
    """The person by name, read as data; no role: one person orders and sets the agent's limits."""
    if actor.kind is not ActorKind.HUMAN:
        return actor_text(actor)
    return plain(actor.display_name or actor.id, MAX_NAME_CHARACTERS)


def _decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str | Decimal):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _as_data(value: Any) -> str:
    return NOT_SET if value is None else label(str(value))


def _money(value: Any) -> str:
    number = _decimal(value)
    return _as_data(value) if number is None else money(number)


def _share(value: Any) -> str:
    number = _decimal(value)
    return _as_data(value) if number is None else percent(number)


def _rule(value: Any) -> str:
    return ALLERGEN_RULES.get(str(value)) or _as_data(value)


def _by_rule(codes: Sequence[str], rules: Mapping[str, Any]) -> dict[str, list[str]]:
    """The codes grouped by the rule each is checked under, in the order given."""
    grouped: dict[str, list[str]] = {}
    for code in codes:
        grouped.setdefault(_rule(rules[code]), []).append(code)
    return grouped


def _exclusions(before: Any, after: Any) -> list[str]:
    """What changed in the allergens kept out: added, taken off, and moved to another rule. Names, never codes."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ["changed the allergens kept out"]
    added = [code for code in after if code not in before]
    removed = [code for code in before if code not in after]
    moved = [code for code in after if code in before and after[code] != before[code]]
    clauses = [
        f"added {allergen_names(codes)} to the allergens kept out ({rule} rule)"
        for rule, codes in _by_rule(added, after).items()
    ]
    if removed:
        clauses.append(f"took {allergen_names(removed)} off the allergens kept out")
    clauses += [f"put {allergen_names(codes)} under the {rule} rule" for rule, codes in _by_rule(moved, after).items()]
    return clauses


def _ordering_alone(after: Any, profile: BuyerProfile | None) -> str:
    if not after:
        return ALONE_OFF
    if profile is None:
        return ALONE_ON
    return ALONE_ON + ALONE_ON_LIMITS.format(
        order=money(profile.max_order_net_eur), day=money(profile.max_daily_net_eur)
    )


def _clauses(change: Mapping[str, Any], profile: BuyerProfile | None) -> list[str]:
    """One setting's change as the verb phrases of a sentence whose subject is the person."""
    name, before, after = change.get("setting"), change.get("before"), change.get("after")
    if name == ORDERING_ALONE:
        return [_ordering_alone(after, profile)]
    if name == EXCLUSIONS:
        return _exclusions(before, after)
    if name == NAME:
        return [f"renamed the kitchen from {quoted(str(before))} to {quoted(str(after))}"]
    if name in MONEY_SETTINGS:
        return [f"changed {MONEY_SETTINGS[name]} from {_money(before)} to {_money(after)}"]
    if name in SHARE_SETTINGS:
        return [f"changed {SHARE_SETTINGS[name]} from {_share(before)} to {_share(after)}"]
    if name in SWITCHES:
        return [f"switched {SWITCHES[name]} {'on' if after else 'off'}"]
    if name in CHOICES:
        what, words = CHOICES[name]
        said = [words.get(str(value)) or _as_data(value) for value in (before, after)]
        return [f"changed {what} from {said[0]} to {said[1]}"]
    return [f"changed the setting {label(str(name))}"]


def settings_changed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """Hanna Laine switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day
    without asking."""
    changes = context.facts.get(CHANGES_FACT)
    listed = [change for change in changes if isinstance(change, dict)] if isinstance(changes, list) else []
    clauses = [clause for change in listed for clause in _clauses(change, context.profile)]
    return f"{_who(actor)} {'; '.join(clauses) if clauses else NOT_RECORDED}."


def supplier_settings_changed(actor: Actor, context: AuditContext, scope: Scope) -> str:
    """Never which setting, never a value: a limit and an allergen exclusion are the buyer's own."""
    return SUPPLIER_SENTENCE
