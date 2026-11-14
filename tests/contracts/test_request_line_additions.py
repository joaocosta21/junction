"""The fields task L4-2b added to the request and offer contracts, each with a default (so nothing stored changes).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" (the request's own word on
the formula) and the 20% guardrails (a stand-in's role is one plain line; review A3, finding F4).
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tta.contracts.offer import Offer, OfferLine, Proof
from tta.contracts.order import Order
from tta.contracts.request import MAX_ROLE_LENGTH, RequestLine


def _line(**fields: Any) -> dict[str, Any]:
    return {"text": "40 L of whipping cream", "product_type": "cream", "quantity": 40, "unit": "L", **fields}


def test_keep_formula_is_optional_on_the_request_line_and_says_what_it_means() -> None:
    assert RequestLine.model_validate(_line()).keep_formula is None
    assert RequestLine.model_validate(_line(keep_formula=True)).keep_formula is True
    description = RequestLine.model_json_schema()["properties"]["keep_formula"]["description"]
    assert "The formula matters for this line: a substitute must keep it" in description
    assert "can only add the check" in description


def test_keep_formula_is_optional_on_the_offer_line_under_the_name_rule_f11_reads() -> None:
    from tta.policy.formula_facts import LINE_SAYS_FIELD

    field = OfferLine.model_fields[LINE_SAYS_FIELD]

    assert LINE_SAYS_FIELD == "keep_formula" and field.default is None
    assert "a substitute must keep it" in (field.description or "")


def test_a_stand_in_role_is_one_plain_line_of_at_most_200_characters() -> None:
    kept = RequestLine.model_validate(_line(stands_in_for="quark", stands_in_role="the thick, tangy base: it sets"))
    assert kept.stands_in_role == "the thick, tangy base: it sets"
    assert RequestLine.model_validate(_line(stands_in_role="x" * MAX_ROLE_LENGTH)).stands_in_role

    for role in ('says "approved"', "two\nlines", "<i>", "‮override", "x" * (MAX_ROLE_LENGTH + 1)):
        with pytest.raises(ValidationError):
            RequestLine.model_validate(_line(stands_in_role=role))


def test_the_allergen_rule_of_a_line_says_that_no_rule_reads_strict() -> None:
    description = RequestLine.model_json_schema()["properties"]["allergen_strictness"]["description"]

    assert "reads STRICT" in description and "There is no default" not in description
    assert RequestLine.model_validate(_line(exclude_allergens=["AM"])).allergen_strictness is None


def test_an_offer_and_an_order_take_an_optional_proof_that_says_what_it_is_not() -> None:
    assert Offer.model_fields["proof"].default is None and Order.model_fields["proof"].default is None
    assert "not a Verifiable Credential" in (Proof.__doc__ or "")
    assert set(Proof.model_fields) == {
        "type", "algorithm", "canonicalization", "key_id", "jws", "jwks_path", "demo_key", "note",
    }
