"""A dietary claim measured against the product's own allergen statements (review P4, item F4, decision D7).

A nutritional claim is a label; an allergen statement is data. Where the two disagree the data wins (Valio,
14 Nov 2026: "take the values as they are in the data"): a product that carries FREE_FROM_GLUTEN and declares
that it contains wheat does not meet a request that requires the claim. Whole catalog, measured for the
proposal: 56 products carry a claim their allergen data contradicts.

The table is ours. Only CONTAINS contradicts a claim: "may contain" and no statement do not.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from tta.allergens.codes import describe
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation

_MEAT_AND_FISH = ("AF", "ABD", "ADQ", "AC", "UM", "UN", "BF", "CM", "PO")
# Claim code → the allergen codes whose CONTAINS statement contradicts it. Oats (GO) are left out of the gluten
# row: gluten-free oats are a legitimate product (AIMO/docs/SCHEMA-AND-CODES.md section 4.3). Spelt (GS) and
# khorasan (GK) are wheats. LOW_LACTOSE is not in the table: a low-lactose product contains lactose.
CONTRADICTED_BY: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "FREE_FROM_GLUTEN": ("AW", "UW", "GB", "NR", "GS", "GK"),
        "FREE_FROM_WHEAT": ("UW", "GS", "GK"),
        "FREE_FROM_LACTOSE": ("ML",),
        "FREE_FROM_EGGS": ("AE",),
        "FREE_FROM_SOY": ("AY",),
        "VEGAN": ("AM", "ML", "AE", *_MEAT_AND_FISH),
        "VEGETARIAN": _MEAT_AND_FISH,
    }
)


def claim_contradictions(
    required_claims: Sequence[str], statements: Sequence[AllergenStatement]
) -> tuple[tuple[str, str], ...]:
    """(claim, allergen code) for each required claim that a CONTAINS statement of the product contradicts."""
    contained = {statement.code for statement in statements if statement.relation is AllergenRelation.CONTAINS}
    return tuple(
        (claim, code)
        for claim in dict.fromkeys(each.strip().upper() for each in required_claims)
        for code in CONTRADICTED_BY.get(claim, ())
        if code in contained
    )


def contradiction_sentence(contradictions: Sequence[tuple[str, str]]) -> str:
    """`The product carries the claim FREE_FROM_GLUTEN, but its allergen data says it contains wheat (UW): ...`"""
    parts = []
    for claim in dict.fromkeys(claim for claim, _ in contradictions):
        codes = ", ".join(describe(code) for each, code in contradictions if each == claim)
        parts.append(f"the claim {claim}, but its allergen data says it contains {codes}")
    return (
        f"The product carries {'; and '.join(parts)}. The data is taken as it stands, so the claim the request "
        "requires is not met."
    )
