"""A required dietary claim that the product's own allergen data contradicts (review P4, item F4)."""

from __future__ import annotations

from tta.allergens.claims import CONTRADICTED_BY, claim_contradictions, contradiction_sentence
from tta.allergens.codes import is_known_code
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation


def statement(code: str, relation: AllergenRelation = AllergenRelation.CONTAINS) -> AllergenStatement:
    return AllergenStatement(code=code, relation=relation)


def test_every_code_of_the_table_is_a_known_allergen_code() -> None:
    assert all(is_known_code(code) for codes in CONTRADICTED_BY.values() for code in codes)


def test_gluten_free_with_wheat_declared_is_contradicted() -> None:
    found = claim_contradictions(("free_from_gluten ",), (statement("UW"), statement("AM")))

    assert found == (("FREE_FROM_GLUTEN", "UW"),)
    assert contradiction_sentence(found) == (
        "The product carries the claim FREE_FROM_GLUTEN, but its allergen data says it contains wheat (UW). "
        "The data is taken as it stands, so the claim the request requires is not met."
    )


def test_gluten_free_oats_are_not_contradicted() -> None:
    assert claim_contradictions(("FREE_FROM_GLUTEN",), (statement("GO"),)) == ()


def test_may_contain_and_free_from_do_not_contradict_a_claim() -> None:
    statements = (statement("AM", AllergenRelation.MAY_CONTAIN), statement("AE", AllergenRelation.FREE_FROM))

    assert claim_contradictions(("VEGAN",), statements) == ()


def test_a_claim_that_was_not_required_is_not_judged() -> None:
    assert claim_contradictions(("FREE_FROM_PRESERVATIVES",), (statement("AM"),)) == ()


def test_vegan_with_lactose_declared_is_contradicted_and_low_lactose_never_is() -> None:
    assert claim_contradictions(("VEGAN", "LOW_LACTOSE"), (statement("ML"),)) == (("VEGAN", "ML"),)
