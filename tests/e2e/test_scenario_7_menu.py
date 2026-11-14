"""Scenario 7 of docs/DEMO.md: need -> recipe -> order, through the menu plan.

The demo's own sentence for it ("I want to make a chocolate cake for 20 people", the bakery) and its figures belong
to the lane that builds it (CK): its tests are in that lane's folders. This file holds what every menu plan must
do, on a recipe that was already there: the recipe becomes one typed request, each ingredient is either offered or
named as one that cannot be sourced, never dropped unsaid, and the order waits for a person.
"""

from __future__ import annotations

from typing import Any

from tta.contracts.common import OrderStatus, Verdict

STEW = {"dishes": [{"dish_id": "beef_stew", "servings": 80}], "needed_by": "2026-11-16"}


def test_scenario_7_a_menu_becomes_one_request_and_every_ingredient_is_offered_or_named_as_missing(
    both: Any, fired: Any, lines_of: Any
) -> None:
    """Need -> recipe -> order: beef stew for 80 needs 14.4 kg of beef chuck, 2.4 L of cream and 0.8 kg of butter
    (our recipe, marked illustrative). Each ingredient is either in the first option or named as one that cannot be
    sourced; none is dropped unsaid. The order waits for a person: beef is sold by weight (P-06)."""
    answer = both.client.post("/v1/menus/plan", json=STEW, headers=both.headers("hotel"))
    assert answer.status_code == 200, answer.text
    plan = answer.json()

    assert [(line["product_type"], line["needed"], line["unit"]) for line in plan["lines"]] == [
        ("beef_chuck", 14.4, "KG"), ("cream", 2.4, "L"), ("butter", 0.8, "KG"),  # 80 servings of our recipe
    ]
    assert all(line["to_order"] >= line["needed"] for line in plan["lines"])
    assert plan["illustrative"] is True  # the recipes and their amounts are ours

    offer = both.get_offer("hotel", plan["offer_id"])
    assert len(offer["request"]["lines"]) == 3
    best = offer["options"][0]
    covered = {line["request_line_index"] for line in best["lines"]}
    missing = {line["request_line_index"] for line in plan["lines"]} - covered
    named = {missing["product_type"] for missing in plan["cannot_be_sourced"]}
    assert {plan["lines"][index]["product_type"] for index in missing} <= named
    assert {"466988", "463797"} <= set(lines_of(best))  # the beef chuck and the cooking cream
    assert best["totals"]["is_ceiling"] is True and "P-06" in fired(best)  # by weight: the total is an estimate
    assert best["decision"]["verdict"] == Verdict.APPROVAL
    if missing:  # an ingredient the recording does not hold: the menu as a whole is short, and a person sees it
        assert "P-03" in fired(best)
    order = both.order("hotel", offer)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
