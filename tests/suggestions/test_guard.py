"""The guard (P15 section 4.3): one check function, every suggestion, the reason kept when one is dropped.

Real products of tonight's recording, at the recording's instant: 463797 cooking cream (114 confirmed), 469346
whipping cream, 464306 milk whose quantity is not confirmed, 464517 the school's yoghurt.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.suggestion import Suggestion, SuggestionEvidence, SuggestionKind
from tta.suggestions.guard import DroppedSuggestion, DropReason, GuardContext, Proposal, check
from tta.suggestions.requests import with_line_added, with_line_changed
from tta.suggestions.service import look_up

HOTEL, WARD, SCHOOL, BAKERY = "hotel-kitchen", "allergy-ward", "school-kitchen", "bakery-cafe"
MILK = {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}
CREAM = {"text": "40 L of whipping cream 469346", "product_ids": ["469346"], "quantity": 40, "unit": "L"}
EVIDENCE = SuggestionEvidence(source="SYNTHETIC_HISTORY", synthetic=True, orders_considered=8, orders_matching=7)


def _added(world: Any, base: dict[str, Any], product_id: str, quantity: str = "10", unit: str = "L",
           kind: SuggestionKind = SuggestionKind.FORGOTTEN_ITEM, **line: Any) -> tuple[Any, Suggestion]:
    request = world.request(base)
    new = {"text": "suggested", "product_ids": [product_id], "quantity": quantity, "unit": unit, **line}
    accept = with_line_added(request, world.request(new).lines[0])
    suggestion = Suggestion(suggestion_id=f"sug_test_{product_id}", kind=kind, customer_id="test",
                            product_id=product_id, name=f"Product {product_id}", quantity=Decimal(quantity),
                            unit=unit, sentence="Suggested.", evidence=EVIDENCE, accept_request=accept)
    return request, suggestion


def _replacing(world: Any, base: dict[str, Any], product_id: str, kind: SuggestionKind) -> tuple[Any, Suggestion]:
    request = world.request(base)
    suggestion = Suggestion(
        suggestion_id=f"sug_test_{product_id}", kind=kind, customer_id="test", request_line_index=0,
        product_id=product_id, name=f"Product {product_id}", quantity=request.lines[0].quantity,
        unit=request.lines[0].unit, replaces_product_id=request.lines[0].product_ids[0], sentence="Suggested.",
        evidence=EVIDENCE, accept_request=with_line_changed(request, 0, product_ids=[product_id]),
    )
    return request, suggestion


def _check(world: Any, customer_id: str, request: Any, suggestion: Suggestion, **options: Any) -> Any:
    context = GuardContext(request=request, profile=world.profile(customer_id),
                           lookup=look_up(world.ports, [suggestion.product_id]), catalog=world.catalog, **options)
    return check(Proposal(suggestion=suggestion), context)


def test_a_product_that_passes_leaves_complete(world_now: Any) -> None:
    request, suggestion = _added(world_now, MILK, "463797")

    passed = _check(world_now, HOTEL, request, suggestion)

    assert isinstance(passed, Suggestion)
    assert passed.stock_confirmed is True and passed.availability.usable_amount == Decimal(114)
    assert passed.effect.net_change_eur == Decimal("33.10")
    assert passed.checks[-1] == "114 sales units are confirmed in stock for delivery on Monday 16 November."


@pytest.mark.parametrize(
    ("customer_id", "base", "product_id", "extra", "reason", "said"),
    [
        (HOTEL, MILK, "9999999", {}, DropReason.UNKNOWN_PRODUCT, "The product is not in the catalog."),
        (HOTEL, MILK, "463797", {"quantity": "500"}, DropReason.STOCK_TOO_LOW,
         "114 sales units are confirmed in stock and 500 are needed for 500 L."),
        (HOTEL, MILK, "464306", {}, DropReason.STOCK_NOT_CONFIRMED, "Quantity not confirmed: "),
        (HOTEL, MILK, "463797", {"required_claims": ["VEGAN"]}, DropReason.DIETARY_CLAIM_MISSING,
         "The request line requires VEGAN, which this product does not carry."),
        (SCHOOL, MILK, "464517", {"unit": "KG", "quantity": "20"}, DropReason.ALLERGEN_NOT_RULED_OUT,
         "The product makes no statement about tree nuts (AN): a dietitian must decide."),
        (WARD, MILK, "463797", {}, "ALLERGEN_DECLARED", "milk"),
    ],
)
def test_a_product_that_fails_a_check_is_dropped_with_the_reason(
    world_now: Any, customer_id: str, base: dict[str, Any], product_id: str, extra: dict[str, Any], reason: str,
    said: str,
) -> None:
    line = {key: value for key, value in extra.items() if key not in ("quantity", "unit")}
    request, suggestion = _added(world_now, base, product_id, extra.get("quantity", "10"), extra.get("unit", "L"),
                                 **line)

    dropped = _check(world_now, customer_id, request, suggestion)

    assert isinstance(dropped, DroppedSuggestion)
    assert (dropped.reason, dropped.product_id, dropped.kind) == (reason, product_id, SuggestionKind.FORGOTTEN_ITEM)
    assert said in dropped.sentence


def test_a_product_whose_cut_off_has_passed_is_dropped_with_the_offers_own_reason(world_now: Any) -> None:
    request, suggestion = _added(world_now, MILK, "471690")  # Terminal, cut-off passed at the recording's instant

    dropped = _check(world_now, HOTEL, request, suggestion)

    assert isinstance(dropped, DroppedSuggestion) and dropped.reason == "CUTOFF_PASSED"


def test_a_product_already_ordered_for_the_date_is_dropped(world_now: Any) -> None:
    request, suggestion = _added(world_now, MILK, "463797")

    dropped = _check(world_now, HOTEL, request, suggestion, already_ordered=("463797",))

    assert isinstance(dropped, DroppedSuggestion) and dropped.reason == DropReason.ALREADY_ORDERED


def test_a_replacement_keeps_the_formula_where_the_profile_says_it_matters(world_now: Any) -> None:
    """Cooking cream 10% for whipping cream: the bakery's profile says the formula matters, the hotel's does not."""
    request, suggestion = _replacing(world_now, CREAM, "463797", SuggestionKind.USUAL_PRODUCT)

    at_the_bakery = _check(world_now, BAKERY, request, suggestion)
    at_the_hotel = _check(world_now, HOTEL, request, suggestion)

    assert isinstance(at_the_bakery, DroppedSuggestion) and at_the_bakery.reason == DropReason.FORMULA_NOT_KEPT
    assert at_the_bakery.sentence.startswith("Different formula: fat ")
    assert isinstance(at_the_hotel, Suggestion)


def test_the_cheaper_kind_keeps_the_formula_whatever_the_profile_says(world_now: Any) -> None:
    request, suggestion = _replacing(world_now, CREAM, "463797", SuggestionKind.CHEAPER_SAME_FORMULA)

    dropped = _check(world_now, HOTEL, request, suggestion)

    assert isinstance(dropped, DroppedSuggestion) and dropped.reason == DropReason.FORMULA_NOT_KEPT


def test_a_replacement_that_loses_a_dietary_claim_is_dropped(world_now: Any) -> None:
    """The soya drink 464013 in place of the lactose-free milk 469363 carries no lactose-free claim... or adds soy:
    either way the guard does not let it replace the milk."""
    request, suggestion = _replacing(world_now, MILK, "464013", SuggestionKind.USUAL_PRODUCT)

    dropped = _check(world_now, HOTEL, request, suggestion)

    assert isinstance(dropped, DroppedSuggestion)
    assert dropped.reason in (DropReason.DIETARY_CLAIM_MISSING, DropReason.ADDS_ALLERGEN)
