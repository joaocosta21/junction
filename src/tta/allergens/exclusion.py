"""The buyer exclusion rule (SPEC section 6): per excluded allergen PASS, REJECT or TO_HUMAN.

A nutritional claim is never an input here: `FREE_FROM_LACTOSE` is not a statement about milk
(AIMO/docs/SCHEMA-AND-CODES.md section 4).
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.allergens.codes import GENERAL_STATEMENT_CODE, describe, gs1_name, is_known_code
from tta.allergens.statements import Basis, Resolution, resolve
from tta.contracts.allergen import AllergenCheck, AllergenFinding, AllergenStatement
from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness
from tta.contracts.errors import InvalidRequest

STRICT = AllergenStrictness.STRICT
DECLARED_ONLY = AllergenStrictness.DECLARED_ONLY

# The table of SPEC section 6, cell by cell. UNDECLARED and no statement share a row.
_OUTCOME_TABLE: dict[tuple[AllergenRelation, AllergenStrictness], AllergenOutcome] = {
    (AllergenRelation.FREE_FROM, STRICT): AllergenOutcome.PASS,
    (AllergenRelation.FREE_FROM, DECLARED_ONLY): AllergenOutcome.PASS,
    (AllergenRelation.CONTAINS, STRICT): AllergenOutcome.REJECT,
    (AllergenRelation.CONTAINS, DECLARED_ONLY): AllergenOutcome.REJECT,
    (AllergenRelation.MAY_CONTAIN, STRICT): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.MAY_CONTAIN, DECLARED_ONLY): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.UNDECLARED, STRICT): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.UNDECLARED, DECLARED_ONLY): AllergenOutcome.PASS,
    (AllergenRelation.NOT_STATED, STRICT): AllergenOutcome.TO_HUMAN,
    (AllergenRelation.NOT_STATED, DECLARED_ONLY): AllergenOutcome.PASS,
}

# Least to most severe: the most severe finding is the outcome for the product.
_SEVERITY = {AllergenOutcome.PASS: 0, AllergenOutcome.TO_HUMAN: 1, AllergenOutcome.REJECT: 2}

# An explicit statement is one that settles the question without a person (SPEC section 4, `allergens`).
_EXPLICIT_RELATIONS = frozenset({AllergenRelation.FREE_FROM, AllergenRelation.CONTAINS})

_VERB = {AllergenRelation.CONTAINS: "contains", AllergenRelation.MAY_CONTAIN: "may contain"}

_DIRECT_FACT = {
    AllergenRelation.FREE_FROM: "The product states it is free from {allergen}",
    AllergenRelation.CONTAINS: "The product declares that it contains {allergen}, which the buyer excludes",
    AllergenRelation.MAY_CONTAIN: "The product declares that it may contain {allergen}, which the buyer excludes",
    AllergenRelation.UNDECLARED: "The product marks {allergen} as UNDECLARED, which is not a free-from statement",
}

_TO_HUMAN_ENDING = ": a dietitian must decide."
_UNVERIFIED_ENDING = ": it passes as unverified."


def check_exclusions(
    statements: Sequence[AllergenStatement],
    excluded: Sequence[str],
    strictness: AllergenStrictness | None,
) -> AllergenCheck:
    """Apply the buyer exclusion rule to the allergen statements of one product.

    Raises `InvalidRequest` for an excluded code outside the code table, for `X99`, and for an
    exclusion without a strictness (there is no default, SPEC section 3).
    """
    codes = tuple(dict.fromkeys(excluded))
    _require_valid_exclusions(codes)
    if not codes:
        return AllergenCheck(outcome=AllergenOutcome.PASS, strictness=strictness, all_explicit=True)
    if strictness is None:
        raise InvalidRequest("allergen_strictness is required when an allergen is excluded: STRICT or DECLARED_ONLY.")
    findings = tuple(_finding(statements, code, strictness) for code in codes)
    return AllergenCheck(
        outcome=max((finding.outcome for finding in findings), key=_SEVERITY.__getitem__),
        strictness=strictness,
        findings=findings,
        all_explicit=all(finding.relation in _EXPLICIT_RELATIONS for finding in findings),
    )


def _require_valid_exclusions(codes: Sequence[str]) -> None:
    if GENERAL_STATEMENT_CODE in codes:
        raise InvalidRequest(
            f"{GENERAL_STATEMENT_CODE} is the general statement '{gs1_name(GENERAL_STATEMENT_CODE)}', "
            "not an allergen that can be excluded."
        )
    unknown = [code for code in codes if not is_known_code(code)]
    if unknown:
        raise InvalidRequest(
            f"Unknown allergen code(s): {', '.join(unknown)}. Use the GS1 codes of the catalog, such as AM for milk.",
            unknown_codes=unknown,
        )


def _finding(statements: Sequence[AllergenStatement], code: str, strictness: AllergenStrictness) -> AllergenFinding:
    resolution = resolve(statements, code)
    outcome = _OUTCOME_TABLE[(resolution.relation, strictness)]
    is_about_another_code = resolution.basis in (Basis.MEMBER, Basis.OATS, Basis.FAMILY)
    return AllergenFinding(
        excluded_code=code,
        relation=resolution.relation,
        matched_code=resolution.source_code if is_about_another_code else None,
        outcome=outcome,
        sentence=_sentence(code, resolution, outcome),
    )


def _sentence(code: str, resolution: Resolution, outcome: AllergenOutcome) -> str:
    fact = _fact(code, resolution)
    if outcome is AllergenOutcome.TO_HUMAN:
        return fact + _TO_HUMAN_ENDING
    if resolution.relation is AllergenRelation.FREE_FROM or outcome is AllergenOutcome.REJECT:
        return fact + "."
    return fact + _UNVERIFIED_ENDING


def _fact(code: str, resolution: Resolution) -> str:
    allergen = describe(code)
    source = describe(resolution.source_code) if resolution.source_code else ""
    if resolution.basis is Basis.DIRECT:
        return _DIRECT_FACT[resolution.relation].format(allergen=allergen)
    if resolution.basis is Basis.MEMBER:
        verb = _VERB[resolution.relation]
        return f"The product declares that it {verb} {source}, part of the excluded {allergen}"
    if resolution.basis is Basis.OATS:
        return (
            f"The product declares that it contains {source} and the buyer excludes {allergen}; "
            "oats can be gluten-free or not"
        )
    if resolution.basis is Basis.FAMILY:
        return f"The product declares {source} and makes no statement about {allergen}, part of that family"
    if resolution.basis is Basis.GENERAL:
        return (
            f"The product carries the general statement {GENERAL_STATEMENT_CODE} "
            f"('{gs1_name(GENERAL_STATEMENT_CODE)}'), which is not a statement about {allergen}"
        )
    return f"The product makes no statement about {allergen}"
