"""Who the caller's customer is: the customer file with its buyer profile's name and limits (P1 C2, review C2 F5).

Scores on the 20% "solving the problem and user need" (an agent that knows its customer's usual products and past
orders needs less correction) and the 15% "clear visibility of assumptions": every answer says the data is made up.
The customer file is answered as it is; the limits are the buyer profile's, where they are decided and hashed.

Who reads what: an agent or an approver reads its own buyer's customer; another customer's id answers as an id
nobody has. The supplier's token reads none: a customer's people, history and limits are the buyer's own, the same
line the supplier's view of the audit trail draws.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import Field

from tta.contracts.common import AllergenStrictness, Contract, Identity, Money, Ratio, SubstitutionScope
from tta.contracts.customer import Customer
from tta.contracts.errors import NotAuthorised, NotFound
from tta.contracts.policy import BuyerProfile
from tta.customers import shipped_customer

SYNTHETIC_NOTE = (
    "Synthetic: every name, number and past order of this customer is made up for the demonstration, and its "
    "limits are illustrative values of ours. The Valio Aimo mock has no customer model."
)
NOT_FOR_THE_SUPPLIER = (
    "The supplier reads its view of the audit trail (GET /v1/audit) and nothing else: a customer's people, past "
    "orders and limits are the buyer's own."
)
NO_SUCH_CUSTOMER = "No customer has this id."

Customers = Callable[[str], Customer | None]


class CustomerLimits(Contract):
    """What the buyer profile sets for this customer. Illustrative; `GET /v1/authority` gives every rule."""

    auto_order_enabled: bool = Field(description="Ordering alone, a buyer setting: off in every shipped profile")
    max_order_net_eur: Money = Field(description="EUR before tax per order without a person (rule P-01)")
    max_daily_net_eur: Money = Field(description="EUR before tax per day without a person (rule P-02)")
    min_fill_ratio: Ratio = Field(description="The share of the requested quantity that must be covered (P-03)")
    excluded_allergens: tuple[str, ...] = Field(description="GS1 codes kept out of every order")
    allergen_strictness: AllergenStrictness | None = None
    substitution_without_approval: SubstitutionScope
    formula_matters: bool = Field(description="A substitute must keep the formula on every line (rule F-11)")
    illustrative: bool = True


class CustomerView(Contract):
    """Answer of GET /v1/customers/{customer_id} and of the MCP tool get_customer."""

    customer: Customer
    display_name: str = Field(description="The buyer profile's name for this customer")
    limits: CustomerLimits
    synthetic: bool = True
    note: str = SYNTHETIC_NOTE


def _limits(profile: BuyerProfile) -> CustomerLimits:
    return CustomerLimits(
        auto_order_enabled=profile.auto_order_enabled, max_order_net_eur=profile.max_order_net_eur,
        max_daily_net_eur=profile.max_daily_net_eur, min_fill_ratio=profile.min_fill_ratio,
        excluded_allergens=profile.excluded_allergens, allergen_strictness=profile.allergen_strictness,
        substitution_without_approval=profile.substitution_without_approval,
        formula_matters=profile.formula_matters, illustrative=profile.illustrative,
    )


def customer_view(
    identity: Identity, profile: Callable[[str], BuyerProfile], customer_id: str | None = None,
    customers: Customers = shipped_customer,
) -> CustomerView:
    """The caller's own customer; `customer_id`, when given, must be it. Raises `NotAuthorised` for the supplier
    and `NotFound` for another customer's id, or when the caller's buyer has no customer file."""
    if identity.is_supplier or identity.profile_id is None:
        raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
    if customer_id is not None and customer_id != identity.profile_id:
        raise NotFound(NO_SUCH_CUSTOMER)  # another buyer's customer answers as an id nobody has
    customer = customers(identity.profile_id)
    if customer is None:
        raise NotFound(NO_SUCH_CUSTOMER)
    own = profile(identity.profile_id)
    return CustomerView(customer=customer, display_name=own.display_name, limits=_limits(own))
