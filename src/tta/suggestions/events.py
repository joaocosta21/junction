"""The audit events "suggestions shown" and "suggestion accepted" (P15 R4a, R4b): their facts as plain dicts, and
the two functions the gateway calls to write them.

    record_suggestions_shown(audit, actor, found, offer_id=offer.offer_id, profile_id=profile.profile_id)
    record_suggestion_accepted(audit, actor, suggestion, offer_id=..., new_offer_id=new.offer_id, profile_id=...)

The facts functions are pure: `*_facts` is the buyer's view, `*_supplier_facts` Valio Aimo's. Every value is JSON:
strings, numbers as strings where they are decimals, lists, dicts. The audit package builds each reader's sentence
from them (`tta.audit.suggestion_sentences`).

What Valio Aimo may see (P15 section 4.2, DECISION 3; decision B13 of the run): that a suggestion was made, its
kind, product, quantity, and whether it was accepted; how many were shown, dropped and held back. Never why the
guard dropped one, since a drop for an allergen names what the buyer excludes: only how many were dropped, and
for which kind of reason. Never a figure of the buyer's history (the orders counted, the quantities a median was
taken from). Never that its own suggestion stayed silent (decision B32), nor why: that is the buyer's log only.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from tta.audit.facts import SUPPLIER_VIEW
from tta.contracts.audit import Actor, AuditContext, AuditEvent, AuditEventType
from tta.contracts.ports import AuditSink
from tta.contracts.suggestion import Suggestion
from tta.suggestions.guard import DroppedSuggestion, DropReason
from tta.suggestions.ranking import HeldBackSuggestion
from tta.suggestions.service import SuggestionList

SHOWN_EVENT = AuditEventType.SUGGESTIONS_SHOWN.value
ACCEPTED_EVENT = AuditEventType.SUGGESTION_ACCEPTED.value
SHOWN_KEY = "suggestions"  # the key of the event's facts, in each reader's view
ACCEPTED_KEY = "suggestion"
# The reasons that say something about what the buyer excludes or requires: Valio Aimo's view groups them.
_BUYERS_OWN = frozenset({DropReason.ALLERGEN_NOT_RULED_OUT.value, DropReason.DIETARY_CLAIM_MISSING.value,
                         DropReason.ADDS_ALLERGEN.value, "ALLERGEN_DECLARED", "ALLERGEN_NOT_STATED",
                         "CLAIM_CONTRADICTED"})
BUYERS_REQUIREMENT = "BUYER_REQUIREMENT"
# Valio Aimo's own suggestion left silent (decision B32): in the buyer's log, never in Valio Aimo's view.
_SILENCED = frozenset({DropReason.OTHER_PACK_KIND.value, DropReason.ONE_UNIT_IN_STOCK.value})


def record_suggestions_shown(audit: AuditSink, actor: Actor, found: SuggestionList, *, offer_id: str,
                             profile_id: str | None = None) -> AuditEvent:
    """Write "suggestions shown" for one offer: what was shown, dropped and held back, each reader its own view.
    `actor`: who the suggestions were shown to (the agent or the person who asked for the offer)."""
    facts = {SHOWN_KEY: suggestions_shown_facts(found, offer_id=offer_id),
             SUPPLIER_VIEW: {SHOWN_KEY: suggestions_shown_supplier_facts(found, offer_id=offer_id)}}
    context = AuditContext(offer_id=offer_id, profile_id=profile_id, facts=facts)
    return audit.record(AuditEventType.SUGGESTIONS_SHOWN, actor, context)


def record_suggestion_accepted(audit: AuditSink, actor: Actor, suggestion: Suggestion, *, offer_id: str,
                               new_offer_id: str, profile_id: str | None = None) -> AuditEvent:
    """Write "suggestion accepted": `actor` posted the suggestion's `accept_request` and got offer
    `new_offer_id`. Accepting is not an approval: the new offer meets every rule again."""
    accepted_by = actor.display_name or actor.id
    facts = {
        ACCEPTED_KEY: suggestion_accepted_facts(suggestion, offer_id=offer_id, new_offer_id=new_offer_id,
                                                accepted_by=accepted_by),
        SUPPLIER_VIEW: {ACCEPTED_KEY: suggestion_accepted_supplier_facts(suggestion, offer_id=offer_id,
                                                                         new_offer_id=new_offer_id)},
    }
    context = AuditContext(offer_id=offer_id, profile_id=profile_id, facts=facts)
    return audit.record(AuditEventType.SUGGESTION_ACCEPTED, actor, context)


def suggestions_shown_facts(found: SuggestionList, *, offer_id: str) -> dict[str, Any]:
    """The facts of "suggestions shown" for the buyer: each one shown with its evidence, each one the guard
    dropped with the reason, each one held back beyond the three."""
    return {
        "event": SHOWN_EVENT,
        "offer_id": offer_id,
        "shown": [_shown(suggestion) for suggestion in found.shown],
        "dropped": [_dropped(dropped) for dropped in found.dropped],
        "held_back": [_held(held) for held in found.held_back],
        "notes": list(found.notes),
        "synthetic_history": any(suggestion.evidence.synthetic for suggestion in found.shown),
    }


def suggestions_shown_supplier_facts(found: SuggestionList, *, offer_id: str) -> dict[str, Any]:
    """The same event for Valio Aimo: kind, product and quantity of what was shown and held back; of what was
    dropped only the count per reason, with every reason about the buyer's own requirements under one name. Its
    own suggestion left silent is not in it."""
    dropped = [each for each in found.dropped if each.reason not in _SILENCED]
    reasons = Counter(BUYERS_REQUIREMENT if each.reason in _BUYERS_OWN else each.reason for each in dropped)
    return {
        "event": SHOWN_EVENT,
        "offer_id": offer_id,
        "shown": [_brief(suggestion) for suggestion in found.shown],
        "dropped_count": len(dropped),
        "dropped_by_reason": dict(sorted(reasons.items())),
        "held_back": [{**_brief(held.suggestion), "reason": held.reason.value} for held in found.held_back],
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
    """What either reader may see of a suggestion. The name is the product's, from Valio Aimo's own catalog."""
    return {
        "suggestion_id": suggestion.suggestion_id,
        "kind": suggestion.kind.value,
        "serves": suggestion.serves.value,
        "product_id": suggestion.product_id,
        "name": suggestion.name,
        "quantity": str(suggestion.quantity),
        "unit": suggestion.unit.value,
        "replaces_product_id": suggestion.replaces_product_id,
    }


def _shown(suggestion: Suggestion) -> dict[str, Any]:
    effect = suggestion.effect
    return {
        **_brief(suggestion),
        "sentence": suggestion.sentence,
        "evidence": suggestion.evidence.model_dump(mode="json"),
        "net_change_eur": None if effect is None or effect.net_change_eur is None else str(effect.net_change_eur),
        "stock_confirmed": suggestion.stock_confirmed,
        "checks": list(suggestion.checks),
    }


def _held(held: HeldBackSuggestion) -> dict[str, Any]:
    return {**_brief(held.suggestion), "reason": held.reason.value, "summary": held.summary}


def _dropped(dropped: DroppedSuggestion) -> dict[str, Any]:
    return dropped.model_dump(mode="json")
