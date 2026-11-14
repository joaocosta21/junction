"""Scenario 4 of docs/DEMO.md: a product whose data does not rule out an allergen the buyer excludes.

4a, the hotel: "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule". Valio
Aimo's data states nothing about milk for `469512`. The first option is a product whose data rules milk out; the
product asked for is a labelled alternative that only the dietitian can release (rule P-04). The dietitian has
three choices: take the safe product, use the product asked for anyway, or leave it out. The manufacturer's page
is attached as evidence; it changes no verdict.

4b, the school: "20 litres of almond drink by Monday". The school's profile excludes tree nuts, peanuts and sesame
under the strict rule. No almond drink's data rules tree nuts out, so no option is suggested as safe. For
`465793` Valio Aimo's data says "may contain"; the manufacturer's recorded page says it contains almond.

The evidence is read from `fixtures/evidence/` (recorded pages): no outside call is made.
Scores on the 20% guardrails (who must sign, and why), the 15% substitutions and the brief's "allergen-safe
substitution under pressure".
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import OptionKind, OrderStatus, PlacedBy, Verdict

ELOVENA = "469512"
ALMOND = "465793"  # Alpro Barista Almond drink 1 L
MILK, TREE_NUTS = "AM", "AN"
NOTE = "Checked against the diet sheet."


def _doubt_for(option: dict[str, Any]) -> list[dict[str, Any]]:
    return [rule for rule in option["decision"]["fired"] if rule["rule_id"] == "P-04"]


def _order_the_doubtful_option(both: Any, buyer: str, offer: dict[str, Any], product_id: str) -> dict[str, Any]:
    place = next(index for index, option in enumerate(offer["options"])
                 if [line["product_id"] for line in option["lines"]] == [product_id])
    order = both.order(buyer, offer, option=place)
    assert (order["status"], order["placed_by"]) == (OrderStatus.PENDING_APPROVAL, None)
    assert order["decision"]["required_roles"] == ["dietitian"]
    return order


# --- 4a: the hotel's oat drink with no milk statement -----------------------------------------------------


def test_scenario_4a_the_sentence_is_read_as_its_typed_request(both: Any, texts: Any) -> None:
    read = both.parse("hotel", texts.dietitian)
    typed = texts.dietitian_request["lines"][0]

    for name in ("product_type", "product_ids", "quantity", "unit", "exclude_allergens", "allergen_strictness"):
        assert read["lines"][0][name] == typed[name], name
    assert read["needed_by"] == texts.monday


def test_scenario_4a_the_safe_product_comes_first_and_the_doubtful_one_is_a_labelled_alternative(
    both: Any, texts: Any, money: Any, fired: Any, lines_of: Any, option_of: Any
) -> None:
    offer = both.offer("hotel", texts.dietitian_request)

    safe = offer["options"][0]
    assert not _doubt_for(safe) and "dietitian" not in safe["decision"]["required_roles"]
    for line in safe["lines"]:  # its data rules milk out: a statement, not a missing one
        assert (line["allergen_check"]["outcome"], line["allergen_check"]["all_explicit"]) == ("PASS", True)
        assert line["substitute"]["original_id"] == ELOVENA
    assert lines_of(safe) == {"473424": Decimal(100)} and money(safe["totals"]["net"]) == Decimal("236.00")
    assert fired(safe) == {"F-10"}

    doubtful = option_of(offer, ELOVENA)
    assert doubtful is not safe and doubtful["title"] == "Alternative: allergen not ruled out"
    assert doubtful["kind"] != OptionKind.BEST_CONFIRMED
    assert money(doubtful["totals"]["net"]) == Decimal("208.00")  # cheaper, and still not the suggestion
    assert doubtful["decision"]["verdict"] == Verdict.APPROVAL
    assert doubtful["decision"]["required_roles"] == ["dietitian"]
    (rule,) = _doubt_for(doubtful)
    assert "(469512)" in rule["sentence"] and rule["approver_role"] == "dietitian"  # the wording is the rule's own


def test_scenario_4a_the_dietitian_sees_the_manufacturers_page_as_evidence_and_nobody_else_can_decide(
    both: Any, texts: Any
) -> None:
    order = _order_the_doubtful_option(both, "hotel", both.offer("hotel", texts.dietitian_request), ELOVENA)

    approval = both.approval_for("hotel:dietitian", order)
    (page,) = approval["evidence"]
    assert (page["product_id"], page["found"]) == (ELOVENA, True)
    assert page["source_url"].startswith("https://") and "Maidoton" in page["free_from"]
    assert "Valio Aimo's data states nothing; the page says free from" in page["sentence"]
    assert any("it is not Valio Aimo's data" in reason and reason.endswith("It changes no verdict: a human decides.")
               for reason in approval["reasons"])

    for other in ("hotel", "hotel:purchasing_manager", "hotel:finance"):  # the agent, and roles not asked for
        assert both.decide(other, order["approval_id"]).status_code == 403, other
    assert both.get_order("hotel", order["order_id"])["status"] == OrderStatus.PENDING_APPROVAL


@pytest.mark.parametrize("choice", ["take the safe product", "use it anyway", "leave it out"])
def test_scenario_4a_each_of_the_dietitians_three_choices_ends_in_the_log(
    both: Any, texts: Any, money: Any, lines_of: Any, event_types: Any, two_views: Any, choice: str
) -> None:
    offer = both.offer("hotel", texts.dietitian_request)
    order = _order_the_doubtful_option(both, "hotel", offer, ELOVENA)

    if choice == "leave it out":
        answer = both.decide("hotel:dietitian", order["approval_id"], "REJECT", note=NOTE)
        assert answer.status_code == 200, answer.text
        decided = answer.json()
        assert (decided["status"], decided["placed_by"]) == (OrderStatus.REJECTED, None)
        assert decided["status_sentence"] == "Rejected by Demo approver Leena (dietitian): nothing was ordered."
    else:
        safe = offer["options"][0]["option_id"] if choice == "take the safe product" else None
        decided = both.confirm("hotel", order, NOTE, option_id=safe)
        assert (decided["status"], decided["placed_by"]) == (OrderStatus.ORDERED, PlacedBy.HUMAN_APPROVAL)
        ordered, net = ({"473424": Decimal(100)}, "236.00") if safe else ({ELOVENA: Decimal(100)}, "208.00")
        assert lines_of(decided["option"]) == ordered and money(decided["option"]["totals"]["net"]) == Decimal(net)

    own, valio = two_views(both, "hotel", order, decided_by="hotel:dietitian", note=NOTE)
    assert "evidence.attached" in event_types(own)
    chosen = next(event for event in own["events"] if event["type"].endswith("approval.decided"))
    if choice == "take the safe product":
        assert "chose another option of the same offer" in chosen["sentence"]
    attached = next(event for event in valio["events"] if event["type"].endswith("evidence.attached"))
    assert "Maidoton" not in attached["sentence"] and "milk" not in attached["sentence"]  # not the page's words


# --- 4b: the school's almond drink, and the page that says it contains almond -------------------------------


def test_scenario_4b_the_sentence_is_read_as_its_typed_request_and_names_no_allergen(both: Any, texts: Any) -> None:
    read = both.parse("school", texts.almond)
    typed = texts.almond_request["lines"][0]

    for name in ("product_type", "name_terms", "quantity", "unit"):
        assert read["lines"][0][name] == typed[name], name
    assert read["lines"][0]["exclude_allergens"] == []  # the exclusions are the school's profile's, not the sentence's


def test_scenario_4b_no_almond_drink_is_suggested_as_safe_and_every_option_goes_to_the_dietitian(
    both: Any, texts: Any, money: Any, option_of: Any
) -> None:
    offer = both.offer("school", texts.almond_request)

    assert offer["options"], offer["notes"]
    for option in offer["options"]:
        assert option["kind"] != OptionKind.BEST_CONFIRMED and "allergen not ruled out" in option["title"]
        assert _doubt_for(option) and "dietitian" in option["decision"]["required_roles"]
    assert any("no option is suggested as safe" in note for note in offer["notes"])
    declared = [left for left in offer["excluded"] if left["reason"] == "ALLERGEN_DECLARED"]
    assert len(declared) == 3  # three almond drinks declare tree nuts: never offered

    almond = option_of(offer, ALMOND)
    assert almond is offer["options"][0] and money(almond["totals"]["net"]) == Decimal("47.60")
    assert "(465793)" in _doubt_for(almond)[0]["sentence"]


def test_scenario_4b_the_page_says_it_contains_almond_the_dietitian_leaves_it_out_and_valio_reads_no_allergen(
    both: Any, texts: Any, event_types: Any, two_views: Any
) -> None:
    run = both.run_agent("school", texts.almond)  # from the sentence: read by the fixed rules, and said so
    assert run["recorded"] is False and run["order_status"] == OrderStatus.PENDING_APPROVAL
    order = both.get_order("school", run["order_id"])
    assert [line["product_id"] for line in order["option"]["lines"]] == [ALMOND]
    assert order["decision"]["required_roles"] == ["dietitian"]

    approval = both.approval_for("school:dietitian", order)
    (page,) = approval["evidence"]
    assert (page["product_id"], page["found"]) == (ALMOND, True)
    assert "alpro.com" in page["source_url"] and page["contains"] == ["manteli"]
    assert "the page says it contains it, in its words “manteli”" in page["sentence"]
    assert page["sentence"].endswith("What a page says can add a doubt and never removes one.")

    assert both.decide("school:purchasing_manager", order["approval_id"]).status_code == 403
    answer = both.decide("school:dietitian", order["approval_id"], "REJECT", note=NOTE)
    assert answer.status_code == 200, answer.text
    decided = answer.json()
    assert (decided["status"], decided["placed_by"]) == (OrderStatus.REJECTED, None)
    assert both.orders("school")[0]["status"] == OrderStatus.REJECTED

    own, valio = two_views(both, "school", order, decided_by="school:dietitian", note=NOTE)
    # the purchasing manager's refused attempt is in the log too, between the evidence and the decision
    assert event_types(own)[-4:] == [
        "evidence.attached", "authorisation.refused", "approval.decided", "order.rejected",
    ]
    shown = " ".join(event["sentence"] for event in valio["events"])
    assert "P-04" in shown and "manteli" not in shown
