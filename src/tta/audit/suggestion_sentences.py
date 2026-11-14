"""The sentences of the two suggestion events (P15 R4a, R4b), for the buyer and for Valio Aimo.

What the context carries (`tta.suggestions.events` writes it):

    suggestions.shown     offer_id · facts: suggestions (the buyer's view) · supplier_view.suggestions (Valio's)
    suggestion.accepted   offer_id · facts: suggestion (the buyer's view) · supplier_view.suggestion (Valio's)

The buyer reads each suggestion shown by kind, product, quantity and what it adds or saves; each one not shown
with the reason in a few words; each one held back with its reason. Valio Aimo reads counts and kinds, its own
suggestion by name, the drops counted by kind of reason with every reason about the buyer's own requirements under
one name: never which allergen or claim, never a figure of the buyer's history. The facts are data written by the
gateway; every value is checked for its type, and a value of another shape is read as not recorded.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from tta.audit.facts import SUPPLIER_VIEW
from tta.audit.phrases import (
    MAX_NAME_CHARACTERS,
    actor_text,
    amount,
    capital,
    count,
    ended,
    joined,
    label,
    money,
    plain,
)
from tta.audit.readers import ROLE_SEPARATOR, supplier_role
from tta.audit.scope import Scope
from tta.audit.supplier_decisions import REASON_WORDS, buyers_roles
from tta.contracts.audit import Actor, ActorKind, AuditContext
from tta.contracts.common import Unit

SHOWN_KEY = "suggestions"
ACCEPTED_KEY = "suggestion"
OWN_KIND = "FROM_SUPPLIER"
KIND_WORDS = {
    "FORGOTTEN_ITEM": "forgotten item",
    "USUAL_PRODUCT": "usual product",
    "USUAL_QUANTITY": "usual quantity",
    "CHEAPER_SAME_FORMULA": "cheaper product with the same formula",
    "LARGER_PACK": "larger pack",
    "QUANTITY_TREND": "trend",
    "REORDER_DUE": "reorder reminder",
}
OWN_WORDS = "Valio Aimo's own suggestion"
OTHER_KIND = "suggestion"
BUYERS_REQUIREMENT = "BUYER_REQUIREMENT"  # `tta.suggestions.events`: every drop about what the buyer excludes
# Why a suggestion was dropped, after its count, for Valio Aimo: "1 for a requirement of the buyer's".
SUPPLIER_DROP_WORDS = {
    BUYERS_REQUIREMENT: "for a requirement of the buyer's (which one is not shown)",
    "UNKNOWN_PRODUCT": "not in the catalog",
    "ALREADY_ORDERED": "already in an order for the same delivery date",
    "FORMULA_NOT_KEPT": "not keeping the formula of the product it would replace",
    "STOCK_NOT_CONFIRMED": "with stock that is not confirmed for the date",
    "STOCK_TOO_LOW": "with too little confirmed stock for the quantity",
    **{reason.value: words for reason, words in REASON_WORDS.items()},
}
HELD_BACK_RULE = "one suggestion per kind and three at most are shown"
MAX_SUMMARY_CHARACTERS = 200  # a reason in a few words, as `tta.suggestions.reasons` writes it
NOT_AN_APPROVAL = "accepting is not an approval"


def _entries(value: Any) -> list[Mapping[str, Any]] | None:
    """A list of dicts, or None for a value of any other shape."""
    if not isinstance(value, list) or not all(isinstance(each, dict) for each in value):
        return None
    return value


def _text(entry: Mapping[str, Any], key: str) -> str | None:
    value = entry.get(key)
    return value if isinstance(value, str) and value.strip() else None


def _decimal(value: Any) -> Decimal | None:
    if not isinstance(value, str | int):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _product(entry: Mapping[str, Any]) -> str:
    """Arla Pro Cooking cream 10% 1 L UHT lactose free (463797)."""
    name, product_id = _text(entry, "name"), _text(entry, "product_id")
    if name and product_id:
        return f"{plain(name, MAX_NAME_CHARACTERS)} ({label(product_id)})"
    return f"product {label(product_id)}" if product_id else "a product"


def _a_kind(entry: Mapping[str, Any]) -> str:
    kind = entry.get("kind")
    return OWN_WORDS if kind == OWN_KIND else f"a {KIND_WORDS.get(str(kind), OTHER_KIND)}"


def _the_kind(entry: Mapping[str, Any]) -> str:
    kind = entry.get("kind")
    return OWN_WORDS if kind == OWN_KIND else f"the {KIND_WORDS.get(str(kind), OTHER_KIND)}"


def _quantity(entry: Mapping[str, Any]) -> str:
    quantity, unit = _decimal(entry.get("quantity")), entry.get("unit")
    return f", {amount(quantity, Unit(unit))}" if quantity is not None and unit in tuple(Unit) else ""


def _money(entry: Mapping[str, Any]) -> str:
    change = _decimal(entry.get("net_change_eur"))
    if change is None or change == 0:
        return ""
    return f", {money(abs(change))} {'more' if change > 0 else 'less'} before tax"


def _shown_item(entry: Mapping[str, Any]) -> str:
    """the cheaper product with the same formula Oatly iKaffe Oat drink 1,5L (473278) in place of 468319, 30
    litres, €42.00 less before tax."""
    replaced = _text(entry, "replaces_product_id")
    instead = f" in place of {label(replaced)}" if replaced else ""
    return f"{_the_kind(entry)} {_product(entry)}{instead}{_quantity(entry)}{_money(entry)}"


def _with_reason(entry: Mapping[str, Any]) -> str:
    """AIMO NATURAL YOGURT 5KG 2% LACTOSE FREE (464517), a forgotten item: its data does not rule out …"""
    summary = _text(entry, "summary")
    reason = _text(entry, "reason")
    why = plain(summary, MAX_SUMMARY_CHARACTERS) if summary else f"reason {label(reason)}" if reason else ""
    return f"{_product(entry)}, {_a_kind(entry)}{f': {why}' if why else ''}"


def _offer(scope: Scope, word: str = "with") -> str:
    return f" {word} offer {label(scope.offer_id)}" if scope.offer_id else ""


def _was(number: int) -> str:
    return f"{number:,} {'was' if number == 1 else 'were'}"


def _view(context: AuditContext, key: str, for_supplier: bool) -> Mapping[str, Any] | None:
    facts: Any = context.facts
    if for_supplier:
        facts = facts.get(SUPPLIER_VIEW)
    found = facts.get(key) if isinstance(facts, dict) else None
    return found if isinstance(found, dict) else None


def suggestions_shown(actor: Actor, context: AuditContext, scope: Scope) -> str:
    facts = _view(context, SHOWN_KEY, for_supplier=False)
    lists = [_entries(facts.get(key)) for key in ("shown", "dropped", "held_back")] if facts else [None]
    if facts is None or any(each is None for each in lists):
        return f"Suggestions were shown{_offer(scope)}; which ones is not recorded."
    shown, dropped, held = lists
    said = [f"{count(len(shown), 'suggestion was', 'suggestions were')} shown{_offer(scope)}: "
            f"{'; '.join(_shown_item(each) for each in shown)}." if shown
            else f"No suggestion was shown{_offer(scope)}."]
    if dropped:
        said.append(f"{_was(len(dropped))} not shown: {'; '.join(_with_reason(each) for each in dropped)}.")
    if held:
        said.append(f"{_was(len(held))} held back: {'; '.join(_with_reason(each) for each in held)}.")
    if facts.get("synthetic_history") is True:
        said.append("From a synthetic order history.")
    notes = facts.get("notes")
    said += [ended(note) for note in notes if isinstance(note, str) and note.strip()] if isinstance(notes, list) else []
    return " ".join(said)


def _supplier_kind(entry: Mapping[str, Any]) -> str:
    return f"{OWN_WORDS} {_product(entry)}" if entry.get("kind") == OWN_KIND else _a_kind(entry)


def _supplier_dropped(facts: Mapping[str, Any]) -> str:
    total, by_reason = facts.get("dropped_count"), facts.get("dropped_by_reason")
    if type(total) is not int or total <= 0:
        return ""
    reasons = by_reason if isinstance(by_reason, dict) else {}
    parts = [f"{number:,} {SUPPLIER_DROP_WORDS.get(str(reason), f'for reason {label(str(reason))}')}"
             for reason, number in reasons.items() if type(number) is int and number > 0]
    return f" {_was(total)} not shown{f': {joined(parts)}' if parts else ''}."


def _supplier_held(facts: Mapping[str, Any]) -> str:
    held = _entries(facts.get("held_back")) or []
    if not held:
        return ""
    own = [each for each in held if each.get("kind") == OWN_KIND]
    named = f" Held back: {OWN_WORDS} {_product(own[0])}." if own else ""
    verb = "was" if len(held) == 1 else "were"
    return f" {len(held):,} more passed every check and {verb} held back: {HELD_BACK_RULE}.{named}"


def supplier_suggestions_shown(actor: Actor, context: AuditContext, scope: Scope) -> str:
    facts = _view(context, SHOWN_KEY, for_supplier=True)
    shown = _entries(facts.get("shown")) if facts else None
    to_buyer = f"to the buyer{_offer(scope)}"
    if facts is None or shown is None:
        return f"Suggestions were shown {to_buyer}; which ones is not recorded."
    start = (f"{count(len(shown), 'suggestion was', 'suggestions were')} shown {to_buyer}: "
             f"{joined(_supplier_kind(each) for each in shown)}." if shown else f"No suggestion was shown {to_buyer}.")
    return f"{start}{_supplier_dropped(facts)}{_supplier_held(facts)}"


def _new_offer(facts: Mapping[str, Any]) -> str | None:
    new_offer = _text(facts, "new_offer_id")
    return label(new_offer) if new_offer else None


def suggestion_accepted(actor: Actor, context: AuditContext, scope: Scope) -> str:
    facts = _view(context, ACCEPTED_KEY, for_supplier=False)
    if facts is None:
        return f"{actor_text(actor)} accepted a suggestion{_offer(scope, 'of')}; which one is not recorded."
    new_offer = _new_offer(facts)
    became = f"The amended request became offer {new_offer}" if new_offer else "The amended request is a new offer"
    return (f"{actor_text(actor)} accepted {_shown_item(facts)}, suggested{_offer(scope)}. {became}, checked "
            f"against every rule again: {NOT_AN_APPROVAL}.")


def _supplier_actor(actor: Actor) -> str:
    """The buyer's agent · the buyer's purchasing manager · the gateway: never a name."""
    if actor.kind is ActorKind.AGENT:
        return "The buyer's agent"
    if actor.kind is ActorKind.SYSTEM:
        return "The gateway"
    role = supplier_role(actor.role)
    return capital(buyers_roles(role.split(ROLE_SEPARATOR) if role else ()))


def supplier_suggestion_accepted(actor: Actor, context: AuditContext, scope: Scope) -> str:
    facts = _view(context, ACCEPTED_KEY, for_supplier=True)
    who = _supplier_actor(actor)
    if facts is None:
        return f"{who} accepted a suggestion{_offer(scope, 'of')}; which one is not recorded."
    what = f"{_supplier_kind(facts)}," if facts.get("kind") == OWN_KIND else _a_kind(facts)
    new_offer = _new_offer(facts)
    became = f" The amended request became offer {new_offer}." if new_offer else ""
    return f"{who} accepted {what} suggested{_offer(scope)}.{became}"
