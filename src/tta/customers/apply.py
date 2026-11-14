"""What a customer's pattern changes in a request, as pure functions (P1 C4).

A pattern may pin a product or add a confirmation. It may never widen what the agent decides alone, remove an
exclusion or weaken a rule (P1 section 6). The usual product of a type-only line is a suggestion of
`tta.suggestions` (kind USUAL_PRODUCT); here is only the default preference.
"""

from __future__ import annotations

from tta.contracts.common import Preference
from tta.contracts.customer import Customer
from tta.contracts.request import PurchaseRequest

PREFER_FIELD = "prefer"


def preference_for(customer: Customer | None, request: PurchaseRequest) -> Preference:
    """The request's preference when it states one, even the default; otherwise the customer's.

    "States one" means the field was given when the request was built (`model_fields_set`), so an explicit
    `"prefer": "PRICE"` is kept and only a request silent on it takes the customer's.
    """
    if customer is None or PREFER_FIELD in request.model_fields_set:
        return request.prefer
    return customer.prefer
