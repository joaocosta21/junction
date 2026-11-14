"""The typed purchase request (SPEC section 3) and the catalog query built from it."""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, Field, StringConstraints, model_validator

from tta.contracts.common import AllergenStrictness, Contract, PackPreference, Preference, Quantity, Unit

MAX_PRODUCT_IDS = 1000
MAX_REQUEST_LINES = 20
MAX_TEXT_LENGTH = 2000
MAX_QUANTITY = Decimal(1_000_000)  # far above any real order; keeps arithmetic and JSON bounded
MAX_QUANTITY_DECIMALS = 3
MAX_TERMS = 10
MAX_ALLERGEN_CODES = 30
MAX_TERM_LENGTH = 60
MAX_ID_LENGTH = 20
MAX_ROLE_LENGTH = 200

_FORBIDDEN_IN_A_TERM = frozenset('"\u201c\u201d\u201e\u00ab\u00bb<>')


def _plain_term(value: str) -> str:
    """A term is a word or a code, never a sentence: no control or format character, no quotation mark."""
    for character in value:
        if unicodedata.category(character).startswith("C") or character in _FORBIDDEN_IN_A_TERM:
            raise ValueError("a term may not contain control characters, quotation marks or angle brackets")
    return value


Term = Annotated[
    str,
    StringConstraints(min_length=1, max_length=MAX_TERM_LENGTH, strip_whitespace=True),
    AfterValidator(_plain_term),
]
ProductId = Annotated[str, StringConstraints(min_length=1, max_length=MAX_ID_LENGTH, pattern=r"^[A-Za-z0-9]+$")]
# A role is one plain line of at most 200 characters: the same character check as a term (review A3, finding F4).
Role = Annotated[str, StringConstraints(max_length=MAX_ROLE_LENGTH), AfterValidator(_plain_term)]


class RequestLine(Contract):
    """One product the buyer asks for."""

    text: str = Field(max_length=MAX_TEXT_LENGTH, description="The buyer's own words, kept for the audit trail")
    product_type: Term | None = Field(default=None, description="A key of the product-type table")
    product_ids: tuple[ProductId, ...] = Field(default=(), max_length=MAX_PRODUCT_IDS)
    name_terms: tuple[Term, ...] = Field(
        default=(), max_length=MAX_TERMS, description="Words that must appear in the product name"
    )
    required_claims: tuple[Term, ...] = Field(
        default=(), max_length=MAX_TERMS, description="nutritionalClaim codes that must be present"
    )
    quantity: Quantity = Field(gt=0, le=MAX_QUANTITY, decimal_places=MAX_QUANTITY_DECIMALS)
    unit: Unit
    exclude_allergens: tuple[Term, ...] = Field(
        default=(), max_length=MAX_ALLERGEN_CODES,
        description="GS1 codes, added to the profile's exclusions; never removes one",
    )
    required_labels: tuple[Term, ...] = Field(
        default=(), max_length=MAX_TERMS,
        description="Certificate labels (packagingMarkedLabel codes, e.g. EU_ORGANIC_FARMING) every product must carry",
    )
    stands_in_for: Term | None = Field(
        default=None,
        description="The product type of a recipe this line replaces, set by the menu planner when recipe logic "
        "chose another ingredient (rule F-09: such a line goes to a human). It can only add a check",
    )
    stands_in_role: Role | None = Field(
        default=None,
        description="The job the recipe's ingredient does in the dish, set by the menu planner with stands_in_for. "
        "Shown in rule F-09's sentence only when the recipe table holds it for that product type",
    )
    keep_formula: bool | None = Field(
        default=None,
        description="The formula matters for this line: a substitute must keep it (six nutrients and the fat "
        "source within the tolerances), or it goes to a person under rule F-11. It can only add the check: "
        "false or absent leaves the buyer profile's own setting in force",
    )
    allergen_strictness: AllergenStrictness | None = Field(
        default=None,
        description="How the exclusions are read: STRICT (a product that may contain the allergen, or says nothing "
        "about it, is not the first option and goes to a person) or DECLARED_ONLY. With no rule here and none in "
        "the profile an exclusion reads STRICT, the safe reading. A request can make the rule stricter, never looser",
    )
    pack: PackPreference = Field(description="Defaults to BULK for L and KG, ANY for UNIT")

    @model_validator(mode="before")
    @classmethod
    def _default_pack(cls, data: Any) -> Any:
        if not isinstance(data, dict) or data.get("pack") is not None:
            return data
        unit = str(data.get("unit", "")).upper().removeprefix("UNIT.")
        default = PackPreference.ANY if unit == Unit.UNIT.value else PackPreference.BULK
        return {**data, "pack": default}


class PurchaseRequest(Contract):
    """What the buyer's agent asks the gateway to find."""

    needed_by: date | None = Field(default=None, description="The date the goods are needed")
    require_confirmed: bool = Field(
        default=False, description="Offer only options in which every claim is confirmed"
    )
    lines: tuple[RequestLine, ...] = Field(min_length=1, max_length=MAX_REQUEST_LINES)
    prefer: Preference = Field(
        default=Preference.PRICE,
        description="What ranks confirmed products once every constraint is met: price (default), earliest delivery, "
        "delivery reliability or lower carbon footprint",
    )
    standing_order_id: str | None = Field(
        default=None, max_length=MAX_ID_LENGTH * 2, pattern=r"^[A-Za-z0-9_-]+$",
        description="The standing order this request renews: its history is checked (rule P-08). It can only add a "
        "check, never remove one",
    )


class ProductQuery(Contract):
    """A catalog search (POST /v1/products/search). Every filter given must hold."""

    product_type: Term | None = None
    product_ids: tuple[ProductId, ...] = Field(default=(), max_length=MAX_PRODUCT_IDS)
    name_terms: tuple[Term, ...] = Field(default=(), max_length=MAX_TERMS)
    required_claims: tuple[Term, ...] = Field(default=(), max_length=MAX_TERMS)
    required_labels: tuple[Term, ...] = Field(
        default=(), max_length=MAX_TERMS, description="Certificate labels (packagingMarkedLabel codes) to carry"
    )
    category_prefix: Term | None = None
    limit: int = Field(default=200, ge=1, le=MAX_PRODUCT_IDS)
