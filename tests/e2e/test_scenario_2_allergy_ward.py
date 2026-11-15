"""Scenario 2 (SPEC section 13): the allergy ward asks for 200 litres of a milk substitute by Monday, with no milk,
no gluten and confirmed data only. Even this fully confirmed option requires human approval.

Tonight's capture differs from Friday's plan: the product chosen is `464013` (Alpro No Sugars Soya, €2.01), not
`464056` (Alpro Barista Soya, €2.14). Both are confirmed and state `FREE_FROM` milk and gluten; the options take
the cheapest product that covers the quantity.

Scenario 2 of docs/DEMO.md. The tests that take `both` run at the recording's clock and at the demo clock: the
option, its total and its rule are the same at both. Ordering alone is the buyer's setting, off in every shipped
profile: switched on in the shop's own book for the ward, the same 200 litres are ordered by the agent, and an
option that holds one unconfirmed statement is not.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, ClaimStatus, OptionKind, OrderStatus, PlacedBy, Verdict

MILK, GLUTEN = "AM", "AW"  # GS1 allergen codes (AIMO/docs/SCHEMA-AND-CODES.md)
CHOSEN = "464013"
SCENARIO_2_EVENTS = [
    "request.received", "request.parsed", "lookup.performed", "offer.created", "policy.evaluated",
    "suggestions.shown", "approval.requested", "approval.decided", "order.confirmed",
]
NOTE = "Reviewed the proposed option."
# The ward's settings as the shop page sends them (the profile file's values), with ordering alone switched on.
WARD_SETTINGS = {
    "display_name": "City Hospital, Ward 4", "auto_order_enabled": True, "max_order_net_eur": 500,
    "max_daily_net_eur": 1500, "min_fill_ratio": 1, "excluded_allergens": ["AM", "AW"],
    "allergen_strictness": "STRICT", "allergen_strictness_by_code": {"AM": "STRICT", "AW": "STRICT"},
    "substitution_without_approval": "NONE", "variable_weight": "APPROVAL", "deposits": "APPROVAL",
    "require_confirmed": True, "standing_order_drift_ratio": 0.1, "formula_matters": False,
    "max_preference_premium_ratio": 0.1,
}


def _declares(product: dict[str, Any], code: str) -> bool:
    return any(
        statement["code"] == code and statement["relation"] == "CONTAINS"
        for statement in product["allergen_statements"]
    )


def _free_from(product: dict[str, Any]) -> set[str]:
    return {statement["code"] for statement in product["allergen_statements"] if statement["relation"] == "FREE_FROM"}


def test_scenario_2_from_the_pasted_sentence_requires_human_approval(
    demo: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any
) -> None:
    run = demo.run_agent("ward", texts.scenario_2)
    offer = demo.get_offer("ward", run["offer_id"])

    assert [option["kind"] for option in offer["options"]] == [OptionKind.BEST_CONFIRMED]
    best = offer["options"][0]
    assert lines_of(best) == {CHOSEN: Decimal(200)}
    assert money(best["totals"]["net"]) == Decimal("402.00")
    line = best["lines"][0]
    assert line["availability"]["state"] == AvailabilityState.CONFIRMED
    assert {claim["status"] for claim in line["claims"]} == {ClaimStatus.CONFIRMED}
    assert best["decision"]["verdict"] == Verdict.APPROVAL
    assert fired(best) == {"F-10"}
    assert {check["result"] for check in best["constraint_checks"]} == {"MET"}

    order = demo.get_order("ward", run["order_id"])
    assert run["order_status"] == OrderStatus.PENDING_APPROVAL == order["status"]
    assert order["placed_by"] is None
    assert demo.approval_of("ward", order)["required_roles"] == ["purchasing_manager"]
    approved = demo.approve_all_roles("ward", order, "Reviewed the proposed option.")
    assert (approved["status"], approved["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)

    trail = demo.audit("ward", order["order_id"])
    assert event_types(trail) == SCENARIO_2_EVENTS
    assert all(event["sentence"].strip() for event in trail["events"])
    assert trail["chain"]["ok"] is True


def test_scenario_2_every_product_declaring_milk_or_gluten_is_excluded_as_allergen_declared(
    demo: Any, texts: Any
) -> None:
    run = demo.run_agent("ward", texts.scenario_2)
    offer = demo.get_offer("ward", run["offer_id"])
    asked = offer["request"]["lines"][0]  # the candidates follow the request as it was read, whoever read it
    query = {name: asked[name] for name in ("product_type", "product_ids", "name_terms", "required_claims")}
    looked_up = demo.search("ward", query)
    assert looked_up["total"] == len(looked_up["products"]) == offer["candidates_considered"]

    declaring = {
        product["id"] for product in looked_up["products"] if _declares(product, MILK) or _declares(product, GLUTEN)
    }
    reasons = {exclusion["product_id"]: exclusion["reason"] for exclusion in offer["excluded"]}
    assert declaring  # tonight: 18 oat and grain drinks declare gluten cereals
    assert {product_id: reasons.get(product_id) for product_id in declaring} == dict.fromkeys(
        declaring, "ALLERGEN_DECLARED"
    )
    assert {product_id for product_id, reason in reasons.items() if reason == "ALLERGEN_DECLARED"} == declaring
    offered = {line["product_id"] for option in offer["options"] for line in option["lines"]}
    assert not offered & declaring


def test_scenario_2_the_chosen_product_states_free_from_milk_and_gluten(demo: Any, texts: Any) -> None:
    run = demo.run_agent("ward", texts.scenario_2)
    line = demo.get_offer("ward", run["offer_id"])["options"][0]["lines"][0]

    assert {MILK, GLUTEN} <= _free_from(demo.product("ward", line["product_id"]))
    check = line["allergen_check"]
    assert (check["outcome"], check["strictness"], check["all_explicit"]) == ("PASS", "STRICT", True)
    assert {(finding["excluded_code"], finding["relation"]) for finding in check["findings"]} == {
        (MILK, "FREE_FROM"), (GLUTEN, "FREE_FROM"),
    }


def test_scenario_2_at_both_clocks_the_sentence_is_read_prepared_confirmed_by_a_person_and_logged_for_both_readers(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any, two_views: Any
) -> None:
    read = both.parse("ward", texts.scenario_2)
    typed = texts.scenario_2_request
    assert (read["needed_by"], read["require_confirmed"]) == (typed["needed_by"], True)
    for name in ("product_type", "quantity", "unit", "exclude_allergens"):
        assert read["lines"][0][name] == typed["lines"][0][name], name

    offer = both.offer("ward", typed)
    assert [option["kind"] for option in offer["options"]] == [OptionKind.BEST_CONFIRMED]
    best = offer["options"][0]
    assert lines_of(best) == {CHOSEN: Decimal(200)} and money(best["totals"]["net"]) == Decimal("402.00")
    assert (best["decision"]["verdict"], fired(best)) == (Verdict.APPROVAL, {"F-10"})
    check = best["lines"][0]["allergen_check"]
    assert (check["outcome"], check["strictness"], check["all_explicit"]) == ("PASS", "STRICT", True)
    reasons = {exclusion["reason"] for exclusion in offer["excluded"]}
    assert {"ALLERGEN_DECLARED", "ALLERGEN_NOT_STATED"} <= reasons  # declared, or nothing stated: never offered

    order = both.order("ward", offer)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert order["status_sentence"].startswith("Prepared: confirm to order.")
    decided = both.confirm("ward", order, NOTE)
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    assert decided["status_sentence"] == (
        "Confirmed by Demo approver Jussi (purchasing manager): ordered for €402.00 net."  # the one role asked
    )

    own, valio = two_views(both, "ward", decided, decided_by="ward:purchasing_manager", note=NOTE)
    assert event_types(own) == SCENARIO_2_EVENTS
    read_as = next(event for event in own["events"] if event["type"].endswith("request.parsed"))
    assert read_as["sentence"] == (  # the buyer reads its own exclusions, by their names
        "The request was read as: 200 litres of product type plant_drink, excluding allergens milk and cereals "
        "containing gluten, needed by Monday 16 November 2026, confirmed data only."
    )


def _shop_offer(both: Any, request: dict[str, Any]) -> dict[str, Any]:
    return both.shop("ward", "POST", "/offers", json=request)


def test_scenario_2_with_the_buyers_setting_on_and_everything_confirmed_the_agent_orders_the_200_litres_alone(
    both: Any, texts: Any, money: Any, lines_of: Any
) -> None:
    both.shop("ward", "PUT", "/kitchen", json=WARD_SETTINGS)
    offer = _shop_offer(both, texts.scenario_2_request)
    best = offer["options"][0]
    assert lines_of(best) == {CHOSEN: Decimal(200)} and money(best["totals"]["net"]) == Decimal("402.00")
    assert {claim["status"] for claim in best["lines"][0]["claims"]} == {ClaimStatus.CONFIRMED}
    assert (best["decision"]["verdict"], best["decision"]["fired"]) == (Verdict.AUTO, [])

    order = both.shop(
        "ward", "POST", "/orders", json={"offer_id": offer["offer_id"], "option_id": best["option_id"], "key": "a-1"}
    )

    assert (order["status"], order["placed_by"], order["approval_id"]) == (OrderStatus.ORDERED, PlacedBy.AGENT, None)
    assert order["status_sentence"] == (  # why it was allowed, with the figures, and no rule id
        "The agent placed this order alone for €402.00 net. That was allowed: ordering alone is switched on for City "
        "Hospital, Ward 4; the total of €402.00 is within the €500 limit per order; today's spend with this order "
        "is €402.00 of the €1,500 limit per day; every statement of the offer is confirmed; and no rule asked for a "
        "person."
    )
    trail = both.shop("ward", "GET", f"/audit?order_id={order['order_id']}")
    assert trail["events"][-1]["type"] == "tta.v1.order.placed_by_agent" and trail["chain"]["ok"] is True


def test_scenario_2_with_the_buyers_setting_on_one_unconfirmed_statement_still_goes_to_a_person(
    both: Any, texts: Any, fired: Any
) -> None:
    """The same 200 litres without "confirmed data only": the offer also holds a product whose quantity Valio Aimo
    does not confirm. With ordering alone on, that option waits for a person (F-01, a fixed rule)."""
    both.shop("ward", "PUT", "/kitchen", json={**WARD_SETTINGS, "require_confirmed": False})
    offer = _shop_offer(both, {**texts.scenario_2_request, "require_confirmed": False})
    unconfirmed = [
        option for option in offer["options"]
        if any(line["availability"]["state"] == AvailabilityState.QUANTITY_NOT_CONFIRMED for line in option["lines"])
    ]
    assert unconfirmed, [option["kind"] for option in offer["options"]]
    assert all("F-01" in fired(option) and option["decision"]["verdict"] == Verdict.APPROVAL for option in unconfirmed)

    order = both.shop(
        "ward", "POST", "/orders",
        json={"offer_id": offer["offer_id"], "option_id": unconfirmed[0]["option_id"], "key": "a-2"},
    )

    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert order["approval_id"] is not None
