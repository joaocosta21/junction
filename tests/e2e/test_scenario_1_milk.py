"""Scenario 1 (SPEC section 13): the hotel kitchen asks for 1,000 litres of lactose-free milk by Monday.

Milk for coffee is a product type of its own since 14 Nov (Valio Aimo: "no be explicit"), so Arla Cafè milk no
longer fills the request. Two confirmed milks cover 435 of the 1,000 litres: option 1 is a partial fill, 43.5%,
and goes to a person for the per-order limit and the minimum fill (P-01, P-03). The alternative is 1,000 litres
of a milk whose quantity Valio Aimo does not confirm. Asking for 1,500 litres changes only what is missing.
Measured at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, ClaimStatus, OptionKind, OrderStatus, PlacedBy, Verdict

PORTION_MILK = "463203"  # Arla portion milk, 100 x 2 cl: a single-serve pack, excluded from a bulk line
CONFIRMED_MILKS = {"469363": Decimal(384), "462775": Decimal(51)}  # 435 L: all the confirmed stock there is
COFFEE_MILKS = {"462626", "463380", "464237", "473142"}  # another product type: never offered for milk
UNCONFIRMED_MILK = "464306"  # the cheapest lactose-free milk; Valio does not confirm its stock
APPROVER_NOTE = "Checked with the kitchen."
SCENARIO_1_EVENTS = [
    "request.received", "request.parsed", "lookup.performed", "offer.created",
    "policy.evaluated", "policy.evaluated", "approval.requested", "approval.decided", "order.confirmed",
]


def _option(offer: dict[str, Any], kind: OptionKind) -> dict[str, Any]:
    found = [option for option in offer["options"] if option["kind"] == kind]
    assert len(found) == 1, [option["kind"] for option in offer["options"]]
    return found[0]


def _assert_scenario_1_offer(offer: dict[str, Any], money: Any, fired: Any, lines_of: Any) -> None:
    best = offer["options"][0]
    assert best["kind"] == OptionKind.BEST_CONFIRMED
    assert lines_of(best) == CONFIRMED_MILKS
    for line in best["lines"]:
        assert line["availability"]["state"] == AvailabilityState.CONFIRMED
        assert {claim["claim"]: claim["status"] for claim in line["claims"]}["quantity"] == ClaimStatus.CONFIRMED
    assert money(best["totals"]["net"]) == Decimal("1083.39")
    assert money(best["fill_ratio"]) == Decimal("0.435")
    coverage = best["coverage"][0]
    assert (money(coverage["covered"]), money(coverage["missing"])) == (Decimal(435), Decimal(565))
    assert best["decision"]["verdict"] == Verdict.APPROVAL
    assert fired(best) == {"P-01", "P-03"}
    offered = {line["product_id"] for option in offer["options"] for line in option["lines"]}
    assert not offered & COFFEE_MILKS
    assert offer["notes"][0].startswith("Request line 1: Coffee milk was left out:")

    alternative = _option(offer, OptionKind.ALTERNATIVE_UNCONFIRMED)
    assert lines_of(alternative) == {UNCONFIRMED_MILK: Decimal(1000)}
    assert alternative["lines"][0]["availability"]["state"] == AvailabilityState.QUANTITY_NOT_CONFIRMED
    assert money(alternative["totals"]["net"]) == Decimal("1010.00")
    assert alternative["decision"]["verdict"] == Verdict.APPROVAL
    assert fired(alternative) == {"F-01", "P-01"}

    excluded = {exclusion["product_id"]: exclusion for exclusion in offer["excluded"]}
    assert excluded[PORTION_MILK]["reason"] == "PORTION_PACK"
    assert all(exclusion["reason"] and exclusion["sentence"].strip() for exclusion in offer["excluded"])
    assert offer["source"] == "replay"


def test_scenario_1_from_the_pasted_sentence_goes_to_a_human_who_approves_it(
    demo: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any
) -> None:
    run = demo.run_agent("hotel", texts.scenario_1)
    offer = demo.get_offer("hotel", run["offer_id"])
    _assert_scenario_1_offer(offer, money, fired, lines_of)

    order = demo.get_order("hotel", run["order_id"])
    assert run["order_status"] == OrderStatus.PENDING_APPROVAL == order["status"]
    assert order["option_id"] == offer["options"][0]["option_id"]
    approval = demo.approval_of("hotel", order)
    assert approval["required_roles"] == ["purchasing_manager"]
    assert approval["valid_until"] == "2026-11-15T17:00:00+02:00"  # "order by": the lines' cut-off

    decided = demo.approve_all_roles("hotel", order, APPROVER_NOTE)
    assert decided["status"] == OrderStatus.ORDERED
    assert decided["placed_by"] == PlacedBy.HUMAN_APPROVAL
    assert money(decided["option"]["totals"]["net"]) == Decimal("1083.39")
    assert {statement["product_id"] for statement in decided["reliance"]} == set(CONFIRMED_MILKS)

    trail = demo.audit("hotel", order["order_id"])
    assert event_types(trail) == SCENARIO_1_EVENTS
    assert all(event["sentence"].strip() for event in trail["events"])
    assert trail["chain"]["ok"] is True
    rules = {event["type"].removeprefix("tta.v1."): set(event["rule_ids"]) for event in trail["events"]}
    assert rules["approval.requested"] == rules["order.confirmed"] == {"P-01", "P-03"}


def test_scenario_1_the_supplier_sees_every_step_without_the_buyers_limits_names_or_notes(
    demo: Any, texts: Any, event_types: Any
) -> None:
    run = demo.run_agent("hotel", texts.scenario_1)
    order = demo.get_order("hotel", run["order_id"])
    demo.approve_all_roles("hotel", order, APPROVER_NOTE)

    buyer = demo.audit("hotel", order["order_id"])
    supplier = demo.audit("supplier", order["order_id"])
    assert supplier["reader"] == "supplier"
    assert event_types(supplier) == event_types(buyer) == SCENARIO_1_EVENTS
    assert all(event["sentence"].strip() for event in supplier["events"])
    assert supplier["chain"]["ok"] is True
    shown = " ".join(event["sentence"] for event in supplier["events"])
    for private in ("€750", "€3,000", "Hanna", APPROVER_NOTE, "hotel-kitchen"):
        assert private not in shown


def test_scenario_1_the_typed_request_gives_the_same_offer_as_the_pasted_sentence(
    demo: Any, texts: Any, money: Any, fired: Any, lines_of: Any
) -> None:
    """The page falls back to the typed request when no model can read the sentence: the offer is the same."""
    offer = demo.offer("hotel", texts.milk(1000))
    _assert_scenario_1_offer(offer, money, fired, lines_of)


def test_scenario_1_partial_fill_typed_request_for_more_than_the_confirmed_stock(
    demo: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any
) -> None:
    """1,500 litres: the confirmed milks cover 435 litres (29%), below the profile's 90% minimum (P-03)."""
    offer = demo.offer("hotel", texts.milk(1500))

    best = offer["options"][0]
    assert best["kind"] == OptionKind.BEST_CONFIRMED
    assert lines_of(best) == CONFIRMED_MILKS
    coverage = best["coverage"][0]
    assert (money(coverage["covered"]), money(coverage["missing"])) == (Decimal(435), Decimal(1065))
    assert money(best["fill_ratio"]) == Decimal("0.29")
    assert money(best["totals"]["net"]) == Decimal("1083.39")
    assert best["decision"]["verdict"] == Verdict.APPROVAL
    assert fired(best) == {"P-01", "P-03"}
    quantity = [check for check in best["constraint_checks"] if check["kind"] == "QUANTITY"]
    assert [check["result"] for check in quantity] == ["NOT_MET"]

    alternative = _option(offer, OptionKind.ALTERNATIVE_UNCONFIRMED)
    assert lines_of(alternative) == {UNCONFIRMED_MILK: Decimal(1500)}

    order = demo.order("hotel", offer)
    assert order["status"] == OrderStatus.PENDING_APPROVAL
    decided = demo.approve_all_roles("hotel", order, APPROVER_NOTE)
    assert decided["status"] == OrderStatus.ORDERED
    trail = demo.audit("hotel", order["order_id"])
    assert event_types(trail)[-3:] == ["approval.requested", "approval.decided", "order.confirmed"]
    assert all(event["sentence"].strip() for event in trail["events"])
