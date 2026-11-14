"""Scenario 5 of docs/DEMO.md, second half: the standing order (the brief's "standing order drift detection").

The customers' standing orders are built at start from the customer files, each with a synthetic history (the
Valio Aimo mock has no order history, and every sentence says so). The hotel's weekly 100 L of milk renewed at
290 L differs from the median of its last 6 renewals by more than the hotel's 25% tolerance: rule P-08 sends it to
the purchasing manager. Renewed as stored it is prepared like any order. The school's oat drink has crept up from
60 L to a median of 84 L: the trend is a suggestion, and accepting it is a new request.

The figures are the same at both clocks.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from tta.contracts.common import OptionKind, OrderStatus, PlacedBy, Verdict

HOTEL_MILK = "so_demo_hotel_milk"
SCHOOL_WEEKLY = "so_school_weekly"
USUAL_MILK = "469363"
OAT_DRINK = "470863"
NOTE = "A conference week: 290 L is right."


def _renew(both: Any, who: str, standing_order_id: str, body: dict[str, Any]) -> dict[str, Any]:
    answer = both.client.post(
        f"/v1/standing-orders/{standing_order_id}/renew", json=body, headers=both.headers(who, both.next_key())
    )
    assert answer.status_code == 201, answer.text
    return answer.json()


def _standing(both: Any, who: str, standing_order_id: str) -> dict[str, Any]:
    answer = both.client.get(f"/v1/standing-orders/{standing_order_id}", headers=both.headers(who))
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_scenario_5_standing_order_the_hotels_is_there_at_start_with_a_history_marked_synthetic(both: Any) -> None:
    detail = _standing(both, "hotel", HOTEL_MILK)

    stored = detail["standing_order"]["request"]["lines"]
    assert [(line["product_ids"], line["quantity"], line["unit"]) for line in stored] == [([USUAL_MILK], 100, "L")]
    assert len(detail["renewals"]) == 8 and all(renewal["synthetic"] for renewal in detail["renewals"])
    assert both.client.get(f"/v1/standing-orders/{HOTEL_MILK}", headers=both.headers("supplier")).status_code == 403


def test_scenario_5_standing_order_renewed_as_stored_it_is_within_the_tolerance_and_prepared_for_a_person(
    both: Any, money: Any, fired: Any
) -> None:
    renewal = _renew(both, "hotel", HOTEL_MILK, {})

    assert renewal["drift"]["judged"] is True
    assert not any(check["over_tolerance"] for check in renewal["drift"]["checks"])
    best = renewal["offer"]["options"][0]
    assert money(best["totals"]["net"]) == Decimal("248.00") and fired(best) == {"F-10"}
    assert (renewal["order"]["status"], renewal["order"]["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)


def test_scenario_5_standing_order_renewed_at_290_litres_it_drifts_beyond_the_tolerance_and_goes_to_a_person_under_p08(
    both: Any, money: Any, fired: Any, lines_of: Any, event_types: Any, two_views: Any
) -> None:
    renewal = _renew(both, "hotel", HOTEL_MILK, {"quantities": [290]})

    drift = renewal["drift"]
    assert drift["judged"] is True and money(drift["tolerance"]) == Decimal("0.25")
    quantity = next(check for check in drift["checks"] if check["kind"] == "QUANTITY")
    assert (quantity["this_renewal"], quantity["median"], quantity["over_tolerance"]) == (290, 100, True)
    assert "290 L" in drift["sentence"] and "100 L" in drift["sentence"] and "synthetic" in drift["sentence"]

    best = renewal["offer"]["options"][0]
    assert best["kind"] == OptionKind.BEST_CONFIRMED and lines_of(best) == {USUAL_MILK: Decimal(290)}
    assert money(best["totals"]["net"]) == Decimal("719.20")
    assert (best["decision"]["verdict"], fired(best)) == (Verdict.APPROVAL, {"P-08"})
    order = renewal["order"]
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert order["decision"]["required_roles"] == ["purchasing_manager"]

    decided = both.confirm("hotel", order, NOTE)
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    own, valio = two_views(both, "hotel", decided, decided_by="hotel:purchasing_manager", note=NOTE)
    kinds = event_types(own)
    assert kinds[-2:] == ["approval.decided", "order.confirmed"] and "standing_order.renewed" in kinds
    assert kinds.index("approval.requested") < kinds.index("approval.decided")
    assert "25%" not in " ".join(event["sentence"] for event in valio["events"])  # the tolerance is the buyer's

    history = _standing(both, "hotel", HOTEL_MILK)["renewals"]
    assert len(history) == 9 and history[-1]["synthetic"] is False  # the confirmed renewal joins the history
    assert history[-1]["order_id"] == order["order_id"]


def test_scenario_5_standing_order_the_schools_oat_drink_trend_is_suggested_and_accepting_it_is_a_new_request(
    both: Any, money: Any
) -> None:
    stored = _standing(both, "school", SCHOOL_WEEKLY)["standing_order"]["request"]["lines"]
    assert [(line["product_ids"], line["quantity"]) for line in stored if line["product_ids"] == [OAT_DRINK]] == [
        ([OAT_DRINK], 60),
    ]
    request = {
        "needed_by": "2026-11-16",
        "lines": [{"text": "60 litres of product 470863", "product_ids": [OAT_DRINK], "quantity": 60, "unit": "L"}],
    }
    offer = both.offer("school", request)

    assert money(offer["options"][0]["totals"]["net"]) == Decimal("84.00")
    (trend,) = [suggestion for suggestion in offer["suggestions"] if suggestion["kind"] == "QUANTITY_TREND"]
    assert "(470863)" in trend["sentence"] and "84 L" in trend["sentence"] and "60 L" in trend["sentence"]
    assert "synthetic" in trend["sentence"] and "€117.60" in trend["sentence"]
    asked = {tuple(line["product_ids"]): line["quantity"] for line in trend["accept_request"]["lines"]}
    assert asked[(OAT_DRINK,)] == 84  # the renewal with the new quantity; nothing is stored or ordered by showing it



def test_scenario_5_standing_order_the_standing_orders_page_loads_the_demo_orders_and_shows_the_trend_with_its_button(
    both: Any
) -> None:
    """The page works on this browser's own order book: one button loads the four customers' standing orders."""
    empty = both.client.get("/standing-orders").text
    assert "No standing order in your order book yet." in empty
    csrf = re.search(r'name="csrf" value="([^"]+)"', empty)
    assert csrf is not None

    loaded = both.client.post("/standing-orders/demo", data={"csrf": csrf.group(1)})

    assert loaded.status_code == 200, loaded.text[:300]
    page = both.client.get("/standing-orders").text
    assert "Weekly lactose-free milk, hotel kitchen" in page
    assert "Renew once at 84 L" in page
    assert "synthetic" in page
