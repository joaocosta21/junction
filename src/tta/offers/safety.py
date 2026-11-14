"""Whether a product's data rules out every allergen the buyer excludes (review P4, rule R1: safe first).

Valio Aimo, 14 Nov 2026: "if you are not sure you need to flag it to the user" and "it is better to not have gluten
if you are unsure". So a product whose data leaves a doubt is never the suggestion, under either allergen rule: it
is an alternative with a label, and a dietitian decides. A declared "contains" is no doubt: such a product has
dropped out before this is asked (`tta.offers.candidates`).
"""

from __future__ import annotations

from collections.abc import Iterable

from tta.allergens.codes import describe
from tta.contracts.allergen import AllergenCheck
from tta.contracts.common import AllergenOutcome, AllergenRelation
from tta.contracts.offer import OfferLine
from tta.offers.wording import joined


def ruled_out(check: AllergenCheck | None) -> bool:
    """True when nothing is excluded, or the product states it is free from every excluded allergen. The same
    test as the allergen claim's status CONFIRMED (`tta.availability.claims`)."""
    if check is None or not check.findings:
        return True
    return check.outcome is AllergenOutcome.PASS and check.all_explicit


def has_doubt(line: OfferLine) -> bool:
    return not ruled_out(line.allergen_check)


def who_decides(checks: Iterable[AllergenCheck | None]) -> str:
    """Who settles the doubt: the dietitian when the allergen rule sends a finding to a person (rule P-04);
    under the declared-only rule nobody is asked, and the person who confirms the order sees it."""
    to_human = any(check is not None and check.outcome is AllergenOutcome.TO_HUMAN for check in checks)
    return "a dietitian must decide" if to_human else "the person who confirms the order must decide"


def open_allergens(checks: Iterable[AllergenCheck | None]) -> str:
    """`cereals containing gluten (AW)`: the excluded allergens the data of these products does not rule out."""
    codes = dict.fromkeys(
        finding.excluded_code
        for check in checks if check is not None
        for finding in check.findings if finding.relation is not AllergenRelation.FREE_FROM
    )
    return joined([describe(code) for code in codes])
