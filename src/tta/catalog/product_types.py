"""The product-type table: a key such as `milk` to category codes, name terms and claims (SPEC section 3, step 2).

A type may also name terms that a product of the type must not have in its name: category 10400
holds milk, 11 sour milks, a coffee drink and a soy yoghurt, and a buyer who asks for milk means milk.

The table is ours, not Valio's: the product file has category codes and no category names
(AIMO/FINDINGS.md section 2). Each entry says how it was derived.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, ValidationError, field_validator

from tta.catalog.data_errors import data_file_error
from tta.catalog.text import normalise
from tta.contracts.common import Contract

PRODUCT_TYPES_FILE = Path(__file__).with_name("product_types.yaml")


class ProductType(Contract):
    """One row of the table. A product is of this type when all four conditions hold."""

    key: str = Field(min_length=1)
    categories: tuple[str, ...] = Field(min_length=1, description="The product's category is one of these")
    name_terms: tuple[str, ...] = Field(
        default=(), description="When given: the English or Finnish name has at least one of these"
    )
    exclude_terms: tuple[str, ...] = Field(
        default=(), description="When given: neither the English nor the Finnish name has any of these"
    )
    claims: tuple[str, ...] = Field(default=(), description="Every one of these nutritionalClaim codes is present")
    products: int = Field(gt=0, description="Products of this type in the catalog when the entry was written")
    derived_from: str = Field(min_length=1, description="How the entry was derived")

    @field_validator("exclude_terms")
    @classmethod
    def _no_blank_exclude_term(cls, terms: tuple[str, ...]) -> tuple[str, ...]:
        """A term with no letter or digit is in every name: it would leave the type with no product."""
        if any(not normalise(term) for term in terms):
            raise ValueError("an exclude term needs at least one letter or digit")
        return terms


def load_product_types(path: Path = PRODUCT_TYPES_FILE) -> dict[str, ProductType]:
    """The table by key. Raises `SupplierUnavailable` when the file is missing or malformed."""
    raw = _read_yaml(path)
    if not isinstance(raw, dict) or not raw:
        raise data_file_error(path, "it must be a mapping from a product-type key to its entry")
    product_types: dict[str, ProductType] = {}
    for key, entry in raw.items():
        if not isinstance(entry, dict):
            raise data_file_error(path, f"the entry {key!r} must be a mapping")
        try:
            product_types[str(key)] = ProductType(key=str(key), **entry)
        except (ValidationError, TypeError) as error:
            raise data_file_error(path, f"the entry {key!r} is not valid: {_first_line(error)}") from error
    return product_types


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise data_file_error(path, "it cannot be read") from error
    except yaml.YAMLError as error:
        raise data_file_error(path, "it is not valid YAML") from error


def _first_line(error: Exception) -> str:
    if isinstance(error, ValidationError):
        first = error.errors(include_url=False, include_input=False)[0]
        return f"{'.'.join(str(part) for part in first['loc'])}: {first['msg']}"
    return str(error).splitlines()[0]
