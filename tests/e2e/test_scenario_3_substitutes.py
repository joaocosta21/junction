"""Scenario 3 of docs/DEMO.md, a supplier stock-out: "100 litres of Oddlygood Barista oat drink, product 473609,
by Monday", asked by the hotel kitchen.

Valio Aimo does not confirm the stock of `473609` (it reports a placeholder). Of the three substitutes Valio lists
for it, `471881` and `464320` add gluten cereals (`AW`, contains) to a gluten-free product and can never be
ordered as a substitute; `471690` adds no allergen.

The first option is the same at both clocks (decisions B16 and B52): a confirmed barista oat drink, `475224`, for
€174.00, because confirmed stock of the same kind stands in before an unconfirmed product, also one Valio lists.
Its formula differs from the product asked for (its line says "Not a like-for-like replacement: a different
formula"), so rule F-12 sends it to a person with that reason, whatever the buyer sets (decision B64).
The product asked for stays as "quantity not confirmed" (€137.00). What differs by clock:
- at the recording's clock (Saturday 02:52) the cut-off of `471690` has passed, so it is not offered;
- at the demo clock (Thursday 14:15) `471690` can still be ordered, but its quantity is not confirmed: it is a
  labelled alternative (€155.50) after the confirmed option.
With "confirmed data only" the answer is the same at both clocks: 100 x `475224`, with what it gives up in numbers.

Scores on the 15% "partial availability, substitutions and delivery constraints".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, OptionKind, OrderStatus, PlacedBy, Verdict

ORIGINAL = "473609"
PASSES = "471690"  # Valio's own listed substitute that adds no allergen
ADDS_GLUTEN = ("471881", "464320")
CONFIRMED_STAND_IN = "475224"  # Fazer Aito Professional Barista oat drink, gluten free: 130 confirmed in stock
NOTE = "The baristas agreed to the stand-in."


def _by_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate["product_id"]: candidate for candidate in result["candidates"]}


def _unconfirmed(option: dict[str, Any]) -> bool:
    return any(
        line["availability"]["state"] == AvailabilityState.QUANTITY_NOT_CONFIRMED for line in option["lines"]
    )


def test_scenario_3_substitutes_listed_by_valio_pass_or_fail_the_allergen_rule(both: Any, texts: Any) -> None:
    result = both.substitutes("hotel", ORIGINAL, {"quantity": 100, "unit": "L", "needed_by": texts.monday})
    candidates = _by_id(result)
    assert result["original_id"] == ORIGINAL and result["source"] == "replay"

    passing = candidates[PASSES]
    assert (passing["passes"], passing["listed_by_supplier"]) == (True, True)
    assert passing["allergen_check"]["added"] == []
    if both.clock == "recording":  # its cut-off has passed: a delivery constraint, said with its reason
        assert (passing["orderable"], passing["reason"]) == (False, "CUTOFF_PASSED")
    else:  # still in time on the demo clock, but Valio Aimo does not know its stock
        assert (passing["orderable"], passing["reason"]) == (True, None)
        assert "Quantity not confirmed" in passing["sentence"]

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
    stand_in = candidates[CONFIRMED_STAND_IN]
    assert (stand_in["passes"], stand_in["orderable"], stand_in["listed_by_supplier"]) == (True, True, False)


def test_scenario_3_the_sentence_is_read_as_its_typed_request(both: Any, texts: Any) -> None:
    read = both.parse("hotel", texts.scenario_3)
    typed = texts.scenario_3_request

    assert read["needed_by"] == typed["needed_by"] and read["require_confirmed"] is False
    for name in ("product_type", "product_ids", "quantity", "unit"):
        assert read["lines"][0][name] == typed["lines"][0][name], name


def test_scenario_3_at_both_clocks_nothing_unconfirmed_is_suggested_and_no_option_adds_gluten(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any, option_of: Any
) -> None:
    offer = both.offer("hotel", texts.scenario_3_request)

    offered = {line["product_id"] for option in offer["options"] for line in option["lines"]}
    assert not offered & set(ADDS_GLUTEN)
    for option in offer["options"]:
        assert option["decision"]["verdict"] == Verdict.APPROVAL  # every option needs a person
        if _unconfirmed(option):  # unconfirmed stock, the original's or a substitute's: a labelled alternative
            assert option["kind"] == OptionKind.ALTERNATIVE_UNCONFIRMED
            assert "F-01" in fired(option) and "not confirmed" in option["title"]
        for line in option["lines"]:
            stands_in = line["substitute"]
            if stands_in is not None:  # a substitute line says what it gives up, in words and numbers
                assert stands_in["original_id"] == ORIGINAL and stands_in["allergen_check"]["passes"] is True
                assert stands_in["gives_up"].strip() and stands_in["formula"]["sentence"].strip()

    original = option_of(offer, ORIGINAL)
    assert lines_of(original) == {ORIGINAL: Decimal(100)}
    assert money(original["totals"]["net"]) == Decimal("137.00") and fired(original) == {"F-01"}

    first = offer["options"][0]  # confirmed stock of the same kind leads at both clocks (decision B52)
    assert first["kind"] == OptionKind.SUBSTITUTE and lines_of(first) == {CONFIRMED_STAND_IN: Decimal(100)}
    assert money(first["totals"]["net"]) == Decimal("174.00") and fired(first) == {"F-12"}
    rule = first["decision"]["fired"][0]  # the rule's own line says why, in the offer's words and numbers
    assert "is not a like-for-like replacement: a different formula" in rule["sentence"]
    assert "sugars 1.6 g, not 3.5 g" in rule["sentence"] and rule["sentence"].endswith(
        "A person decides whether it will do."
    )
    assert not _unconfirmed(first)
    assert all(_unconfirmed(option) for option in offer["options"][1:])  # the one confirmed option; the rest labelled
    if both.clock == "recording":
        assert PASSES not in offered  # its cut-off has passed
    else:
        listed = option_of(offer, PASSES)  # Valio's own listed substitute: in time, quantity not confirmed
        assert listed is not first
        assert listed["lines"][0]["substitute"]["listed_by_supplier"] is True
        assert money(listed["totals"]["net"]) == Decimal("155.50") and "F-01" in fired(listed)
        assert "1.5 g" in listed["lines"][0]["substitute"]["gives_up"]  # its fat, against the original's 3 g


def test_scenario_3_with_confirmed_data_only_the_confirmed_stand_in_is_prepared_and_a_person_confirms_it(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any, event_types: Any, two_views: Any
) -> None:
    """ "...; confirmed data only" gives the same answer at both clocks: the product asked for is left out with
    its reason, and the confirmed stand-in says what it gives up."""
    sentence = texts.scenario_3 + "; confirmed data only"
    read = both.parse("hotel", sentence)
    assert read["require_confirmed"] is True and read["lines"][0]["product_ids"] == [ORIGINAL]

    offer = both.offer("hotel", {**texts.scenario_3_request, "require_confirmed": True})
    assert [option["kind"] for option in offer["options"]] == [OptionKind.SUBSTITUTE]
    stand_in = offer["options"][0]
    assert lines_of(stand_in) == {CONFIRMED_STAND_IN: Decimal(100)}
    assert money(stand_in["totals"]["net"]) == Decimal("174.00")
    assert (stand_in["decision"]["verdict"], fired(stand_in)) == (Verdict.APPROVAL, {"F-12"})
    gives_up = stand_in["lines"][0]["substitute"]["gives_up"]
    assert "€0.37" in gives_up and "1.6 g" in gives_up  # dearer per litre, and less sugar: said in numbers
    assert {(left["product_id"], left["reason"]) for left in offer["excluded"]} == {
        (ORIGINAL, "QUANTITY_NOT_CONFIRMED"),
    }

    order = both.order("hotel", offer)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    decided = both.confirm("hotel", order, NOTE)
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    assert decided["status_sentence"] == (
        "Ordered for €174.00 net with approval by Demo approver Hanna: rule F-12 asked for a human and was accepted."
    )
    own, _ = two_views(both, "hotel", decided, decided_by="hotel:purchasing_manager", note=NOTE)
    assert event_types(own)[-3:] == ["approval.requested", "approval.decided", "order.confirmed"]


def test_scenario_3_the_plain_sentence_end_to_end_a_person_confirms_the_first_option_at_either_clock(
    both: Any, texts: Any, two_views: Any
) -> None:
    run = both.run_agent("hotel", texts.scenario_3)  # no recording: read by the fixed rules, and said so
    assert run["recorded"] is False and run["order_status"] == OrderStatus.PENDING_APPROVAL

    order = both.get_order("hotel", run["order_id"])
    assert order["placed_by"] is None and order["decision"]["required_roles"] == ["purchasing_manager"]
    decided = both.confirm("hotel", order, NOTE)

    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    two_views(both, "hotel", decided, decided_by="hotel:purchasing_manager", note=NOTE)
