"""Scenario 2 (SPEC section 13): the allergy ward asks for 200 litres of a milk substitute by Monday, with no milk,
no gluten and confirmed data only. Even this fully confirmed option requires human approval.

Tonight's capture differs from Friday's plan: the product chosen is `464013` (Alpro No Sugars Soya, €2.01), not
`464056` (Alpro Barista Soya, €2.14). Both are confirmed and state `FREE_FROM` milk and gluten; the options take
the cheapest product that covers the quantity.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, ClaimStatus, OptionKind, OrderStatus, PlacedBy, Verdict

MILK, GLUTEN = "AM", "AW"  # GS1 allergen codes (AIMO/docs/SCHEMA-AND-CODES.md)
CHOSEN = "464013"
SCENARIO_2_EVENTS = [
    "request.received", "request.parsed", "lookup.performed", "offer.created", "policy.evaluated",
    "approval.requested", "approval.decided", "order.confirmed",
]


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
