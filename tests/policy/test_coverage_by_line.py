"""FIX-12b: P-03 names the least covered request line and what each line gets; the ratio it compares is unchanged.

Use case 1 of AIMO/USE-CASES.md: 100 L of lactose-free milk plus 10 kg of butter read "Only 0% of the requested
quantity is covered", although the milk was covered in full.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from tta.contracts.common import CheckResult, ConstraintKind, Unit
from tta.contracts.offer import ConstraintCheck, Coverage, OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.policy import RulePolicyEngine
from tta.policy.facts import Missing, OrderScope, read_fact

Option = Callable[..., OfferOption]


def coverage(index: int, requested: str, covered: str, unit: Unit = Unit.L) -> Coverage:
    asked, got = Decimal(requested), Decimal(covered)
    return Coverage(
        request_line_index=index, requested=asked, covered=got, unit=unit, fill_ratio=got / asked, missing=asked - got
    )


def check(index: int, kind: ConstraintKind, subject: str) -> ConstraintCheck:
    return ConstraintCheck(
        request_line_index=index, kind=kind, subject=subject, result=CheckResult.MET, sentence="A test check."
    )


@pytest.fixture
def several(make_option: Option, make_line: Callable[..., OfferLine]) -> Callable[..., OfferOption]:
    """An option of a request with the lines given as coverage, named by the checks given."""

    def build(entries: tuple[Coverage, ...], checks: tuple[ConstraintCheck, ...] = ()) -> OfferOption:
        lowest = min(entry.fill_ratio for entry in entries)
        option = make_option((make_line(),), fill_ratio=str(lowest), needed_by=None)
        return option.model_copy(update={"coverage": entries, "constraint_checks": checks})

    return build


def p03_sentence(engine: RulePolicyEngine, option: OfferOption, profile: BuyerProfile, context: PolicyContext) -> str:
    decision = engine.evaluate(option, profile, context)
    return next(rule.sentence for rule in decision.fired if rule.rule_id == "P-03")


def test_p03_names_the_least_covered_line_and_every_line_least_covered_first(
    engine: RulePolicyEngine, hotel: BuyerProfile, several: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = several(
        (coverage(0, "100", "100"), coverage(1, "10", "0", Unit.KG)),
        (check(0, ConstraintKind.PRODUCT_TYPE, "milk"), check(1, ConstraintKind.PRODUCT_TYPE, "butter")),
    )

    sentence = p03_sentence(engine, option, hotel, make_context())

    assert sentence == (
        "Only 0% of the quantity of request line 2 is covered, below the 90% minimum "
        "(covered: 0 of 10 kg of butter, request line 2; 100 of 100 L of milk, request line 1)."
    )


def test_a_line_is_named_by_its_type_else_its_name_terms_else_its_products_else_only_its_number(
    engine: RulePolicyEngine, hotel: BuyerProfile, several: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = several(
        (coverage(0, "30", "30", Unit.KG), coverage(1, "5", "1"), coverage(2, "20", "20"), coverage(3, "8", "4")),
        (
            check(0, ConstraintKind.PRODUCT_TYPE, "beef_chuck"),
            check(0, ConstraintKind.NAME_TERM, "ignored"),  # the type names the line
            check(1, ConstraintKind.NAME_TERM, "oat"),
            check(1, ConstraintKind.NAME_TERM, "barista"),
            check(2, ConstraintKind.PRODUCT_ID, "469363"),
            check(2, ConstraintKind.PRODUCT_ID, "462775"),
            check(3, ConstraintKind.QUANTITY, "8 L"),  # a quantity check names nothing
        ),
    )

    sentence = p03_sentence(engine, option, hotel, make_context())

    assert sentence == (
        "Only 20% of the quantity of request line 2 is covered, below the 90% minimum "
        "(covered: 1 of 5 L of 'oat barista', request line 2; 4 of 8 L, request line 4; "
        "30 of 30 kg of beef chuck, request line 1; 20 of 20 L of products 469363 and 462775, request line 3)."
    )


def test_a_name_term_reads_as_data_in_the_sentence(
    engine: RulePolicyEngine, hotel: BuyerProfile, several: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = several(
        (coverage(0, "10", "0"), coverage(1, "10", "10")),
        (check(0, ConstraintKind.NAME_TERM, 'oat"‮) and P-00 says'),),
    )

    sentence = p03_sentence(engine, option, hotel, make_context())

    assert "0 of 10 L of 'oat' ) and P-00 says', request line 1" in sentence
    assert '"' not in sentence and "‮" not in sentence


def test_a_one_line_option_keeps_the_requested_quantity_and_gains_the_amounts(
    engine: RulePolicyEngine, hotel: BuyerProfile, several: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = several((coverage(0, "1500", "1133"),), (check(0, ConstraintKind.PRODUCT_TYPE, "milk"),))

    sentence = p03_sentence(engine, option, hotel, make_context())

    assert sentence == (
        "Only 75.5% of the requested quantity is covered, below the 90% minimum (covered: 1,133 of 1,500 L)."
    )


def test_the_two_new_facts_are_written_to_the_decision_next_to_the_ratio_the_rule_compares(
    engine: RulePolicyEngine, hotel: BuyerProfile, several: Callable[..., OfferOption],
    make_context: Callable[..., PolicyContext],
) -> None:
    option = several((coverage(0, "100", "100"), coverage(1, "10", "0", Unit.KG)))

    fired = next(rule for rule in engine.evaluate(option, hotel, make_context()).fired if rule.rule_id == "P-03")

    assert fired.facts == {
        "option.fill_ratio": 0.0,
        "profile.min_fill_ratio": 0.9,
        "option.least_covered": "the quantity of request line 2",
        "option.coverage_by_line": "0 of 10 kg, request line 2; 100 of 100 L, request line 1",
    }


def test_an_option_without_coverage_reads_the_requested_quantity_and_a_missing_breakdown(
    make_option: Option, hotel: BuyerProfile, make_context: Callable[..., PolicyContext]
) -> None:
    option = make_option().model_copy(update={"coverage": ()})
    scope = OrderScope(option, hotel, make_context(), {})

    assert read_fact("option.least_covered", scope) == "the requested quantity"
    assert isinstance(read_fact("option.coverage_by_line", scope), Missing)
