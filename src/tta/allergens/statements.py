"""What a product says about one allergen code, with the code families taken into account.

How the family is read (SPEC section 6; the choices are listed in the T03 hand-back):
- A statement on the code itself always counts.
- Asked about a family code: a member that is declared (CONTAINS or MAY_CONTAIN) is a declaration
  of the family. A member stated FREE_FROM or UNDECLARED says nothing about the family as a whole.
- Declared oats (GO) count as MAY_CONTAIN for the gluten cereals (AW): gluten-free oats exist, so
  the product is neither rejected nor passed on that statement alone.
- Asked about a member: a declared family means the member may be contained, unless the member
  itself is stated FREE_FROM (lactose-free milk declares milk and states lactose FREE_FROM). A member
  marked UNDECLARED, or not stated at all, does not outrank its declared family. A family stated
  FREE_FROM or UNDECLARED is not read as a statement about the member.
- On conflicting statements the least safe one counts.
- X99 is a general statement and never a statement about one allergen.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from tta.allergens.codes import (
    GENERAL_STATEMENT_CODE,
    GLUTEN_CEREALS_CODE,
    OATS_CODE,
    members_of,
    parent_of,
)
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation

# CONTAINS and MAY_CONTAIN are the two relations that declare an allergen (SPEC section 6).
DECLARING_RELATIONS = frozenset({AllergenRelation.CONTAINS, AllergenRelation.MAY_CONTAIN})

# Least safe first wins. NOT_STATED is absent on purpose: it is the answer when nothing counts.
_UNSAFETY = {
    AllergenRelation.FREE_FROM: 0,
    AllergenRelation.UNDECLARED: 1,
    AllergenRelation.MAY_CONTAIN: 2,
    AllergenRelation.CONTAINS: 3,
}


class Basis(StrEnum):
    """Where the answer about a code comes from."""

    DIRECT = "DIRECT"  # a statement on the code itself
    MEMBER = "MEMBER"  # a declared member of the family asked about
    OATS = "OATS"  # declared oats, asked about the gluten cereals
    FAMILY = "FAMILY"  # the declared family of the member asked about
    GENERAL = "GENERAL"  # only the general statement X99
    NONE = "NONE"  # no statement at all


# On equal unsafety the most direct basis is reported.
_BASIS_RANK = {Basis.DIRECT: 3, Basis.MEMBER: 2, Basis.OATS: 1, Basis.FAMILY: 0}


@dataclass(frozen=True)
class Resolution:
    """The relation that counts for one code, the code the statement was made about, and the basis.

    `own_relation` is what the statements on the code itself say, least safe first. It differs from
    `relation` when the statement about another code counts.
    """

    relation: AllergenRelation
    source_code: str | None
    basis: Basis
    own_relation: AllergenRelation = AllergenRelation.NOT_STATED


def least_safe(relations: Iterable[AllergenRelation]) -> AllergenRelation:
    """The least safe of the given relations; `NOT_STATED` when none of them is a statement."""
    stated = [relation for relation in relations if relation in _UNSAFETY]
    return max(stated, key=_UNSAFETY.__getitem__, default=AllergenRelation.NOT_STATED)


def resolve(statements: Sequence[AllergenStatement], code: str) -> Resolution:
    """What the statements say about `code`, family-aware, least safe first."""
    direct = _direct(statements, code)
    own_relation = least_safe(resolution.relation for resolution in direct)
    # Only FREE_FROM on the member itself settles the question against its declared family.
    family = [] if own_relation is AllergenRelation.FREE_FROM else _from_family(statements, code)
    candidates = [*direct, *_from_members(statements, code), *family]
    if candidates:
        return replace(max(candidates, key=_preference), own_relation=own_relation)
    if any(statement.code == GENERAL_STATEMENT_CODE for statement in statements):
        return Resolution(AllergenRelation.NOT_STATED, GENERAL_STATEMENT_CODE, Basis.GENERAL)
    return Resolution(AllergenRelation.NOT_STATED, None, Basis.NONE)


def statement_for(statements: Sequence[AllergenStatement], code: str) -> AllergenRelation:
    """`FREE_FROM`, `CONTAINS`, `MAY_CONTAIN`, `UNDECLARED` or `NOT_STATED` for one allergen code."""
    return resolve(statements, code).relation


def _preference(resolution: Resolution) -> tuple[int, int, str]:
    return (_UNSAFETY[resolution.relation], _BASIS_RANK[resolution.basis], resolution.source_code or "")


def _direct(statements: Sequence[AllergenStatement], code: str) -> list[Resolution]:
    if code == GENERAL_STATEMENT_CODE:
        return []
    return [
        Resolution(statement.relation, code, Basis.DIRECT)
        for statement in statements
        if statement.code == code and statement.relation in _UNSAFETY
    ]


def _from_members(statements: Sequence[AllergenStatement], family: str) -> list[Resolution]:
    members = members_of(family)
    return [
        _member_declaration(statement, family)
        for statement in statements
        if statement.code in members and statement.relation in DECLARING_RELATIONS
    ]


def _member_declaration(statement: AllergenStatement, family: str) -> Resolution:
    is_contained_oats = (
        family == GLUTEN_CEREALS_CODE
        and statement.code == OATS_CODE
        and statement.relation is AllergenRelation.CONTAINS
    )
    if is_contained_oats:
        return Resolution(AllergenRelation.MAY_CONTAIN, OATS_CODE, Basis.OATS)
    return Resolution(statement.relation, statement.code, Basis.MEMBER)


def _from_family(statements: Sequence[AllergenStatement], member: str) -> list[Resolution]:
    family = parent_of(member)
    if family is None:
        return []
    return [
        Resolution(AllergenRelation.MAY_CONTAIN, family, Basis.FAMILY)
        for statement in statements
        if statement.code == family and statement.relation in DECLARING_RELATIONS
    ]
