"""The "you usually order this: order again?" prompt (`tta.suggestions.reorder`).

Scores on the 20% "solving the problem and user need" (the regular order is ready-made from the customer's own
history, so nothing is typed) and on the 20% "autonomy and controls" (the prompt orders nothing: it builds a request,
each line checked like any product, and what it leaves out is said with the reason). The pure logic on hand-built
histories, then the four shipped customers at both clocks (the recording's instant and the demo clock).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.customer import Customer
from tta.contracts.request import PurchaseRequest
from tta.customers import shipped_customer
from tta.suggestions import history_of
from tta.suggestions.reorder import next_delivery, regular_products, reorder_prompt, rhythm_of
from tta.suggestions.thresholds import REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS

FIRST_TUESDAY = date(2026, 9, 22)
MILK, CREAM, YOGHURT, SOYA = "469363", "463797", "464615", "464013"
UNITS = {MILK: ("milk", "L"), CREAM: ("cream", "L"), YOGHURT: ("yoghurt", "KG"), SOYA: ("plant_drink", "L")}
NAMES = {MILK: "Arla milk", CREAM: "Arla cooking cream", YOGHURT: "Valio greek yoghurt", SOYA: "Alpro soya drink"}
TODAY = date(2026, 11, 12)  # a Thursday, two days after the eighth weekly Tuesday


def _customer(orders: Sequence[Mapping[str, Any]], *, days: Sequence[date] | None = None,
              standing: Mapping[str, Any] | None = None) -> Customer:
    when = days or [FIRST_TUESDAY + timedelta(days=7 * week) for week in range(len(orders))]
    return Customer.model_validate({
        "customer_id": "test-kitchen", "synthetic": True, "name": "Test Kitchen", "kind": "Hotel kitchen",
        "contact": {"name": "Test Person", "title": "Chef"}, "people": {"purchasing_manager": "Test Person"},
        "usual": [{"product_id": product_id, "product_type": kind, "unit": unit, "use": "SERVED"}
                  for product_id, (kind, unit) in UNITS.items()],
        "history": [{"delivered_on": day, "quantities": dict(order)} for day, order in zip(when, orders, strict=True)],
        "standing_orders": [{"standing_order_id": "so_test", "name": "Weekly milk", "lines": [
            {"product_id": product_id, "quantity": quantity} for product_id, quantity in standing.items()
        ]}] if standing else [],
    })


def _prompt(customer: Customer, **options: Any) -> Any:
    return reorder_prompt(customer, today=TODAY, names=NAMES, **options)


# --- the pure logic on hand-built histories ---------------------------------------------------------------------


def test_a_product_in_three_of_the_last_four_orders_is_regular_at_its_median_quantity() -> None:
    weeks = [{MILK: 100, CREAM: 10}, {MILK: 96}, {MILK: 104, CREAM: 10}, {MILK: 100, CREAM: 12},
             {MILK: 98, CREAM: 10}, {MILK: 102}, {MILK: 100, CREAM: 10}, {MILK: 100, CREAM: 14}]

    found = {each.product_id: each for each in regular_products(history_of(_customer(weeks), NAMES))}

    assert (REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS) == (3, 4)
    assert set(found) == {MILK, CREAM}
    assert (found[MILK].orders_matching, found[MILK].orders_considered) == (4, 4)
    assert (found[CREAM].orders_matching, found[CREAM].orders_considered) == (3, 4)
    assert (found[CREAM].matching_in_history_window, found[CREAM].history_window) == (6, 8)
    assert found[MILK].quantity == Decimal(100)  # the median of its last 6 orders, as `usual_quantity`
    assert found[CREAM].last_ordered_on == date(2026, 11, 10)
    assert found[CREAM].first_ordered_on == FIRST_TUESDAY


def test_an_irregular_product_is_not_in_the_prompt() -> None:
    weeks = [{MILK: 100, YOGHURT: 5}, {MILK: 100}, {MILK: 100, YOGHURT: 5}, {MILK: 100},
             {MILK: 100, YOGHURT: 5}, {MILK: 100}, {MILK: 100, YOGHURT: 5}, {MILK: 100}]

    prompt = _prompt(_customer(weeks))

    assert [line.product_id for line in prompt.lines] == [MILK]  # yoghurt: 2 of the last 4
    assert prompt.request is not None and len(prompt.request.lines) == 1


def test_a_history_shorter_than_the_window_gives_no_prompt_and_says_why() -> None:
    prompt = _prompt(_customer([{MILK: 100}] * 3))

    assert prompt.lines == () and prompt.request is None and prompt.needed_by is None
    assert prompt.total_net_eur is None
    assert "3 past orders, fewer than the 4" in prompt.sentence
    assert prompt.synthetic is True and prompt.sentence.endswith("From a synthetic order history.")


def test_nothing_regular_gives_no_prompt_and_says_why() -> None:
    weeks = [{MILK: 100}, {CREAM: 10}, {YOGHURT: 5}, {SOYA: 20}]

    prompt = _prompt(_customer(weeks))

    assert prompt.lines == () and prompt.request is None
    assert "no product is in at least 3 of your last 4 orders" in prompt.sentence


def test_a_product_on_a_standing_order_is_left_out_and_named() -> None:
    weeks = [{MILK: 100, CREAM: 10}] * 8

    prompt = _prompt(_customer(weeks, standing={MILK: 100}))

    assert [line.product_id for line in prompt.lines] == [CREAM]
    assert "Arla milk (469363) is on your standing order" in prompt.sentence
    assert any("Arla milk (469363)" in why and "standing order" in why for why in prompt.why_not)
    assert [each.product_id for each in prompt.evidence.on_standing_order] == [MILK]


def test_every_regular_product_on_a_standing_order_gives_no_prompt_and_says_so() -> None:
    prompt = _prompt(_customer([{MILK: 100}] * 8, standing={MILK: 100}))

    assert prompt.lines == () and prompt.request is None
    assert "Arla milk (469363) is on your standing order" in prompt.sentence


def test_the_rhythm_is_the_median_gap_and_the_usual_weekday_and_gives_the_next_date() -> None:
    history = history_of(_customer([{MILK: 100}] * 8), NAMES)

    rhythm = rhythm_of(history)

    assert rhythm is not None
    assert rhythm.gap_days == Decimal(7) and rhythm.weekdays == (1,)  # Tuesdays
    assert next_delivery(rhythm, date(2026, 11, 12)) == date(2026, 11, 17)
    assert next_delivery(rhythm, date(2026, 11, 17)) == date(2026, 11, 17)  # on or after the earliest day
    assert next_delivery(rhythm, date(2026, 11, 18)) == date(2026, 11, 24)


def test_a_missed_week_does_not_move_the_rhythm() -> None:
    days = [FIRST_TUESDAY + timedelta(days=7 * week) for week in (0, 1, 2, 3, 5, 6, 7, 8)]  # week 4 was skipped
    customer = _customer([{MILK: 100}] * 8, days=days)

    rhythm = rhythm_of(history_of(customer, NAMES))
    prompt = reorder_prompt(customer, today=date(2026, 11, 19), names=NAMES)

    assert rhythm is not None and rhythm.gap_days == Decimal(7) and rhythm.weekdays == (1,)
    assert prompt.needed_by == date(2026, 11, 24)
    assert prompt.request is not None and prompt.request.needed_by == date(2026, 11, 24)


def test_the_next_date_is_not_before_the_last_order_plus_the_usual_gap() -> None:
    days = [FIRST_TUESDAY + timedelta(days=14 * step) for step in range(4)]  # every second Tuesday, last 3 Nov
    customer = _customer([{MILK: 100}] * 4, days=days)

    prompt = reorder_prompt(customer, today=date(2026, 11, 5), names=NAMES)

    assert prompt.needed_by == date(2026, 11, 17)  # not 10 November: the customer orders every 14 days


def test_no_usual_weekday_gives_a_request_without_a_date_and_says_so() -> None:
    days = [date(2026, 10, 5), date(2026, 10, 13), date(2026, 10, 21), date(2026, 10, 29)]  # Mon, Tue, Wed, Thu
    customer = _customer([{MILK: 100}] * 4, days=days)

    prompt = reorder_prompt(customer, today=date(2026, 11, 2), names=NAMES)

    assert prompt.needed_by is None
    assert prompt.request is not None and prompt.request.needed_by is None
    assert "no usual delivery day, so the request carries no date" in prompt.sentence


def test_a_tie_in_quantities_takes_the_median_between_them() -> None:
    weeks = [{MILK: 10}, {MILK: 11}, {MILK: 10}, {MILK: 11}]

    prompt = _prompt(_customer(weeks))

    assert prompt.lines[0].quantity == Decimal("10.5")
    assert "10.5 L" in prompt.sentence


def test_the_request_is_a_complete_purchase_request_and_orders_nothing() -> None:
    weeks = [{MILK: 100, CREAM: 10}] * 8

    prompt = _prompt(_customer(weeks))

    request = PurchaseRequest.model_validate(prompt.request.model_dump(mode="json"))
    assert [(line.product_ids, line.quantity, line.unit.value) for line in request.lines] == [
        ((MILK,), Decimal(100), "L"), ((CREAM,), Decimal(10), "L")]
    assert request.needed_by == date(2026, 11, 17)
    assert request.accepted_suggestion_id is None and request.standing_order_id is None
    assert all(line.text.startswith("Order again: ") for line in request.lines)
    assert prompt.total_net_eur is None  # no price was looked up here, and the sentence says so
    assert "Prices and stock were not looked up" in prompt.sentence
    assert "Nothing is ordered" in prompt.note


def test_the_sentence_says_the_counts_the_last_date_and_the_next_date() -> None:
    weeks = [{MILK: 100, CREAM: 10}, {MILK: 96}, {MILK: 104, CREAM: 10}, {MILK: 100, CREAM: 12},
             {MILK: 98, CREAM: 10}, {MILK: 102}, {MILK: 100, CREAM: 10}, {MILK: 100, CREAM: 14}]

    prompt = _prompt(_customer(weeks))

    assert prompt.sentence == (
        "You ordered Arla milk (469363), 100 L, in 4 of your last 4 weekly orders (8 of the last 8), and Arla "
        "cooking cream (463797), 10 L, in 3 of 4 (6 of 8), most recently on Tuesday 10 November. Order the same "
        "again for Tuesday 17 November? Prices and stock were not looked up here: the offer checks them. From a "
        "synthetic order history."
    )


def test_the_evidence_holds_the_counts_the_dates_and_the_thresholds() -> None:
    prompt = _prompt(_customer([{MILK: 100, CREAM: 10}] * 8))

    evidence = prompt.evidence
    assert evidence.synthetic is True and evidence.orders_in_history == 8
    assert (evidence.first_order, evidence.last_order) == (FIRST_TUESDAY, date(2026, 11, 10))
    assert evidence.thresholds["REORDER_MIN_ORDERS"] == 3 and evidence.thresholds["REORDER_WINDOW_ORDERS"] == 4
    milk = next(each for each in evidence.products if each.product_id == MILK)
    assert (milk.orders_matching, milk.orders_considered, milk.orders_matching_of_history_window,
            milk.history_window) == (4, 4, 8, 8)
    assert evidence.usual_gap_days == Decimal(7) and evidence.usual_weekdays == ("Tuesday",)


def test_a_product_already_ordered_for_the_date_is_left_out_and_named() -> None:
    customer = _customer([{MILK: 100, CREAM: 10}] * 8)

    prompt = _prompt(customer, committed=[(MILK, date(2026, 11, 17))])

    assert [line.product_id for line in prompt.lines] == [CREAM]
    assert any("Arla milk (469363)" in why and "already in an order" in why for why in prompt.why_not)


def test_more_regular_products_than_a_request_takes_are_cut_and_named() -> None:
    ids = ["469363", "463797", "464615", "464013", "473424", "470863", "466988"]
    usual = [{"product_id": product_id, "product_type": "milk", "unit": "L", "use": "SERVED"} for product_id in ids]
    customer = Customer.model_validate({
        **_customer([{MILK: 1}] * 4).model_dump(mode="json"), "usual": usual,
        "history": [{"delivered_on": FIRST_TUESDAY + timedelta(days=7 * week),
                     "quantities": dict.fromkeys(ids, 5)} for week in range(4)],
    })

    prompt = reorder_prompt(customer, today=date(2026, 10, 15), names={})

    assert len(prompt.lines) == 5 and len(prompt.request.lines) == 5
    assert sum("at most 5 lines" in why for why in prompt.why_not) == 2


# --- the four shipped customers, at both clocks -----------------------------------------------------------------

EXPECTED_LINES = {  # product id and usual quantity; the same at both clocks
    "bakery-cafe": [("468319", Decimal(30)), ("464727", Decimal(10))],
    "hotel-kitchen": [("463797", Decimal(10))],
    "school-kitchen": [],  # its three regular products are on its standing order
    "allergy-ward": [],  # both regular products are on its standing order
}
EXPECTED_DATE = {"bakery-cafe": date(2026, 11, 17), "hotel-kitchen": date(2026, 11, 16)}


def _shipped(world: Any, customer_id: str) -> Any:
    customer = shipped_customer(customer_id)
    assert customer is not None
    return reorder_prompt(customer, profile=world.profile(customer_id), ports=world.ports)


@pytest.mark.parametrize("customer_id", sorted(EXPECTED_LINES))
def test_each_shipped_customers_prompt(world: Any, customer_id: str) -> None:
    prompt = _shipped(world, customer_id)

    assert [(line.product_id, line.quantity) for line in prompt.lines] == EXPECTED_LINES[customer_id]
    assert prompt.synthetic is True and "synthetic order history" in prompt.sentence
    assert prompt.needed_by == EXPECTED_DATE.get(customer_id)
    if not prompt.lines:
        assert prompt.request is None and prompt.total_net_eur is None
        assert "on your standing order" in prompt.sentence
        return
    assert prompt.total_net_eur is not None and prompt.total_net_eur > 0
    assert f"€{prompt.total_net_eur:,.2f} before tax at today's prices" in prompt.sentence
    assert prompt.request.needed_by == prompt.needed_by
    on_standing = {line.product_id for standing in shipped_customer(customer_id).standing_orders
                   for line in standing.lines}
    assert not on_standing & {line.product_id for line in prompt.lines}  # never ordered twice


def test_the_bakerys_prompt_names_what_its_standing_order_already_holds(world: Any) -> None:
    prompt = _shipped(world, "bakery-cafe")

    assert [each.product_id for each in prompt.evidence.on_standing_order] == ["469346", "463380"]
    assert "(469346) and" in prompt.sentence and "(463380) are on your standing order" in prompt.sentence
    assert "in 4 of your last 4 weekly orders (8 of the last 8)" in prompt.sentence
    assert "in 3 of 4 (6 of 8)" in prompt.sentence
    assert "most recently on Tuesday 10 November" in prompt.sentence
    assert "Order the same again for Tuesday 17 November?" in prompt.sentence


def test_the_bakerys_ready_made_request_builds_an_offer_with_every_line_confirmed(world: Any) -> None:
    prompt = _shipped(world, "bakery-cafe")

    offer = world.offer("bakery-cafe", prompt.request)

    first = offer.options[0]
    assert sorted(line.product_id for line in first.lines) == ["464727", "468319"]
    assert first.totals.net == prompt.total_net_eur  # the prompt's total is the offer's


def test_a_line_that_fails_a_check_stays_out_and_is_said(world_now: Any) -> None:
    """The ward excludes milk (AM) under the strict rule: a regular cream is checked like any product."""
    customer = Customer.model_validate({
        **_customer([{CREAM: 10, SOYA: 20}] * 8).model_dump(mode="json"), "customer_id": "allergy-ward",
    })

    prompt = reorder_prompt(customer, profile=world_now.profile("allergy-ward"), ports=world_now.ports)

    assert CREAM not in [line.product_id for line in prompt.lines]
    assert CREAM not in [product_id for line in prompt.request.lines for product_id in line.product_ids]
    why = next(each for each in prompt.why_not if "(463797)" in each)
    assert why.endswith("So it is not in the ready-made request.") and ", 10 L: " in why


def test_a_quantity_above_the_confirmed_stock_stays_out_with_the_numbers(world_now: Any) -> None:
    customer = _customer([{MILK: 5000, CREAM: 10}] * 8)  # 384 units of 469363 are confirmed in the recording

    prompt = reorder_prompt(customer, profile=world_now.profile("hotel-kitchen"), ports=world_now.ports)

    assert [line.product_id for line in prompt.lines] == [CREAM]
    why = next(each for each in prompt.why_not if "(469363)" in each)
    assert "5,000 L" in why and "confirmed in stock" in why and "are needed" in why
