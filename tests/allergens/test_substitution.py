"""`check_substitute`: a substitute must not declare an allergen that the original does not declare."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.allergens import check_substitute
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation

Build = Callable[..., tuple[AllergenStatement, ...]]


def _added_codes(check_added: tuple[AllergenStatement, ...]) -> list[str]:
    return [statement.code for statement in check_added]


def test_a_substitute_that_adds_may_contain_fails_and_names_the_code(statements: Build) -> None:
    original = statements(("AM", "CONTAINS"))
    substitute = statements(("AM", "CONTAINS"), ("AN", "MAY_CONTAIN"))

    check = check_substitute(original, substitute)

    assert not check.passes
    assert check.added == (AllergenStatement(code="AN", relation=AllergenRelation.MAY_CONTAIN),)
    assert "tree nuts (AN, may contain)" in check.sentence
    assert "1 allergen" in check.sentence


def test_a_substitute_that_adds_contains_fails(statements: Build) -> None:
    check = check_substitute(statements(("AM", "CONTAINS")), statements(("AM", "CONTAINS"), ("AE", "CONTAINS")))

    assert not check.passes
    assert _added_codes(check.added) == ["AE"]
    assert "eggs (AE, contains)" in check.sentence


def test_the_same_declarations_pass(statements: Build) -> None:
    original = statements(("AM", "CONTAINS"), ("AY", "MAY_CONTAIN"))

    check = check_substitute(original, statements(("AY", "MAY_CONTAIN"), ("AM", "CONTAINS")))

    assert check.passes
    assert check.added == ()
    assert check.sentence.endswith(".")


def test_a_substitute_that_declares_less_passes(statements: Build) -> None:
    check = check_substitute(statements(("AM", "CONTAINS"), ("AE", "CONTAINS")), statements(("AM", "CONTAINS")))

    assert check.passes


@pytest.mark.parametrize("relation", ["FREE_FROM", "UNDECLARED"])
def test_free_from_and_undeclared_are_not_declarations(statements: Build, relation: str) -> None:
    check = check_substitute(statements(("AM", "CONTAINS")), statements(("AM", "CONTAINS"), ("AN", relation)))

    assert check.passes


def test_an_original_stated_free_from_does_not_cover_a_declaring_substitute(statements: Build) -> None:
    check = check_substitute(statements(("AM", "FREE_FROM")), statements(("AM", "CONTAINS")))

    assert not check.passes
    assert _added_codes(check.added) == ["AM"]


def test_an_original_with_no_statement_and_a_declaring_substitute_fails(statements: Build) -> None:
    check = check_substitute(statements(), statements(("AW", "CONTAINS")))

    assert not check.passes
    assert _added_codes(check.added) == ["AW"]


def test_two_products_with_no_statement_pass(statements: Build) -> None:
    assert check_substitute(statements(), statements()).passes


def test_oat_drink_substitute_that_also_declares_gluten_cereals_adds_aw(statements: Build) -> None:
    # Scenario 3: 473609 declares only oats; 471881 and 464320 declare AW as well.
    original = statements(("GO", "CONTAINS"))
    substitute = statements(("AW", "CONTAINS"), ("GO", "CONTAINS"))

    check = check_substitute(original, substitute)

    assert not check.passes
    assert check.added == (AllergenStatement(code="AW", relation=AllergenRelation.CONTAINS),)
    assert "cereals containing gluten (AW, contains)" in check.sentence


def test_codes_are_compared_one_by_one_without_families(statements: Build) -> None:
    check = check_substitute(statements(("AW", "CONTAINS")), statements(("AW", "CONTAINS"), ("UW", "CONTAINS")))

    assert not check.passes
    assert _added_codes(check.added) == ["UW"]


def test_the_rule_is_about_codes_not_about_the_level(statements: Build) -> None:
    # SPEC section 6 names the allergen, not the level: MAY_CONTAIN on the original, CONTAINS on the substitute.
    check = check_substitute(statements(("AN", "MAY_CONTAIN")), statements(("AN", "CONTAINS")))

    assert check.passes


def test_x99_on_the_substitute_is_not_an_added_allergen(statements: Build) -> None:
    check = check_substitute(statements(), statements(("X99", "CONTAINS")))

    assert check.passes
    assert check.added == ()


def test_x99_on_the_original_does_not_cover_a_declared_allergen(statements: Build) -> None:
    check = check_substitute(statements(("X99", "CONTAINS")), statements(("AM", "CONTAINS")))

    assert not check.passes
    assert _added_codes(check.added) == ["AM"]


def test_an_added_code_is_listed_once_with_its_least_safe_relation(statements: Build) -> None:
    substitute = statements(("AN", "MAY_CONTAIN"), ("AN", "CONTAINS"))

    check = check_substitute(statements(), substitute)

    assert check.added == (AllergenStatement(code="AN", relation=AllergenRelation.CONTAINS),)


def test_several_added_allergens_are_counted_and_listed_in_code_order(statements: Build) -> None:
    substitute = statements(("GB", "MAY_CONTAIN"), ("AE", "CONTAINS"), ("AM", "CONTAINS"))

    check = check_substitute(statements(("AM", "CONTAINS")), substitute)

    assert _added_codes(check.added) == ["AE", "GB"]
    assert "2 allergens" in check.sentence
    assert "eggs (AE, contains)" in check.sentence
    assert "barley (GB, may contain)" in check.sentence


def test_an_unknown_code_on_the_substitute_is_still_an_added_allergen(statements: Build) -> None:
    check = check_substitute(statements(), statements(("ZZ", "CONTAINS")))

    assert not check.passes
    assert "ZZ" in check.sentence


def test_the_inputs_are_not_changed(statements: Build) -> None:
    original = statements(("GO", "CONTAINS"))
    substitute = statements(("AW", "CONTAINS"), ("GO", "CONTAINS"))

    check_substitute(original, substitute)

    assert original == statements(("GO", "CONTAINS"))
    assert substitute == statements(("AW", "CONTAINS"), ("GO", "CONTAINS"))
