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

    # Several lines: how many are covered in full and which are not, by name (the menu planner's order, browser
    # walk of 15 Nov 2026). Never "0% of request line 2" for an option that covers a line in full.
    assert sentence == (
        "1 of the 2 items asked for are covered in full; nothing is offered for butter; Harbourside Hotel asks for "
        "at least 90% of every item."
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
        "2 of the 4 items asked for are covered in full; 'oat barista' is covered in part (1 of 5 L); request line "
        "4 is covered in part (4 of 8 L); Harbourside Hotel asks for at least 90% of every item."
    )
    fired = next(rule for rule in engine.evaluate(option, hotel, make_context()).fired if rule.rule_id == "P-03")
    assert fired.facts["option.coverage_by_line"] == (  # every line with its figures stays in the decision's facts
        "1 of 5 L of 'oat barista', request line 2; 4 of 8 L, request line 4; "
        "30 of 30 kg of beef chuck, request line 1; 20 of 20 L of products 469363 and 462775, request line 3"
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

    assert "nothing is offered for 'oat' ) and P-00 says';" in sentence
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
        "option.coverage_said": (
            "1 of the 2 items asked for are covered in full; nothing is offered for request line 2; Harbourside "
            "Hotel asks for at least 90% of every item"
        ),
    }


def test_an_option_without_coverage_reads_the_requested_quantity_and_a_missing_breakdown(
    make_option: Option, hotel: BuyerProfile, make_context: Callable[..., PolicyContext]
) -> None:
    option = make_option().model_copy(update={"coverage": ()})
    scope = OrderScope(option, hotel, make_context(), {})

    assert read_fact("option.least_covered", scope) == "the requested quantity"
    assert isinstance(read_fact("option.coverage_by_line", scope), Missing)


# --- the menu planner's order, as a person reads it (browser walk of 15 Nov 2026) --------------------------------


def test_a_recipe_order_says_how_many_items_are_covered_and_names_the_missing_ones_and_no_late_date(
    engine: RulePolicyEngine, make_option: Option, make_line: Callable[..., OfferLine],
    make_context: Callable[..., PolicyContext],
) -> None:
    """The bakery's chocolate cake for 20: 4 of 7 ingredients covered in full, nothing late. Before: "only 0% of the
    quantity of request line 2 is covered ..." and "the needed-by date 2026-11-16 is not met for this option"."""
    from tta.menus.recipes import shipped_recipes

    bakery = engine.get_profile("bakery-cafe")
    key, products = next(iter(shipped_recipes().named_products.items()))  # an ingredient named by product ids
    types = ("flour", key, "milk", "baking_powder", "sugar", "eggs", "butter")
    covered = (True, True, True, True, False, False, False)
    entries = tuple(coverage(index, "1", "1" if full else "0", Unit.KG) for index, full in enumerate(covered))
    checks = tuple(
        check(index, ConstraintKind.PRODUCT_ID, products[0]) if name == key
        else check(index, ConstraintKind.PRODUCT_TYPE, name)
        for index, name in enumerate(types)
    )
    offered = tuple(
        make_line().model_copy(update={"request_line_index": index}) for index, full in enumerate(covered) if full
    )
    needed_by = ConstraintCheck(
        kind=ConstraintKind.NEEDED_BY, subject="2026-11-16", result=CheckResult.NOT_MET,
        sentence="Nothing is offered for request lines 5, 6 and 7, so the request is not delivered in full.",
    )
    option = make_option(offered, fill_ratio="0", needed_by=None).model_copy(
        update={"coverage": entries, "constraint_checks": (*checks, needed_by)}
    )

    decision = engine.evaluate(option, bakery, make_context())

    said = {rule.rule_id: rule.sentence for rule in decision.fired}
    assert said["P-03"] == (
        "4 of the 7 items asked for are covered in full; nothing is offered for sugar, eggs and butter; Kallio "
        "Bakery asks for every item in full."
    )
    # The check still fails on an empty line (an incomplete dated order never passes); the words say what is so.
    assert said["F-07"] == "Nothing is offered for sugar, eggs and butter; what is offered arrives by Monday 16 Nov."
    assert "is not met" not in decision.sentence and "request line" not in decision.sentence
    assert key.replace("_", " ") in p03_names(option)


def p03_names(option: OfferOption) -> tuple[str, ...]:
    from tta.policy.coverage import line_names

    return tuple(line_names(option).values())


def test_a_product_that_arrives_after_the_date_is_said_once_with_the_day_it_arrives(
    engine: RulePolicyEngine, hotel: BuyerProfile, make_option: Option, make_line: Callable[..., OfferLine],
    make_context: Callable[..., PolicyContext],
) -> None:
    """A later-date option: before, "for X the delivery date is ruled out (F-07)" and then "the needed-by date ...
    is not met for this option (F-07)"."""
    from datetime import date

    from tta.contracts.common import ClaimStatus

    late = make_line("462775", "Milk drink", delivery_date_claim=ClaimStatus.RULED_OUT)
    arrives = late.availability.model_copy(update={"available_date": date(2026, 11, 18)})
    option = make_option((late.model_copy(update={"availability": arrives}),), needed_by=CheckResult.NOT_MET)

    decision = engine.evaluate(option, hotel, make_context())

    assert [rule.sentence for rule in decision.fired] == [
        "The needed-by date 2026-11-16 is not met for this option: Milk drink (462775) arrives on Wednesday 18 Nov."
    ]
    assert decision.sentence.count("F-07") == 1 and "ruled out" not in decision.sentence
