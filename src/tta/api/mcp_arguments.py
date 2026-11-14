"""The typed arguments of the MCP tools for menus and standing orders, with the text an agent reads for each."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from tta.contracts.menu import MenuRequest
from tta.contracts.standing import NewStandingOrder, RenewStandingOrder, StandingOrderId

MenuArgument = Annotated[
    MenuRequest,
    Field(description="The dishes with their servings (dish ids from the recipe table, GET /v1/menus/recipes), what "
                      "the kitchen already holds, the date and what to exclude."),
]
NewStandingOrderArgument = Annotated[
    NewStandingOrder,
    Field(description="A name, a cadence in days and the typed request to repeat, as for get_offer."),
]
StandingOrderIdArgument = Annotated[
    StandingOrderId, Field(description="The `standing_order_id` from set_up_standing_order or list_standing_orders")
]
RenewalArgument = Annotated[
    RenewStandingOrder,
    Field(description="This time's quantities, one per line of the stored request in order; an empty object "
                      "renews the stored quantities."),
]
