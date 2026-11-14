"""The audit facts of "suggestions shown" and "suggestion accepted" (P15 R4a), as plain dicts.

Pure functions: the gateway writes the events, with these as `facts` (the buyer's view) and `supplier_facts`
(Valio Aimo's view). Every value is JSON: strings, numbers as strings where they are decimals, lists, dicts.

What Valio Aimo may see (P15 section 4.2, DECISION 3; decision B13 of the run): that a suggestion was made, its
kind, product, quantity and counts, and whether it was accepted. Never why the guard dropped one, since a drop
for an allergen names what the buyer excludes: only how many were dropped, and for which kind of reason.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from tta.contracts.suggestion import Suggestion
from tta.suggestions.guard import DroppedSuggestion, DropReason
from tta.suggestions.service import SuggestionList

SHOWN_EVENT = "suggestions.shown"  # proposed names of the two events; the audit package owns the enum
ACCEPTED_EVENT = "suggestion.accepted"
# The reasons that say something about what the buyer excludes or requires: Valio Aimo's view groups them.
_BUYERS_OWN = frozenset({DropReason.ALLERGEN_NOT_RULED_OUT.value, DropReason.DIETARY_CLAIM_MISSING.value,
                         DropReason.ADDS_ALLERGEN.value, "ALLERGEN_DECLARED", "ALLERGEN_NOT_STATED"})
BUYERS_REQUIREMENT = "BUYER_REQUIREMENT"


def suggestions_shown_facts(found: SuggestionList, *, offer_id: str) -> dict[str, Any]:
    """The facts of "suggestions shown" for the buyer: each one shown with its evidence, each one the guard
    dropped with the reason, each one held back beyond the three."""
    return {
        "event": SHOWN_EVENT,
        "offer_id": offer_id,
        "shown": [_shown(suggestion) for suggestion in found.shown],
        "dropped": [_dropped(dropped) for dropped in found.dropped],
        "held_back": [_brief(suggestion) for suggestion in found.held_back],
        "notes": list(found.notes),
        "synthetic_history": any(suggestion.evidence.synthetic for suggestion in found.shown),
    }


def suggestions_shown_supplier_facts(found: SuggestionList, *, offer_id: str) -> dict[str, Any]:
    """The same event for Valio Aimo: kind, product, quantity and counts of what was shown; of what was dropped
    only the count per reason, with every reason about the buyer's own requirements under one name."""
    reasons = Counter(BUYERS_REQUIREMENT if dropped.reason in _BUYERS_OWN else dropped.reason
                      for dropped in found.dropped)
    return {
        "event": SHOWN_EVENT,
        "offer_id": offer_id,
        "shown": [{**_brief(suggestion), "orders_considered": suggestion.evidence.orders_considered,
                   "orders_matching": suggestion.evidence.orders_matching} for suggestion in found.shown],
        "dropped_count": len(found.dropped),
        "dropped_by_reason": dict(sorted(reasons.items())),
    }


def suggestion_accepted_facts(suggestion: Suggestion, *, offer_id: str, new_offer_id: str,
                              accepted_by: str) -> dict[str, Any]:
    """The facts of "suggestion accepted": which suggestion of which offer, who accepted it, and the new offer
    its `accept_request` built. Accepting is not an approval: the new offer meets every rule again."""
    return {
        "event": ACCEPTED_EVENT,
        "offer_id": offer_id,
        "new_offer_id": new_offer_id,
        "accepted_by": accepted_by,
        **_shown(suggestion),
    }


def suggestion_accepted_supplier_facts(suggestion: Suggestion, *, offer_id: str, new_offer_id: str) -> dict[str, Any]:
    """The same event for Valio Aimo: no name of who accepted, no evidence values."""
    return {"event": ACCEPTED_EVENT, "offer_id": offer_id, "new_offer_id": new_offer_id, **_brief(suggestion)}


def _brief(suggestion: Suggestion) -> dict[str, Any]:
    return {
        "suggestion_id": suggestion.suggestion_id,
        "kind": suggestion.kind.value,
        "serves": suggestion.serves.value,
        "product_id": suggestion.product_id,
        "quantity": str(suggestion.quantity),
        "unit": suggestion.unit.value,
        "replaces_product_id": suggestion.replaces_product_id,
    }


def _shown(suggestion: Suggestion) -> dict[str, Any]:
    effect = suggestion.effect
    return {
        **_brief(suggestion),
        "name": suggestion.name,
        "sentence": suggestion.sentence,
        "evidence": suggestion.evidence.model_dump(mode="json"),
        "net_change_eur": None if effect is None or effect.net_change_eur is None else str(effect.net_change_eur),
        "stock_confirmed": suggestion.stock_confirmed,
        "checks": list(suggestion.checks),
    }


def _dropped(dropped: DroppedSuggestion) -> dict[str, Any]:
    return dropped.model_dump(mode="json")
