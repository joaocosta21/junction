"""The cheaper product with the same formula (P10 F6, kind CHEAPER_SAME_FORMULA), as a pure function."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.availability import AvailabilityAssessment
from tta.contracts.common import AvailabilityState, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import FormulaCheck, FormulaOutcome
from tta.contracts.request import PurchaseRequest
from tta.contracts.suggestion import EvidenceSource, SuggestionKind
from tta.suggestions import CheaperOption, PackOption, cheaper_same_formula

MONDAY = date(2026, 11, 16)
CUSTOMER = "bakery-cafe"
KEPT = "Same formula within our tolerance of 15% or 1 g per nutrient (salt 0.25 g): fat 36 g against 35 g per 100 g."


def _pack(product_id: str, size: str, price: str, *, units: int | None = 500, same: bool = False) -> PackOption:
    availability = None if units is None else AvailabilityAssessment(
        product_id=product_id, state=AvailabilityState.CONFIRMED, usable_amount=Decimal(units), sales_unit="ST",
        available_date=MONDAY, sentence=f"{units} ST confirmed in stock.",
    )
    return PackOption(product_id=product_id, name=f"Cream {product_id}", pack_size=Decimal(size), measure=Unit.L,
                      unit_net_price_eur=Decimal(price), availability=availability, same_product=same)


def _option(product_id: str, size: str, price: str, outcome: FormulaOutcome = FormulaOutcome.OTHER_BRAND,
            **pack: Any) -> CheaperOption:
    sentence = KEPT if outcome is not FormulaOutcome.DIFFERENT else "Different formula: fat 15 g, not 35 g per 100 g."
    return CheaperOption(pack=_pack(product_id, size, price, **pack),
                         formula=FormulaCheck(outcome=outcome, sentence=sentence))


def _request(quantity: str = "40", **line: Any) -> PurchaseRequest:
    base = {"text": "cream", "product_ids": ["100001"], "quantity": quantity, "unit": "L"}
    return PurchaseRequest.model_validate({"needed_by": "2026-11-16", "lines": [{**base, **line}]})


ORIGINAL = _pack("100001", "1", "7.37")


def test_a_cheaper_product_that_keeps_the_formula_states_both_prices_and_the_tolerance() -> None:
    found = cheaper_same_formula(CUSTOMER, _request(), 0, ORIGINAL, [_option("100002", "1", "5.77", units=48)])

    assert found is not None
    assert (found.kind, found.product_id, found.replaces_product_id, found.request_line_index) == (
        SuggestionKind.CHEAPER_SAME_FORMULA, "100002", "100001", 0,
    )
    assert found.sentence == (
        "Cream 100002 (100002) costs €5.77 per litre against €7.37 for Cream 100001 (100001): 22% less. "
        f"It keeps the formula within our tolerance. {KEPT} It is another brand. "
        "40 × 1 L cover the 40 L for €230.80, €64.00 less. "
        "48 are confirmed in stock for delivery on Monday 16 November."
    )
    assert found.effect is not None and found.effect.net_change_eur == Decimal("-64.00")
    assert found.effect.saving_ratio == Decimal("0.2171")
    assert found.evidence.source is EvidenceSource.CATALOG and found.evidence.synthetic is False
    assert found.evidence.thresholds["CHEAPER_MIN_SAVING"] == Decimal("0.05")
    assert found.accept_request is not None and found.accept_request.lines[0].product_ids == ("100002",)
    assert found.stock_confirmed is True and found.checks == (KEPT,)


def test_the_largest_saving_is_the_one_suggested() -> None:
    found = cheaper_same_formula(CUSTOMER, _request(), 0, ORIGINAL,
                                 [_option("100002", "1", "5.77"), _option("100003", "1", "4.00")])

    assert found is not None and found.product_id == "100003"


@pytest.mark.parametrize(
    "candidate",
    [
        _option("100002", "1", "4.00", FormulaOutcome.DIFFERENT),  # the formula is not kept
        _option("100002", "1", "4.00", FormulaOutcome.NOT_KNOWN),  # not known is never read as the same
        _option("100002", "1", "7.10"),  # 3.7% cheaper: under the 5% threshold
        _option("100002", "1", "5.77", units=39),  # confirmed stock does not cover the 40 L
        _option("100002", "1", "5.77", units=None),  # no availability at all
        _option("100002", "25", "100.00"),  # one 25 L pack for 40 L: two packs hold 25% more than asked
        _option("100002", "1.5", "5.00", FormulaOutcome.SAME_PRODUCT_OTHER_PACK, same=True),  # the larger pack's
        _option("100001", "1", "5.00"),  # the product itself
    ],
)
def test_it_stays_silent(candidate: CheaperOption) -> None:
    assert cheaper_same_formula(CUSTOMER, _request(), 0, ORIGINAL, [candidate]) is None


def test_where_the_formula_matters_another_brand_stays_silent_and_the_same_brand_speaks() -> None:
    other = _option("100002", "1", "5.77", FormulaOutcome.OTHER_BRAND)
    same = _option("100003", "1", "6.00", FormulaOutcome.SAME_BRAND)

    assert cheaper_same_formula(CUSTOMER, _request(), 0, ORIGINAL, [other], same_brand_only=True) is None
    found = cheaper_same_formula(CUSTOMER, _request(), 0, ORIGINAL, [other, same], same_brand_only=True)
    assert found is not None and found.product_id == "100003" and "another brand" not in found.sentence


def test_a_line_for_portion_packs_or_in_another_measure_gets_none() -> None:
    candidate = [_option("100002", "1", "5.77")]

    assert cheaper_same_formula(CUSTOMER, _request(pack="PORTION"), 0, ORIGINAL, candidate) is None
    assert cheaper_same_formula(CUSTOMER, _request(unit="KG"), 0, ORIGINAL, candidate) is None


def test_a_line_the_request_does_not_have_is_refused() -> None:
    with pytest.raises(InvalidRequest, match="The request has no line 2."):
        cheaper_same_formula(CUSTOMER, _request(), 1, ORIGINAL, [])
