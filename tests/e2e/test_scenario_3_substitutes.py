"""Scenario 3 (SPEC section 13): the substitutes Valio lists for `473609`, Oddlygood Barista oat drink, gluten free.

`471690` passes the substitution rule (it declares oats only, like the original); tonight its cut-off has passed,
so it cannot be ordered either: that is an exception of its own, shown with its reason. `471881` and `464320` add
gluten cereals (`AW`, contains) and fail with `SUBSTITUTE_ADDS_ALLERGEN`: they can never be ordered.

On the page, scenario 3 is the hotel kitchen's request "100 litres of Oddlygood Barista oat drink, product 473609,
by Monday". It has no recording, so it is sent as its typed request.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import OptionKind, OrderStatus, Verdict

ORIGINAL = "473609"
PASSES = "471690"
ADDS_GLUTEN = ("471881", "464320")
BEST_ORDERABLE = "475224"  # Fazer Aito Professional Barista oat drink, confirmed, same category
SCENARIO_3_EVENTS = [
    "request.received", "request.parsed", "lookup.performed", "offer.created",
    "policy.evaluated", "policy.evaluated", "approval.requested",
]


def _by_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate["product_id"]: candidate for candidate in result["candidates"]}


def test_scenario_3_substitutes_listed_by_valio_pass_or_fail_the_allergen_rule(demo: Any, texts: Any) -> None:
    result = demo.substitutes("hotel", ORIGINAL, {"quantity": 100, "unit": "L", "needed_by": texts.monday})
    candidates = _by_id(result)
    assert result["original_id"] == ORIGINAL and result["source"] == "replay"

    passing = candidates[PASSES]
    assert (passing["passes"], passing["listed_by_supplier"]) == (True, True)
    assert passing["allergen_check"]["added"] == []
    assert (passing["orderable"], passing["reason"]) == (False, "CUTOFF_PASSED")  # tonight's exception

    for product_id in ADDS_GLUTEN:
        failing = candidates[product_id]
        assert (failing["passes"], failing["orderable"]) == (False, False)
        assert failing["reason"] == "SUBSTITUTE_ADDS_ALLERGEN"
        assert failing["listed_by_supplier"] is True
        assert {(added["code"], added["relation"]) for added in failing["allergen_check"]["added"]} == {
            ("AW", "CONTAINS"),
        }
        assert failing["sentence"].strip()

    ranks = {candidate["product_id"]: candidate["rank"] for candidate in result["candidates"]}
    last_passing = max(rank for product_id, rank in ranks.items() if candidates[product_id]["passes"])
    assert all(ranks[product_id] > last_passing for product_id in ADDS_GLUTEN)


def test_scenario_3_typed_request_orders_a_substitute_that_passes_and_never_one_that_adds_gluten(
    demo: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any
) -> None:
    offer = demo.offer("hotel", texts.scenario_3_request)

    kinds = [option["kind"] for option in offer["options"]]
    assert kinds == [OptionKind.SUBSTITUTE, OptionKind.ALTERNATIVE_UNCONFIRMED]
    substitute, original = offer["options"]
    assert lines_of(substitute) == {BEST_ORDERABLE: Decimal(100)}
    assert substitute["lines"][0]["substitute"]["original_id"] == ORIGINAL
    assert substitute["lines"][0]["substitute"]["allergen_check"]["passes"] is True
    assert money(substitute["totals"]["net"]) == Decimal("174.00")
    assert lines_of(original) == {ORIGINAL: Decimal(100)}
    assert original["lines"][0]["availability"]["state"] == "QUANTITY_NOT_CONFIRMED"
    assert (original["decision"]["verdict"], fired(original)) == (Verdict.APPROVAL, {"F-01"})

    offered = {line["product_id"] for option in offer["options"] for line in option["lines"]}
    assert not offered & {PASSES, *ADDS_GLUTEN}

    assert (substitute["decision"]["verdict"], fired(substitute)) == (Verdict.APPROVAL, {"F-10"})
    order = demo.order("hotel", offer)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    trail = demo.audit("hotel", order["order_id"])
    assert event_types(trail) == SCENARIO_3_EVENTS
    assert all(event["sentence"].strip() for event in trail["events"])
