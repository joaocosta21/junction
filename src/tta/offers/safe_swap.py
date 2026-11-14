"""A substitute chosen for an allergen says so (lane FC2, 14 Nov 2026).

Safe first (review P4, item M1) puts a product whose data rules out every excluded allergen before the product
the buyer named when that one's data leaves a doubt. The named product can then be supplied, and the same offer
holds it as the alternative "allergen not ruled out". The option with the substitute was still titled "With a
substitute for a product that cannot be supplied in full", which is not why it was replaced. The title and one
sentence of the summary now give the real reason.
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.allergens.codes import describe
from tta.contracts.allergen import AllergenFinding
from tta.contracts.common import AllergenRelation
from tta.contracts.offer import OfferLine
from tta.offers.safety import has_doubt
from tta.offers.wording import joined, plain_name

SAFE_SWAP_TITLE = "With a substitute whose data rules out the allergen you exclude"
STATES_NOTHING = "states nothing about"
MAY_CONTAIN = "may contain"


def safe_swap_said(lines: Sequence[OfferLine], other_options: Sequence[Sequence[OfferLine]]) -> str:
    """ " Elovena oat drink (469512) states nothing about milk (AM), which is excluded; Alpro Rice drink
    (473424) is free from it." One sentence per stand-in, or "" unless every stand-in of the option is safe and
    replaces a product that another option of the offer supplies with a doubt about an excluded allergen."""
    stand_ins = [line for line in lines if line.substitute is not None]
    doubtful = {line.product_id: line for option in other_options for line in option if has_doubt(line)}
    if not stand_ins or any(_swapped_for_safety(line, doubtful) is None for line in stand_ins):
        return ""
    return "".join(_sentence(line, doubtful[line.substitute.original_id]) for line in stand_ins if line.substitute)


def _swapped_for_safety(line: OfferLine, doubtful: dict[str, OfferLine]) -> OfferLine | None:
    """The line of the product this one replaces, where that product is offered with a doubt and this one's data
    rules out every excluded allergen."""
    check = line.allergen_check
    if line.substitute is None or check is None or not check.findings or has_doubt(line):
        return None
    return doubtful.get(line.substitute.original_id)


def _sentence(stand_in: OfferLine, original: OfferLine) -> str:
    findings = original.allergen_check.findings if original.allergen_check is not None else ()
    unsure = [each for each in findings if each.relation is not AllergenRelation.FREE_FROM]
    may_contain = _described([each for each in unsure if each.relation is AllergenRelation.MAY_CONTAIN])
    not_stated = _described([each for each in unsure if each.relation is not AllergenRelation.MAY_CONTAIN])
    parts = [
        f"{verb} {joined(codes)}" for verb, codes in ((MAY_CONTAIN, may_contain), (STATES_NOTHING, not_stated))
        if codes
    ]
    it = "it" if len(may_contain) + len(not_stated) == 1 else "them"
    return f" {_named(original)} {' and '.join(parts)}, which is excluded; {_named(stand_in)} is free from {it}."


def _described(findings: Sequence[AllergenFinding]) -> list[str]:
    return list(dict.fromkeys(describe(each.excluded_code) for each in findings))


def _named(line: OfferLine) -> str:
    return f"{plain_name(line.name)} ({line.product_id})"
