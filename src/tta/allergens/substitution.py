"""The substitution rule (SPEC section 6): a substitute must not add a declared allergen, and must
not raise one from MAY_CONTAIN to CONTAINS.

It holds for every buyer, with or without exclusions. Codes are compared one by one: a product
that declares only oats (GO) does not declare the gluten cereals (AW), which is what separates
`473609` from its listed substitutes `471881` and `464320` (SPEC section 13, scenario 3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from tta.allergens.codes import GENERAL_STATEMENT_CODE, describe
from tta.allergens.statements import DECLARING_RELATIONS, least_safe
from tta.contracts.allergen import AllergenStatement, SubstituteAllergenCheck
from tta.contracts.common import AllergenRelation

_LEVEL = {AllergenRelation.CONTAINS: "contains", AllergenRelation.MAY_CONTAIN: "may contain"}
_NOTHING_ADDED = (
    "The substitute declares no allergen that the original does not declare, "
    "and raises none from may contain to contains."
)


def check_substitute(
    original: Sequence[AllergenStatement], substitute: Sequence[AllergenStatement]
) -> SubstituteAllergenCheck:
    """Pass or fail, with what the substitute declares beyond the original.

    `added` holds, in code order, each code the original does not declare and each code raised from
    MAY_CONTAIN to CONTAINS, with the substitute's level.
    """
    original_levels = _declared_levels(original)
    substitute_levels = _declared_levels(substitute)
    new = [code for code in sorted(substitute_levels) if code not in original_levels]
    raised = [
        code
        for code in sorted(substitute_levels)
        if substitute_levels[code] is AllergenRelation.CONTAINS
        and original_levels.get(code) is AllergenRelation.MAY_CONTAIN
    ]
    if not new and not raised:
        return SubstituteAllergenCheck(passes=True, sentence=_NOTHING_ADDED)
    added = tuple(
        AllergenStatement(code=code, relation=substitute_levels[code]) for code in sorted((*new, *raised))
    )
    return SubstituteAllergenCheck(passes=False, added=added, sentence=_fail_sentence(substitute_levels, new, raised))


def _declared_levels(statements: Sequence[AllergenStatement]) -> Mapping[str, AllergenRelation]:
    """Each declared code with its least safe level, CONTAINS or MAY_CONTAIN.

    X99 names no allergen, so it is never one of them.
    """
    declared = [
        statement
        for statement in statements
        if statement.relation in DECLARING_RELATIONS and statement.code != GENERAL_STATEMENT_CODE
    ]
    return {
        code: least_safe(statement.relation for statement in declared if statement.code == code)
        for code in {statement.code for statement in declared}
    }


def _fail_sentence(levels: Mapping[str, AllergenRelation], new: Sequence[str], raised: Sequence[str]) -> str:
    parts: list[str] = []
    if new:
        names = ", ".join(describe(code, _LEVEL[levels[code]]) for code in new)
        parts.append(f"adds {len(new)} {_noun(new)} that the original does not declare: {names}.")
    if raised:
        names = ", ".join(describe(code) for code in raised)
        parts.append(f"raises {len(raised)} {_noun(raised)} from may contain to contains: {names}.")
    return "The substitute " + " It ".join(parts)


def _noun(codes: Sequence[str]) -> str:
    return "allergen" if len(codes) == 1 else "allergens"
