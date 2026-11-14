"""Scenario 5 of docs/DEMO.md: the customer's pattern, and Valio Aimo's own suggestion.

The hotel asks for its usual "100 litres of lactose-free milk by Monday". The offer carries two suggestions, each
checked like any product (allergen rule, confirmed stock for the date): the forgotten item (in 7 of its last 8
orders with this milk the hotel also ordered 10 L of cooking cream `463797`) and Valio Aimo's own suggestion from
its catalog (the brief's proactive selling agent). A suggestion is shown, never applied: accepting one is a new
request, a new offer, and the same rules. The history behind them is synthetic and every sentence says so.

Suggestions exist in replay only. The figures are the same at both clocks.
Scores on the 20% "how precisely the agent matches what the buyer asked" and the 20% log.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import OptionKind, OrderStatus, PlacedBy, Verdict

USUAL_MILK = "469363"
COOKING_CREAM = "463797"
NOTE = "The cream was missing from the list."


def _suggestion(offer: dict[str, Any], kind: str) -> dict[str, Any]:
    found = [suggestion for suggestion in offer["suggestions"] if suggestion["kind"] == kind]
    assert len(found) == 1, [suggestion["kind"] for suggestion in offer["suggestions"]]
    return found[0]


def _pattern_offer(both: Any, texts: Any) -> dict[str, Any]:
    read = both.parse("hotel", texts.pattern)
    assert read["lines"][0]["quantity"] == 100 and read["lines"][0]["required_claims"] == ["FREE_FROM_LACTOSE"]
    return both.offer("hotel", texts.milk(100))


def test_scenario_5_the_usual_milk_is_prepared_and_the_offer_suggests_without_adding_anything(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any
) -> None:
    offer = _pattern_offer(both, texts)

    best = offer["options"][0]
    assert best["kind"] == OptionKind.BEST_CONFIRMED and lines_of(best) == {USUAL_MILK: Decimal(100)}
    assert money(best["totals"]["net"]) == Decimal("248.00")
    assert (best["decision"]["verdict"], fired(best)) == (Verdict.APPROVAL, {"F-10"})
    offered = {line["product_id"] for option in offer["options"] for line in option["lines"]}
    assert COOKING_CREAM not in offered  # shown as a suggestion, never put into an option

    forgotten = _suggestion(offer, "FORGOTTEN_ITEM")
    assert forgotten["stock_confirmed"] is True
    assert money(forgotten["effect"]["net_change_eur"]) == Decimal("33.10")
    assert "(469363)" in forgotten["sentence"] and "(463797)" in forgotten["sentence"]
    assert "7 of your last 8 orders" in forgotten["sentence"]
    assert "synthetic" in forgotten["sentence"]  # the history is made up, and the sentence says so

    from_valio = _suggestion(offer, "FROM_SUPPLIER")
    assert from_valio["stock_confirmed"] is True
    assert "Valio Aimo" in from_valio["sentence"]  # said to come from the supplier, not from the buyer's orders
    assert len({suggestion["kind"] for suggestion in offer["suggestions"]}) == len(offer["suggestions"]) <= 3


def test_scenario_5_accepting_the_forgotten_item_is_a_new_offer_that_a_person_confirms_and_both_logs_say_so(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any, two_views: Any
) -> None:
    first = _pattern_offer(both, texts)
    forgotten = _suggestion(first, "FORGOTTEN_ITEM")

    accepted = both.offer("hotel", forgotten["accept_request"])  # one click on the page: the request it carries

    assert accepted["offer_id"] != first["offer_id"]
    assert accepted["request"]["accepted_suggestion_id"] == forgotten["suggestion_id"]
    best = accepted["options"][0]
    assert lines_of(best) == {USUAL_MILK: Decimal(100), COOKING_CREAM: Decimal(10)}
    assert money(best["totals"]["net"]) == Decimal("281.10")  # 248.00 + 33.10
    assert (best["decision"]["verdict"], fired(best)) == (Verdict.APPROVAL, {"F-10"})
    assert "FORGOTTEN_ITEM" not in {suggestion["kind"] for suggestion in accepted["suggestions"]}
    shown_with_first = event_types(both.offer_audit("hotel", first["offer_id"]))
    assert shown_with_first[-2:] == ["suggestions.shown", "suggestion.accepted"]

    order = both.order("hotel", accepted)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    decided = both.confirm("hotel", order, NOTE)
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    assert decided["status_sentence"] == (
        "Confirmed by Demo approver Hanna (purchasing manager): ordered for €281.10 net."
    )

    own, valio = two_views(both, "hotel", decided, decided_by="hotel:purchasing_manager", note=NOTE)
    asked = own["events"][0]["sentence"]
    assert "(463797)" in asked
    # Valio Aimo reads that suggestions were shown, and its own by name: never the buyer's order history.
    told = next(event for event in valio["events"] if event["type"].endswith("suggestions.shown"))["sentence"]
    assert "Valio Aimo's own suggestion" in told
    assert "of your last" not in told and "synthetic" not in told


def test_scenario_5_valio_aimos_own_suggestion_is_accepted_the_same_way_and_meets_the_same_rules(
    both: Any, texts: Any, fired: Any
) -> None:
    first = _pattern_offer(both, texts)
    from_valio = _suggestion(first, "FROM_SUPPLIER")

    accepted = both.offer("hotel", from_valio["accept_request"])

    best = accepted["options"][0]
    assert from_valio["product_id"] in {line["product_id"] for line in best["lines"]}
    assert best["decision"]["verdict"] == Verdict.APPROVAL and "F-10" in fired(best)  # still a person's decision
    order = both.order("hotel", accepted)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
