"""Suggestions on an offer: computed after the offer is built, shown on it, written to the audit trail (P15 R3, R4b).

Scores on the 20% "solving the problem and user need" (the forgotten item, the cheaper line, the trend: less manual
correction) and on the 20% "autonomy and controls" (a suggestion never adds itself to an order, and what was shown,
dropped and accepted is logged for both readers). Nothing here picks, checks or words a suggestion: that is
`tta.suggestions.suggestions_for`, whose guard puts each one through the buyer's allergen rule, claims, formula and
confirmed stock. This module gives it the customer, the buyer's standing orders and the products already ordered
for the same delivery date, puts what it shows on the offer, and calls the audit writers.

    offer, outcome = suggesting.add_to(identity, offer)      # before the offer is stored
    suggesting.record(identity, offer, outcome)              # inside the offer's unit of work

Accepting a suggestion is a new `POST /v1/offers` with its `accept_request`, which carries the suggestion's id
(`PurchaseRequest.accepted_suggestion_id`, stamped here). The acceptance is recorded when an earlier offer of the
same buyer showed that suggestion and the request is its `accept_request` unchanged; otherwise the offer says in a
note that nothing was recorded. A buyer with no customer file (a visitor's own kitchen) gets no suggestion. A
failure in the suggestions never fails the offer: it is returned without them, with a note.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import Field, ValidationError

from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEventType
from tta.contracts.common import Contract, Identity, OrderStatus
from tta.contracts.customer import Customer
from tta.contracts.offer import Offer
from tta.contracts.ports import AuditSink, PolicyEngine, Store
from tta.contracts.request import PurchaseRequest
from tta.contracts.suggestion import Suggestion
from tta.customers import shipped_customer
from tta.orders.access import actor_of
from tta.suggestions import DroppedSuggestion, SuggestionList, SuggestionPorts, suggestions_for
from tta.suggestions.events import record_suggestion_accepted, record_suggestions_shown

SHOWN_TYPE = f"{EVENT_TYPE_PREFIX}{AuditEventType.SUGGESTIONS_SHOWN.value}"
SHOWN_KEY = "suggestions"  # the key of the event's facts (`tta.suggestions.events`)
COMMITTED = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)  # an order placed, or waiting for a person
NEVER_ADDED = (
    "Suggestions never add themselves to an order: accept one by sending its `accept_request` as a new request."
)
NOT_COMPUTED = (
    "No suggestion was computed for this offer: working them out failed inside the gateway, and the failure is "
    "logged. The offer itself is complete."
)
SUPPLIER_NOT_ASKED = "The suggestions of offer %s were not computed, the supplier could not be asked: %s"
LOOKUP_FAILED = (
    "The request names suggestion {suggestion_id} as accepted, but looking up the offer that showed it failed "
    "inside the gateway (the failure is logged): no acceptance was recorded. The offer is built as for any request."
)
SUGGESTIONS_OFF = (
    "The request names suggestion {suggestion_id} as accepted, but suggestions are off in this mode, so the "
    "acceptance was not recorded. The offer is built as for any request."
)
REASONS_NOT_READ = (
    "What this offer did not show, and why, could not be read back from its audit event: the lists of dropped and "
    "held-back suggestions here are empty for that reason, not because nothing was dropped."
)
NOT_SHOWN_BEFORE = (
    "The request names suggestion {suggestion_id} as accepted, but no earlier offer of this buyer showed it: no "
    "acceptance was recorded. The offer is built as for any request."
)
NOT_THE_ACCEPT_REQUEST = (
    "The request names suggestion {suggestion_id} as accepted, but it differs from that suggestion's "
    "accept_request on offer {offer_id}: no acceptance was recorded. The offer is built as for any request."
)

CustomerOf = Callable[[Identity], Customer | None]

logger = logging.getLogger(__name__)


def customer_on_file(identity: Identity) -> Customer | None:
    """The customer file of the caller's buyer profile; None for a buyer without one."""
    return shipped_customer(identity.profile_id) if identity.profile_id else None


class HeldBack(Contract):
    """A suggestion that passed every check and is not shown: one per kind and three in all are (decision B32)."""

    suggestion_id: str
    kind: str
    product_id: str
    name: str
    reason: str
    summary: str = ""


class OfferSuggestionsView(Contract):
    """What an offer suggested, for the buyer: what it shows, and what it does not show with the reason."""

    offer_id: str
    suggestions: tuple[Suggestion, ...] = Field(default=(), description="As on the offer: at most three")
    dropped: tuple[DroppedSuggestion, ...] = Field(
        default=(), description="Why not: what a check did not let through, each with the reason in one sentence"
    )
    held_back: tuple[HeldBack, ...] = ()
    notes: tuple[str, ...] = Field(
        default=(), description="Why nothing was computed, or that the reasons could not be read back"
    )
    note: str = NEVER_ADDED


@dataclass(frozen=True)
class Accepted:
    """The suggestion a request accepts, and the earlier offer that showed it."""

    suggestion: Suggestion
    offer_id: str


@dataclass(frozen=True)
class Outcome:
    """What `add_to` found for one offer, for `record`."""

    found: SuggestionList | None = None  # None: no customer file; notes only: the suggestions were not computed
    accepted: Accepted | None = None


def _stamped(suggestion: Suggestion) -> Suggestion:
    """The suggestion with its own id in its `accept_request`, so the gateway knows an acceptance when it arrives."""
    if suggestion.accept_request is None:
        return suggestion
    accept = suggestion.accept_request.model_copy(update={"accepted_suggestion_id": suggestion.suggestion_id})
    return suggestion.model_copy(update={"accept_request": accept})


def without_acceptance(request: PurchaseRequest) -> PurchaseRequest:
    """The request without the suggestion it accepted: for an offer rebuilt from a stored request."""
    if request.accepted_suggestion_id is None:
        return request
    return request.model_copy(update={"accepted_suggestion_id": None})


def acceptance_not_recorded(offer: Offer) -> Offer:
    """Where suggestions are not wired (live mode): an offer whose request names an accepted suggestion says in a
    note that nothing was recorded; any other offer is returned as it is."""
    suggestion_id = offer.request.accepted_suggestion_id
    if suggestion_id is None:
        return offer
    return offer.model_copy(update={"notes": (*offer.notes, SUGGESTIONS_OFF.format(suggestion_id=suggestion_id))})


def _entries(value: Any) -> list[Mapping[str, Any]]:
    """A stored list of objects; anything of another shape reads as empty."""
    return [each for each in value if isinstance(each, dict)] if isinstance(value, list) else []


@dataclass(frozen=True)
class OfferSuggestions:
    """The suggestions of the offers of one order book."""

    ports: SuggestionPorts
    policy: PolicyEngine
    store: Store
    audit: AuditSink
    supplier_suggestions: bool = True  # Valio Aimo's own suggestion (decision B31; `TTA_SUPPLIER_SUGGESTIONS`)
    customer_of: CustomerOf = customer_on_file

    def add_to(self, identity: Identity, offer: Offer) -> tuple[Offer, Outcome]:
        """The offer with its suggestions, and what `record` writes once the offer is stored. Never raises."""
        notes: list[str] = []
        accepted = self._accepted(offer, notes)
        found = self._found(identity, offer, notes)
        shown = found.shown if found is not None else ()
        if not shown and not notes:
            return offer, Outcome(found=found, accepted=accepted)
        update = {"suggestions": shown, "notes": (*offer.notes, *notes)}
        return offer.model_copy(update=update), Outcome(found=found, accepted=accepted)

    def record(self, identity: Identity, offer: Offer, outcome: Outcome) -> None:
        """Write "suggestions shown" when the offer shows, drops or holds back any, and also when they could not
        be computed (the event then holds the reason in `notes`, so the trail tells "nothing to suggest" from
        "not computed"); and "suggestion accepted" when its request accepted one. Called inside the unit of work
        that stores the offer."""
        actor, found = actor_of(identity), outcome.found
        if found is not None and (found.shown or found.dropped or found.held_back or found.notes):
            record_suggestions_shown(self.audit, actor, found, offer_id=offer.offer_id, profile_id=offer.profile_id)
        if outcome.accepted is not None:
            record_suggestion_accepted(
                self.audit, actor, outcome.accepted.suggestion, offer_id=outcome.accepted.offer_id,
                new_offer_id=offer.offer_id, profile_id=offer.profile_id,
            )

    def view(self, offer: Offer) -> OfferSuggestionsView:
        """What the offer suggested and what it did not show, read back from its "suggestions shown" event. The
        event is the buyer's own record: this view is never the supplier's."""
        facts: Mapping[str, Any] = {}
        for event in self.store.list_audit_events(offer_id=offer.offer_id):
            recorded = event.data.facts.get(SHOWN_KEY)
            if event.type == SHOWN_TYPE and isinstance(recorded, dict) and recorded.get("offer_id") == offer.offer_id:
                facts = recorded
        recorded = facts.get("notes")
        notes = tuple(each for each in recorded if isinstance(each, str)) if isinstance(recorded, list) else ()
        try:
            dropped = tuple(DroppedSuggestion.model_validate(each) for each in _entries(facts.get("dropped")))
            held = tuple(HeldBack.model_validate({name: each.get(name) for name in HeldBack.model_fields
                                                  if each.get(name) is not None})
                         for each in _entries(facts.get("held_back")))
        except ValidationError:  # an event of another shape: the offer's own list is still the answer
            logger.warning("The suggestions event of offer %s cannot be read back.", offer.offer_id)
            dropped, held, notes = (), (), (*notes, REASONS_NOT_READ)
        return OfferSuggestionsView(offer_id=offer.offer_id, suggestions=offer.suggestions, dropped=dropped,
                                    held_back=held, notes=notes)

    # --- computing ----------------------------------------------------------------------------------------

    def _found(self, identity: Identity, offer: Offer, notes: list[str]) -> SuggestionList | None:
        try:
            customer = self.customer_of(identity)
            if customer is None:
                return None
            found = suggestions_for(
                customer, offer.request, offer, profile=self.policy.get_profile(offer.profile_id), ports=self.ports,
                standing_orders=self.store.list_standing_orders(offer.profile_id),
                already_ordered=self._already_ordered(offer), supplier_suggestions=self.supplier_suggestions,
            )
        except Exception:  # a suggestion is an extra: whatever fails here, the offer is answered
            logger.exception("The suggestions of offer %s could not be computed.", offer.offer_id)
            notes.append(NOT_COMPUTED)
            return SuggestionList(notes=(NOT_COMPUTED,))  # recorded: the trail says they were not computed
        for note in found.notes:  # `suggestions_for` caught a supplier that could not be asked
            logger.warning(SUPPLIER_NOT_ASKED, offer.offer_id, note)
        notes.extend(found.notes)
        return found.model_copy(update={"shown": tuple(_stamped(each) for each in found.shown)})

    def _already_ordered(self, offer: Offer) -> frozenset[str]:
        """The products of this buyer's orders, placed or waiting for a person, for the same delivery: the date
        the request needs the goods by, and each delivery date of any option of the offer (a request with no date
        has only those)."""
        dates = {line.availability.available_date for option in offer.options for line in option.lines}
        dates.add(offer.request.needed_by)
        dates.discard(None)
        return frozenset(
            line.product_id
            for order in self.store.list_orders(profile_id=offer.profile_id) if order.status in COMMITTED
            for line in order.option.lines if line.availability.available_date in dates
        )

    # --- accepting ----------------------------------------------------------------------------------------

    def _accepted(self, offer: Offer, notes: list[str]) -> Accepted | None:
        """The suggestion the offer's request accepts: shown by an earlier offer of the same buyer, and sent as its
        `accept_request` unchanged. Anything else is said in a note and not recorded."""
        suggestion_id = offer.request.accepted_suggestion_id
        if suggestion_id is None:
            return None
        try:
            shown = self._last_shown(offer.profile_id, suggestion_id)
        except Exception:
            logger.exception("The suggestion offer %s accepts could not be looked up.", offer.offer_id)
            notes.append(LOOKUP_FAILED.format(suggestion_id=suggestion_id))
            return None
        if shown is None:
            notes.append(NOT_SHOWN_BEFORE.format(suggestion_id=suggestion_id))
            return None
        if shown.suggestion.accept_request != offer.request:
            notes.append(NOT_THE_ACCEPT_REQUEST.format(suggestion_id=suggestion_id, offer_id=shown.offer_id))
            return None
        return shown

    def _last_shown(self, profile_id: str, suggestion_id: str) -> Accepted | None:
        """The newest offer of this buyer that showed the suggestion, found through the audit trail."""
        for event in reversed(self.store.list_audit_events(profile_id=profile_id)):
            recorded = event.data.facts.get(SHOWN_KEY)
            if event.type != SHOWN_TYPE or not isinstance(recorded, dict) or event.data.offer_id is None:
                continue
            if not any(each.get("suggestion_id") == suggestion_id for each in _entries(recorded.get("shown"))):
                continue
            offer = self.store.get_offer(event.data.offer_id)
            if offer is None or offer.profile_id != profile_id:
                continue
            for suggestion in offer.suggestions:
                if suggestion.suggestion_id == suggestion_id:
                    return Accepted(suggestion=suggestion, offer_id=offer.offer_id)
        return None
