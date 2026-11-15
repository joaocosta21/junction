"""The facts of rule F-12: a substitute that is not a like-for-like replacement, and why it is not.

The customer is told that, whatever is set, the agent never chooses on its own a substitute that is not a
like-for-like replacement. So the rule reads the offer's own verdict on every substitute
(`SubstituteInfo.replaceable`, `tta.offers.substitutes`): REPLACEABLE passes, and anything else goes to a person,
"not like for like" (another formula, use, flavour or type, a lost claim) and "replaceable as far as the data
shows" (the formula or the kind of product could not be compared) alike. The offer's `last_resort` mark counts too:
it is set on a substitute shown only because nothing like for like can be ordered. Until Sunday 15 Nov 2026 the
rule read that mark alone, and a substitute of another formula or use was ordered by the agent (check CK3, decision
B64). Nothing is judged again here: the verdict, the mark and the offer's own reasons are read. A substitute that
carries neither a verdict nor a mark leaves the fact missing: no data means unknown, never "like for like".

One fact, one sentence. A lost dietary claim is rule F-08's to say and a formula that differs where the formula
matters is rule F-11's. Where one of them fires on the line, its reason is left out of F-12's; when no reason
is left, F-12 does not fire, because the person would read the same fact twice. The line still goes to a
person, under the rule that says the fact.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from tta.contracts.offer import OfferLine, SubstituteInfo
from tta.contracts.product import FormulaOutcome, ReplaceVerdict
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
# What the rule's sentence says of the substitute, by the offer's verdict: "is not ..." where the offer names a
# reason against it, "is not shown to be ..." where nothing speaks against it and the data cannot show it.
NOT_LIKE_SAID = "is not a like-for-like replacement"
NOT_SHOWN_SAID = "is not shown to be a like-for-like replacement"
# Why a substitute is "replaceable as far as the data shows" and no further: from the two things the offer could
# not compare (`ReplaceCheck.type_not_judged`, a formula outcome of NOT_KNOWN). The words are ours.
TYPE_NOT_JUDGED = "only its category could be compared with the product asked for, not its kind of product"
FORMULA_NOT_KNOWN = "its formula cannot be compared with that of the product asked for"
NOT_SHOWN_NO_REASON = "the data does not show that it is the same kind of product with the same formula"
NO_REASON_GIVEN = "it is not the same kind of product as the one asked for, and nothing like for like can be ordered"
SAID_BY_ANOTHER_RULE = "the only reason is one another rule of this line says"
NO_SUBSTITUTE = "the line replaces no product"
NO_CHECK = "the offer carries no like-for-like check for this substitute"
REASON_MAX_CHARACTERS = 400  # of the offer's reasons inside a rule sentence: a flavour, a type and six figures fit


def _is_shown_only(substitute: SubstituteInfo) -> bool:
    """The offer's verdict is "replaceable as far as the data shows" and it is no last resort: nothing speaks
    against the substitute, and the data cannot show that it is like for like."""
    check = substitute.replaceable
    return check is not None and check.verdict is ReplaceVerdict.NOT_SHOWN and not substitute.last_resort


def _is_not_like_for_like(_: OrderScope, line: OfferLine) -> Reading:
    """True for every substitute the offer does not judge REPLACEABLE, and for one it marks a last resort."""
    substitute = line.substitute
    if substitute is None:
        return False
    if substitute.last_resort:
        return True
    if substitute.replaceable is None:
        return Missing(NO_CHECK)
    return substitute.replaceable.verdict is not ReplaceVerdict.REPLACEABLE


def _verdict(_: OrderScope, line: OfferLine) -> Reading:
    substitute = line.substitute
    if substitute is None:
        return Missing(NO_SUBSTITUTE)
    return substitute.replaceable.verdict.value if substitute.replaceable is not None else Missing(NO_CHECK)


def _like_for_like_said(_: OrderScope, line: OfferLine) -> Reading:
    if line.substitute is None:
        return Missing(NO_SUBSTITUTE)
    return NOT_SHOWN_SAID if _is_shown_only(line.substitute) else NOT_LIKE_SAID


def _not_shown_reasons(substitute: SubstituteInfo) -> tuple[str, ...]:
    """What the offer could not compare, each as one reason; empty when neither of the two explains the verdict."""
    check, formula = substitute.replaceable, substitute.formula
    type_not_judged = check is not None and check.type_not_judged
    formula_not_known = formula is None or formula.outcome is FormulaOutcome.NOT_KNOWN
    return (*((TYPE_NOT_JUDGED,) if type_not_judged else ()), *((FORMULA_NOT_KNOWN,) if formula_not_known else ()))


def _offer_reasons(substitute: SubstituteInfo) -> tuple[tuple[str, ...], bool]:
    """Each reason the offer gives, and whether they are one per entry. A line that carries the sentence and not
    the list (stored before the list existed) gives its reasons as one text: they cannot be told apart."""
    check = substitute.replaceable
    if check is None:
        return (), True
    if check.reasons:
        return tuple(check.reasons), True
    if _is_shown_only(substitute):
        return _not_shown_reasons(substitute), True
    if check.sentence.startswith(NOT_LIKE_FOR_LIKE_PREFIX):
        whole = check.sentence[len(NOT_LIKE_FOR_LIKE_PREFIX):].rstrip(". ")
        return ((whole,) if whole else ()), False
    return (), True


def _is_formula_reason(reason: str) -> bool:
    """A reason rule F-11 says where the formula matters: a formula that differs, or one that cannot be compared."""
    return reason.startswith(FORMULA_REASON_PREFIX) or reason in (FORMULA_REASON_FAT_SOURCE, FORMULA_NOT_KNOWN)


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
    """False for a like-for-like substitute, and when every reason against the substitute is said by rule F-08 or
    rule F-11 on the same line. True also where the like-for-like check itself is missing, so that the missing
    fact, and not this one, leaves the rule unknown."""
    if _is_not_like_for_like(scope, line) is False:
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
        return NOT_SHOWN_NO_REASON if _is_shown_only(line.substitute) else NO_REASON_GIVEN
    said = plain_name(REASON_SEPARATOR.join(reasons), REASON_MAX_CHARACTERS).rstrip(". ")
    return said or Missing(SAID_BY_ANOTHER_RULE)


# The fact names say "last resort", as the rule did when it read the offer's mark alone; decisions already
# stored carry them, so they are kept.
LAST_RESORT_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.substitute_last_resort": _is_not_like_for_like,
    "line.substitute_last_resort_own_reason": _has_reason_of_its_own,
    "line.substitute_last_resort_reason": _reason,
    "line.substitute_replace_verdict": _verdict,
    "line.substitute_like_for_like_said": _like_for_like_said,
}
