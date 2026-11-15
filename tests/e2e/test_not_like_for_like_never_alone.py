"""The agent never orders alone a substitute that is not a like-for-like replacement (check CK3, decision B64).

The page tells the buyer so, whatever is set. The three orders below were placed by the agent alone on commit
`016cc08`, measured at the demo clock in replay on Sunday 15 Nov 2026, each through the shop page's own routes
with ordering alone switched on:

A. the hotel, one setting changed: 100 x `475224` for `473609` (€174.00), while the line said "Not a like-for-like
   replacement: a different formula";
B. the ward, also accepting same-category substitutes: 100 L of the rice drink `473424` (€236.00) for the barista
   oat drink, "not made for coffee ... protein 0.1 g, not 1.2 g";
C. the hotel: 40 x `470341` "Visp 250ml" (€50.40) for 10 x cooking cream `460697` (€24.80), check C1-8.

A and B now end with a person confirming, and the rule's own line says why in the offer's words and numbers. Which
product stands in can differ by clock (a cut-off that has passed on the recording's clock); the rule does not, so
the invariant is checked at both clocks and the two products at the demo clock.

C is checked without naming the stand-in: the offer may no longer hold `470341` at all (a candidate that shares no
distinguishing name word with the product asked for is no offer option, decision B65, another lane's change). What
must hold whatever the offer holds: no option with a substitute that is not judged replaceable can be ordered by
the agent, and the order of the first option waits for a person. The measured line itself is judged in
`tests/policy/test_not_like_for_like.py`.

Scores on the 20% "autonomy and controls": what the agent can decide alone, and what needs a person.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import OrderStatus, Verdict

MONDAY = "2026-11-16"
# The settings of each customer as the shop page sends them (the profile files' values).
_BASE = {
    "variable_weight": "APPROVAL", "deposits": "APPROVAL", "formula_matters": False, "formula_mode": "LEARN",
}
HOTEL = {
    **_BASE, "display_name": "Harbourside Hotel", "auto_order_enabled": False, "max_order_net_eur": 750,
    "max_daily_net_eur": 3000, "min_fill_ratio": 0.9, "excluded_allergens": [], "allergen_strictness": None,
    "allergen_strictness_by_code": {}, "substitution_without_approval": "SAME_CATEGORY", "require_confirmed": False,
    "standing_order_drift_ratio": 0.25, "max_preference_premium_ratio": None,
}
WARD = {
    **_BASE, "display_name": "City Hospital, Ward 4", "auto_order_enabled": False, "max_order_net_eur": 500,
    "max_daily_net_eur": 1500, "min_fill_ratio": 1, "excluded_allergens": ["AM", "AW"],
    "allergen_strictness": "STRICT", "allergen_strictness_by_code": {"AM": "STRICT", "AW": "STRICT"},
    "substitution_without_approval": "NONE", "require_confirmed": True, "standing_order_drift_ratio": 0.1,
    "max_preference_premium_ratio": 0.1,
}
OAT_DRINK = {"needed_by": MONDAY, "lines": [{"text": "x", "product_ids": ["473609"], "quantity": 100, "unit": "L"}]}
COOKING_CREAM = {
    "needed_by": MONDAY, "lines": [{"text": "x", "product_ids": ["460697"], "quantity": 10, "unit": "UNIT"}],
}
# (kitchen, the settings sent, the request, then at the demo clock: the stand-in, its quantity, the net total and
# words of the reason the rule's line must carry)
REPRODUCTIONS = {
    "A hotel, ordering alone on": (
        "hotel", {**HOTEL, "auto_order_enabled": True}, OAT_DRINK,
        ("475224", Decimal(100), Decimal("174.00"), "a different formula", "sugars 1.6 g, not 3.5 g"),
    ),
    "B ward, ordering alone on and same-category substitutes": (
        "ward", {**WARD, "auto_order_enabled": True, "substitution_without_approval": "SAME_CATEGORY"}, OAT_DRINK,
        ("473424", Decimal(100), Decimal("236.00"), "not made for coffee", "protein 0.1 g, not 1.2 g"),
    ),
}


def _stand_ins(option: dict[str, Any]) -> list[dict[str, Any]]:
    return [line for line in option["lines"] if line["substitute"] is not None]


def _is_like_for_like(line: dict[str, Any]) -> bool:
    check = line["substitute"]["replaceable"]
    return check is not None and check["verdict"] == "REPLACEABLE" and not line["substitute"]["last_resort"]


@pytest.mark.parametrize("case", list(REPRODUCTIONS))
def test_with_ordering_alone_on_a_substitute_that_is_not_like_for_like_ends_with_a_person_confirming(
    both: Any, money: Any, fired: Any, lines_of: Any, case: str
) -> None:
    kitchen, settings, request, (product_id, quantity, net, *reason_words) = REPRODUCTIONS[case]
    both.shop(kitchen, "PUT", "/kitchen", json=settings)

    offer = both.shop(kitchen, "POST", "/offers", json=request)

    # At either clock: no option that holds a substitute the offer does not judge replaceable may be ordered alone.
    with_stand_in = [option for option in offer["options"] if _stand_ins(option)]
    assert with_stand_in, [option["kind"] for option in offer["options"]]
    for option in with_stand_in:
        if all(_is_like_for_like(line) for line in _stand_ins(option)):
            continue
        assert option["decision"]["verdict"] == Verdict.APPROVAL, option["option_id"]
        assert option["decision"]["required_roles"], option["option_id"]
    first = offer["options"][0]
    assert _stand_ins(first) and not _is_like_for_like(_stand_ins(first)[0])

    order = both.shop(
        kitchen, "POST", "/orders",
        json={"offer_id": offer["offer_id"], "option_id": first["option_id"], "key": "never-alone-1"},
    )

    # Before: ORDERED, placed by the agent, verdict AUTO with no rule fired.
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert order["decision"]["verdict"] == Verdict.APPROVAL and order["approval_id"]
    assert "F-12" in fired(order)
    f12 = next(rule for rule in order["decision"]["fired"] if rule["rule_id"] == "F-12")
    assert "would replace" in f12["sentence"] and "is not a like-for-like replacement: " in f12["sentence"]
    assert f12["sentence"].endswith("A person decides whether it will do.")
    kinds = [event["type"] for event in both.shop(kitchen, "GET", f"/audit?order_id={order['order_id']}")["events"]]
    assert "tta.v1.order.placed_by_agent" not in kinds and "tta.v1.approval.requested" in kinds

    if both.clock == "demo":  # the three products as measured
        assert lines_of(first) == {product_id: quantity} and money(first["totals"]["net"]) == net
        assert f12["product_id"] == product_id
        for words in reason_words:
            assert words in f12["sentence"], words


def test_reproduction_c_the_cooking_cream_no_substitute_that_is_not_like_for_like_is_ordered_by_the_agent(
    both: Any, fired: Any
) -> None:
    both.shop("hotel", "PUT", "/kitchen", json={**HOTEL, "auto_order_enabled": True})

    offer = both.shop("hotel", "POST", "/offers", json=COOKING_CREAM)

    assert offer["options"]
    for option in offer["options"]:
        if any(not _is_like_for_like(line) for line in _stand_ins(option)):
            assert option["decision"]["verdict"] == Verdict.APPROVAL and "F-12" in fired(option), option["option_id"]
    first = offer["options"][0]
    order = both.shop(
        "hotel", "POST", "/orders",
        json={"offer_id": offer["offer_id"], "option_id": first["option_id"], "key": "never-alone-c"},
    )
    # Before: 40 x 470341 for €50.40 against €24.80, ORDERED by the agent with no rule fired.
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert order["decision"]["verdict"] == Verdict.APPROVAL and order["decision"]["fired"]


def test_at_the_ward_the_question_of_a_formula_that_differs_is_asked_of_the_dietitian(both: Any, fired: Any) -> None:
    """The same request with the ward's own token and profile file: the rice drink's protein is 0.1 g against
    1.2 g. That is a nutrition question, and the ward's second person is its dietitian (decision B66). The ward
    takes no substitute alone, so the person who orders is asked too (P-05). At the hotel, where one person holds
    every role, the same rule asks the purchasing manager: nothing changes there."""
    at_the_ward = both.offer("ward", OAT_DRINK)
    at_the_hotel = both.offer("hotel", OAT_DRINK)

    ward_option = next(option for option in at_the_ward["options"] if _stand_ins(option))
    hotel_option = at_the_hotel["options"][0]

    f12 = next(rule for rule in ward_option["decision"]["fired"] if rule["rule_id"] == "F-12")
    assert f12["approver_role"] == "dietitian" and {"F-12", "P-05"} <= fired(ward_option)
    assert ward_option["decision"]["required_roles"] == ["purchasing_manager", "dietitian"]
    assert ward_option["decision"]["sentence"].endswith("It needs the purchasing manager and the dietitian.")
    assert "protein 0.1 g, not 1.2 g" in f12["sentence"] or both.clock != "demo"
    hotel_rule = next(rule for rule in hotel_option["decision"]["fired"] if rule["rule_id"] == "F-12")
    assert hotel_rule["approver_role"] == "purchasing_manager"
    assert hotel_option["decision"]["required_roles"] == ["purchasing_manager"]
