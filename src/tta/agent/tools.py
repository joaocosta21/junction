"""The four functions of the gateway the model may call, and the checks on what it asks for (SPEC 11).

Scores on the 20% "autonomy and controls". The model chooses the next function and, for an order, one
option of the offer. Everything else is bound here and decided by the gateway:
- the offer is built for the request the parser read, and for nothing else (`create_offer` takes no argument);
- an order names the top option (rank 1) of the latest offer of this run (`place_order` takes `option_id`
  only): the gateway ranks the options, the model does not choose among them (task FIX-9);
- one run asks for at most `MAX_OFFERS_PER_RUN` offers and places one order;
- when an order is refused because the offer is stale or has expired, the gateway has already made a fresh
  offer for the same request (`fresh_offer_id` in its problem): that offer becomes the run's latest, and the
  model is shown it, so it orders its top option without asking for another offer.
A call that breaks one of these is refused and becomes a failed step; nothing reaches the order book.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from tta.agent.summaries import (
    authority_sentence,
    authority_summary,
    gateway_refusal,
    offer_sentence,
    offer_summary,
    order_summary,
    refusal,
)
from tta.contracts.common import Identity, JsonDict
from tta.contracts.errors import InvalidRequest, OfferExpired, OfferStale, TtaError
from tta.contracts.offer import Offer
from tta.contracts.order import MAX_RECORD_ID_LENGTH, Order
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest

GET_AUTHORITY = "get_authority"
CREATE_OFFER = "create_offer"
PLACE_ORDER = "place_order"
GET_ORDER = "get_order"
OPTION_ID = "option_id"

TOOL_DECLARATIONS: tuple[JsonDict, ...] = (
    {
        "type": "function", "name": GET_AUTHORITY,
        "description": "Read what this agent may decide alone for its buyer: the spend limits, the allergen "
                       "exclusions and what always goes to a human. Takes no arguments.",
    },
    {
        "type": "function", "name": CREATE_OFFER,
        "description": "Get an offer for the buyer's request at fixed prices with current availability. "
                       "Takes no arguments: the offer is built for the request as it was read. Returns the "
                       "options by rank, each with the verdict of the buyer's policy.",
    },
    {
        "type": "function", "name": PLACE_ORDER,
        "description": "Order the option ranked 1 of the latest offer; any other option is refused. The "
                       "gateway decides whether the order is placed at once or waits for a human.",
        "parameters": {
            "type": "object",
            "properties": {
                OPTION_ID: {"type": "string", "description": "The option_id of the option ranked 1."},
            },
            "required": [OPTION_ID],
        },
    },
    {
        "type": "function", "name": GET_ORDER,
        "description": "Read the status of the order placed in this run. Takes no arguments.",
    },
)
FUNCTION_NAMES = tuple(str(tool["name"]) for tool in TOOL_DECLARATIONS)
MAX_OFFERS_PER_RUN = 2  # the first offer, and one more
FRESH_OFFER_ID = "fresh_offer_id"  # the extension member of an offer-stale or offer-expired problem

IDEMPOTENCY_PREFIX = "agent-run"
KEY_DIGEST_CHARACTERS = 16
MAX_PROPOSED_ARGUMENTS = 5  # how much of a refused call the trace keeps
MAX_PROPOSED_CHARACTERS = 60
_RECORD_ID = re.compile(rf"[A-Za-z0-9_-]{{1,{MAX_RECORD_ID_LENGTH}}}")  # an id as the gateway issues it

NOT_A_FUNCTION = "This is not a function of the gateway. The functions are: " + ", ".join(FUNCTION_NAMES) + "."
NO_ARGUMENTS = "{name} takes no arguments. {why}"
WHY_NO_AUTHORITY_ARGUMENT = "The authority is that of the caller's own buyer."
WHY_NO_OFFER_ARGUMENT = "The offer is built for the buyer's request as it was read, and for nothing else."
WHY_NO_ORDER_ARGUMENT = "It reads the order placed in this run."
OPTION_ID_ONLY = (
    "place_order takes option_id and nothing else: the option_id of an option of the latest offer, for "
    "example opt_1. The products, quantities and prices are those of the offer."
)
NO_OFFER_YET = "There is no offer in this run yet: call create_offer first."
NO_OPTION = "The latest offer has no option, so there is nothing to order."
ONLY_THE_TOP_OPTION = (
    "Only the option ranked 1 of the latest offer, {top}, may be ordered by the agent: the gateway ranks the "
    "options, and the agent does not choose among them. Nothing was ordered."
)
OFFERS_SPENT = "This run has asked for {count} offers, the most one run may. Order from the latest offer or stop."
FRESH_OFFER = "The gateway made a fresh offer for the same request, {offer_id}: order its option ranked 1."

logger = logging.getLogger(__name__)
NO_ORDER_YET = "There is no order in this run yet, so there is nothing to read."
ONE_ORDER_PER_RUN = "This run already placed order {order_id}. One run places one order."


@dataclass(frozen=True)
class RunState:
    """What one run holds: the request as it was read, the latest offer, the order once there is one."""

    request: PurchaseRequest
    run_id: str
    offer: Offer | None = None
    order: Order | None = None
    offers_asked: int = 0  # create_offer calls sent to the gateway


@dataclass(frozen=True)
class ToolOutcome:
    """One call and what came of it. `result` is shown to the model and kept in the trace."""

    ok: bool
    arguments: JsonDict  # what was sent to the gateway; for a call refused here, what the model proposed
    result: JsonDict
    sentence: str | None
    state: RunState
    by_gateway: bool = False  # a refusal of the gateway itself, not of the runner's checks


def _short(value: Any) -> Any:
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, str):
        return value[:MAX_PROPOSED_CHARACTERS]
    return f"<{type(value).__name__}>"


def _proposed(arguments: Mapping[str, Any]) -> JsonDict:
    """What the model proposed, cut short: it is untrusted text on its way into the trace."""
    kept = list(arguments.items())[:MAX_PROPOSED_ARGUMENTS]
    return {str(name)[:MAX_PROPOSED_CHARACTERS]: _short(value) for name, value in kept}


def _refused(arguments: Mapping[str, Any], state: RunState, detail: str) -> ToolOutcome:
    """A call the runner does not make. Reported as the gateway reports a request it cannot process."""
    return ToolOutcome(False, _proposed(arguments), refusal(InvalidRequest.slug, detail), detail, state)


def _refused_by_gateway(sent: JsonDict, state: RunState, error: TtaError) -> ToolOutcome:
    return ToolOutcome(False, sent, gateway_refusal(error), error.detail, state, by_gateway=True)


def _idempotency_key(state: RunState, offer_id: str, option_id: str) -> str:
    """One key per run, offer and option: asking twice for the same order gives the same order."""
    digest = hashlib.sha256(f"{offer_id}/{option_id}".encode()).hexdigest()[:KEY_DIGEST_CHARACTERS]
    return f"{IDEMPOTENCY_PREFIX}:{state.run_id}:{digest}"


class GatewayTools:
    """Makes the model's calls as the caller's identity, through the gateway service and nothing below it."""

    def __init__(self, gateway: GatewayService, identity: Identity) -> None:
        self._gateway = gateway
        self._identity = identity
        self._handlers: Mapping[str, Callable[[Mapping[str, Any], RunState], ToolOutcome]] = {
            GET_AUTHORITY: self._get_authority,
            CREATE_OFFER: self._create_offer,
            PLACE_ORDER: self._place_order,
            GET_ORDER: self._get_order,
        }

    def call(self, name: str, arguments: Mapping[str, Any], state: RunState) -> ToolOutcome:
        handler = self._handlers.get(name)
        if handler is None:
            return _refused(arguments, state, NOT_A_FUNCTION)
        return handler(arguments, state)

    def _get_authority(self, arguments: Mapping[str, Any], state: RunState) -> ToolOutcome:
        if arguments:
            return _refused(arguments, state, NO_ARGUMENTS.format(name=GET_AUTHORITY, why=WHY_NO_AUTHORITY_ARGUMENT))
        try:
            authority = self._gateway.get_authority(self._identity)
        except TtaError as error:
            return _refused_by_gateway({}, state, error)
        return ToolOutcome(True, {}, authority_summary(authority), authority_sentence(authority), state)

    def _create_offer(self, arguments: Mapping[str, Any], state: RunState) -> ToolOutcome:
        if arguments:
            return _refused(arguments, state, NO_ARGUMENTS.format(name=CREATE_OFFER, why=WHY_NO_OFFER_ARGUMENT))
        if state.order is not None:
            return _refused(arguments, state, ONE_ORDER_PER_RUN.format(order_id=state.order.order_id))
        if state.offers_asked >= MAX_OFFERS_PER_RUN:
            return _refused(arguments, state, OFFERS_SPENT.format(count=state.offers_asked))
        sent: JsonDict = {"request": state.request.model_dump(mode="json")}
        asked = replace(state, offers_asked=state.offers_asked + 1)
        try:
            offer = self._gateway.create_offer(self._identity, state.request)
        except TtaError as error:
            return _refused_by_gateway(sent, asked, error)
        return ToolOutcome(True, sent, offer_summary(offer), offer_sentence(offer), replace(asked, offer=offer))

    def _place_order(self, arguments: Mapping[str, Any], state: RunState) -> ToolOutcome:
        option_id = arguments.get(OPTION_ID)
        if set(arguments) != {OPTION_ID} or not isinstance(option_id, str) or not _RECORD_ID.fullmatch(option_id):
            return _refused(arguments, state, OPTION_ID_ONLY)
        if state.offer is None:
            return _refused(arguments, state, NO_OFFER_YET)
        if state.order is not None:
            return _refused(arguments, state, ONE_ORDER_PER_RUN.format(order_id=state.order.order_id))
        if not state.offer.options:
            return _refused(arguments, state, NO_OPTION)
        top = state.offer.options[0].option_id
        if option_id != top:
            return _refused(arguments, state, ONLY_THE_TOP_OPTION.format(top=top))
        offer_id = state.offer.offer_id
        sent: JsonDict = {"offer_id": offer_id, OPTION_ID: option_id}
        try:
            order = self._gateway.place_order(
                self._identity, offer_id, option_id, _idempotency_key(state, offer_id, option_id)
            )
        except (OfferStale, OfferExpired) as error:
            return self._fresh_offer(sent, state, error)
        except TtaError as error:
            return _refused_by_gateway(sent, state, error)
        return ToolOutcome(True, sent, order_summary(order), order.status_sentence, replace(state, order=order))

    def _fresh_offer(self, sent: JsonDict, state: RunState, error: TtaError) -> ToolOutcome:
        """The refusal, with the fresh offer the gateway made as the run's latest offer, when it made one."""
        fresh_id = error.extensions.get(FRESH_OFFER_ID)
        if not isinstance(fresh_id, str) or not _RECORD_ID.fullmatch(fresh_id):
            return _refused_by_gateway(sent, state, error)
        try:
            fresh = self._gateway.get_offer(self._identity, fresh_id)
        except TtaError as unreadable:
            logger.warning("The fresh offer %s could not be read: %s", fresh_id, unreadable.slug)
            return _refused_by_gateway(sent, state, error)
        result = {**gateway_refusal(error), FRESH_OFFER_ID: fresh.offer_id, "fresh_offer": offer_summary(fresh)}
        sentence = f"{error.detail} {FRESH_OFFER.format(offer_id=fresh.offer_id)}"
        return ToolOutcome(False, sent, result, sentence, replace(state, offer=fresh), by_gateway=True)

    def _get_order(self, arguments: Mapping[str, Any], state: RunState) -> ToolOutcome:
        if arguments:
            return _refused(arguments, state, NO_ARGUMENTS.format(name=GET_ORDER, why=WHY_NO_ORDER_ARGUMENT))
        if state.order is None:
            return _refused(arguments, state, NO_ORDER_YET)
        sent: JsonDict = {"order_id": state.order.order_id}
        try:
            order = self._gateway.get_order(self._identity, state.order.order_id)
        except TtaError as error:
            return _refused_by_gateway(sent, state, error)
        return ToolOutcome(True, sent, order_summary(order), order.status_sentence, replace(state, order=order))
