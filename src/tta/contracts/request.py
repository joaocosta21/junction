"""The typed purchase request (SPEC section 3) and the catalog query built from it."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import Field, model_validator

from tta.contracts.common import AllergenStrictness, Contract, PackPreference, Quantity, Unit

MAX_PRODUCT_IDS = 1000
MAX_REQUEST_LINES = 20
MAX_TEXT_LENGTH = 2000


class RequestLine(Contract):
    """One product the buyer asks for."""

    text: str = Field(max_length=MAX_TEXT_LENGTH, description="The buyer's own words, kept for the audit trail")
    product_type: str | None = Field(default=None, description="A key of the product-type table")
    product_ids: tuple[str, ...] = Field(default=(), max_length=MAX_PRODUCT_IDS)
    name_terms: tuple[str, ...] = Field(default=(), description="Words that must appear in the product name")
    required_claims: tuple[str, ...] = Field(default=(), description="nutritionalClaim codes that must be present")
    quantity: Quantity = Field(gt=0)
    unit: Unit
    exclude_allergens: tuple[str, ...] = Field(
        default=(), description="GS1 codes, added to the profile's exclusions; never removes one"
    )
    allergen_strictness: AllergenStrictness | None = Field(
        default=None,
        description="Required when there is any exclusion and the profile sets none. There is no default.",
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


class ProductQuery(Contract):
    """A catalog search (POST /v1/products/search). Every filter given must hold."""

    product_type: str | None = None
    product_ids: tuple[str, ...] = Field(default=(), max_length=MAX_PRODUCT_IDS)
    name_terms: tuple[str, ...] = ()
    required_claims: tuple[str, ...] = ()
    category_prefix: str | None = None
    limit: int = Field(default=200, ge=1, le=MAX_PRODUCT_IDS)
