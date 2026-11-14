"""How the order was decided, read from the facts of the supplier's view of the trail (P9b B13-2)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tta.contracts.common import ApproverRole, ExclusionReason, Verdict
from tta.ui.supplier_view import supplier_decision


def _audit(*facts: dict[str, Any]) -> Any:
    """A trail whose events carry these facts, oldest first: the page reads only `events[].facts` and `.id`."""
    return SimpleNamespace(events=[SimpleNamespace(id=f"evt_{n}", facts=one) for n, one in enumerate(facts)])


DECISION = {
    "verdict": "APPROVAL",
    "rules": [
        {"rule_id": "P-01", "title": "The order is above the spend limit per order", "fixed": False,
         "verdict": "APPROVAL", "approver_role": "purchasing_manager", "product_id": None},
        {"rule_id": "F-01", "title": "A quantity is not confirmed", "fixed": True, "verdict": "APPROVAL",
         "approver_role": "purchasing_manager", "product_id": "464306"},
        {"rule_id": "F-01", "title": "A quantity is not confirmed", "fixed": True, "verdict": "APPROVAL",
         "approver_role": "purchasing_manager", "product_id": "473609"},
    ],
}
OFFER = {
    "excluded_by_reason": {"ALLERGEN_DECLARED": 2, "CUTOFF_PASSED": 1, "NOT_DELIVERABLE": 12},
    "left_out": [{"product_id": "471690", "name": "Oat drink", "reason": "CUTOFF_PASSED"}]
    + [{"product_id": f"4700{n:02d}", "name": None, "reason": "NOT_DELIVERABLE"} for n in range(12)],
}


def test_a_rule_that_fired_on_two_lines_is_one_row_with_both_products_and_what_is_masked() -> None:
    found = supplier_decision(_audit({"offer": OFFER}, {"decision": DECISION}))

    assert found is not None and found.verdict is Verdict.APPROVAL
    assert [(row.rule_id, row.product_ids) for row in found.rules] == [("P-01", ()), ("F-01", ("464306", "473609"))]
    assert found.rules[0].masked == "the amount is not shown" and found.rules[1].masked is None
    assert found.rules[0].approver_role is ApproverRole.PURCHASING_MANAGER


def test_products_left_out_come_by_reason_with_valios_own_reasons_first_and_the_allergen_ones_masked() -> None:
    found = supplier_decision(_audit({"offer": OFFER}, {"decision": DECISION}))

    assert found is not None
    rows = {row.reason: row for row in found.left_out}
    assert list(rows) == [ExclusionReason.NOT_DELIVERABLE, ExclusionReason.CUTOFF_PASSED,
                          ExclusionReason.ALLERGEN_DECLARED]
    assert (len(rows[ExclusionReason.NOT_DELIVERABLE].products), rows[ExclusionReason.NOT_DELIVERABLE].more) == (10, 2)
    allergen = rows[ExclusionReason.ALLERGEN_DECLARED]
    assert (allergen.count, allergen.products, allergen.masked) == (2, (), True)


def test_a_trail_without_a_decision_or_with_one_that_cannot_be_read_shows_none() -> None:
    assert supplier_decision(_audit({"offer": OFFER})) is None
    assert supplier_decision(_audit({"decision": {"verdict": "MAYBE"}})) is None


def test_an_offer_fact_that_cannot_be_read_leaves_the_decision_and_no_product_list() -> None:
    found = supplier_decision(_audit({"offer": {"left_out": "not a list"}}, {"decision": DECISION}))

    assert found is not None and found.rules and found.left_out == ()
