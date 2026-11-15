"""The facts of rule F-11: where the formula matters, and what the offer measured of a substitute's formula.

Valio Aimo, 14 Nov 2026: "for cakes/things that require the formula the ingredient and chemestry can make a
difference". The measure itself is the offer's (`tta.offers.formula`, on `SubstituteInfo.formula`); nothing is
measured again here. A substitute that carries no comparison leaves the fact missing: no data means unknown,
never "the same formula".

The formula matters on a line when the buyer profile says so for every line (`BuyerProfile.formula_matters`) or
when the request line says so. Either can add the check; neither can remove what the other added.

Who says so. In the buyer's mode LEARN the gateway adds the request's word itself, on a line whose product it
learned the recipe matters for (`tta.customers.learned`); the offer line then carries `keep_formula` although the
buyer's request did not say it. The rule's sentence must not put those words in the buyer's mouth. The engine sees
the option and not the request, so whoever holds the request as the buyer sent it says so for the length of one
evaluation (`request_as_sent`, as `tta.policy.custom.profile_in_force` does for a profile); the order book does at
order time. It changes the words of who says the formula matters, never whether the rule fires.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from tta.contracts.offer import OfferLine
from tta.contracts.policy import FormulaMode
from tta.contracts.product import FormulaCheck
from tta.contracts.request import PurchaseRequest
from tta.policy.reading import Missing, Reading
from tta.policy.text import format_number, join_words, plain_name

if TYPE_CHECKING:  # facts.py imports this module; OrderScope is only named in annotations
    from tta.policy.facts import OrderScope

# The request line's own word, copied onto the offer line as `stands_in_for` is (`OfferLine.keep_formula`,
# AIMO/build/replan/P10-formula.md, item F5): None or False reads as "not said", never as "does not matter".
LINE_SAYS_FIELD = "keep_formula"
REQUEST_SAYS = "the request says so for this line"
# The gateway added the check from what it learned of the buyer's orders; the request did not say it.
LEARNED_SAYS = "what the agent learned about the orders of {buyer} says so for this line"
PROFILE_SAYS = "{buyer} uses its products as ingredients"
NOBODY_SAYS = "neither the request nor the buyer profile says the formula matters"
NO_SUBSTITUTE = "the line replaces no product"
NO_COMPARISON = "the offer carries no formula comparison for this substitute"
# Said only where the two ingredient lists could not be compared component by component (no shared language):
# there the words of both languages still show that one names a vegetable oil or fat and the other does not.
OTHER_FAT_SOURCE = "another fat source"
SENTENCE_MAX_CHARACTERS = 400  # of the formula's part of a rule sentence: six figures and a note fit
COMPONENT_MAX_CHARACTERS = 60  # of one component in a sentence; a longer one is said by its name alone
LACKS = "lacks"
CONTAINS = "contains"
_ASKED_FOR = {LACKS: "which the product asked for contains", CONTAINS: "which the product asked for does not"}


# The request as the buyer sent it, while an option built from it is judged. None: nobody said, and a line that
# carries the mark reads as the request's own word, as before.
_AS_SENT: ContextVar[PurchaseRequest | None] = ContextVar("tta_request_as_sent", default=None)


@contextmanager
def request_as_sent(request: PurchaseRequest | None) -> Iterator[None]:
    """Inside the block, rule F-11 knows the request as the buyer sent it, in this thread of control only: a line
    whose mark the gateway added from what it learned is said to be learned, not asked for."""
    token = _AS_SENT.set(request)
    try:
        yield
    finally:
        _AS_SENT.reset(token)


def _line_says(line: OfferLine) -> bool:
    return getattr(line, LINE_SAYS_FIELD, None) is True


def _request_did_not_say(line: OfferLine) -> bool:
    """The request as the buyer sent it is known, and its line does not say the formula matters. False whenever
    the request as sent is not known: the mark on the offer line then reads as the request's own word."""
    request = _AS_SENT.get()
    if request is None or line.request_line_index >= len(request.lines):
        return False
    return request.lines[line.request_line_index].keep_formula is not True


def _added_by_learning(scope: OrderScope, line: OfferLine) -> bool:
    """The offer line carries the mark, the buyer's own request line does not, and the buyer's mode is not ALWAYS
    (where the profile says it for every line): the gateway added the check from what it learned."""
    mode = scope.profile.formula_mode_in_force
    return _line_says(line) and _request_did_not_say(line) and mode is not FormulaMode.ALWAYS


def _formula_matters(scope: OrderScope, line: OfferLine) -> Reading:
    return scope.profile.formula_matters or _line_says(line)


def _formula_matters_reason(scope: OrderScope, line: OfferLine) -> Reading:
    """Who says the formula matters: the request's own line, else what the gateway learned of the buyer's orders,
    else the buyer profile. Never "the request" for a mark the buyer's request did not carry."""
    if _added_by_learning(scope, line):
        return LEARNED_SAYS.format(buyer=plain_name(scope.profile.display_name))
    if _line_says(line) and not _request_did_not_say(line):
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


def formula_rule_fires(scope: OrderScope, line: OfferLine) -> bool:
    """Whether rule F-11 fires on the line: a substitute, where the formula matters, that does not keep it. Read
    by rule F-12's facts, so that one difference of formula is said once."""
    matters = _formula_matters(scope, line) is True
    return line.substitute is not None and matters and _keeps_formula(scope, line) is False


def _outcome(_: OrderScope, line: OfferLine) -> Reading:
    check = _check(line)
    return check if isinstance(check, Missing) else check.outcome.value


def _sentence(_: OrderScope, line: OfferLine) -> Reading:
    """What the comparison found, for the end of a clause (its full stop is left to the rule's sentence).

    Where the two ingredient lists were compared and differ, the sentence is built here from the components
    and the figures, so that the cut falls after a whole component and says how many more there are. Otherwise
    it is the offer's own sentence. Either can name a brand, so the text is read as data."""
    check = _check(line)
    if isinstance(check, Missing):
        return check
    if not (check.contents_compared and (check.only_in_other or check.only_in_original)):
        return plain_name(check.sentence, SENTENCE_MAX_CHARACTERS).rstrip(".")
    figures = _figures(check)
    after = f"; figures outside our tolerance: {', '.join(figures)}" if figures else ""
    sides = [(LACKS, check.only_in_original), (CONTAINS, check.only_in_other)]
    budget = (SENTENCE_MAX_CHARACTERS - len(after)) // sum(1 for _, found in sides if found)
    said = "; ".join(_side(verb, found, budget) for verb, found in sides if found)
    return f"it {said}{after}"


def _side(verb: str, components: tuple[str, ...], budget: int) -> str:
    """ "lacks lactase enzyme, which the product asked for contains": whole components while they fit the
    budget, then "and N more". The first is always said."""
    said: list[str] = []
    for component in components:
        words = _component(component)
        if said and len(", ".join((*said, words))) + len(_ASKED_FOR[verb]) + len(verb) > budget:
            break
        said.append(words)
    more = len(components) - len(said)
    listed = ", ".join(said) if more else join_words(said)
    return f"{verb} {listed}{f' and {more} more' if more else ''}, {_ASKED_FOR[verb]}"


def _component(words: str) -> str:
    """One component as data. One too long for a sentence is said by its name, without what its brackets hold."""
    shown = plain_name(words, len(words) or 1)
    if len(shown) <= COMPONENT_MAX_CHARACTERS:
        return shown
    return plain_name(shown.split(" (")[0], COMPONENT_MAX_CHARACTERS)


def _figures(check: FormulaCheck) -> list[str]:
    return [
        f"{each.nutrient.replace('_', ' ')} {format_number(each.other)} g, not {format_number(each.original)} g"
        for each in check.differences if not each.within_tolerance
    ]


def _differences(_: OrderScope, line: OfferLine) -> Reading:
    """Every component only one ingredient list names, as "lacks lactase enzyme" or "contains carrageenan" (of
    the substitute, against the product asked for), then every figure outside the tolerance as "fat 15 g, not
    36 g", then the fat source where the lists could not be compared and their words show it differs."""
    check = _check(line)
    if isinstance(check, Missing):
        return ()
    components = (
        *(f"{LACKS} {_component(each)}" for each in check.only_in_original),
        *(f"{CONTAINS} {_component(each)}" for each in check.only_in_other),
    ) if check.contents_compared else ()
    by_words = (OTHER_FAT_SOURCE,) if check.fat_source_differs and not check.contents_compared else ()
    return (*components, *_figures(check), *by_words)


FORMULA_FACTS: Mapping[str, Callable[[OrderScope, OfferLine], Reading]] = {
    "line.formula_matters": _formula_matters,
    "line.formula_matters_reason": _formula_matters_reason,
    "line.substitute_keeps_formula": _keeps_formula,
    "line.substitute_formula_outcome": _outcome,
    "line.substitute_formula": _sentence,
    "line.substitute_formula_differences": _differences,
}
