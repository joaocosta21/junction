"""The facts of rule F-12: a substitute that is a last resort, and why it is one.

The offer marks a substitute `last_resort` when it loses a dietary claim, is flavoured where the product asked
for is not, or is another product type, and stands in only because nothing like for like can be ordered
(`tta.offers.substitutes`). Nothing is judged again here: the mark and the offer's own reasons are read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from tta.contracts.offer import OfferLine
from tta.policy.reading import Missing, Reading
from tta.policy.text import plain_name

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

# How `tta.offers.substitute_wording.replace_sentence` starts the sentence of a candidate that is not like for
# like; what follows are its reasons, joined by "; ".
NOT_LIKE_FOR_LIKE_PREFIX = "Not a like-for-like replacement: "
CLAIMS_LOST = "it lacks a nutritional claim the original carries ({claims})"
NO_REASON_GIVEN = "it is not the same kind of product as the one asked for, and nothing like for like can be ordered"
NO_SUBSTITUTE = "the line replaces no product"
REASON_MAX_CHARACTERS = 400  # of the offer's reasons inside a rule sentence: a flavour, a type and six figures fit


def _is_last_resort(_: OrderScope, line: OfferLine) -> Reading:
    return line.substitute is not None and line.substitute.last_resort


def _reason(_: OrderScope, line: OfferLine) -> Reading:
    """Why it is not like for like, in the offer's own words when the line carries them. The text can name a
    brand or a flavour from the product file, so it is read as data, and it stands inside a sentence, so its
    full stop is left to the rule's sentence."""
    substitute = line.substitute
    if substitute is None:
        return Missing(NO_SUBSTITUTE)
    sentence = substitute.replaceable.sentence if substitute.replaceable is not None else ""
    if sentence.startswith(NOT_LIKE_FOR_LIKE_PREFIX):
        reasons = plain_name(sentence[len(NOT_LIKE_FOR_LIKE_PREFIX):], REASON_MAX_CHARACTERS).rstrip(". ")
        if reasons:
            return reasons
    if substitute.claims_lost:
        return CLAIMS_LOST.format(claims=", ".join(plain_name(claim) for claim in substitute.claims_lost))
    return NO_REASON_GIVEN


LAST_RESORT_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.substitute_last_resort": _is_last_resort,
    "line.substitute_last_resort_reason": _reason,
}
