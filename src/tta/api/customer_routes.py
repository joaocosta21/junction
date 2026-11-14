"""The customer routes (review C2, finding F5): who the caller's customer is, from the customer files (P1 C2).

Scores on the 20% "solving the problem and user need": the shop page and an agent read the same customer (people,
usual products, past orders, standing orders) the suggestions are computed from, instead of each keeping a copy.
Every answer is marked synthetic. The rule of who reads what is in `tta.api.customers`, behind the gateway service.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Path, Request

from tta.api import docs
from tta.api.customers import CustomerView
from tta.api.identity import Caller
from tta.api.routes import CALLER
from tta.api.service import Gateway
from tta.contracts.customer import CUSTOMER_ID_PATTERN, MAX_TEXT
from tta.contracts.errors import InvalidRequest, NotFound

customer_router = APIRouter(prefix="/v1", tags=[docs.TAG_CUSTOMERS])
CustomerIdPath = Annotated[
    str, Path(min_length=1, max_length=MAX_TEXT, pattern=CUSTOMER_ID_PATTERN, description="A customer id, which is "
              "the id of its buyer profile, for example `hotel-kitchen`"),
]


def _service(request: Request) -> Gateway:
    return request.app.state.parts.service


@customer_router.get(
    "/customers", operation_id="list_customers", responses=docs.problems(*CALLER, NotFound),
    summary="The customers the caller may read: its own",
)
def list_customers(request: Request, caller: Caller) -> tuple[CustomerView, ...]:
    """For an agent or an approver: the one customer its token is bound to, as a list of one. The supplier's token
    is refused: a customer's people, past orders and limits are the buyer's own. Everything is synthetic."""
    return (_service(request).get_customer(caller),)


@customer_router.get(
    "/customers/{customer_id}", operation_id="get_customer",
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="One customer: the caller's own",
)
def get_customer(request: Request, caller: Caller, customer_id: CustomerIdPath) -> CustomerView:
    """The customer file as it is (who orders, who holds each role, the usual products with their use, the past
    orders oldest first, the standing orders, `synthetic: true`), with the buyer profile's display name and
    limits. Another customer's id answers as an id nobody has. The limits are illustrative; `GET /v1/authority`
    gives every rule."""
    return _service(request).get_customer(caller, customer_id)
