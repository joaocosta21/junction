"""Enumerations, number types and identity shared by every contract (SPEC sections 2, 4, 5, 7)."""

from __future__ import annotations

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, PlainSerializer, model_validator

MONEY_PLACES = 2
QUANTITY_PLACES = 3
UNIT_PRICE_PLACES = 4
RATIO_PLACES = 4
NUMBER_PLACES = 6

CURRENCY_EUR = "EUR"


def _as_number(places: int) -> Callable[[Decimal], float]:
    quantum = Decimal(1).scaleb(-places)

    def serialise(value: Decimal) -> float:
        return float(value.quantize(quantum, rounding=ROUND_HALF_UP))

    return serialise


def round_money(value: Decimal) -> Decimal:
    """Round half up to cents: the one rounding rule for every total."""
    return value.quantize(Decimal(1).scaleb(-MONEY_PLACES), rounding=ROUND_HALF_UP)


# Computed as Decimal, serialised as JSON numbers (SPEC section 2).
Money = Annotated[Decimal, PlainSerializer(_as_number(MONEY_PLACES), return_type=float, when_used="json")]
Quantity = Annotated[Decimal, PlainSerializer(_as_number(QUANTITY_PLACES), return_type=float, when_used="json")]
UnitPrice = Annotated[
    Decimal, PlainSerializer(_as_number(UNIT_PRICE_PLACES), return_type=float, when_used="json")
]
Ratio = Annotated[Decimal, PlainSerializer(_as_number(RATIO_PLACES), return_type=float, when_used="json")]
# Any other decimal the supplier or the product file states (a tax rate, a stock figure, a lot step): exact inside,
# a JSON number outside, like money and quantities.
Number = Annotated[Decimal, PlainSerializer(_as_number(NUMBER_PLACES), return_type=float, when_used="json")]

JsonDict = dict[str, Any]


class Contract(BaseModel):
    """Base of every contract model: immutable, and unknown fields are an error."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Unit(StrEnum):
    """Unit of a requested quantity. `UNIT` means sales units."""

    L = "L"
    KG = "KG"
    UNIT = "UNIT"


class PackPreference(StrEnum):
    ANY = "ANY"
    BULK = "BULK"
    PORTION = "PORTION"


class PackSizeSource(StrEnum):
    PRICE_RATIO = "PRICE_RATIO"
    UNIT_CONVERSION = "UNIT_CONVERSION"
    NAME = "NAME"
    UNKNOWN = "UNKNOWN"


class AllergenStrictness(StrEnum):
    STRICT = "STRICT"
    DECLARED_ONLY = "DECLARED_ONLY"


class AllergenRelation(StrEnum):
    """What a product says about one allergen. `NOT_STATED` is our word for no statement at all."""

    FREE_FROM = "FREE_FROM"
    CONTAINS = "CONTAINS"
    MAY_CONTAIN = "MAY_CONTAIN"
    UNDECLARED = "UNDECLARED"
    NOT_STATED = "NOT_STATED"


class AllergenOutcome(StrEnum):
    PASS = "PASS"  # noqa: S105
    REJECT = "REJECT"
    TO_HUMAN = "TO_HUMAN"


class AvailabilityState(StrEnum):
    """The six states, in the order they are evaluated (SPEC section 4)."""

    BLOCKED = "BLOCKED"
    NOT_DELIVERABLE = "NOT_DELIVERABLE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    CUTOFF_PASSED = "CUTOFF_PASSED"
    QUANTITY_NOT_CONFIRMED = "QUANTITY_NOT_CONFIRMED"
    CONFIRMED = "CONFIRMED"


class ClaimName(StrEnum):
    PRICE = "price"
    QUANTITY = "quantity"
    DELIVERY_DATE = "delivery_date"
    ALLERGENS = "allergens"
    ORIGIN = "origin"


class ClaimStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    UNKNOWN = "UNKNOWN"
    RULED_OUT = "RULED_OUT"


class OptionKind(StrEnum):
    BEST_CONFIRMED = "BEST_CONFIRMED"
    ALTERNATIVE_UNCONFIRMED = "ALTERNATIVE_UNCONFIRMED"
    SUBSTITUTE = "SUBSTITUTE"


class ExclusionReason(StrEnum):
    BLOCKED = "BLOCKED"
    NOT_DELIVERABLE = "NOT_DELIVERABLE"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    CUTOFF_PASSED = "CUTOFF_PASSED"
    LATE_FOR_NEEDED_BY = "LATE_FOR_NEEDED_BY"
    ALLERGEN_DECLARED = "ALLERGEN_DECLARED"
    ALLERGEN_NOT_STATED = "ALLERGEN_NOT_STATED"
    PORTION_PACK = "PORTION_PACK"
    NOT_A_PORTION_PACK = "NOT_A_PORTION_PACK"  # on a line that asks for portion packs
    PACK_SIZE_UNKNOWN = "PACK_SIZE_UNKNOWN"
    PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
    SUBSTITUTE_ADDS_ALLERGEN = "SUBSTITUTE_ADDS_ALLERGEN"
    QUANTITY_NOT_CONFIRMED = "QUANTITY_NOT_CONFIRMED"  # only when the buyer asked for confirmed data only
    DELIVERY_DATE_NOT_CONFIRMED = "DELIVERY_DATE_NOT_CONFIRMED"  # only when the buyer asked for confirmed data only
    NOT_IN_RECORDING = "NOT_IN_RECORDING"  # replay only: the recorded copy of Valio's answers does not hold this product


class ConstraintKind(StrEnum):
    """One kind per thing a buyer can ask for (SPEC section 5, step 4)."""

    PRODUCT_TYPE = "PRODUCT_TYPE"
    PRODUCT_ID = "PRODUCT_ID"
    NAME_TERM = "NAME_TERM"
    QUANTITY = "QUANTITY"
    NEEDED_BY = "NEEDED_BY"
    CLAIM = "CLAIM"
    ALLERGEN = "ALLERGEN"
    PACK = "PACK"
    CONFIRMED_ONLY = "CONFIRMED_ONLY"


class CheckResult(StrEnum):
    MET = "MET"
    NOT_MET = "NOT_MET"
    UNVERIFIED = "UNVERIFIED"


class Verdict(StrEnum):
    """Least to most severe. The most severe verdict of the rules that fire wins."""

    AUTO = "AUTO"
    APPROVAL = "APPROVAL"
    BLOCK = "BLOCK"

    @property
    def severity(self) -> int:
        return _VERDICT_SEVERITY[self]


_VERDICT_SEVERITY = {Verdict.AUTO: 0, Verdict.APPROVAL: 1, Verdict.BLOCK: 2}


def most_severe(verdicts: list[Verdict] | tuple[Verdict, ...]) -> Verdict:
    """`AUTO` when nothing fired, otherwise the most severe verdict."""
    return max(verdicts, key=lambda verdict: verdict.severity, default=Verdict.AUTO)


class ApproverRole(StrEnum):
    PURCHASING_MANAGER = "purchasing_manager"
    DIETITIAN = "dietitian"
    FINANCE = "finance"


class SubstitutionScope(StrEnum):
    NONE = "NONE"
    LISTED_BY_SUPPLIER = "LISTED_BY_SUPPLIER"
    SAME_CATEGORY = "SAME_CATEGORY"


class VariableWeightRule(StrEnum):
    APPROVAL = "APPROVAL"
    AUTO_WITH_CEILING = "AUTO_WITH_CEILING"


class DepositRule(StrEnum):
    APPROVAL = "APPROVAL"
    NOTE = "NOTE"


class OrderStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ORDERED = "ORDERED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class DecisionKind(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class PlacedBy(StrEnum):
    AGENT = "AGENT"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"


class IdentityKind(StrEnum):
    AGENT = "AGENT"
    APPROVER = "APPROVER"
    SUPPLIER = "SUPPLIER"


class AuditReader(StrEnum):
    BUYER = "buyer"
    SUPPLIER = "supplier"


class DataSource(StrEnum):
    LIVE = "live"
    REPLAY = "replay"


class Identity(Contract):
    """Who is calling. A token maps to exactly one identity (SPEC section 2).

    An agent is bound to one buyer profile and holds no role. An approver holds one or more
    roles for one buyer profile. The supplier reader has neither.
    """

    kind: IdentityKind
    id: str
    display_name: str
    profile_id: str | None = None
    roles: tuple[ApproverRole, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Identity:
        if self.kind is IdentityKind.AGENT and (not self.profile_id or self.roles):
            raise ValueError("an agent is bound to one buyer profile and holds no approver role")
        if self.kind is IdentityKind.APPROVER and (not self.profile_id or not self.roles):
            raise ValueError("an approver belongs to one buyer profile and holds at least one role")
        if self.kind is IdentityKind.SUPPLIER and (self.profile_id or self.roles):
            raise ValueError("the supplier reader has no buyer profile and no role")
        return self

    @property
    def is_agent(self) -> bool:
        return self.kind is IdentityKind.AGENT

    @property
    def is_approver(self) -> bool:
        return self.kind is IdentityKind.APPROVER

    @property
    def is_supplier(self) -> bool:
        return self.kind is IdentityKind.SUPPLIER
