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
    ClockBasis,
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
from tta.contracts.product import FormulaCheck, PackSize, ReplaceCheck
from tta.contracts.request import MAX_QUANTITY, PurchaseRequest
from tta.contracts.suggestion import Suggestion


class SubstituteInfo(Contract):
    """Set on a line that stands in for a product the buyer named."""

    original_id: str
    original_name: str | None = None
    listed_by_supplier: bool
    category_distance: int = Field(
        ge=0,
        description="0 same 5-digit category, 1 another category, which only a pair Valio lists can be",
    )
    allergen_check: SubstituteAllergenCheck
    claims_lost: tuple[str, ...] = ()  # nutritional claims of the original that the substitute does not carry
    gives_up: str  # one sentence: what the buyer gives up
    formula: FormulaCheck | None = None  # its composition measured against the original's (`tta.offers.formula`)
    # It loses a dietary claim or is another kind of product, and stands in only because no product that keeps
    # every claim and is the same kind can be ordered.
    last_resort: bool = False
    # Can it take the original's place like for like: type, flavour, use, formula, claims (`tta.offers.substitutes`).
    # None on a line stored before the field existed.
    replaceable: ReplaceCheck | None = None


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
    # Copied from the request line (P10 item F5): the request's own word that the formula matters. Rule F-11
    # reads it by this name. None: the request did not say, and the buyer profile's setting decides.
    keep_formula: bool | None = Field(
        default=None, description="The formula matters for this line: a substitute must keep it (rule F-11)"
    )

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
    # Variable weight: the total is an estimate, because Valio Aimo invoices the weight delivered (answer Q16 of
    # 14 Nov 2026). It is not a ceiling; the field keeps its name so stored offers and clients still read it.
    is_ceiling: bool = False


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
    # On the option ranked by the buyer's preference, when a cheaper confirmed option is offered next to it: what
    # the preference costs (review A2b, finding H2). None: no preference, or it costs nothing.
    net_above_cheapest: Money | None = Field(
        default=None, description="Net total minus the net total of the cheapest confirmed option of the offer"
    )

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
    supplier_reason: ExclusionReason | None = Field(
        default=None,
        description="The reason in the supplier's own data, when there is one beside the buyer's",
    )


PROOF_ALGORITHM = "EdDSA"  # RFC 8037: Ed25519 in JSON Web Signatures
PROOF_CANONICALIZATION = "RFC 8785"  # the JSON Canonicalization Scheme the signed bytes are written in


class Proof(Contract):
    """The gateway's signature of an offer or an order record (P12 W8). It says that this gateway answered this
    record; it does not say Valio Aimo signed anything, and it is not a Verifiable Credential. To check it: remove
    `proof` from the record, write the rest as RFC 8785 says, and verify the detached JSON Web Signature with the
    key of `key_id` in the key set at `jwks_path`."""

    type: str = Field(default="JsonWebSignature", description="A detached JSON Web Signature (RFC 7515, appendix F)")
    algorithm: str = Field(default=PROOF_ALGORITHM, description="EdDSA over Ed25519 (RFC 8037)")
    canonicalization: str = Field(default=PROOF_CANONICALIZATION, description="How the signed bytes are written")
    key_id: str = Field(description="The `kid` of the signing key: its RFC 7638 thumbprint")
    jws: str = Field(description="`<protected header>..<signature>`, base64url; the payload is the record itself")
    jwks_path: str = Field(description="Where this gateway publishes its public key, as a JSON Web Key set")
    demo_key: bool = Field(description="True: the key was generated when the gateway started and proves nothing later")
    note: str


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
    # What that clock rests on: the recording's own instant, the supplier's server time, or an instant we set
    # (TTA_DEMO_CLOCK, replay only). None on an offer stored before the field existed.
    time_basis: ClockBasis | None = None
    notes: tuple[str, ...] = ()  # for example why there is no option
    # Computed from the customer's past orders or the catalog (`tta.suggestions`). A suggestion is in no option
    # and in no total, and never adds itself to an order. Empty on an offer stored before the field existed.
    suggestions: tuple[Suggestion, ...] = ()
    # Set on the copy a REST route or an MCP tool answers (`tta.api.signing`); never stored, never in the trail.
    proof: Proof | None = Field(default=None, description="The gateway's signature of this offer without `proof`")

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
    formula: FormulaCheck | None = None  # its composition measured against the original's (`tta.offers.formula`)
    # It loses a dietary claim or is another kind of product, and is shown only because no candidate that keeps
    # every claim and is the same kind can be ordered.
    last_resort: bool = False
    # The same difference per litre or kilogram of content: each price divided by what one sales unit holds, so
    # a case is never compared with a carton (review P2, item W7). None: a pack size is not known, or the two
    # are not in the same measure.
    price_difference_per_requested_unit: UnitPrice | None = Field(
        default=None, description="Substitute minus original, per litre or kilogram of content"
    )
    # Can it take the original's place like for like: type, flavour, use, formula, claims.
    replaceable: ReplaceCheck | None = None


class SubstituteResult(Contract):
    original_id: str
    original_name: str | None = None
    candidates: tuple[SubstituteCandidate, ...] = ()
    source: DataSource
    time_now: datetime
    notes: tuple[str, ...] = ()
