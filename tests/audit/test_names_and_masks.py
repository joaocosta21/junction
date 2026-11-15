"""Names instead of codes in the buyer's log, and a mask that claims no more than it hides (lane FIX-A1, item 10).

From the browser walk of 15 Nov. The buyer's log said "excluding allergens AM and AW": a person reads names. And
Valio Aimo's view of the school's almond-drink order said "which allergen and which product are not shown", then
named product 465793 as the order's one line: where an order has one product, that product is the order's line and
other steps show it, so the sentence claims to hide the allergen only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.audit import AuditTrail
from tta.audit.readers import EVIDENCE_PRODUCT_NOT_SHOWN, shown_sentence
from tta.contracts.audit import AuditContext, AuditEventType
from tta.contracts.common import AllergenStrictness, ApproverRole, Unit, Verdict
from tta.contracts.policy import FiredRule
from tta.contracts.request import PurchaseRequest, RequestLine

DIETITIAN_ASKED = FiredRule(
    rule_id="P-04", title="A line does not rule out an excluded allergen", fixed=False, verdict=Verdict.APPROVAL,
    approver_role=ApproverRole.DIETITIAN, sentence="465793 may contain tree nuts.", facts={"allergen": "AN"},
    product_id="465793",
)
MISSING_ALLERGEN_FACT = FiredRule(
    rule_id="F-03", title="A fact a rule needs is missing", fixed=True, verdict=Verdict.APPROVAL,
    approver_role=ApproverRole.DIETITIAN, sentence="The allergen statement of 465793 is missing.",
    facts={"missing_fact": "line.allergen_outcome", "needed_by": ["P-04"]}, product_id="465793",
)


def _request(strictness: AllergenStrictness | None, *codes: str) -> PurchaseRequest:
    line = RequestLine(text="a plant drink", product_type="plant_drink", quantity=Decimal(20), unit=Unit.L,
                       exclude_allergens=codes, allergen_strictness=strictness)
    return PurchaseRequest(lines=(line,))


def _read_as(trail: AuditTrail, samples: Any, request: PurchaseRequest) -> Any:
    return trail.record(AuditEventType.REQUEST_PARSED, samples.gateway,
                        AuditContext(profile_id="school-kitchen", offer_id="off_1", request=request))


def test_the_buyer_reads_the_allergens_it_excludes_by_name_and_the_rule_in_words(
    trail: AuditTrail, samples: Any
) -> None:
    strict = _read_as(trail, samples, _request(AllergenStrictness.STRICT, "AM", "AW"))
    declared = _read_as(trail, samples, _request(AllergenStrictness.DECLARED_ONLY, "AN"))
    unknown = _read_as(trail, samples, _request(None, "ZZ"))

    assert strict.data.sentence == (
        "The request was read as: 20 litres of product type plant_drink, excluding allergens milk and cereals "
        "containing gluten (strict rule)."
    )
    assert declared.data.sentence.endswith("excluding allergens tree nuts (declared only rule).")
    assert unknown.data.sentence.endswith("excluding allergens ZZ.")  # a code the table does not hold, as data
    for event in (strict, declared):
        assert " AM" not in event.data.sentence and "STRICT" not in event.data.sentence
        assert "allergen" not in event.data.supplier_sentence  # Valio Aimo still reads no exclusion


def test_on_an_order_of_one_product_valio_aimo_is_told_the_allergen_is_hidden_and_nothing_about_the_product(
    trail: AuditTrail, samples: Any
) -> None:
    """The school's almond drink: the next step names 465793 as the order's line."""
    one_line = samples.option("opt_1", (samples.line("465793", "20", "2.38"),),
                              samples.decision(DIETITIAN_ASKED, MISSING_ALLERGEN_FACT), requested="20")

    checked = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                           AuditContext(offer_id="off_1", option=one_line)).data.supplier_sentence

    assert (
        "P-04, a rule the buyer set (a line does not rule out an excluded allergen; which allergen is not shown): "
    ) in checked
    assert (
        "F-03, a fixed rule (a fact a rule needs is missing; the missing fact is about a requirement of the "
        "buyer's, which is not shown): "
    ) in checked
    assert "product" not in checked and "465793" not in checked and "tree nuts" not in checked


def test_on_an_order_of_several_products_the_product_the_rule_fired_on_stays_hidden_and_is_said_to_be(
    trail: AuditTrail, samples: Any
) -> None:
    two_lines = samples.option("opt_1", (samples.line("465793", "20", "2.38"), samples.line("464013", "20", "2.01")),
                               samples.decision(DIETITIAN_ASKED, MISSING_ALLERGEN_FACT), requested="40")

    checked = trail.record(AuditEventType.POLICY_EVALUATED, samples.gateway,
                           AuditContext(offer_id="off_1", option=two_lines)).data.supplier_sentence

    assert "which allergen and which product are not shown): " in checked
    assert "a product is not shown where the missing fact is about a requirement of the buyer's): " in checked
    assert "465793" not in checked


def test_the_evidence_sentence_says_the_product_is_not_named_in_this_step_and_nothing_about_other_steps(
    trail: AuditTrail, samples: Any
) -> None:
    event = trail.record(AuditEventType.EVIDENCE_ATTACHED, samples.gateway,
                         AuditContext(approval=samples.approval(), evidence=samples.evidence()))
    stored_before = (
        "Evidence from outside Valio Aimo's data was attached to an approval for product 473609: The manufacturer's "
        "page lists oats. It changes no status and no verdict."
    )

    assert event.data.supplier_sentence == (
        "Evidence from outside Valio Aimo's data was attached to an approval (the product is not named in this "
        "step). It changes no status and no verdict."
    )
    assert EVIDENCE_PRODUCT_NOT_SHOWN in shown_sentence(stored_before) and "473609" not in shown_sentence(stored_before)


# --- item 12 (from the menu lane): an option of several request lines says how many it covers in full --------------


def _with_lines_covered(samples: Any, covered: tuple[str, ...]) -> Any:
    """An option whose request has one line per entry: each entry is what is covered of 10 litres asked."""
    from tta.contracts.offer import Coverage

    option = samples.option("opt_1", (samples.line("464013", "10", "2.01"),), samples.decision(), requested="10")
    parts = tuple(
        Coverage(request_line_index=index, requested=Decimal(10), covered=Decimal(amount), unit=Unit.L,
                 fill_ratio=Decimal(amount) / 10, missing=Decimal(10) - Decimal(amount))
        for index, amount in enumerate(covered)
    )
    return option.model_copy(update={"coverage": parts, "fill_ratio": Decimal(0)})


def test_a_menu_option_with_some_lines_missing_says_how_many_request_lines_it_covers_in_full(samples: Any) -> None:
    """Demo scenario 7: the log said "covering 0% of the request" of an order that covers 4 of 7 lines in full."""
    from tta.audit.phrases import coverage_text

    four_of_seven = _with_lines_covered(samples, ("10", "10", "10", "10", "0", "0", "4"))
    one_line = _with_lines_covered(samples, ("4",)).model_copy(update={"fill_ratio": Decimal("0.4")})
    complete = _with_lines_covered(samples, ("10", "10")).model_copy(update={"fill_ratio": Decimal(1)})

    assert coverage_text(four_of_seven) == "covering 4 of the 7 items asked for in full"
    assert coverage_text(one_line) == "covering 40% of the request"
    assert coverage_text(complete) == "covering the full quantity"
