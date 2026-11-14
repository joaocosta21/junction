"""Scenario 6 of docs/DEMO.md: the bakery-café, where the formula matters (rule F-11).

6a, "40 kg of Valio crème fraîche, product 477055, by Monday, for baking". Valio Aimo does not confirm the stock of
`477055`, and no substitute that keeps its formula can be ordered. The product itself comes first, as "quantity
not confirmed"; the one substitute there is comes last, titled "a substitute that does not keep the formula", with
the difference in grams, and goes to a person under F-11. Which substitute that is depends on the clock (at the
recording's clock the cut-off of the demo clock's candidate has passed); the rule and the label do not.

6b, "100 litres of whipping cream by Monday, for cakes". Whipping creams with confirmed stock fill 85 of the
100 L, and the vegetable-fat blend `463975` is never used to top the line up. Whether a stand-in keeps the formula
is the formula comparison's answer (nutrition figures and contents); these tests pin what the offer does with that
answer, not the answer: a stand-in that does not keep the formula is never the suggestion, is labelled, and goes to
a person under F-11; one that keeps it says so and F-11 stays silent.

Scores on the 20% "matches what the buyer asked" and the 15% substitutions.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, OptionKind, OrderStatus, PlacedBy, Verdict

CREME_FRAICHE = "477055"
# The substitute offered for it, by clock: measured in replay over the recording on 14 Nov 2026.
FORMULA_CHANGER = {"recording": "468277", "demo": "477003"}
VEGETABLE_FAT_BLEND = "463975"
NOTE = "The pastry chef accepts the wait."


def test_scenario_6a_the_sentence_is_read_with_the_formula_mark(both: Any, texts: Any) -> None:
    read = both.parse("bakery", texts.formula_changed)
    typed = texts.formula_changed_request["lines"][0]

    for name in ("product_ids", "quantity", "unit", "keep_formula"):
        assert read["lines"][0][name] == typed[name], name
    assert read["needed_by"] == texts.monday


def test_scenario_6a_a_substitute_that_changes_the_formula_is_never_the_suggestion_and_f11_says_why(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any, option_of: Any
) -> None:
    offer = both.offer("bakery", texts.formula_changed_request)

    first = offer["options"][0]
    assert lines_of(first) == {CREME_FRAICHE: Decimal(20)}  # 20 tubs of 2 kg: the 40 kg asked for
    assert first["lines"][0]["availability"]["state"] == AvailabilityState.QUANTITY_NOT_CONFIRMED
    assert money(first["totals"]["net"]) == Decimal("214.40") and fired(first) == {"F-01"}
    assert not any(line["substitute"] for line in first["lines"])

    stand_ins = [option for option in offer["options"] if any(line["substitute"] for line in option["lines"])]
    assert len(stand_ins) == 1 and stand_ins[0] is offer["options"][-1]
    changed = stand_ins[0]
    assert changed["kind"] == OptionKind.ALTERNATIVE_UNCONFIRMED
    assert "a substitute that does not keep the formula" in changed["title"]
    assert {"F-11", "P-05"} <= fired(changed) and changed["decision"]["verdict"] == Verdict.APPROVAL
    rule = next(rule for rule in changed["decision"]["fired"] if rule["rule_id"] == "F-11")
    assert "where the formula matters" in rule["sentence"]
    assert " g, not " in rule["sentence"]  # the difference in grams per 100 g
    line = changed["lines"][0]
    assert line["substitute"]["formula"]["sentence"].strip()
    assert line["substitute"]["gives_up"].startswith("Not a like-for-like replacement:")
    assert any("no substitute that keeps the formula can be ordered" in note for note in offer["notes"])
    assert option_of(offer, FORMULA_CHANGER[both.clock]) is changed


def test_scenario_6a_from_the_sentence_the_owner_confirms_the_product_itself_and_valio_reads_the_rule(
    both: Any, texts: Any, fired: Any, lines_of: Any, two_views: Any
) -> None:
    run = both.run_agent("bakery", texts.formula_changed)
    order = both.get_order("bakery", run["order_id"])
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert lines_of(order["option"]) == {CREME_FRAICHE: Decimal(20)}
    assert fired(order) == {"F-01"} and order["decision"]["required_roles"] == ["purchasing_manager"]

    decided = both.confirm("bakery", order, NOTE)

    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    assert decided["status_sentence"] == (  # the owner holds every role of the bakery (decision B27)
        "Ordered for €214.40 net with approval by Demo approver Marko (purchasing manager, finance and dietitian): "
        "rule F-01 asked for a human and was accepted."
    )
    _, valio = two_views(both, "bakery", decided, decided_by="bakery:purchasing_manager", note=NOTE)
    judged = " ".join(event["sentence"] for event in valio["events"] if event["type"].endswith("policy.evaluated"))
    assert "F-11" in judged  # the rule on the option that was not taken is in Valio Aimo's view too


def _stand_ins(option: dict[str, Any]) -> list[dict[str, Any]]:
    return [line["substitute"] for line in option["lines"] if line["substitute"]]


def _assert_f11_is_labelled_and_never_the_suggestion(offer: dict[str, Any], fired: Any) -> None:
    """Whatever the formula comparison answers: an option on which F-11 fires says so in its title, needs a person
    and is not the first option; an option on which it does not fire is not labelled as changing the formula."""
    for place, option in enumerate(offer["options"]):
        if "F-11" in fired(option):
            assert place > 0 and "does not keep the formula" in option["title"], option["title"]
            assert option["decision"]["verdict"] == Verdict.APPROVAL
            rule = next(rule for rule in option["decision"]["fired"] if rule["rule_id"] == "F-11")
            assert "where the formula matters" in rule["sentence"]
        else:
            assert "does not keep the formula" not in option["title"]


def test_scenario_6b_whipping_cream_is_never_topped_up_with_a_vegetable_fat_blend(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any
) -> None:
    read = both.parse("bakery", texts.formula_kept)
    assert read["lines"][0]["keep_formula"] is True and read["lines"][0]["name_terms"] == ["whipping"]

    offer = both.offer("bakery", texts.formula_kept_request)

    best = offer["options"][0]
    assert best["kind"] == OptionKind.BEST_CONFIRMED and "F-11" not in fired(best)
    assert all(line["availability"]["state"] == AvailabilityState.CONFIRMED for line in best["lines"])
    assert "469346" in lines_of(best) and lines_of(best)["469346"] == Decimal(48)  # all its confirmed stock
    assert money(best["fill_ratio"]) < 1 and "P-03" in fired(best)  # short of 100 L, and said so
    for option in offer["options"]:
        assert VEGETABLE_FAT_BLEND not in lines_of(option)
        assert all(line["keep_formula"] is True for line in option["lines"])
        assert option["decision"]["verdict"] == Verdict.APPROVAL
    _assert_f11_is_labelled_and_never_the_suggestion(offer, fired)


def test_scenario_6b_asked_for_by_id_the_stand_in_says_whether_it_keeps_the_formula_and_a_person_decides(
    both: Any, fired: Any, lines_of: Any, option_of: Any, two_views: Any
) -> None:
    """60 L of `469346`, of which 48 are confirmed: the first option is the confirmed 48 L; 12 L of another
    whipping cream stand in only in a later option, with what they give up, and a person decides (the bakery
    accepts no substitute alone, rule P-05)."""
    request = {
        "needed_by": "2026-11-16",
        "lines": [{
            "text": "60 litres of Arla Pro whipping cream, product 469346, by Monday, for cakes",
            "product_type": "cream", "product_ids": ["469346"], "quantity": 60, "unit": "L", "keep_formula": True,
        }],
    }
    offer = both.offer("bakery", request)

    partial = offer["options"][0]
    assert lines_of(partial) == {"469346": Decimal(48)} and "P-03" in fired(partial)
    _assert_f11_is_labelled_and_never_the_suggestion(offer, fired)
    topped_up = option_of(offer, "464727")
    assert lines_of(topped_up) == {"469346": Decimal(48), "464727": Decimal(12)}
    assert "P-05" in fired(topped_up)
    (stand_in,) = _stand_ins(topped_up)
    assert stand_in["gives_up"].strip() and stand_in["formula"]["sentence"].strip()
    assert ("F-11" in fired(topped_up)) == ("does not keep the formula" in topped_up["title"])

    order = both.order("bakery", offer, option=offer["options"].index(topped_up))
    decided = both.confirm("bakery", order, NOTE)
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
    two_views(both, "bakery", decided, decided_by="bakery:purchasing_manager", note=NOTE)
