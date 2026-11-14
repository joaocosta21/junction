"""The offer: options, a status per claim, exclusions with reasons, a verdict per option (SPEC section 5)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from tta.contracts.allergen import AllergenCheck, SubstituteAllergenCheck
from tta.contracts.availability import AvailabilityAssessment, ClaimCheck
from tta.contracts.common import (
    CURRENCY_EUR,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    Contract,
    DataSource,
    ExclusionReason,
    Money,
    Number,
    OptionKind,
    Quantity,
    Ratio,
    Unit,
    UnitPrice,
)
from tta.contracts.policy import PolicyDecision
from tta.contracts.product import PackSize
from tta.contracts.request import MAX_QUANTITY, PurchaseRequest


class SubstituteInfo(Contract):
    """Set on a line that stands in for a product the buyer named."""

    original_id: str
    original_name: str | None = None
    listed_by_supplier: bool
    category_distance: int = Field(
        ge=0,
        description="0 same 5-digit category, 1 same first 4, 2 same first 3, 3 listed from further away",
    )
    allergen_check: SubstituteAllergenCheck
    claims_lost: tuple[str, ...] = ()  # nutritional claims of the original that the substitute does not carry
    gives_up: str  # one sentence: what the buyer gives up


class OfferLine(Contract):
    """One product of an option, with the statements the offer relies on."""

    product_id: str
    name: str
    vendor_name: str | None = None
    category: str
    request_line_index: int = Field(ge=0)
    quantity: Quantity = Field(gt=0, description="In sales units, rounded up to the lot step")
    sales_unit: str  # the sales unit on the API line
    pack_size: PackSize
    covers: Quantity = Field(description="How much of the requested quantity this line covers, in the request's unit")
    unit_net_price: UnitPrice
    tax_rate: Number | None = None  # percent, from tax.taxRate
    net: Money
    tax: Money
    gross: Money
    price_valid_to: datetime | None = None
    availability: AvailabilityAssessment
    claims: tuple[ClaimCheck, ...] = ()
    allergen_check: AllergenCheck | None = None  # None when the buyer excluded nothing
    variable_weight: bool | None = None  # None: the product file does not say (a missing fact)
    has_deposits: bool = False
    country_of_origin: str | None = None
    substitute: SubstituteInfo | None = None
    # From the product, for the comparison of delivery and sustainability (task SUST-1). None: the file has no
    # value, which is unknown, never 0 and never 1.
    delivery_reliability: Number | None = Field(default=None, description="Share 0 to 1, from the reliability file")
    carbon_kg_co2e_per_kg: Number | None = Field(default=None, description="From the carbon footprint file")
    labels: tuple[str, ...] = Field(default=(), description="Certificate labels (packagingMarkedLabel codes)")
    # Copied from the request line when recipe logic chose this product type in place of the recipe's own (task
    # MENU-1, rule F-09). None: the line stands in for nothing.
    stands_in_for: str | None = Field(default=None, description="The recipe's product type this line replaces")
    stands_in_role: str | None = Field(default=None, description="The job that ingredient does in the dish")

    @property
    def quantity_confirmed(self) -> bool:
        return self.availability.state is AvailabilityState.CONFIRMED

    def confirmed_for_order(self, *, dated: bool) -> bool:
        """True when every claim the order depends on is confirmed (SPEC section 4, "Which claims gate").

        Price, quantity and allergens always; the delivery date only when the request gave a date.
        Origin is shown to the buyer and never gates an order.
        """
        gating = {ClaimName.PRICE, ClaimName.QUANTITY, ClaimName.ALLERGENS}
        if dated:
            gating.add(ClaimName.DELIVERY_DATE)
        found = {check.claim: check.status for check in self.claims}
        return all(found.get(claim) is ClaimStatus.CONFIRMED for claim in gating)


class Totals(Contract):
    net: Money
    tax: Money
    gross: Money
    currency: str = CURRENCY_EUR
    excludes_deposits: bool = False  # a line carries deposits that the total does not include
    is_ceiling: bool = False  # variable weight: the invoiced total can be lower, never higher


class Coverage(Contract):
    """How much of one request line an option covers."""

    request_line_index: int = Field(ge=0)
    requested: Quantity
    covered: Quantity
    unit: Unit
    fill_ratio: Ratio
    missing: Quantity


class ConstraintCheck(Contract):
    """One thing the buyer asked for, and whether the option meets it."""

    request_line_index: int | None = None  # None for a request-level constraint such as needed_by
    kind: ConstraintKind
    subject: str  # for example the claim code, the allergen code or the date
    result: CheckResult
    sentence: str


class OptionComparison(Contract):
    """Delivery dates, delivery reliability, carbon footprint and labels of an option's lines (task SUST-1).

    Each figure is over the lines that have a value; how many lines have none is stated beside it.
    """

    earliest_delivery: date | None = None
    latest_delivery: date | None = None
    delivery_unknown_lines: int = Field(default=0, ge=0)
    lowest_reliability: Number | None = Field(default=None, description="The lowest share 0 to 1 among the lines")
    reliability_unknown_lines: int = Field(default=0, ge=0)
    carbon_kg_co2e: Number | None = Field(
        default=None,
        description="Estimate: amount delivered times kg CO2e per kg, over the lines whose amount is known in kg or "
        "litres; a litre is counted as a kilogram",
    )
    carbon_unknown_lines: int = Field(default=0, ge=0)
    labels_on_every_line: tuple[str, ...] = ()
    sentence: str


class OfferOption(Contract):
    option_id: str
    kind: OptionKind
    rank: int = Field(ge=1)
    title: str
    summary: str  # one sentence a person can read without the table
    lines: tuple[OfferLine, ...] = Field(min_length=1)
    totals: Totals
    coverage: tuple[Coverage, ...] = ()
    fill_ratio: Ratio  # the lowest fill ratio over the request's lines
    valid_until: datetime | None = None  # earliest price validity and cut-off of the lines
    constraint_checks: tuple[ConstraintCheck, ...] = ()
    decision: PolicyDecision | None = None  # filled in by the offer builder before the offer leaves it
    comparison: OptionComparison | None = None  # filled in by the offer builder (task SUST-1)

    @property
    def is_partial(self) -> bool:
        return self.fill_ratio < 1

    @property
    def product_ids(self) -> tuple[str, ...]:
        return tuple(line.product_id for line in self.lines)


class Exclusion(Contract):
    """A product that dropped out, with a reason code and one sentence."""

    product_id: str
    name: str
    request_line_index: int = Field(ge=0)
    reason: ExclusionReason
    sentence: str


class Offer(Contract):
    offer_id: str
    created_at: datetime
    profile_id: str
    agent_id: str
    request: PurchaseRequest
    options: tuple[OfferOption, ...] = ()
    excluded: tuple[Exclusion, ...] = ()
    candidates_considered: int = 0
    source: DataSource  # live or replay
    time_now: datetime  # the clock the offer was built against
    notes: tuple[str, ...] = ()  # for example why there is no option

    def option(self, option_id: str) -> OfferOption | None:
        return next((option for option in self.options if option.option_id == option_id), None)


class SubstituteQuery(Contract):
    """Body of POST /v1/products/{id}/substitutes."""

    quantity: Quantity | None = Field(default=None, gt=0, le=MAX_QUANTITY)
    unit: Unit = Unit.UNIT
    needed_by: date | None = None


class SubstituteCandidate(Contract):
    """One ranked substitute. A candidate that fails is shown with its reason and cannot be ordered."""

    rank: int = Field(ge=1)
    product_id: str
    name: str
    passes: bool
    orderable: bool
    reason: ExclusionReason | None = None  # set whenever the candidate cannot be ordered
    sentence: str  # why it passes or fails
    gives_up: str  # what the buyer gives up
    claims_lost: tuple[str, ...] = ()  # nutritional claims of the original that this product does not carry
    listed_by_supplier: bool
    category_distance: int = Field(ge=0)
    pack_size: PackSize
    availability: AvailabilityAssessment | None = None
    claims: tuple[ClaimCheck, ...] = ()
    allergen_check: SubstituteAllergenCheck
    unit_net_price: UnitPrice | None = None
    price_difference: UnitPrice | None = None  # substitute minus original, per sales unit


class SubstituteResult(Contract):
    original_id: str
    original_name: str | None = None
    candidates: tuple[SubstituteCandidate, ...] = ()
    source: DataSource
    time_now: datetime
    notes: tuple[str, ...] = ()
