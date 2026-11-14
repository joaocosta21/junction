"""Allergen statements and the results of the two allergen rules (SPEC section 6)."""

from __future__ import annotations

from tta.contracts.common import AllergenOutcome, AllergenRelation, AllergenStrictness, Contract


class AllergenStatement(Contract):
    """One statement of a product about one GS1 allergen code.

    `relation` is one of FREE_FROM, CONTAINS, MAY_CONTAIN, UNDECLARED as the product file gives it.
    A product with no statement for a code simply has no entry.
    """

    code: str
    relation: AllergenRelation


class AllergenFinding(Contract):
    """The outcome for one excluded allergen on one product."""

    excluded_code: str
    relation: AllergenRelation
    matched_code: str | None = None  # the code the statement was made about, when it is a family member
    outcome: AllergenOutcome
    sentence: str


class AllergenCheck(Contract):
    """Result of the buyer exclusion rule for one product."""

    outcome: AllergenOutcome
    strictness: AllergenStrictness | None = None
    findings: tuple[AllergenFinding, ...] = ()
    all_explicit: bool  # True when every excluded allergen has an explicit FREE_FROM or CONTAINS

    @property
    def declares_excluded(self) -> bool:
        return any(finding.outcome is AllergenOutcome.REJECT for finding in self.findings)


class SubstituteAllergenCheck(Contract):
    """Result of the substitution rule: a substitute must not add a declared allergen."""

    passes: bool
    added: tuple[AllergenStatement, ...] = ()
    sentence: str
