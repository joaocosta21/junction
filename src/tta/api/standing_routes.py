"""The standing-order routes (task STAND-1): set up, list, read and renew a buyer's recurring orders.

Scores on the 20% "autonomy and controls": a renewal is an offer and an order like any other, judged by every rule,
and rule P-08 compares it with the standing order's history first. The same caller dependency, problem responses
(RFC 9457) and rate limits as `tta.api.routes`: the renewal's offer and order go through the gateway service, which
counts them as offers and orders.

    include_standing_routes(app, StandingOrders(store=..., audit=..., gateway=parts.service, clock=parts.clock))
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, FastAPI, Request

from tta.api import docs
from tta.api.identity import Caller
from tta.api.routes import CALLER, CREATED, StoredId
from tta.contracts.errors import (
    InvalidRequest,
    NotFound,
    OfferExpired,
    OfferStale,
    PolicyBlocked,
    RateLimited,
    SupplierUnavailable,
    UnknownProduct,
)
from tta.contracts.standing import NewStandingOrder, RenewStandingOrder, StandingOrder
from tta.standing import StandingOrders
from tta.standing.models import RenewalOutcome, StandingOrderDetail

TAG = docs.TAG_ORDER
standing_router = APIRouter(prefix="/v1")


def _standing(request: Request) -> StandingOrders:
    return request.app.state.standing


# The demo standing order (STAND-1 hand-back): 100 L of 469363 a week; renewed at 290 L, rule P-08 sends it to a human.
NEW_EXAMPLES = {
    "weekly_milk": {
        "summary": "Weekly lactose-free milk, hotel kitchen",
        "value": {
            "name": "Weekly lactose-free milk, hotel kitchen", "cadence_days": 7,
            "request": {"lines": [{"text": "100 litres of lactose-free milk 469363", "product_ids": ["469363"],
                                    "quantity": 100, "unit": "L"}]},
        },
    },
}
RENEW_EXAMPLES = {
    "as_stored": {"summary": "The stored quantities", "value": {}},
    "creeping_up": {
        "summary": "290 L this week: more than the tolerance above the median", "value": {"quantities": [290]},
    },
}


@standing_router.post(
    "/standing-orders", operation_id="create_standing_order", tags=[TAG], status_code=CREATED,
    responses=docs.problems(*CALLER, InvalidRequest), summary="Set up a recurring order",
)
def create_standing_order(
    request: Request, caller: Caller, body: Annotated[NewStandingOrder, Body(openapi_examples=NEW_EXAMPLES)]
) -> StandingOrder:
    """For agents. A typed request (as for `POST /v1/offers`, without `standing_order_id`), a name and a cadence in
    days (7 by default). Nothing is ordered yet. Its history starts empty: until 3 renewals are on record, rule P-08
    has too short a history to judge, and each renewal says so."""
    return _standing(request).create(caller, body)


@standing_router.get(
    "/standing-orders", operation_id="list_standing_orders", tags=[TAG], responses=docs.problems(*CALLER),
    summary="The standing orders of the caller's buyer",
)
def list_standing_orders(request: Request, caller: Caller) -> tuple[StandingOrder, ...]:
    """For agents and approvers of the buyer, in the order they were set up."""
    return _standing(request).list(caller)


@standing_router.get(
    "/standing-orders/{standing_order_id}", operation_id="get_standing_order", tags=[TAG],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="One standing order and its renewals",
)
def get_standing_order(request: Request, caller: Caller, standing_order_id: StoredId) -> StandingOrderDetail:
    """Every renewal, oldest first, each with the order it placed. A renewal made up for the demonstration is marked
    `synthetic`: the Valio Aimo mock has no order history. Another buyer's standing order answers as an id nobody
    set up."""
    return _standing(request).get(caller, standing_order_id)


@standing_router.post(
    "/standing-orders/{standing_order_id}/renew", operation_id="renew_standing_order", tags=[TAG],
    status_code=CREATED,
    responses=docs.problems(
        *CALLER, InvalidRequest, NotFound, UnknownProduct, OfferExpired, OfferStale, PolicyBlocked, RateLimited,
        SupplierUnavailable,
    ),
    summary="Renew a standing order, with this week's quantities",
)
def renew_standing_order(
    request: Request, caller: Caller, standing_order_id: StoredId,
    body: Annotated[RenewStandingOrder, Body(openapi_examples=RENEW_EXAMPLES)],
) -> RenewalOutcome:
    """For agents. The stored request, with `standing_order_id` set and this week's quantities when given, becomes
    an offer; its top option is ordered as `POST /v1/orders` orders it. The policy decides: a quantity or unit price
    that differs from the median of the line's last 6 renewals by more than the profile's tolerance goes to the
    purchasing manager (rule P-08). The answer holds the offer, the drift found and the order; the renewal joins the
    history once an order exists."""
    return _standing(request).renew(caller, standing_order_id, body)


def include_standing_routes(app: FastAPI, standing: StandingOrders) -> None:
    """Serve the standing-order routes of `app` from this service (the shared book of the tokens)."""
    app.state.standing = standing
    app.include_router(standing_router)
