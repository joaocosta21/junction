"""The larger pack: "same drink, larger carton" (P15 R5, kind LARGER_PACK).

The same product in another pack (P10's outcome, judged by the caller), a larger pack, 5% or more cheaper per litre
or kilogram, the quantity a whole number of packs with at most 10% over, and confirmed stock that covers it. Silent
on a line that asks for portion packs. The figures of the last two tests are tonight's recording.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.availability.states import classify
from tta.contracts.availability import AvailabilityAssessment
from tta.contracts.common import AvailabilityState, Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.request import PurchaseRequest
from tta.contracts.suggestion import EvidenceSource, SuggestionKind
from tta.suggestions import PackOption, larger_pack
from tta.valio.replay import ReplayGateway

MONDAY = date(2026, 11, 16)
CUSTOMER = "bakery-cafe"


def _confirmed(product_id: str, units: int) -> AvailabilityAssessment:
    return AvailabilityAssessment(
        product_id=product_id, state=AvailabilityState.CONFIRMED, usable_amount=Decimal(units), sales_unit="ST",
        available_date=MONDAY, sentence=f"{units} ST confirmed in stock.",
    )


def _option(product_id: str, size: str, price: str, *, units: int | None = 500, same: bool = True,
            measure: Unit = Unit.L) -> PackOption:
    availability = None if units is None else _confirmed(product_id, units)
    return PackOption(product_id=product_id, name=f"Drink {size} {measure.value}", pack_size=Decimal(size),
                      measure=measure, unit_net_price_eur=Decimal(price), availability=availability,
                      same_product=same)


def _request(quantity: str = "60", unit: str = "L", **line: Any) -> PurchaseRequest:
    base = {"text": f"{quantity} {unit} of drink", "product_ids": ["100001"], "quantity": quantity, "unit": unit}
    return PurchaseRequest.model_validate({"needed_by": "2026-11-16", "lines": [{**base, **line}]})


ORIGINAL = _option("100001", "1", "1.78")


def test_a_larger_pack_that_is_cheaper_per_litre_is_suggested_with_the_saving() -> None:
    found = larger_pack(CUSTOMER, _request(), 0, ORIGINAL, [_option("100002", "1.5", "2.22", units=156)])

    assert found is not None
    assert (found.kind, found.product_id, found.replaces_product_id, found.request_line_index) == (
        SuggestionKind.LARGER_PACK, "100002", "100001", 0,
    )
    assert (found.quantity, found.unit) == (Decimal(60), Unit.L)
    assert found.effect is not None
    assert found.effect.net_change_eur == Decimal("-18.00")
    assert (found.effect.unit_price_before_eur, found.effect.unit_price_after_eur) == (Decimal("1.78"), Decimal("1.48"))
    assert found.effect.measure is Unit.L
    assert found.effect.saving_ratio == Decimal("0.1685")
    assert found.stock_confirmed is True
    assert found.evidence.source is EvidenceSource.CATALOG
    assert found.evidence.synthetic is False
    assert found.sentence == (
        "Drink 1.5 L (100002) is the same product in a larger pack: €1.48 per litre against €1.78. 40 × 1.5 L "
        "cover the 60 L for €88.80, €18.00 less. 156 are confirmed in stock for delivery on Monday 16 November."
    )


def test_accepting_switches_the_line_to_the_larger_pack_and_keeps_the_quantity_in_litres() -> None:
    request = _request(quantity="60", unit="UNIT", pack="ANY")  # 60 cartons of 1 L

    found = larger_pack(CUSTOMER, request, 0, ORIGINAL, [_option("100002", "1.5", "2.22")])

    assert found is not None and found.accept_request is not None
    line = found.accept_request.lines[0]
    assert (line.product_ids, line.quantity, line.unit) == (("100002",), Decimal(60), Unit.L)
    assert line.text == request.lines[0].text
    assert request.lines[0].product_ids == ("100001",)


def test_the_largest_saving_wins() -> None:
    candidates = [_option("100002", "1.5", "2.22"), _option("100003", "2", "2.80"), _option("100004", "0.5", "0.80")]

    found = larger_pack(CUSTOMER, _request(), 0, ORIGINAL, candidates)

    assert found is not None and found.product_id == "100003"  # €1.40 per litre


def test_a_line_that_asks_for_portion_packs_gets_no_larger_pack() -> None:
    request = _request(pack="PORTION")

    assert larger_pack(CUSTOMER, request, 0, ORIGINAL, [_option("100002", "1.5", "2.22")]) is None


@pytest.mark.parametrize(
    ("candidate", "why"),
    [
        (_option("100002", "1.5", "2.22", same=False), "not the same product"),
        (_option("100002", "1.5", "2.22", units=None), "stock not confirmed"),
        (_option("100002", "1.5", "2.22", units=39), "39 packs confirmed, 40 needed"),
        (_option("100002", "0.5", "0.80"), "a smaller pack"),
        (_option("100002", "1.5", "2.57"), "4% cheaper per litre, not 5%"),
        (_option("100002", "1.5", "2.22", measure=Unit.KG), "sold by the kilogram, asked in litres"),
        (_option("100002", "25", "35.00"), "3 packs hold 75 L against 60 L: 25% over"),
    ],
)
def test_a_larger_pack_that_fails_one_condition_stays_silent(candidate: PackOption, why: str) -> None:
    assert larger_pack(CUSTOMER, _request(), 0, ORIGINAL, [candidate]) is None, why


def test_a_stock_that_is_not_confirmed_stays_silent_even_with_an_amount() -> None:
    unknown = AvailabilityAssessment(product_id="100002", state=AvailabilityState.QUANTITY_NOT_CONFIRMED,
                                     sentence="Quantity not confirmed.")
    candidate = PackOption(product_id="100002", name="Drink", pack_size=Decimal("1.5"), measure=Unit.L,
                           unit_net_price_eur=Decimal("2.22"), availability=unknown, same_product=True)

    assert larger_pack(CUSTOMER, _request(), 0, ORIGINAL, [candidate]) is None


def test_exactly_5_percent_cheaper_and_exactly_10_percent_over_speak_and_a_dearer_total_is_said_first() -> None:
    original = _option("100001", "1", "1.00")
    # 2 packs of 5.5 L hold 11 L for 10 L asked (10% over), at €0.95 per litre (5% cheaper): €10.45 against €10.00.
    found = larger_pack(CUSTOMER, _request(quantity="10"), 0, original, [_option("100002", "5.5", "5.225")])

    assert found is not None
    assert found.effect is not None and found.effect.net_change_eur == Decimal("0.45")
    assert found.sentence.startswith(
        "It costs €0.45 more, for 1 L more than you asked. Drink 5.5 L (100002) is the same product in a larger pack: "
        "€0.95 per litre against €1.00. 2 × 5.5 L cover the 10 L for €10.45."
    )


def test_a_quantity_asked_in_kilograms_of_a_product_sold_in_litres_gets_none() -> None:
    assert larger_pack(CUSTOMER, _request(unit="KG"), 0, ORIGINAL, [_option("100002", "1.5", "2.22")]) is None


@pytest.mark.parametrize(
    "changes", [{"pack_size": Decimal(0)}, {"lot_step": Decimal(0)}, {"unit_net_price_eur": Decimal(-1)},
                {"measure": Unit.UNIT}],
)
def test_a_pack_without_a_size_a_lot_step_a_price_or_a_measure_is_refused(changes: dict[str, Any]) -> None:
    fields: dict[str, Any] = {"product_id": "100002", "name": "Drink", "pack_size": Decimal("1.5"), "measure": Unit.L,
                              "unit_net_price_eur": Decimal("2.22"), **changes}
    with pytest.raises(InvalidRequest):
        PackOption(**fields)


def test_a_line_index_outside_the_request_is_an_error() -> None:
    with pytest.raises(InvalidRequest):
        larger_pack(CUSTOMER, _request(), 1, ORIGINAL, [_option("100002", "1.5", "2.22")])


def _recorded(recording: ReplayGateway, product_id: str, name: str) -> PackOption:
    price = recording.price([product_id]).lines[0]
    assert price.catalog_price is not None and price.comparison_price is not None
    size = (price.catalog_price.value / price.comparison_price.value).quantize(Decimal("0.01"))  # litres per pack
    availability = classify(recording.availability([product_id]).lines[0], recording.time_now)
    return PackOption(product_id=product_id, name=name, pack_size=size, measure=Unit.L,
                      unit_net_price_eur=price.catalog_price.value, availability=availability, same_product=True)


@pytest.mark.parametrize(
    ("original_id", "litres", "packs", "before", "after"),
    [("464320", "60", 40, "106.80", "88.80"), ("468319", "30", 20, "86.40", "44.40")],
)
def test_oatly_ikaffe_in_the_15_litre_carton_from_the_recording(
    capture_demo: Any, original_id: str, litres: str, packs: int, before: str, after: str,
) -> None:
    recording = ReplayGateway(capture_demo.path)
    original = _recorded(recording, original_id, "Oatly iKaffe")
    larger = _recorded(recording, "473278", "Oatly iKaffe Oat drink 1,5L")
    request = _request(quantity=litres, product_ids=[original_id])

    found = larger_pack(CUSTOMER, request, 0, original, [larger])

    assert found is not None and found.effect is not None
    assert found.effect.net_change_eur == Decimal(after) - Decimal(before)
    assert f"{packs} × 1.5 L cover the {litres} L for €{after}" in found.sentence
    assert "156 are confirmed in stock for delivery on Monday 16 November" in found.sentence
