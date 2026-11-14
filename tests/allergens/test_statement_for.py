"""`statement_for`: what a product says about one allergen code, families included."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.allergens import statement_for
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation

Build = Callable[..., tuple[AllergenStatement, ...]]

FREE_FROM = AllergenRelation.FREE_FROM
CONTAINS = AllergenRelation.CONTAINS
MAY_CONTAIN = AllergenRelation.MAY_CONTAIN
UNDECLARED = AllergenRelation.UNDECLARED
NOT_STATED = AllergenRelation.NOT_STATED


@pytest.mark.parametrize("relation", [FREE_FROM, CONTAINS, MAY_CONTAIN, UNDECLARED])
def test_a_direct_statement_is_returned_as_it_is(statements: Build, relation: AllergenRelation) -> None:
    product = statements(("AM", relation.value), ("AE", "FREE_FROM"))

    assert statement_for(product, "AM") is relation


def test_no_statements_at_all_is_not_stated(statements: Build) -> None:
    assert statement_for(statements(), "AM") is NOT_STATED


def test_statements_about_other_allergens_are_not_a_statement(statements: Build) -> None:
    product = statements(("AE", "CONTAINS"), ("AY", "FREE_FROM"))

    assert statement_for(product, "AM") is NOT_STATED


@pytest.mark.parametrize(
    ("first", "second", "least_safe"),
    [
        ("FREE_FROM", "MAY_CONTAIN", MAY_CONTAIN),
        ("FREE_FROM", "CONTAINS", CONTAINS),
        ("MAY_CONTAIN", "CONTAINS", CONTAINS),
        ("FREE_FROM", "UNDECLARED", UNDECLARED),
        ("UNDECLARED", "MAY_CONTAIN", MAY_CONTAIN),
    ],
)
def test_on_conflicting_statements_the_least_safe_counts(
    statements: Build, first: str, second: str, least_safe: AllergenRelation
) -> None:
    assert statement_for(statements(("AM", first), ("AM", second)), "AM") is least_safe
    assert statement_for(statements(("AM", second), ("AM", first)), "AM") is least_safe


def test_a_relation_of_not_stated_is_no_statement(statements: Build) -> None:
    product = statements(("AM", "NOT_STATED"), ("AM", "FREE_FROM"))

    assert statement_for(product, "AM") is FREE_FROM


# --- a family code asked, a member stated ---------------------------------------------------------


@pytest.mark.parametrize(
    ("family", "member"),
    [("AW", "UW"), ("AW", "GB"), ("AW", "NR"), ("AW", "GS"), ("AW", "GK"), ("AN", "SA"), ("AM", "ML"), ("AF", "ABD")],
)
def test_a_member_that_is_contained_means_the_family_is_contained(
    statements: Build, family: str, member: str
) -> None:
    assert statement_for(statements((member, "CONTAINS")), family) is CONTAINS


def test_a_member_that_may_be_contained_means_the_family_may_be_contained(statements: Build) -> None:
    assert statement_for(statements(("SH", "MAY_CONTAIN")), "AN") is MAY_CONTAIN


def test_a_member_stated_free_from_says_nothing_about_the_family(statements: Build) -> None:
    assert statement_for(statements(("UW", "FREE_FROM")), "AW") is NOT_STATED


def test_a_member_stated_undeclared_says_nothing_about_the_family(statements: Build) -> None:
    assert statement_for(statements(("UW", "UNDECLARED")), "AW") is NOT_STATED


def test_family_free_from_and_member_contained_conflict_towards_contained(statements: Build) -> None:
    product = statements(("AW", "FREE_FROM"), ("UW", "CONTAINS"))

    assert statement_for(product, "AW") is CONTAINS


def test_a_code_outside_the_family_does_not_count(statements: Build) -> None:
    assert statement_for(statements(("NM", "CONTAINS")), "AW") is NOT_STATED


# --- oats under the gluten cereals ----------------------------------------------------------------


def test_declared_oats_alone_count_as_may_contain_for_gluten_cereals(statements: Build) -> None:
    assert statement_for(statements(("GO", "CONTAINS")), "AW") is MAY_CONTAIN
    assert statement_for(statements(("GO", "MAY_CONTAIN")), "AW") is MAY_CONTAIN


def test_declared_oats_override_a_free_from_gluten_cereals(statements: Build) -> None:
    product = statements(("AW", "FREE_FROM"), ("GO", "CONTAINS"))

    assert statement_for(product, "AW") is MAY_CONTAIN


def test_declared_oats_do_not_soften_a_contained_gluten_cereal(statements: Build) -> None:
    assert statement_for(statements(("AW", "CONTAINS"), ("GO", "CONTAINS")), "AW") is CONTAINS
    assert statement_for(statements(("UW", "CONTAINS"), ("GO", "CONTAINS")), "AW") is CONTAINS


def test_oats_stated_free_from_say_nothing_about_gluten_cereals(statements: Build) -> None:
    assert statement_for(statements(("GO", "FREE_FROM")), "AW") is NOT_STATED


# --- a member asked, the family stated ------------------------------------------------------------


@pytest.mark.parametrize("family_relation", ["CONTAINS", "MAY_CONTAIN"])
def test_a_declared_family_means_an_unnamed_member_may_be_contained(
    statements: Build, family_relation: str
) -> None:
    assert statement_for(statements(("AN", family_relation)), "SA") is MAY_CONTAIN


@pytest.mark.parametrize("family_relation", ["FREE_FROM", "UNDECLARED"])
def test_a_family_free_from_or_undeclared_is_not_a_statement_about_a_member(
    statements: Build, family_relation: str
) -> None:
    # 178 catalog products state a family FREE_FROM and still declare one of its members.
    assert statement_for(statements(("AW", family_relation)), "UW") is NOT_STATED


def test_a_direct_statement_on_the_member_wins_over_the_family(statements: Build) -> None:
    lactose_free_milk = statements(("AM", "CONTAINS"), ("ML", "FREE_FROM"))
    rye_bread = statements(("AW", "CONTAINS"), ("NR", "CONTAINS"), ("UW", "FREE_FROM"))

    assert statement_for(lactose_free_milk, "ML") is FREE_FROM
    assert statement_for(rye_bread, "UW") is FREE_FROM


@pytest.mark.parametrize(("family", "member"), [("AN", "SA"), ("AM", "ML")])
@pytest.mark.parametrize("family_relation", ["CONTAINS", "MAY_CONTAIN"])
def test_a_member_marked_undeclared_does_not_hide_its_declared_family(
    statements: Build, family: str, member: str, family_relation: str
) -> None:
    # Least safe wins: UNDECLARED on the member is not a free-from statement, so the declared family counts.
    product = statements((family, family_relation), (member, "UNDECLARED"))

    assert statement_for(product, member) is MAY_CONTAIN
    assert statement_for(tuple(reversed(product)), member) is MAY_CONTAIN


def test_a_member_stated_free_from_and_undeclared_does_not_hide_its_declared_family(statements: Build) -> None:
    product = statements(("AM", "CONTAINS"), ("ML", "FREE_FROM"), ("ML", "UNDECLARED"))

    assert statement_for(product, "ML") is MAY_CONTAIN


@pytest.mark.parametrize("family_relation", ["FREE_FROM", "UNDECLARED", None])
def test_a_member_marked_undeclared_stays_undeclared_when_its_family_is_not_declared(
    statements: Build, family_relation: str | None
) -> None:
    family = (("AN", family_relation),) if family_relation else ()

    assert statement_for(statements(*family, ("SA", "UNDECLARED")), "SA") is UNDECLARED


def test_a_declared_member_keeps_its_own_level_next_to_its_family(statements: Build) -> None:
    assert statement_for(statements(("AN", "MAY_CONTAIN"), ("SA", "CONTAINS")), "SA") is CONTAINS
    assert statement_for(statements(("AN", "CONTAINS"), ("SA", "MAY_CONTAIN")), "SA") is MAY_CONTAIN


def test_a_sibling_says_nothing_about_another_member(statements: Build) -> None:
    assert statement_for(statements(("SH", "CONTAINS")), "SA") is NOT_STATED


# --- the general statement X99 --------------------------------------------------------------------


@pytest.mark.parametrize("relation", ["CONTAINS", "FREE_FROM"])
def test_x99_is_not_a_statement_about_one_allergen(statements: Build, relation: str) -> None:
    assert statement_for(statements(("X99", relation)), "AM") is NOT_STATED


def test_asked_about_x99_itself_there_is_no_allergen_to_answer_for(statements: Build) -> None:
    assert statement_for(statements(("X99", "CONTAINS")), "X99") is NOT_STATED


def test_a_specific_statement_counts_next_to_x99(statements: Build) -> None:
    assert statement_for(statements(("X99", "CONTAINS"), ("NW", "CONTAINS")), "NW") is CONTAINS


def test_the_statements_are_not_changed(statements: Build) -> None:
    product = statements(("AW", "FREE_FROM"), ("GO", "CONTAINS"))
    before = tuple(product)

    statement_for(product, "AW")

    assert product == before
