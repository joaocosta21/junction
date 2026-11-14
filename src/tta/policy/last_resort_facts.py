"""The facts of rule F-12: a substitute that is a last resort, and why it is one.

The offer marks a substitute `last_resort` when it loses a dietary claim, is flavoured where the product asked
for is not, is another product type, or cannot be shown to be like for like, and stands in only because nothing
like for like can be ordered (`tta.offers.substitutes`). Nothing is judged again here: the mark and the offer's
own reasons are read.

One fact, one sentence. A lost dietary claim is rule F-08's to say and a formula that differs where the formula
matters is rule F-11's. Where one of them fires on the line, its reason is left out of F-12's; when no reason
is left, F-12 does not fire, because the person would read the same fact twice. The line still goes to a
person, under the rule that says the fact.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from tta.contracts.offer import OfferLine, SubstituteInfo
from tta.policy.formula_facts import formula_rule_fires
from tta.policy.reading import Missing, Reading
from tta.policy.text import plain_name

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

# How `tta.offers.substitute_wording.replace_sentence` starts the sentence of a candidate that is not like for
# like; what follows are its reasons, joined by "; ".
NOT_LIKE_FOR_LIKE_PREFIX = "Not a like-for-like replacement: "
REASON_SEPARATOR = "; "
# How `tta.offers.substitute_wording.replace_reasons` starts the reason rule F-08 says, and the two forms of the
# reason rule F-11 says. A test builds the offer's reasons and fails when these no longer match them.
CLAIM_REASON_PREFIX = "it does not carry the claim"
FORMULA_REASON_PREFIX = "a different formula ("
FORMULA_REASON_FAT_SOURCE = "another fat source"
NO_REASON_GIVEN = "it is not the same kind of product as the one asked for, and nothing like for like can be ordered"
SAID_BY_ANOTHER_RULE = "the only reason is one another rule of this line says"
NO_SUBSTITUTE = "the line replaces no product"
REASON_MAX_CHARACTERS = 400  # of the offer's reasons inside a rule sentence: a flavour, a type and six figures fit


def _is_last_resort(_: OrderScope, line: OfferLine) -> Reading:
    return line.substitute is not None and line.substitute.last_resort


def _offer_reasons(substitute: SubstituteInfo) -> tuple[tuple[str, ...], bool]:
    """Each reason the offer gives, and whether they are one per entry. A line that carries the sentence and not
    the list (stored before the list existed) gives its reasons as one text: they cannot be told apart."""
    check = substitute.replaceable
    if check is None:
        return (), True
    if check.reasons:
        return tuple(check.reasons), True
    if check.sentence.startswith(NOT_LIKE_FOR_LIKE_PREFIX):
        whole = check.sentence[len(NOT_LIKE_FOR_LIKE_PREFIX):].rstrip(". ")
        return ((whole,) if whole else ()), False
    return (), True


def _is_formula_reason(reason: str) -> bool:
    return reason.startswith(FORMULA_REASON_PREFIX) or reason == FORMULA_REASON_FAT_SOURCE


def _reasons_of_its_own(scope: OrderScope, line: OfferLine) -> tuple[str, ...] | None:
    """The reasons no other rule of the line says, in the offer's own words. None: the offer gives no reason at
    all and no claim is lost, so the mark alone is the reason. Reasons that cannot be told apart are all kept:
    saying a fact twice is the lesser fault, leaving one out is not."""
    substitute = line.substitute
    if substitute is None:
        return ()
    claim_said = bool(substitute.claims_lost)  # rule F-08 fires on the line
    formula_said = formula_rule_fires(scope, line)  # rule F-11 fires on the line
    reasons, one_per_entry = _offer_reasons(substitute)
    if not reasons:
        return () if claim_said else None
    if not one_per_entry:
        return reasons
    return tuple(
        reason for reason in reasons
        if not (claim_said and reason.startswith(CLAIM_REASON_PREFIX))
        and not (formula_said and _is_formula_reason(reason))
    )


def _has_reason_of_its_own(scope: OrderScope, line: OfferLine) -> Reading:
    """False only when every reason of the last resort is said by rule F-08 or rule F-11 on the same line."""
    if line.substitute is None or not line.substitute.last_resort:
        return False
    reasons = _reasons_of_its_own(scope, line)
    return reasons is None or bool(reasons)


def _reason(scope: OrderScope, line: OfferLine) -> Reading:
    """Why it is not like for like, in the offer's own words when the line carries them. The text can name a
    brand or a flavour from the product file, so it is read as data, and it stands inside a sentence, so its
    full stop is left to the rule's sentence."""
    if line.substitute is None:
        return Missing(NO_SUBSTITUTE)
    reasons = _reasons_of_its_own(scope, line)
    if reasons is None:
        return NO_REASON_GIVEN
    said = plain_name(REASON_SEPARATOR.join(reasons), REASON_MAX_CHARACTERS).rstrip(". ")
    return said or Missing(SAID_BY_ANOTHER_RULE)


LAST_RESORT_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.substitute_last_resort": _is_last_resort,
    "line.substitute_last_resort_own_reason": _has_reason_of_its_own,
    "line.substitute_last_resort_reason": _reason,
}
