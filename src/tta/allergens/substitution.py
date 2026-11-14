"""The substitution rule (SPEC section 6): a substitute must not add a declared allergen.

It holds for every buyer, with or without exclusions. Codes are compared one by one: a product
that declares only oats (GO) does not declare the gluten cereals (AW), which is what separates
`473609` from its listed substitutes `471881` and `464320` (SPEC section 13, scenario 3).
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.allergens.codes import GENERAL_STATEMENT_CODE, describe
from tta.allergens.statements import DECLARING_RELATIONS, least_safe
from tta.contracts.allergen import AllergenStatement, SubstituteAllergenCheck
from tta.contracts.common import AllergenRelation

_LEVEL = {AllergenRelation.CONTAINS: "contains", AllergenRelation.MAY_CONTAIN: "may contain"}
_NOTHING_ADDED = "The substitute declares no allergen that the original does not declare."


def check_substitute(
    original: Sequence[AllergenStatement], substitute: Sequence[AllergenStatement]
) -> SubstituteAllergenCheck:
    """Pass or fail, with the allergens (CONTAINS or MAY_CONTAIN) the substitute adds."""
    declared_by_original = _declared_codes(original)
    added_codes = sorted(_declared_codes(substitute) - declared_by_original)
    added = tuple(
        AllergenStatement(code=code, relation=_declared_relation(substitute, code)) for code in added_codes
    )
    if not added:
        return SubstituteAllergenCheck(passes=True, sentence=_NOTHING_ADDED)
    return SubstituteAllergenCheck(passes=False, added=added, sentence=_fail_sentence(added))


def _declared_codes(statements: Sequence[AllergenStatement]) -> frozenset[str]:
    """Codes declared as CONTAINS or MAY_CONTAIN. X99 names no allergen, so it is never one of them."""
    return frozenset(
        statement.code
        for statement in statements
        if statement.relation in DECLARING_RELATIONS and statement.code != GENERAL_STATEMENT_CODE
    )


def _declared_relation(statements: Sequence[AllergenStatement], code: str) -> AllergenRelation:
    return least_safe(
        statement.relation
        for statement in statements
        if statement.code == code and statement.relation in DECLARING_RELATIONS
    )


def _fail_sentence(added: Sequence[AllergenStatement]) -> str:
    noun = "allergen" if len(added) == 1 else "allergens"
    names = ", ".join(describe(statement.code, _LEVEL[statement.relation]) for statement in added)
    return f"The substitute adds {len(added)} {noun} that the original does not declare: {names}."
