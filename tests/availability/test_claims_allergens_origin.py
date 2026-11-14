"""Verification status per claim (SPEC section 4): allergens and origin."""

from __future__ import annotations

import pytest

from tta.contracts.allergen import AllergenCheck, AllergenFinding
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    ClaimName,
    ClaimStatus,
)


def _finding(code: str, relation: AllergenRelation, outcome: AllergenOutcome) -> AllergenFinding:
    return AllergenFinding(excluded_code=code, relation=relation, outcome=outcome, sentence="(written by the rule)")


def _allergen_check(
    outcome: AllergenOutcome, all_explicit: bool, *findings: AllergenFinding,
    strictness: AllergenStrictness = AllergenStrictness.STRICT,
) -> AllergenCheck:
    return AllergenCheck(outcome=outcome, strictness=strictness, findings=findings, all_explicit=all_explicit)


# --- allergens ---------------------------------------------------------------------------------


def test_allergens_are_confirmed_when_every_excluded_allergen_has_an_explicit_statement(build_line,
                                                                                       claim_of) -> None:
    allergens = _allergen_check(
        AllergenOutcome.PASS, True,
        _finding("AM", AllergenRelation.FREE_FROM, AllergenOutcome.PASS),
        _finding("AW", AllergenRelation.FREE_FROM, AllergenOutcome.PASS),
    )

    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=allergens)

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "The product states that it is free from every excluded allergen (AM, AW)."


def test_allergens_are_confirmed_when_the_buyer_excluded_nothing(build_line, claim_of) -> None:
    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=None)

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "The buyer excluded no allergen, so there is nothing to check."


def test_allergens_are_confirmed_for_a_passing_check_with_no_finding(build_line, claim_of) -> None:
    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=_allergen_check(AllergenOutcome.PASS, True))

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "The buyer excluded no allergen, so there is nothing to check."


def test_allergens_are_unknown_for_a_check_sent_to_a_human_with_no_finding(build_line, claim_of) -> None:
    allergens = _allergen_check(AllergenOutcome.TO_HUMAN, False)

    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=allergens)

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == "The product data does not confirm that it is free from an excluded allergen."


def test_allergens_are_ruled_out_by_a_rejecting_check_even_with_no_finding(build_line, claim_of) -> None:
    check = claim_of(ClaimName.ALLERGENS, build_line(),
                     allergen_outcome=_allergen_check(AllergenOutcome.REJECT, False))

    assert check.status is ClaimStatus.RULED_OUT
    assert check.sentence == "The product declares that it contains an excluded allergen."


@pytest.mark.parametrize(
    ("relation", "outcome", "strictness"),
    [
        (AllergenRelation.MAY_CONTAIN, AllergenOutcome.TO_HUMAN, AllergenStrictness.STRICT),
        (AllergenRelation.MAY_CONTAIN, AllergenOutcome.TO_HUMAN, AllergenStrictness.DECLARED_ONLY),
        (AllergenRelation.UNDECLARED, AllergenOutcome.TO_HUMAN, AllergenStrictness.STRICT),
        (AllergenRelation.NOT_STATED, AllergenOutcome.TO_HUMAN, AllergenStrictness.STRICT),
        (AllergenRelation.UNDECLARED, AllergenOutcome.PASS, AllergenStrictness.DECLARED_ONLY),
        (AllergenRelation.NOT_STATED, AllergenOutcome.PASS, AllergenStrictness.DECLARED_ONLY),
    ],
)
def test_allergens_are_unknown_for_may_contain_undeclared_or_no_statement(
    build_line, claim_of, relation: AllergenRelation, outcome: AllergenOutcome, strictness: AllergenStrictness
) -> None:
    allergens = _allergen_check(
        outcome, False,
        _finding("AM", AllergenRelation.FREE_FROM, AllergenOutcome.PASS),
        _finding("AW", relation, outcome),
        strictness=strictness,
    )

    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=allergens)

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == "The product data does not confirm that it is free from an excluded allergen (AW)."


def test_allergens_are_unknown_when_the_rule_sends_explicit_statements_to_a_human(build_line, claim_of) -> None:
    # "No gluten" and a product that declares oats: to a human, whatever else it states (SPEC section 6).
    allergens = _allergen_check(
        AllergenOutcome.TO_HUMAN, True, _finding("AW", AllergenRelation.CONTAINS, AllergenOutcome.TO_HUMAN)
    )

    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=allergens)

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == "The product data does not confirm that it is free from an excluded allergen (AW)."


def test_allergens_are_ruled_out_by_one_rejected_finding_whatever_the_overall_outcome(build_line, claim_of) -> None:
    allergens = _allergen_check(
        AllergenOutcome.TO_HUMAN, False, _finding("AM", AllergenRelation.CONTAINS, AllergenOutcome.REJECT)
    )

    assert claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=allergens).status is ClaimStatus.RULED_OUT


def test_allergens_are_ruled_out_when_an_excluded_allergen_is_declared(build_line, claim_of) -> None:
    allergens = _allergen_check(
        AllergenOutcome.REJECT, False,
        _finding("AM", AllergenRelation.CONTAINS, AllergenOutcome.REJECT),
        _finding("AW", AllergenRelation.NOT_STATED, AllergenOutcome.TO_HUMAN),
    )

    check = claim_of(ClaimName.ALLERGENS, build_line(), allergen_outcome=allergens)

    assert check.status is ClaimStatus.RULED_OUT
    assert check.sentence == "The product declares that it contains an excluded allergen (AM)."


# --- origin ------------------------------------------------------------------------------------


def test_origin_is_confirmed_when_the_product_file_states_it(build_line, build_product, claim_of) -> None:
    check = claim_of(ClaimName.ORIGIN, build_line(), product=build_product(country_of_origin="fi"))

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "The product file states the country of origin: FI."


def test_origin_is_confirmed_from_the_numeric_list_when_that_is_all_the_file_has(build_line, build_product,
                                                                                claim_of) -> None:
    product = build_product(country_of_origin="zy", countries_of_origin=("246", "752"))

    check = claim_of(ClaimName.ORIGIN, build_line(), product=product)

    assert check.status is ClaimStatus.CONFIRMED
    assert check.sentence == "The product file states the country of origin by ISO 3166-1 numeric code: 246, 752."


@pytest.mark.parametrize("code", [None, "zy", "xs", "zz", "ZZ"])
def test_origin_is_unknown_when_absent_or_a_placeholder(build_line, build_product, claim_of,
                                                        code: str | None) -> None:
    check = claim_of(ClaimName.ORIGIN, build_line(), product=build_product(country_of_origin=code))

    assert check.status is ClaimStatus.UNKNOWN
    assert check.sentence == "The product file does not state a country of origin."
