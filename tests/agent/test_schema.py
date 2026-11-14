"""The schema the model's answer is held to follows the typed request of the contract (SPEC sections 3, 11)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from tta.agent.parser import RequestProposal
from tta.agent.schema import CLAIM_CODES, EXCLUDABLE_ALLERGEN_CODES, LABEL_CODES, proposal_schema
from tta.allergens import ALLERGEN_CODES
from tta.contracts.common import AllergenStrictness, PackPreference, Preference, Unit
from tta.contracts.request import PurchaseRequest, RequestLine

KEYS = ("milk", "plant_drink", "beef_chuck")
# Not the buyer's to say, so never the reader's to set. `standing_order_id`: the standing order a request renews.
# `accepted_suggestion_id`: accepting a suggestion is a person's click that builds a new request (decision B8), so
# no reading of free text may claim it.
REQUEST_FIELDS_THE_GATEWAY_SETS = {"standing_order_id", "accepted_suggestion_id"}
# `text`: the buyer's own words, set by the parser. `stands_in_for`, `stands_in_role`: the menu planner.
LINE_FIELDS_THE_GATEWAY_SETS = {"text", "stands_in_for", "stands_in_role"}
# `keep_formula`: the buyer's words say what the product is for ("cream for whipping"), so the reader sets it.
READER_MAY_SET = {"keep_formula"}
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


def test_the_schema_has_the_fields_of_the_typed_request_except_the_buyers_words() -> None:
    schema = proposal_schema(KEYS)
    line = schema["properties"]["lines"]["items"]

    # Every field of the contract is placed: the reader may set it (it is in the schema), or the gateway sets it.
    # A field the contract gains fails this test until it is placed in one of the two.
    assert set(schema["properties"]) == set(PurchaseRequest.model_fields) - REQUEST_FIELDS_THE_GATEWAY_SETS
    assert set(line["properties"]) == set(RequestLine.model_fields) - LINE_FIELDS_THE_GATEWAY_SETS
    assert set(line["properties"]) >= READER_MAY_SET
    for node in (schema, line):
        assert set(node["required"]) == set(node["properties"])  # nothing may be left out: null says "not said"
        assert node["additionalProperties"] is False


def test_keep_formula_is_true_or_not_said() -> None:
    keep_formula = proposal_schema(KEYS)["properties"]["lines"]["items"]["properties"]["keep_formula"]

    assert keep_formula["anyOf"] == [{"type": "boolean"}, {"type": "null"}]
    assert "whipping cream" in keep_formula["description"]  # a product's own name is not a use


def test_every_recording_still_parses_with_the_schema_as_it_is_now(fixtures_agent_dir: Path) -> None:
    """A recording made before a field existed leaves it out: the proposal reads it as not said."""
    recordings = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(fixtures_agent_dir.glob("*.json"))]
    proposals = [recording["proposal"] for recording in recordings if recording["kind"] == "parse"]

    assert len(proposals) == 7  # the seven parse recordings of fixtures/agent
    for answer in proposals:
        proposal = RequestProposal.model_validate(json.loads(json.dumps(answer), parse_float=Decimal))
        assert all(line.keep_formula is None for line in proposal.lines)


def test_every_choice_is_a_closed_list_taken_from_the_contract_and_the_code_tables() -> None:
    line = proposal_schema(KEYS)["properties"]["lines"]["items"]["properties"]

    assert _choices(line["product_type"]) == set(KEYS)
    assert _choices(line["unit"]) == {unit.value for unit in Unit}
    assert _choices(line["allergen_strictness"]) == {value.value for value in AllergenStrictness}
    assert _choices(line["pack"]) == {value.value for value in PackPreference}
    assert set(line["exclude_allergens"]["items"]["enum"]) == set(EXCLUDABLE_ALLERGEN_CODES)
    assert set(line["required_claims"]["items"]["enum"]) == set(CLAIM_CODES)
    assert set(line["required_labels"]["items"]["enum"]) == set(LABEL_CODES)
    assert _choices(proposal_schema(KEYS)["properties"]["prefer"]) == {value.value for value in Preference}
    for name in ("product_type", "unit", "allergen_strictness", "pack", "quantity"):
        assert {"type": "null"} in line[name]["anyOf"]  # the model can say "the text does not say"
    assert {"type": "null"} in proposal_schema(KEYS)["properties"]["prefer"]["anyOf"]


def test_the_code_lists_are_the_catalogs() -> None:
    assert set(EXCLUDABLE_ALLERGEN_CODES) == set(ALLERGEN_CODES) - {"X99"}
    assert len(CLAIM_CODES) == 21 and "FREE_FROM_LACTOSE" in CLAIM_CODES  # AIMO/docs/SCHEMA-AND-CODES.md 2.4
    # The 19 packagingMarkedLabel ids less the three temperature ones (AIMO/docs/PRODUCT-DATA.md 3.5).
    assert len(LABEL_CODES) == 16 and {"EU_ORGANIC_FARMING", "MARINE_STEWARDSHIP_COUNCIL_LABEL"} <= set(LABEL_CODES)
    assert not {"warmTemperature", "coolTemperature", "freezeTemperature"} & set(LABEL_CODES)


def test_the_schema_uses_only_keywords_gemini_enforces() -> None:
    assert _keywords(proposal_schema(KEYS)) & UNWANTED == set()


@pytest.mark.parametrize("keys", [(), ("milk", "Bad Key"), ("milk", "x" * 61), ("milk", "milk")])
def test_product_type_keys_that_are_not_plain_keys_are_refused(keys: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="product type"):
        proposal_schema(keys)
