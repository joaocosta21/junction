"""The schema the model's answer is held to follows the typed request of the contract (SPEC sections 3, 11)."""

from __future__ import annotations

from typing import Any

import pytest

from tta.agent.schema import CLAIM_CODES, EXCLUDABLE_ALLERGEN_CODES, proposal_schema
from tta.allergens import ALLERGEN_CODES
from tta.contracts.common import AllergenStrictness, PackPreference, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

KEYS = ("milk", "plant_drink", "beef_chuck")
# Keywords the Gemini documentation says are ignored, or that make a schema too complex to enforce.
UNWANTED = {"minLength", "maxLength", "pattern", "maxItems", "uniqueItems", "minimum", "maximum", "default", "$ref"}


def _keywords(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set(node) | {key for value in node.values() for key in _keywords(value)}
    if isinstance(node, list):
        return {key for value in node for key in _keywords(value)}
    return set()


def _choices(prop: dict[str, Any]) -> set[Any]:
    return set(prop["anyOf"][0]["enum"])


@pytest.mark.xfail(strict=True, reason="FALLBACK-1 adds prefer and required_labels to the schema, and leaves out "
                   "standing_order_id, which the gateway sets")
def test_the_schema_has_the_fields_of_the_typed_request_except_the_buyers_words() -> None:
    schema = proposal_schema(KEYS)
    line = schema["properties"]["lines"]["items"]

    assert set(schema["properties"]) == set(PurchaseRequest.model_fields)
    assert set(line["properties"]) == set(RequestLine.model_fields) - {"text"}  # the parser sets `text` itself
    for node in (schema, line):
        assert set(node["required"]) == set(node["properties"])  # nothing may be left out: null says "not said"
        assert node["additionalProperties"] is False


def test_every_choice_is_a_closed_list_taken_from_the_contract_and_the_code_tables() -> None:
    line = proposal_schema(KEYS)["properties"]["lines"]["items"]["properties"]

    assert _choices(line["product_type"]) == set(KEYS)
    assert _choices(line["unit"]) == {unit.value for unit in Unit}
    assert _choices(line["allergen_strictness"]) == {value.value for value in AllergenStrictness}
    assert _choices(line["pack"]) == {value.value for value in PackPreference}
    assert set(line["exclude_allergens"]["items"]["enum"]) == set(EXCLUDABLE_ALLERGEN_CODES)
    assert set(line["required_claims"]["items"]["enum"]) == set(CLAIM_CODES)
    for name in ("product_type", "unit", "allergen_strictness", "pack", "quantity"):
        assert {"type": "null"} in line[name]["anyOf"]  # the model can say "the text does not say"


def test_the_code_lists_are_the_catalogs() -> None:
    assert set(EXCLUDABLE_ALLERGEN_CODES) == set(ALLERGEN_CODES) - {"X99"}
    assert len(CLAIM_CODES) == 21 and "FREE_FROM_LACTOSE" in CLAIM_CODES  # AIMO/docs/SCHEMA-AND-CODES.md 2.4


def test_the_schema_uses_only_keywords_gemini_enforces() -> None:
    assert _keywords(proposal_schema(KEYS)) & UNWANTED == set()


@pytest.mark.parametrize("keys", [(), ("milk", "Bad Key"), ("milk", "x" * 61), ("milk", "milk")])
def test_product_type_keys_that_are_not_plain_keys_are_refused(keys: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="product type"):
        proposal_schema(keys)
