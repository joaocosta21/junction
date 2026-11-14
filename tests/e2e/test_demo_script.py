"""The demo script of docs/DEMO.md on one database: scenarios 1 to 6 once each, in order (7 is the menu page).

In replay the data clock is pinned, so the day's spend of a database never resets (question T12-1). The script
therefore starts from an empty database; these tests pin that one pass in order never meets the hotel's limit per
day (rule P-02), and show why a repeated run would change the outcomes.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import OrderStatus, PlacedBy

HOTEL_DAILY_LIMIT = Decimal(3000)  # hotel-kitchen, max_daily_net_eur (illustrative, src/tta/policy/profiles/)
WARD_DAILY_LIMIT = Decimal(1500)  # allergy-ward, max_daily_net_eur
DAY_RULE = "P-02"


def _day_spend(demo: Any, who: str, money: Any) -> Decimal:
    counted = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)
    return sum(
        (money(order["option"]["totals"]["net"]) for order in demo.orders(who) if order["status"] in counted),
        Decimal(0),
    )


def _renew_at_290(both: Any) -> dict[str, Any]:
    answer = both.client.post(
        "/v1/standing-orders/so_demo_hotel_milk/renew", json={"quantities": [290]},
        headers=both.headers("hotel", both.next_key()),
    )
    assert answer.status_code == 201, answer.text
    return answer.json()["order"]


def test_demo_script_the_scenarios_in_order_on_one_database_never_meet_the_limit_per_day(
    both: Any, texts: Any, money: Any, fired: Any
) -> None:
    placed: list[dict[str, Any]] = []

    first = both.get_order("hotel", both.run_agent("hotel", texts.scenario_1)["order_id"])  # 1: the brief's sentence
    placed.append(both.confirm("hotel", first, "Checked with the kitchen."))
    second = both.get_order("ward", both.run_agent("ward", texts.scenario_2)["order_id"])  # 2: the ward
    both.confirm("ward", second, "Reviewed.")
    placed.append(both.order("hotel", both.offer("hotel", texts.scenario_3_request)))  # 3: the stock-out
    doubt = both.offer("hotel", texts.dietitian_request)  # 4a: the dietitian takes the safe product
    asked = both.order("hotel", doubt, option=1)
    placed.append(both.confirm("hotel", asked, "Took the safe product.", option_id=doubt["options"][0]["option_id"]))
    both.run_agent("school", texts.almond)  # 4b: the school's almond drink waits for its dietitian
    usual = both.offer("hotel", texts.milk(100))  # 5: the pattern, with the forgotten item accepted
    forgotten = next(one for one in usual["suggestions"] if one["kind"] == "FORGOTTEN_ITEM")
    placed.append(both.order("hotel", both.offer("hotel", forgotten["accept_request"])))
    placed.append(_renew_at_290(both))  # 5, then: the hotel's standing order at 290 L
    both.run_agent("bakery", texts.formula_changed)  # 6: the bakery
    both.order("bakery", both.offer("bakery", texts.formula_kept_request))

    assert all(DAY_RULE not in fired(order) for order in placed), [sorted(fired(order)) for order in placed]
    assert [order["status"] for order in placed] == [
        OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL, OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL,
        OrderStatus.PENDING_APPROVAL,
    ]
    assert all(order["placed_by"] in (None, PlacedBy.HUMAN_APPROVAL) for order in placed)  # never the agent alone
    stock_out = {"recording": "174.00", "demo": "137.00"}[both.clock]  # scenario 3's first option, by clock
    spent = Decimal("1083.39") + Decimal(stock_out) + Decimal("236.00") + Decimal("281.10") + Decimal("719.20")
    assert _day_spend(both, "hotel", money) == spent < HOTEL_DAILY_LIMIT
    assert _day_spend(both, "ward", money) == Decimal("402.00")
    for buyer in ("hotel", "ward", "school", "bakery"):
        assert all(order["placed_by"] != PlacedBy.AGENT for order in both.orders(buyer))


def test_demo_script_run_twice_on_one_database_changes_the_outcome_so_start_empty(
    demo: Any, texts: Any, money: Any, fired: Any
) -> None:
    """The fourth scenario 2 of one replay day is above the ward's €1,500 a day: finance must approve (P-02)."""
    statuses = [demo.run_agent("ward", texts.scenario_2)["order_status"] for _ in range(4)]
    assert statuses == [OrderStatus.PENDING_APPROVAL] * 4
    assert _day_spend(demo, "ward", money) > WARD_DAILY_LIMIT

    demo.run_agent("hotel", texts.scenario_1)
    second = demo.offer("hotel", texts.milk(1000))["options"][0]
    assert fired(second) == {"P-01", "P-03"}  # 2 x 1,083.39 = 2,166.78: a second one is still under €3,000 a day
    demo.order("hotel", demo.offer("hotel", texts.milk(1000)))
    again = demo.offer("hotel", texts.milk(1000))["options"][0]
    assert fired(again) == {"P-01", "P-02", "P-03"}  # a third scenario 1 the same day also needs finance
    assert _day_spend(demo, "hotel", money) + money(again["totals"]["net"]) > HOTEL_DAILY_LIMIT
