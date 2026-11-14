"""The facts of rule F-11: where the formula matters, and what the offer measured of a substitute's formula.

Valio Aimo, 14 Nov 2026: "for cakes/things that require the formula the ingredient and chemestry can make a
difference". The measure itself is the offer's (`tta.offers.formula`, on `SubstituteInfo.formula`); nothing is
measured again here. A substitute that carries no comparison leaves the fact missing: no data means unknown,
never "the same formula".

The formula matters on a line when the buyer profile says so for every line (`BuyerProfile.formula_matters`) or
when the request line says so. Either can add the check; neither can remove what the other added.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from tta.contracts.offer import OfferLine
from tta.contracts.product import FormulaCheck
from tta.policy.reading import Missing, Reading
from tta.policy.text import format_number, plain_name

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

# The request line's own word, copied onto the offer line as `stands_in_for` is. No offer line carries it yet
# (AIMO/build/replan/P10-formula.md, item F5): absent reads as "not said", never as "does not matter".
LINE_SAYS_FIELD = "keep_formula"
REQUEST_SAYS = "the request says so for this line"
PROFILE_SAYS = "{buyer} uses its products as ingredients"
NOBODY_SAYS = "neither the request nor the buyer profile says the formula matters"
NO_SUBSTITUTE = "the line replaces no product"
NO_COMPARISON = "the offer carries no formula comparison for this substitute"
OTHER_FAT_SOURCE = "another fat source"
SENTENCE_MAX_CHARACTERS = 400  # of the offer's formula sentence inside a rule sentence: six figures and a note fit


def _line_says(line: OfferLine) -> bool:
    return getattr(line, LINE_SAYS_FIELD, None) is True


def _formula_matters(scope: OrderScope, line: OfferLine) -> Reading:
    return scope.profile.formula_matters or _line_says(line)


def _formula_matters_reason(scope: OrderScope, line: OfferLine) -> Reading:
    if _line_says(line):
        return REQUEST_SAYS
    if scope.profile.formula_matters:
        return PROFILE_SAYS.format(buyer=plain_name(scope.profile.display_name))
    return Missing(NOBODY_SAYS)


def _check(line: OfferLine) -> FormulaCheck | Missing:
    if line.substitute is None:
        return Missing(NO_SUBSTITUTE)
    return line.substitute.formula if line.substitute.formula is not None else Missing(NO_COMPARISON)


def _keeps_formula(_: OrderScope, line: OfferLine) -> Reading:
    check = _check(line)
    return check if isinstance(check, Missing) else check.keeps_formula


def _outcome(_: OrderScope, line: OfferLine) -> Reading:
    check = _check(line)
    return check if isinstance(check, Missing) else check.outcome.value


def _sentence(_: OrderScope, line: OfferLine) -> Reading:
    """The offer's own sentence, with its numbers. It can name a brand, so it is read as data, and it stands at
    the end of a clause, so its full stop is left to the rule's sentence."""
    check = _check(line)
    if isinstance(check, Missing):
        return check
    return plain_name(check.sentence, SENTENCE_MAX_CHARACTERS).rstrip(".")


def _differences(_: OrderScope, line: OfferLine) -> Reading:
    """Every figure outside the tolerance as "fat 15 g, not 36 g", then the fat source when it differs."""
    check = _check(line)
    if isinstance(check, Missing):
        return ()
    outside = [
        f"{each.nutrient.replace('_', ' ')} {format_number(each.other)} g, not {format_number(each.original)} g"
        for each in check.differences if not each.within_tolerance
    ]
    return (*outside, *((OTHER_FAT_SOURCE,) if check.fat_source_differs else ()))


FORMULA_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.formula_matters": _formula_matters,
    "line.formula_matters_reason": _formula_matters_reason,
    "line.substitute_keeps_formula": _keeps_formula,
    "line.substitute_formula_outcome": _outcome,
    "line.substitute_formula": _sentence,
    "line.substitute_formula_differences": _differences,
}
