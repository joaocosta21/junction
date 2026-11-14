"""The "this is one of your regular orders" alert (`tta.suggestions.regular`).

Scores on the 20% "solving the problem and user need" (a request that repeats a standing order is caught before it is
ordered twice; a regular request is offered as a standing order; a quantity far from the usual one is asked about)
and on the 20% "autonomy and controls" (the alert orders nothing and changes nothing; every finding carries the counts
and thresholds it rests on). The pure logic on hand-built histories, then the four shipped customers at both clocks
(the recording's instant and the demo clock).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.customer import Customer
from tta.contracts.request import PurchaseRequest
from tta.contracts.standing import NewStandingOrder, StandingOrder
from tta.customers import shipped_customer
from tta.suggestions import history_of
from tta.suggestions.regular import Comparison, Finding, chosen_products, held_lines, regular_alert
from tta.suggestions.thresholds import REGULAR_QUANTITY_TOLERANCE, REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS

FIRST_TUESDAY = date(2026, 9, 22)
MILK, CREAM, YOGHURT, SOYA = "469363", "463797", "464615", "464013"
UNITS = {MILK: ("milk", "L"), CREAM: ("cream", "L"), YOGHURT: ("yoghurt", "KG"), SOYA: ("plant_drink", "L")}
NAMES = {MILK: "Arla milk", CREAM: "Arla cooking cream", YOGHURT: "Valio greek yoghurt", SOYA: "Alpro soya drink"}
TODAY = date(2026, 11, 12)  # a Thursday, two days after the eighth weekly Tuesday
# Milk and soya drink every week, cream in 7 of 8, yoghurt in 2 of the last 4.
WEEKS = [{MILK: 100, CREAM: 10, SOYA: 30}, {MILK: 96, CREAM: 10, SOYA: 30}, {MILK: 104, CREAM: 10, SOYA: 30},
         {MILK: 100, SOYA: 30}, {MILK: 98, CREAM: 10, SOYA: 30, YOGHURT: 5}, {MILK: 102, CREAM: 10, SOYA: 30},
         {MILK: 100, CREAM: 10, SOYA: 30, YOGHURT: 5}, {MILK: 100, CREAM: 10, SOYA: 30}]
TAIL = "From a synthetic order history."
SET_UP = ("Make it a standing order, so each week it is one renewal you confirm instead of a new request? Setting it "
          "up orders nothing, and every renewal goes to a person as always.")


def _customer(orders: Sequence[Mapping[str, Any]] = WEEKS, *, standing: Mapping[str, Any] | None = None) -> Customer:
    when = [FIRST_TUESDAY + timedelta(days=7 * week) for week in range(len(orders))]
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


def _line(product_id: str | None, quantity: Any, unit: str = "L", **more: Any) -> dict[str, Any]:
    named = {"product_ids": [product_id]} if product_id else {}
    return {"text": "a line", "quantity": quantity, "unit": unit, **named, **more}


def _request(*lines: Mapping[str, Any], **fields: Any) -> PurchaseRequest:
    return PurchaseRequest.model_validate({"needed_by": "2026-11-17", "lines": list(lines), **fields})


def _alert(customer: Customer, *lines: Mapping[str, Any], chosen: Mapping[int, str] | None = None,
           **fields: Any) -> Any:
    history = history_of(customer, NAMES)
    return regular_alert(history, held_lines(history, customer.standing_orders), _request(*lines, **fields),
                         today=TODAY, chosen=chosen)


# --- each finding ---------------------------------------------------------------------------------------------------


def test_a_product_on_a_standing_order_is_said_first_with_its_quantity_and_next_date() -> None:
    alert = _alert(_customer(standing={MILK: 100}), _line(MILK, 100))

    assert alert.finding is Finding.ALREADY_ON_STANDING_ORDER
    assert alert.sentence == (
        "Arla milk (469363) is already on your standing order “Weekly milk” (100 L every week, next for Tuesday "
        f"17 November). This request would be on top of it. {TAIL}"
    )
    assert alert.standing_order_request is None and alert.usual_request is None
    line = alert.lines[0]
    assert (line.product_id, line.standing_order_id, line.standing_order_name) == (MILK, "so_test", "Weekly milk")
    assert (line.regular, line.usual_quantity, line.comparison) == (True, Decimal(100), Comparison.USUAL)
    assert line.sentence == "your usual 100 L"
    assert alert.evidence.next_delivery == date(2026, 11, 17)


def test_a_regular_request_with_no_standing_order_is_offered_as_one() -> None:
    alert = _alert(_customer(standing={MILK: 100}), _line(SOYA, 30))

    assert alert.finding is Finding.REGULAR_NOT_STANDING
    assert alert.sentence == (
        f"You order this every week: Alpro soya drink (464013), 30 L, in 8 of your last 8 orders. {SET_UP} {TAIL}"
    )
    line = alert.lines[0]
    assert (line.orders_matching, line.orders_considered, line.standing_order_id) == (8, 8, None)
    body = alert.standing_order_request
    assert isinstance(body, NewStandingOrder)
    assert NewStandingOrder.model_validate(body.model_dump(mode="json")) == body  # what the route's body takes
    assert (body.name, body.cadence_days) == ("Weekly Alpro soya drink", 7)
    assert body.request.standing_order_id is None and body.request.needed_by is None
    assert [(each.product_ids, each.quantity, each.unit.value) for each in body.request.lines] == [
        ((SOYA,), Decimal(30), "L")]


def test_a_product_missing_from_one_order_is_almost_every_week() -> None:
    alert = _alert(_customer(), _line(CREAM, 10))

    assert alert.finding is Finding.REGULAR_NOT_STANDING
    assert alert.sentence.startswith(
        "You order this almost every week: Arla cooking cream (463797), 10 L, in 7 of your last 8 orders. Make it")


def test_two_regular_lines_make_one_standing_order_request() -> None:
    alert = _alert(_customer(), _line(SOYA, 30), _line(CREAM, 11))

    assert alert.finding is Finding.REGULAR_NOT_STANDING
    assert alert.sentence.startswith(
        "You order this almost every week: Alpro soya drink (464013), 30 L, in 8 of your last 8 orders, and Arla "
        "cooking cream (463797), 10 L, in 7 of 8. Make it a standing order")
    assert alert.standing_order_request.name == "Weekly Alpro soya drink and Arla cooking cream"
    # the standing order stores the usual quantity, not the 11 L of this request
    assert [each.quantity for each in alert.standing_order_request.request.lines] == [Decimal(30), Decimal(10)]


def test_a_regular_product_at_a_clearly_different_quantity_is_asked_about() -> None:
    alert = _alert(_customer(), _line(SOYA, 90))

    assert alert.finding is Finding.REGULAR_DIFFERENT_QUANTITY
    assert alert.sentence == (
        f"You usually order 30 L of Alpro soya drink (464013); this request says 90 L. Is 90 L right? {TAIL}")
    line = alert.lines[0]
    assert (line.quantity, line.usual_quantity, line.comparison) == (Decimal(90), Decimal(30), Comparison.MORE)
    assert line.sentence == "you usually order 30 L; this request says 90 L"
    assert alert.standing_order_request is None
    assert [each.quantity for each in alert.usual_request.lines] == [Decimal(30)]  # "Use my usual 30 L"
    assert alert.usual_request.needed_by == date(2026, 11, 17)


def test_a_product_that_is_not_regular_gives_no_alert() -> None:
    alert = _alert(_customer(), _line(YOGHURT, 5, "KG"))  # in 2 of the last 4 orders

    assert alert.finding is None and alert.sentence == ""
    assert alert.standing_order_request is None and alert.usual_request is None
    assert (alert.lines[0].regular, alert.lines[0].usual_quantity) == (False, None)
    assert (alert.evidence.products[0].orders_matching, alert.evidence.products[0].orders_considered) == (2, 4)
    assert alert.evidence.findings == ()


def test_a_history_shorter_than_the_window_gives_no_alert() -> None:
    alert = _alert(_customer(WEEKS[:3]), _line(SOYA, 30))

    assert alert.finding is None and alert.evidence.orders_in_history == 3


# --- the tolerance --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("quantity", "comparison", "finding"), [
    ("37.4", Comparison.USUAL, Finding.REGULAR_NOT_STANDING),  # 24.7% above the usual 30 L
    ("37.5", Comparison.MORE, Finding.REGULAR_DIFFERENT_QUANTITY),  # exactly the tolerance: clearly more
    ("22.6", Comparison.USUAL, Finding.REGULAR_NOT_STANDING),
    ("22.5", Comparison.LESS, Finding.REGULAR_DIFFERENT_QUANTITY),
    ("30", Comparison.USUAL, Finding.REGULAR_NOT_STANDING),
])
def test_the_tolerance_edges(quantity: str, comparison: Comparison, finding: Finding) -> None:
    alert = _alert(_customer(), _line(SOYA, quantity))

    assert Decimal("0.25") == REGULAR_QUANTITY_TOLERANCE
    assert (alert.lines[0].comparison, alert.finding) == (comparison, finding)
    assert alert.evidence.thresholds["REGULAR_QUANTITY_TOLERANCE"] == REGULAR_QUANTITY_TOLERANCE


def test_less_than_usual_is_said_with_both_quantities() -> None:
    alert = _alert(_customer(), _line(SOYA, 10))

    assert alert.sentence == (
        f"You usually order 30 L of Alpro soya drink (464013); this request says 10 L. Is 10 L right? {TAIL}")


def test_a_line_in_another_unit_is_not_compared() -> None:
    alert = _alert(_customer(), _line(SOYA, 30, "UNIT"))

    assert alert.finding is None and alert.lines[0].regular is False


# --- a line that names only a product type --------------------------------------------------------------------------


def test_a_type_only_line_is_judged_on_the_product_the_offer_chose() -> None:
    line = _line(None, 30, product_type="plant_drink")

    unresolved = _alert(_customer(), line)
    resolved = _alert(_customer(), line, chosen={0: SOYA})

    assert unresolved.finding is None and unresolved.lines == ()
    assert resolved.finding is Finding.REGULAR_NOT_STANDING
    assert resolved.lines[0].product_id == SOYA
    assert resolved.evidence.products[0].resolved_by == "OFFER"
    assert resolved.standing_order_request.request.lines[0].product_ids == (SOYA,)


def test_a_type_only_line_the_offer_filled_from_a_standing_order_product_is_caught() -> None:
    alert = _alert(_customer(standing={MILK: 100}), _line(None, 100, product_type="milk"), chosen={0: MILK})

    assert alert.finding is Finding.ALREADY_ON_STANDING_ORDER


# --- more than one finding ------------------------------------------------------------------------------------------


def test_the_strongest_finding_wins_and_the_other_is_in_the_evidence() -> None:
    alert = _alert(_customer(standing={MILK: 100}), _line(MILK, 100), _line(SOYA, 90))

    assert alert.finding is Finding.ALREADY_ON_STANDING_ORDER
    assert alert.sentence.startswith("Arla milk (469363) is already on your standing order")
    assert alert.evidence.findings == (Finding.ALREADY_ON_STANDING_ORDER, Finding.REGULAR_DIFFERENT_QUANTITY)
    assert [(other.finding, other.sentence) for other in alert.evidence.also] == [(
        Finding.REGULAR_DIFFERENT_QUANTITY,
        f"You usually order 30 L of Alpro soya drink (464013); this request says 90 L. Is 90 L right? {TAIL}",
    )]
    assert alert.standing_order_request is None and alert.usual_request is None  # the buttons are the finding's


def test_a_standing_order_product_at_another_quantity_is_both() -> None:
    alert = _alert(_customer(standing={MILK: 100}), _line(MILK, 200))

    assert alert.finding is Finding.ALREADY_ON_STANDING_ORDER
    assert alert.evidence.findings == (Finding.ALREADY_ON_STANDING_ORDER, Finding.REGULAR_DIFFERENT_QUANTITY)


def test_a_regular_line_beside_one_at_a_different_quantity_is_not_offered_as_a_standing_order() -> None:
    alert = _alert(_customer(), _line(CREAM, 10), _line(SOYA, 90))

    assert alert.finding is Finding.REGULAR_DIFFERENT_QUANTITY
    assert alert.evidence.findings == (Finding.REGULAR_DIFFERENT_QUANTITY,)
    assert [each.quantity for each in alert.usual_request.lines] == [Decimal(10), Decimal(30)]


def test_two_products_of_one_standing_order_are_said_together() -> None:
    alert = _alert(_customer(standing={MILK: 100, SOYA: 30}), _line(MILK, 100), _line(SOYA, 30))

    assert alert.sentence == (
        "Arla milk (469363) and Alpro soya drink (464013) are already on your standing order “Weekly milk” (100 L "
        f"and 30 L every week, next for Tuesday 17 November). This request would be on top of it. {TAIL}"
    )


# --- what does not alert --------------------------------------------------------------------------------------------


def test_the_renewal_of_a_standing_order_is_not_on_top_of_it() -> None:
    alert = _alert(_customer(standing={MILK: 100}), _line(MILK, 100), standing_order_id="so_test")

    assert alert.finding is None and alert.sentence == ""
    assert "renews" in alert.note


def test_a_standing_order_set_up_in_the_book_counts_like_the_customer_files() -> None:
    customer = _customer()
    history = history_of(customer, NAMES)
    stored = StandingOrder(standing_order_id="so_abc", profile_id="my-kitchen", agent_id="agent:my-kitchen",
                           name="Weekly Alpro soya drink", request=_request(_line(SOYA, 30)).model_copy(
                               update={"needed_by": None}), created_at=datetime(2026, 11, 12, tzinfo=UTC))

    held = held_lines(history, (stored, stored))  # the same standing order twice is read once
    alert = regular_alert(history, held, _request(_line(SOYA, 30)), today=TODAY)

    assert [(each.standing_order_id, each.product_id, each.quantity) for each in held] == [
        ("so_abc", SOYA, Decimal(30))]
    assert alert.finding is Finding.ALREADY_ON_STANDING_ORDER
    assert "“Weekly Alpro soya drink” (30 L every week" in alert.sentence


def test_a_history_that_is_not_synthetic_does_not_say_it_is() -> None:
    history = replace(history_of(_customer(), NAMES), synthetic=False)

    alert = regular_alert(history, (), _request(_line(SOYA, 90)), today=TODAY)

    assert alert.synthetic is False and not alert.sentence.endswith(TAIL)
    assert alert.sentence.endswith("Is 90 L right?")


def test_the_evidence_holds_the_counts_the_quantities_and_the_thresholds() -> None:
    alert = _alert(_customer(), _line(CREAM, 20))

    facts = alert.evidence.products[0]
    assert (REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS) == (3, 4)
    assert (facts.orders_matching, facts.orders_considered) == (4, 4)
    assert (facts.orders_matching_of_history_window, facts.history_window) == (7, 8)
    assert (facts.requested, facts.usual_quantity, facts.difference_ratio) == (Decimal(20), Decimal(10), Decimal(1))
    assert facts.values == (Decimal(10),) * 6
    assert alert.evidence.thresholds == {
        "REORDER_MIN_ORDERS": Decimal(3), "REORDER_WINDOW_ORDERS": Decimal(4), "HISTORY_WINDOW_ORDERS": Decimal(8),
        "REGULAR_QUANTITY_TOLERANCE": Decimal("0.25"), "USUAL_QUANTITY_WINDOW": Decimal(6),
    }
    assert (alert.evidence.synthetic, alert.evidence.orders_in_history, alert.evidence.today) == (True, 8, TODAY)
    assert (alert.evidence.usual_gap_days, alert.evidence.usual_weekdays) == (Decimal(7), ("Tuesday",))


# --- the four shipped customers, at both clocks ---------------------------------------------------------------------

BAKERY_STANDING = (
    "Arla Pro Whipping cream (469346) is already on your standing order “Weekly whipping cream and coffee milk, "
    "bakery” (40 L every week, next for Tuesday 17 November). This request would be on top of it. " + TAIL
)
BAKERY_REGULAR = (
    "You order this every week: Oatly iKaffe (468319), 30 L, in 8 of your last 8 orders. " + SET_UP + " " + TAIL
)
BAKERY_QUANTITY = "You usually order 30 L of Oatly iKaffe (468319); this request says 90 L. Is 90 L right? " + TAIL
HOTEL_STANDING = (
    "Arla Semi skimmed milkdrink (469363) is already on your standing order “Weekly lactose-free "
    "milk, hotel kitchen” (100 L every week, next for Monday 16 November). This request would be on top of it. " + TAIL
)
HOTEL_REGULAR = (
    "You order this almost every week: Arla Pro Cooking cream 10% (463797), 10 L, in 7 of your last 8 orders. "
    + SET_UP + " " + TAIL
)
ALMOND = {"text": "20 L of almond drink", "product_type": "plant_drink", "name_terms": ["almond"], "quantity": 20,
          "unit": "L"}
SHIPPED = [
    ("bakery-cafe", _line("469346", 40), Finding.ALREADY_ON_STANDING_ORDER, BAKERY_STANDING),
    ("bakery-cafe", _line("468319", 30), Finding.REGULAR_NOT_STANDING, BAKERY_REGULAR),
    ("bakery-cafe", _line("468319", 90), Finding.REGULAR_DIFFERENT_QUANTITY, BAKERY_QUANTITY),
    ("hotel-kitchen", _line("469363", 100), Finding.ALREADY_ON_STANDING_ORDER, HOTEL_STANDING),
    ("hotel-kitchen", _line("463797", 10), Finding.REGULAR_NOT_STANDING, HOTEL_REGULAR),
    ("school-kitchen", ALMOND, None, ""),
]


def _shipped(world: Any, customer_id: str, line: Mapping[str, Any]) -> Any:
    customer = shipped_customer(customer_id)
    assert customer is not None
    request = world.request(line)
    offer = world.offer(customer_id, request)
    products = {usual.product_id: world.catalog.get_product(usual.product_id) for usual in customer.usual}
    history = history_of(customer, {key: product.display_name for key, product in products.items() if product})
    return regular_alert(history, held_lines(history, customer.standing_orders), request,
                         today=world.replay.clock.now().date(), chosen=chosen_products(offer), offer_id=offer.offer_id)


@pytest.mark.parametrize(("customer_id", "line", "finding", "sentence"), SHIPPED,
                         ids=["bakery-40L-469346", "bakery-30L-468319", "bakery-90L-468319", "hotel-100L-469363",
                              "hotel-10L-463797", "school-20L-almond"])
def test_each_shipped_request(world: Any, customer_id: str, line: Mapping[str, Any], finding: Finding | None,
                              sentence: str) -> None:
    alert = _shipped(world, customer_id, line)

    assert alert.finding is finding
    assert alert.sentence == sentence
    assert alert.synthetic is True and alert.offer_id


def test_the_bakerys_standing_order_request_is_one_the_service_takes(world: Any) -> None:
    alert = _shipped(world, "bakery-cafe", _line("468319", 30))

    body = alert.standing_order_request
    assert (body.name, body.cadence_days) == ("Weekly Oatly iKaffe", 7)
    assert [(each.product_ids, each.quantity) for each in body.request.lines] == [(("468319",), Decimal(30))]
    assert world.offer("bakery-cafe", body.request).options  # a renewal of it finds an option


def test_a_shipped_type_only_request_is_caught_when_the_offer_fills_it_from_the_standing_order(world: Any) -> None:
    milk = {"text": "100 litres of lactose-free milk", "product_type": "milk",
            "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 100, "unit": "L"}

    alert = _shipped(world, "hotel-kitchen", milk)

    assert (alert.finding, alert.sentence) == (Finding.ALREADY_ON_STANDING_ORDER, HOTEL_STANDING)
    assert alert.evidence.products[0].resolved_by == "OFFER"
