"""The four functions of the gateway the model may call, and the checks on what it asks for (SPEC 11).

Scores on the 20% "autonomy and controls". The model chooses the next function and, for an order, one
option of the offer. Everything else is bound here and decided by the gateway:
- the offer is built for the request the parser read, and for nothing else (`create_offer` takes no argument);
- an order names an option of the latest offer of this run (`place_order` takes `option_id` only), and the
  gateway refuses an option it never issued;
- one run places one order.
A call that breaks one of these is refused and becomes a failed step; nothing reaches the order book.
"""

from __future__ import annotations

import hashlib
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
from tta.contracts.errors import InvalidRequest, TtaError
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
        "description": "Order one option of the latest offer. The gateway decides whether the order is "
                       "placed at once or waits for a human.",
        "parameters": {
            "type": "object",
            "properties": {
                OPTION_ID: {"type": "string", "description": "The option_id of an option of the latest offer."},
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
NO_ORDER_YET = "There is no order in this run yet, so there is nothing to read."
ONE_ORDER_PER_RUN = "This run already placed order {order_id}. One run places one order."


@dataclass(frozen=True)
class RunState:
    """What one run holds: the request as it was read, the latest offer, the order once there is one."""

    request: PurchaseRequest
    run_id: str
    offer: Offer | None = None
    order: Order | None = None


@dataclass(frozen=True)
class ToolOutcome:
    """One call and what came of it. `result` is shown to the model and kept in the trace."""

    ok: bool
    arguments: JsonDict  # what was sent to the gateway; for a call refused here, what the model proposed
    result: JsonDict
    sentence: str | None
    state: RunState


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
    return ToolOutcome(False, sent, gateway_refusal(error), error.detail, state)


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
        sent: JsonDict = {"request": state.request.model_dump(mode="json")}
        try:
            offer = self._gateway.create_offer(self._identity, state.request)
        except TtaError as error:
            return _refused_by_gateway(sent, state, error)
        return ToolOutcome(True, sent, offer_summary(offer), offer_sentence(offer), replace(state, offer=offer))

    def _place_order(self, arguments: Mapping[str, Any], state: RunState) -> ToolOutcome:
        option_id = arguments.get(OPTION_ID)
        if set(arguments) != {OPTION_ID} or not isinstance(option_id, str) or not _RECORD_ID.fullmatch(option_id):
            return _refused(arguments, state, OPTION_ID_ONLY)
        if state.offer is None:
            return _refused(arguments, state, NO_OFFER_YET)
        if state.order is not None:
            return _refused(arguments, state, ONE_ORDER_PER_RUN.format(order_id=state.order.order_id))
        offer_id = state.offer.offer_id
        sent: JsonDict = {"offer_id": offer_id, OPTION_ID: option_id}
        try:
            order = self._gateway.place_order(
                self._identity, offer_id, option_id, _idempotency_key(state, offer_id, option_id)
            )
        except TtaError as error:
            return _refused_by_gateway(sent, state, error)
        return ToolOutcome(True, sent, order_summary(order), order.status_sentence, replace(state, order=order))

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
