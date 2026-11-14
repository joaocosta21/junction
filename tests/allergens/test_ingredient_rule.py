"""`check_exclusions` with the ingredient list: the list counts as a statement (SPEC section 6).

When the list names an excluded allergen that the declaration states FREE_FROM, marks UNDECLARED or does
not state, the finding becomes MAY_CONTAIN and goes to a dietitian, with a sentence quoting both. A declared
CONTAINS stays a rejection; a declared MAY_CONTAIN is already a dietitian's.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.allergens import check_exclusions
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness

STRICT = AllergenStrictness.STRICT
DECLARED_ONLY = AllergenStrictness.DECLARED_ONLY
PASS, TO_HUMAN, REJECT = AllergenOutcome.PASS, AllergenOutcome.TO_HUMAN, AllergenOutcome.REJECT

ALMOND_DRINK = (  # 465793, quoted from the catalog
    "Water, ALMOND (2.5%), Sugar, Fructose, Sea salt. MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS). "
    "Dairy-free and gluten-free. Low sugar."
)
Statements = Callable[..., tuple[AllergenStatement, ...]]


@pytest.mark.parametrize("strictness", list(AllergenStrictness))
def test_the_almond_drink_declared_free_from_tree_nuts_goes_to_a_dietitian(
    statements: Statements, strictness: AllergenStrictness
) -> None:
    declared = statements(("AN", "FREE_FROM"), ("AM", "FREE_FROM"), ("AW", "FREE_FROM"))

    check = check_exclusions(declared, ["AN"], strictness, ingredients=ALMOND_DRINK)

    assert check.outcome is TO_HUMAN
    assert not check.all_explicit
    (finding,) = check.findings
    assert finding.relation is AllergenRelation.MAY_CONTAIN
    assert finding.matched_code == "SA"
    assert finding.sentence == (
        'The ingredient list names "ALMOND" and says "MAY CONTAIN REMAINS FROM NUTS (NOT PEANUTS)", while the '
        "product states it is free from tree nuts (AN): a dietitian must decide."
    )


def test_without_the_ingredient_list_the_declaration_alone_decides(statements: Statements) -> None:
    declared = statements(("AN", "FREE_FROM"))

    assert check_exclusions(declared, ["AN"], STRICT).outcome is PASS
    assert check_exclusions(declared, ["AN"], STRICT, ingredients=None) == check_exclusions(declared, ["AN"], STRICT)
    assert check_exclusions(declared, ["AN"], STRICT, ingredients="Water, oats, salt.").outcome is PASS


def test_a_declared_contains_stays_a_rejection(statements: Statements) -> None:
    check = check_exclusions(statements(("AM", "CONTAINS")), ["AM"], STRICT, ingredients="Skimmed MILK")

    assert check.outcome is REJECT
    assert check.findings[0].relation is AllergenRelation.CONTAINS
    assert "ingredient list" not in check.findings[0].sentence


def test_a_declared_may_contain_keeps_its_own_finding(statements: Statements) -> None:
    declared = statements(("AE", "MAY_CONTAIN"))
    without_text = check_exclusions(declared, ["AE"], DECLARED_ONLY)

    assert check_exclusions(declared, ["AE"], DECLARED_ONLY, ingredients="EGG yolk") == without_text


def test_no_statement_and_a_named_allergen_goes_to_a_dietitian_even_under_declared_only(
    statements: Statements,
) -> None:
    check = check_exclusions((), ["AW"], DECLARED_ONLY, ingredients="WHEAT flour, water, yeast, salt.")

    assert check.outcome is TO_HUMAN
    assert check.findings[0].sentence == (
        'The ingredient list names "WHEAT", while the product makes no statement about cereals containing '
        "gluten (AW): a dietitian must decide."
    )


def test_undeclared_and_a_may_contain_phrase_goes_to_a_dietitian(statements: Statements) -> None:
    check = check_exclusions(
        statements(("AM", "UNDECLARED")), ["AM"], DECLARED_ONLY, ingredients="Sugar. May contain traces of milk."
    )

    assert check.outcome is TO_HUMAN
    assert check.findings[0].sentence == (
        'The ingredient list says "May contain traces of milk", while the product marks milk (AM) as '
        "UNDECLARED: a dietitian must decide."
    )


def test_the_general_statement_x99_is_named_in_the_sentence(statements: Statements) -> None:
    check = check_exclusions(statements(("X99", "FREE_FROM")), ["AM"], DECLARED_ONLY, ingredients="MILK powder")

    assert check.outcome is TO_HUMAN
    assert "only the general statement X99" in check.findings[0].sentence


def test_a_free_from_wording_in_the_list_changes_nothing(statements: Statements) -> None:
    declared = statements(("AM", "FREE_FROM"), ("AW", "FREE_FROM"))

    check = check_exclusions(declared, ["AM", "AW"], STRICT, ingredients="Dairy-free and gluten-free. Free from milk.")

    assert check.outcome is PASS
    assert check.all_explicit


def test_only_the_excluded_allergen_and_its_family_members_count(statements: Statements) -> None:
    declared = statements(("AW", "FREE_FROM"), ("AM", "FREE_FROM"))

    # Oats are a gluten cereal: a list naming oats does not rule gluten out (the oats rule of SPEC section 6).
    oats = check_exclusions(declared, ["AW"], STRICT, ingredients="gluten-free OATS (Finland), water")
    soya = check_exclusions(declared, ["AW", "AM"], STRICT, ingredients="SOYA beans, water")

    assert oats.outcome is TO_HUMAN and oats.findings[0].matched_code == "GO"
    assert soya.outcome is PASS


def test_a_family_word_counts_for_a_member_unless_the_member_is_stated_free_from(statements: Statements) -> None:
    # Lactose-free milk declares milk and states lactose FREE_FROM: "MILK" in its list is no news about lactose.
    lactose_free = check_exclusions(
        statements(("AM", "CONTAINS"), ("ML", "FREE_FROM")), ["ML"], STRICT, ingredients="lactose-free MILK"
    )
    # Nothing is stated about almonds, and the list says it may contain nuts.
    nuts = check_exclusions((), ["SA"], DECLARED_ONLY, ingredients="Sugar. May contain nuts.")

    assert lactose_free.outcome is PASS
    assert nuts.outcome is TO_HUMAN and nuts.findings[0].matched_code == "AN"


def test_a_long_phrase_from_the_list_is_quoted_short_and_on_one_line(statements: Statements) -> None:
    text = "Sugar. May contain traces of milk,\n" + "and of many other things " * 20 + "."

    sentence = check_exclusions(statements(("AM", "FREE_FROM")), ["AM"], STRICT, ingredients=text).findings[0].sentence

    assert "\n" not in sentence
    assert '"May contain traces of milk, and of many other' in sentence
    assert len(sentence) < 240
