"""The demo script of docs/DEMO.md on one database: scenarios 1, 2 and 3 once each, in that order.

In replay the data clock is pinned to the capture, so the day's spend of a database never resets (question T12-1).
The script therefore starts from an empty database; these tests pin the outcomes it promises, and show why a
repeated run would change them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import OrderStatus, PlacedBy, Verdict

HOTEL_DAILY_LIMIT = Decimal(3000)  # hotel-kitchen, max_daily_net_eur (illustrative, src/tta/policy/profiles/)
WARD_DAILY_LIMIT = Decimal(1500)  # allergy-ward, max_daily_net_eur


def _day_spend(demo: Any, who: str, money: Any) -> Decimal:
    counted = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)
    return sum(
        (money(order["option"]["totals"]["net"]) for order in demo.orders(who) if order["status"] in counted),
        Decimal(0),
    )


def test_demo_script_scenarios_1_2_3_in_order_on_an_empty_database(
    demo: Any, texts: Any, money: Any, fired: Any
) -> None:
    first = demo.run_agent("hotel", texts.scenario_1)
    assert first["order_status"] == OrderStatus.PENDING_APPROVAL
    approved = demo.approve_all_roles("hotel", demo.get_order("hotel", first["order_id"]), "Checked with the kitchen.")
    assert (approved["status"], approved["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)

    second = demo.run_agent("ward", texts.scenario_2)
    assert second["order_status"] == OrderStatus.ORDERED
    assert demo.get_order("ward", second["order_id"])["placed_by"] == PlacedBy.AGENT

    third = demo.offer("hotel", texts.scenario_3_request)
    substitute = third["options"][0]
    assert (substitute["decision"]["verdict"], fired(substitute)) == (Verdict.AUTO, set())
    order = demo.order("hotel", third)
    assert (order["status"], order["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.AGENT)

    assert _day_spend(demo, "hotel", money) == Decimal("2754.64")  # 2,580.64 + 174.00, under the €3,000 a day
    assert _day_spend(demo, "ward", money) == Decimal("402.00")


def test_demo_script_run_twice_on_one_database_changes_the_outcome_so_start_empty(
    demo: Any, texts: Any, money: Any, fired: Any
) -> None:
    """The fourth scenario 2 of one replay day is above the ward's €1,500 a day: finance must approve (P-02)."""
    statuses = [demo.run_agent("ward", texts.scenario_2)["order_status"] for _ in range(4)]
    assert statuses == [OrderStatus.ORDERED] * 3 + [OrderStatus.PENDING_APPROVAL]
    assert _day_spend(demo, "ward", money) > WARD_DAILY_LIMIT

    demo.run_agent("hotel", texts.scenario_1)
    again = demo.offer("hotel", texts.milk(1000))["options"][0]
    assert fired(again) == {"P-01", "P-02"}  # a second scenario 1 the same day also needs finance
    assert _day_spend(demo, "hotel", money) + money(again["totals"]["net"]) > HOTEL_DAILY_LIMIT
