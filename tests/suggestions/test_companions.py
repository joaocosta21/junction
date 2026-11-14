"""The forgotten item: "you usually order this with it, did you forget it?" (P15 R2, kind FORGOTTEN_ITEM).

Support = past orders that hold both the requested product and the other one; confidence = support / past orders
that hold the requested product; the quantity is the median of the other product in those orders. Only the last
8 orders count. It speaks from support 4 and confidence 0.75 (P15 section 4.1).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from tta.contracts.common import Unit
from tta.contracts.request import MAX_REQUEST_LINES, PurchaseRequest
from tta.contracts.suggestion import EvidenceSource, Serves, SuggestionKind
from tta.suggestions import OrderHistory, forgotten_items

MILK_LINE: dict[str, Any] = {
    "text": "100 litres of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L",
}


def _request(*lines: dict[str, Any]) -> PurchaseRequest:
    return PurchaseRequest.model_validate({"needed_by": "2026-11-16", "lines": list(lines or [MILK_LINE])})


def _weeks(milk_weeks: int, cream_weeks: int, *, cream: int = 10) -> list[dict[str, int]]:
    """`milk_weeks` weekly orders of milk 469363; the last `cream_weeks` of them also hold cream 463797."""
    return [{"469363": 100, **({"463797": cream} if week >= milk_weeks - cream_weeks else {})}
            for week in range(milk_weeks)]


def test_cream_in_7_of_the_last_8_milk_orders_is_suggested_with_its_median_quantity(
    make_history: Callable[..., OrderHistory],
) -> None:
    orders = _weeks(8, 7)
    orders[-1]["463797"] = 12  # the median of 10, 10, 10, 10, 10, 10, 12 stays 10
    history = make_history(orders)

    suggestions = forgotten_items(history, _request())

    assert len(suggestions) == 1
    found = suggestions[0]
    assert (found.kind, found.serves, found.product_id, found.quantity, found.unit) == (
        SuggestionKind.FORGOTTEN_ITEM, Serves.BUYER, "463797", Decimal(10), Unit.L,
    )
    assert found.name == "Arla cooking cream"
    assert found.request_line_index is None  # a new line
    assert found.sentence == (
        "In 7 of your last 8 orders with Arla milk (469363) you also ordered Arla cooking cream (463797), usually "
        "10 L. It is not in this request. From a synthetic order history."
    )
    evidence = found.evidence
    assert (evidence.source, evidence.synthetic) == (EvidenceSource.SYNTHETIC_HISTORY, True)
    assert (evidence.orders_considered, evidence.orders_matching) == (8, 7)
    assert (evidence.first_order, evidence.last_order) == (date(2026, 9, 21), date(2026, 11, 9))
    assert evidence.values == (10, 10, 10, 10, 10, 10, 12)
    assert evidence.thresholds == {"COMPANION_MIN_SUPPORT": 4, "COMPANION_MIN_CONFIDENCE": Decimal("0.75")}
    assert found.suggestion_id == "sug_forgotten_item_463797_test-kitchen"


def test_accepting_builds_a_new_request_with_one_more_line_and_changes_nothing_else(
    make_history: Callable[..., OrderHistory],
) -> None:
    request = _request()

    found = forgotten_items(make_history(_weeks(8, 7)), request)[0]

    assert found.accept_request is not None
    assert found.accept_request.lines[0] == request.lines[0]
    assert found.accept_request.needed_by == request.needed_by
    added = found.accept_request.lines[1]
    assert (added.product_ids, added.quantity, added.unit) == (("463797",), Decimal(10), Unit.L)
    assert added.text == "10 L of Arla cooking cream (463797), suggested from your order history"
    assert len(request.lines) == 1  # the request given is not changed


def test_six_of_eight_is_exactly_the_confidence_needed_and_speaks(make_history: Callable[..., OrderHistory]) -> None:
    assert forgotten_items(make_history(_weeks(8, 6)), _request())


def test_five_of_seven_is_below_the_confidence_and_stays_silent(make_history: Callable[..., OrderHistory]) -> None:
    assert forgotten_items(make_history(_weeks(7, 5)), _request()) == ()


def test_three_of_three_is_below_the_support_and_stays_silent(make_history: Callable[..., OrderHistory]) -> None:
    assert forgotten_items(make_history(_weeks(3, 3)), _request()) == ()


def test_four_of_four_is_enough_support(make_history: Callable[..., OrderHistory]) -> None:
    assert forgotten_items(make_history(_weeks(4, 4)), _request())


def test_only_the_last_8_orders_count(make_history: Callable[..., OrderHistory]) -> None:
    # Cream with every milk order four months ago, never in the last 8 orders.
    orders = [{"469363": 100, "463797": 10}] * 8 + [{"469363": 100}] * 8

    assert forgotten_items(make_history(orders), _request()) == ()


def test_an_item_already_in_the_request_is_not_suggested(make_history: Callable[..., OrderHistory]) -> None:
    cream = {"text": "5 litres of cream 463797", "product_ids": ["463797"], "quantity": 5, "unit": "L"}

    suggestions = forgotten_items(make_history(_weeks(8, 8)), _request(MILK_LINE, cream))

    assert suggestions == ()


def test_a_line_of_the_items_type_means_the_buyer_chose_and_it_stays_silent(
    make_history: Callable[..., OrderHistory],
) -> None:
    any_cream = {"text": "5 litres of cream", "product_type": "cream", "quantity": 5, "unit": "L"}

    assert forgotten_items(make_history(_weeks(8, 8)), _request(MILK_LINE, any_cream)) == ()


def test_another_product_of_the_items_type_never_ordered_with_it_stays_silent(
    make_history: Callable[..., OrderHistory],
) -> None:
    # Whole milk 463047 and soya 464013 always go together; the request asks for soya and the other milk 469363.
    orders = [{"464013": 200, "463047": 20}] * 8 + [{"469363": 100}]
    other_milk = {"text": "100 litres of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}
    soya = {"text": "200 litres of soya drink 464013", "product_ids": ["464013"], "quantity": 200, "unit": "L"}

    assert forgotten_items(make_history(orders), _request(soya, other_milk)) == ()


def test_a_product_of_the_same_type_ordered_together_with_it_is_a_companion_not_an_alternative(
    make_history: Callable[..., OrderHistory],
) -> None:
    # The ward's pattern: rice drink with soya drink, both plant drinks, in 7 of the last 8 orders.
    orders = [{"464013": 200, "473424": 20}] * 3 + [{"464013": 200}] + [{"464013": 200, "473424": 20}] * 4
    soya = {"text": "200 litres of soya drink 464013", "product_ids": ["464013"], "quantity": 200, "unit": "L"}

    suggestions = forgotten_items(make_history(orders), _request(soya))

    assert [(found.product_id, found.quantity) for found in suggestions] == [("473424", Decimal(20))]


def test_a_type_only_line_counts_the_products_the_offer_chose_for_it(
    make_history: Callable[..., OrderHistory],
) -> None:
    any_milk = {"text": "100 litres of milk", "product_type": "milk", "quantity": 100, "unit": "L"}
    history = make_history(_weeks(8, 7))

    assert forgotten_items(history, _request(any_milk)) == ()
    assert [found.product_id for found in forgotten_items(history, _request(any_milk), offered_product_ids=["469363"])
            ] == ["463797"]


def test_with_two_requested_products_each_item_is_suggested_once_from_its_strongest_companion(
    make_history: Callable[..., OrderHistory],
) -> None:
    orders = [{"469363": 100, "464615": 5, "463797": 10}] * 4 + [{"469363": 100, "463797": 10}] * 4
    yoghurt = {"text": "5 kg of yoghurt 464615", "product_ids": ["464615"], "quantity": 5, "unit": "KG"}

    suggestions = forgotten_items(make_history(orders), _request(MILK_LINE, yoghurt))

    assert len(suggestions) == 1
    assert suggestions[0].product_id == "463797"
    # Both give a confidence of 1.0; the milk's 8 orders are more support than the yoghurt's 4.
    assert (suggestions[0].evidence.orders_considered, suggestions[0].evidence.orders_matching) == (8, 8)


def test_the_strongest_suggestion_comes_first(make_history: Callable[..., OrderHistory]) -> None:
    orders = [{"469363": 100, "463797": 10, "464615": 5}] * 6 + [{"469363": 100, "463797": 10}] * 2

    suggestions = forgotten_items(make_history(orders), _request())

    assert [found.product_id for found in suggestions] == ["463797", "464615"]


def test_a_full_request_cannot_take_one_more_line_so_nothing_is_suggested(
    make_history: Callable[..., OrderHistory],
) -> None:
    filler = {"text": "1 kg of beef 466988", "product_ids": ["466988"], "quantity": 3, "unit": "KG"}
    request = _request(MILK_LINE, *[filler] * (MAX_REQUEST_LINES - 1))

    assert forgotten_items(make_history(_weeks(8, 8)), request) == ()


def test_a_product_never_ordered_finds_no_companion(make_history: Callable[..., OrderHistory]) -> None:
    soya = {"text": "200 litres of soya drink 464013", "product_ids": ["464013"], "quantity": 200, "unit": "L"}

    assert forgotten_items(make_history(_weeks(8, 8)), _request(soya)) == ()


def test_without_a_name_the_sentence_says_the_product_id(make_history: Callable[..., OrderHistory]) -> None:
    found = forgotten_items(make_history(_weeks(8, 8), names={}), _request())[0]

    assert found.sentence.startswith("In 8 of your last 8 orders with product 469363 you also ordered product 463797")


def test_fewer_orders_with_the_product_than_the_window_are_said_as_such(
    make_history: Callable[..., OrderHistory],
) -> None:
    orders = [{"464615": 5}] * 3 + [{"469363": 100, "463797": 10}] * 5

    found = forgotten_items(make_history(orders), _request())[0]

    assert found.sentence.startswith(
        "In 5 of the 5 orders with Arla milk (469363) among your last 8 orders you also ordered Arla cooking cream"
    )


def test_an_order_book_history_is_not_called_synthetic(make_history: Callable[..., OrderHistory]) -> None:
    history = make_history(_weeks(8, 8))
    from_orders = OrderHistory(
        customer_id=history.customer_id, orders=history.orders, usual=history.usual, names=history.names,
        source=EvidenceSource.ORDER_BOOK, synthetic=False,
    )

    found = forgotten_items(from_orders, _request())[0]

    assert "synthetic" not in found.sentence
    assert (found.evidence.source, found.evidence.synthetic) == (EvidenceSource.ORDER_BOOK, False)
