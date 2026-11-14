"""`check_exclusions`: the buyer exclusion rule. The table of SPEC section 6 is the specification."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.allergens import check_exclusions
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness
from tta.contracts.errors import InvalidRequest, SupplierUnavailable

Build = Callable[..., tuple[AllergenStatement, ...]]

STRICT = AllergenStrictness.STRICT
DECLARED_ONLY = AllergenStrictness.DECLARED_ONLY
PASS = AllergenOutcome.PASS
REJECT = AllergenOutcome.REJECT
TO_HUMAN = AllergenOutcome.TO_HUMAN

# SPEC section 6, one row per cell: what the product says, the strictness, the outcome.
SPEC_TABLE = [
    ("FREE_FROM", STRICT, PASS),
    ("FREE_FROM", DECLARED_ONLY, PASS),
    ("CONTAINS", STRICT, REJECT),
    ("CONTAINS", DECLARED_ONLY, REJECT),
    ("MAY_CONTAIN", STRICT, TO_HUMAN),
    ("MAY_CONTAIN", DECLARED_ONLY, TO_HUMAN),
    ("UNDECLARED", STRICT, TO_HUMAN),
    ("UNDECLARED", DECLARED_ONLY, PASS),
    (None, STRICT, TO_HUMAN),  # no statement
    (None, DECLARED_ONLY, PASS),  # no statement: passes, shown as unverified
]


@pytest.mark.parametrize(("says", "strictness", "outcome"), SPEC_TABLE)
def test_every_cell_of_the_spec_table(
    statements: Build, says: str | None, strictness: AllergenStrictness, outcome: AllergenOutcome
) -> None:
    product = statements(("AM", says)) if says else statements()

    check = check_exclusions(product, ["AM"], strictness)

    assert check.outcome is outcome
    assert check.strictness is strictness
    assert len(check.findings) == 1
    finding = check.findings[0]
    assert finding.excluded_code == "AM"
    assert finding.outcome is outcome
    assert finding.relation is (AllergenRelation(says) if says else AllergenRelation.NOT_STATED)
    assert finding.matched_code is None
    assert "milk (AM)" in finding.sentence


@pytest.mark.parametrize("strictness", [STRICT, DECLARED_ONLY])
def test_free_from_and_may_contain_for_one_code_count_as_may_contain(
    statements: Build, strictness: AllergenStrictness
) -> None:
    product = statements(("AM", "FREE_FROM"), ("AM", "MAY_CONTAIN"))

    check = check_exclusions(product, ["AM"], strictness)

    assert check.findings[0].relation is AllergenRelation.MAY_CONTAIN
    assert check.outcome is TO_HUMAN


def test_free_from_and_contains_for_one_code_is_rejected(statements: Build) -> None:
    product = statements(("AM", "FREE_FROM"), ("AM", "CONTAINS"))

    assert check_exclusions(product, ["AM"], DECLARED_ONLY).outcome is REJECT


# --- families -------------------------------------------------------------------------------------


def test_gluten_excluded_and_wheat_contained_is_rejected(statements: Build) -> None:
    product = statements(("UW", "CONTAINS"))

    check = check_exclusions(product, ["AW"], STRICT)

    finding = check.findings[0]
    assert check.outcome is REJECT
    assert finding.relation is AllergenRelation.CONTAINS
    assert finding.matched_code == "UW"
    assert "wheat (UW)" in finding.sentence
    assert "cereals containing gluten (AW)" in finding.sentence


@pytest.mark.parametrize("strictness", [STRICT, DECLARED_ONLY])
def test_gluten_free_product_that_declares_oats_goes_to_a_human(
    statements: Build, strictness: AllergenStrictness
) -> None:
    product = statements(("AW", "FREE_FROM"), ("GO", "CONTAINS"))

    check = check_exclusions(product, ["AW"], strictness)

    finding = check.findings[0]
    assert check.outcome is TO_HUMAN
    assert finding.matched_code == "GO"
    assert "oats (GO)" in finding.sentence
    assert "dietitian" in finding.sentence


def test_oats_alone_go_to_a_human_when_gluten_is_excluded(statements: Build) -> None:
    assert check_exclusions(statements(("GO", "CONTAINS")), ["AW"], DECLARED_ONLY).outcome is TO_HUMAN


def test_oats_next_to_a_contained_gluten_cereal_are_still_rejected(statements: Build) -> None:
    product = statements(("AW", "CONTAINS"), ("GO", "CONTAINS"))

    check = check_exclusions(product, ["AW"], STRICT)

    assert check.outcome is REJECT
    assert check.findings[0].matched_code is None


def test_a_member_that_may_be_contained_goes_to_a_human(statements: Build) -> None:
    check = check_exclusions(statements(("SA", "MAY_CONTAIN")), ["AN"], DECLARED_ONLY)

    assert check.outcome is TO_HUMAN
    assert check.findings[0].matched_code == "SA"


@pytest.mark.parametrize("strictness", [STRICT, DECLARED_ONLY])
def test_member_excluded_and_only_the_family_declared_goes_to_a_human(
    statements: Build, strictness: AllergenStrictness
) -> None:
    check = check_exclusions(statements(("AN", "CONTAINS")), ["SA"], strictness)

    finding = check.findings[0]
    assert check.outcome is TO_HUMAN
    assert finding.relation is AllergenRelation.MAY_CONTAIN
    assert finding.matched_code == "AN"
    assert "tree nuts (AN)" in finding.sentence
    assert "almonds (SA)" in finding.sentence


@pytest.mark.parametrize("strictness", [STRICT, DECLARED_ONLY])
@pytest.mark.parametrize(("family", "member"), [("AN", "SA"), ("AM", "ML")])
def test_member_excluded_and_marked_undeclared_under_a_declared_family_goes_to_a_human(
    statements: Build, family: str, member: str, strictness: AllergenStrictness
) -> None:
    product = statements((family, "CONTAINS"), (member, "UNDECLARED"))

    check = check_exclusions(product, [member], strictness)

    finding = check.findings[0]
    assert check.outcome is TO_HUMAN
    assert finding.relation is AllergenRelation.MAY_CONTAIN
    assert finding.matched_code == family
    assert "UNDECLARED" in finding.sentence
    assert "no statement" not in finding.sentence
    assert "dietitian" in finding.sentence
    assert not check.all_explicit


def test_member_marked_undeclared_with_no_declared_family_still_passes_as_unverified(statements: Build) -> None:
    check = check_exclusions(statements(("AN", "FREE_FROM"), ("SA", "UNDECLARED")), ["SA"], DECLARED_ONLY)

    assert check.outcome is PASS
    assert check.findings[0].relation is AllergenRelation.UNDECLARED
    assert check.findings[0].matched_code is None
    assert "unverified" in check.findings[0].sentence


def test_lactose_excluded_and_lactose_free_milk_passes(statements: Build) -> None:
    product = statements(("AM", "CONTAINS"), ("ML", "FREE_FROM"))

    check = check_exclusions(product, ["ML"], STRICT)

    assert check.outcome is PASS
    assert check.findings[0].matched_code is None


def test_milk_excluded_and_lactose_contained_is_rejected(statements: Build) -> None:
    check = check_exclusions(statements(("ML", "CONTAINS")), ["AM"], DECLARED_ONLY)

    assert check.outcome is REJECT
    assert check.findings[0].matched_code == "ML"


# --- no statement and the general statement X99 ---------------------------------------------------


def test_no_statements_at_all_goes_to_a_human_under_strict(statements: Build) -> None:
    check = check_exclusions(statements(), ["AM", "AW"], STRICT)

    assert check.outcome is TO_HUMAN
    assert [finding.outcome for finding in check.findings] == [TO_HUMAN, TO_HUMAN]
    assert all("no statement" in finding.sentence for finding in check.findings)
    assert not check.all_explicit


def test_no_statements_at_all_passes_as_unverified_under_declared_only(statements: Build) -> None:
    check = check_exclusions(statements(), ["AM", "AW"], DECLARED_ONLY)

    assert check.outcome is PASS
    assert all(finding.relation is AllergenRelation.NOT_STATED for finding in check.findings)
    assert all("unverified" in finding.sentence for finding in check.findings)
    assert not check.all_explicit


@pytest.mark.parametrize("x99_relation", ["CONTAINS", "FREE_FROM"])
def test_x99_goes_to_a_human_under_strict_and_the_sentence_says_why(statements: Build, x99_relation: str) -> None:
    check = check_exclusions(statements(("X99", x99_relation)), ["AM"], STRICT)

    finding = check.findings[0]
    assert check.outcome is TO_HUMAN
    assert finding.relation is AllergenRelation.NOT_STATED
    assert "X99" in finding.sentence
    assert "general statement" in finding.sentence
    assert "milk (AM)" in finding.sentence
    assert not check.all_explicit


@pytest.mark.parametrize("x99_relation", ["CONTAINS", "FREE_FROM"])
def test_x99_passes_under_declared_only(statements: Build, x99_relation: str) -> None:
    check = check_exclusions(statements(("X99", x99_relation)), ["AM"], DECLARED_ONLY)

    assert check.outcome is PASS
    assert "X99" in check.findings[0].sentence
    assert "unverified" in check.findings[0].sentence


def test_a_specific_statement_counts_next_to_x99(statements: Build) -> None:
    check = check_exclusions(statements(("X99", "CONTAINS"), ("AM", "CONTAINS")), ["AM"], DECLARED_ONLY)

    assert check.outcome is REJECT
    assert "X99" not in check.findings[0].sentence


# --- the overall result ---------------------------------------------------------------------------


def test_a_soya_drink_free_from_milk_and_gluten_passes_with_explicit_statements(statements: Build) -> None:
    soya_drink = statements(("AY", "CONTAINS"), ("AM", "FREE_FROM"), ("AW", "FREE_FROM"), ("UW", "FREE_FROM"))

    check = check_exclusions(soya_drink, ["AM", "AW"], STRICT)

    assert check.outcome is PASS
    assert check.all_explicit
    assert not check.declares_excluded
    assert [finding.excluded_code for finding in check.findings] == ["AM", "AW"]


def test_the_most_severe_finding_is_the_overall_outcome(statements: Build) -> None:
    product = statements(("AM", "FREE_FROM"), ("AE", "MAY_CONTAIN"), ("AW", "CONTAINS"))

    to_human = check_exclusions(product, ["AM", "AE"], STRICT)
    rejected = check_exclusions(product, ["AM", "AE", "AW"], STRICT)

    assert to_human.outcome is TO_HUMAN
    assert not to_human.declares_excluded
    assert rejected.outcome is REJECT
    assert rejected.declares_excluded
    assert [finding.outcome for finding in rejected.findings] == [PASS, TO_HUMAN, REJECT]


def test_all_explicit_needs_free_from_or_contains_for_every_exclusion(statements: Build) -> None:
    product = statements(("AM", "FREE_FROM"), ("AW", "CONTAINS"), ("AE", "UNDECLARED"))

    assert check_exclusions(product, ["AM", "AW"], STRICT).all_explicit
    assert not check_exclusions(product, ["AM", "AE"], STRICT).all_explicit
    assert not check_exclusions(product, ["AM", "AY"], DECLARED_ONLY).all_explicit


def test_there_is_one_sentence_per_excluded_allergen(statements: Build) -> None:
    check = check_exclusions(statements(("AM", "CONTAINS")), ["AM", "AW", "AE"], STRICT)

    assert len(check.findings) == 3
    assert all(finding.sentence.endswith(".") for finding in check.findings)
    assert len({finding.sentence for finding in check.findings}) == 3


def test_an_exclusion_given_twice_is_checked_once(statements: Build) -> None:
    check = check_exclusions(statements(("AM", "CONTAINS")), ["AM", "AW", "AM"], STRICT)

    assert [finding.excluded_code for finding in check.findings] == ["AM", "AW"]


def test_nothing_excluded_passes_with_no_finding(statements: Build) -> None:
    check = check_exclusions(statements(("AM", "CONTAINS")), [], None)

    assert check.outcome is PASS
    assert check.findings == ()
    assert check.all_explicit
    assert check.strictness is None


# --- bad input ------------------------------------------------------------------------------------


def test_an_exclusion_without_a_strictness_is_an_invalid_request(statements: Build) -> None:
    with pytest.raises(InvalidRequest, match="allergen_strictness"):
        check_exclusions(statements(("AM", "CONTAINS")), ["AM"], None)


def test_an_unknown_excluded_code_is_an_invalid_request(statements: Build) -> None:
    with pytest.raises(InvalidRequest, match="ZZ"):
        check_exclusions(statements(), ["AM", "ZZ"], STRICT)


def test_a_lower_case_code_is_not_guessed(statements: Build) -> None:
    with pytest.raises(InvalidRequest, match="am"):
        check_exclusions(statements(), ["am"], STRICT)


@pytest.mark.parametrize("written", ["am", " AM ", "Am\n"])
@pytest.mark.parametrize("strictness", [STRICT, DECLARED_ONLY])
def test_a_statement_code_is_read_as_the_table_spells_it(
    statements: Build, written: str, strictness: AllergenStrictness
) -> None:
    # Unnormalised, "am" matches nothing and the product would pass under DECLARED_ONLY.
    check = check_exclusions(statements((written, "CONTAINS")), ["AM"], strictness)

    assert check.outcome is REJECT
    assert check.findings[0].relation is AllergenRelation.CONTAINS


@pytest.mark.parametrize("unknown", ["QQ", "MILK", ""])
@pytest.mark.parametrize("strictness", [STRICT, DECLARED_ONLY])
def test_a_statement_with_a_code_outside_the_table_is_refused(
    statements: Build, unknown: str, strictness: AllergenStrictness
) -> None:
    product = statements(("AW", "FREE_FROM"), (unknown, "CONTAINS"))

    with pytest.raises(SupplierUnavailable) as raised:
        check_exclusions(product, ["AM"], strictness)

    assert repr(unknown) in raised.value.detail
    assert "code table" in raised.value.detail


def test_statement_codes_are_checked_even_when_nothing_is_excluded(statements: Build) -> None:
    with pytest.raises(SupplierUnavailable):
        check_exclusions(statements(("QQ", "CONTAINS")), [], None)


def test_x99_cannot_be_excluded(statements: Build) -> None:
    with pytest.raises(InvalidRequest, match="X99"):
        check_exclusions(statements(), ["X99"], STRICT)


def test_the_inputs_are_not_changed(statements: Build) -> None:
    product = statements(("AW", "FREE_FROM"), ("GO", "CONTAINS"))
    excluded = ["AW", "AM"]

    check_exclusions(product, excluded, STRICT)

    assert product == statements(("AW", "FREE_FROM"), ("GO", "CONTAINS"))
    assert excluded == ["AW", "AM"]
