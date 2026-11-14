""""The usual milk", "same as usual", "the usual amount": what the fixed rules do with them (replan P1 C4, C5; B8).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 20% "what the agent
can decide alone": a suggestion never adds itself (decision B8), so the reader never turns "the usual" into a
product or a number.
- "the usual" with a product type and a quantity ("50 litres of the usual milk"): the line is read as the plain
  type. The typed request has no field for "usual"; the gateway already suggests the customer's usual product for
  every line that names a type and no product (`tta.suggestions.usual.usual_products_for_request`), and the
  reading's sentence says so (`tta.agent.notes`).
- "the usual" with a product type and no quantity ("the usual milk", "the usual amount of cream"): asked. "The
  usual" is not a number; the question names the usual-quantity suggestion.
- "the usual" with no product type ("the usual order", "same as usual"): asked. The question names the
  standing-order page, where a standing order is renewed.
English only: no Finnish or Swedish wording was checked with a speaker.
"""

from __future__ import annotations

import re
from dataclasses import replace

from tta.agent.asking import Seen
from tta.agent.unread import NotReadByRules

_USUAL = re.compile(r"\b(?:(?:the\s+)?same\s+as\s+usual|as\s+usual|usual)\b")
_USUAL_AMOUNT = re.compile(r"\busual\s+(?:amounts?|quantity|quantities|volumes?)\b")
STANDING_ORDER_PAGE = "/standing-orders"  # the page of `tta.ui.standing_page`

USUAL_NO_QUANTITY = '{what} is named with "the usual" and no quantity in digits and unit'
ASK_USUAL_AMOUNT = (
    'How much {what} is needed? "The usual" is not a number, and a quantity is never guessed: your usual quantity '
    "is shown as a suggestion for you to confirm. Write the number in digits with litres, kilograms or packs, for "
    "example 200 litres."
)
USUAL_NO_PRODUCT = 'it says "the usual" and names no product type'
ASK_USUAL_PRODUCT = (
    'Which products does "the usual" stand for, and how much of each? Nothing is chosen for you. To repeat a '
    f"regular order, renew it on the standing-order page ({STANDING_ORDER_PAGE}); or write each product with its "
    "quantity, for example 100 litres of the usual milk by Monday."
)
USUAL_SAID = (
    'The request says "the usual": the usual product is suggested with the offer for you to confirm; nothing was '
    "chosen for you."
)


def says_usual(text: str) -> bool:
    """True when the buyer's words say "usual"."""
    return _USUAL.search(text.casefold()) is not None


def usual_words(seen: Seen) -> frozenset[int]:
    """The indices of the words that say "the usual": none of them narrows a product type."""
    spans = [match.span() for match in _USUAL.finditer(seen.folded)]
    return frozenset(index for index, start in enumerate(seen.starts)
                     if any(first <= start < end for first, end in spans))


def says_usual_amount(seen: Seen) -> bool:
    return _USUAL_AMOUNT.search(seen.folded) is not None


def without_usual(seen: Seen) -> Seen:
    """The text with "same as usual" blanked, so "the same" in it is not read as "the same again"."""
    return replace(seen, folded=_USUAL.sub(lambda match: " " * len(match.group()), seen.folded))


def usual_amount(what: str) -> NotReadByRules:
    """The question for "the usual milk": how much, naming the suggestion."""
    return NotReadByRules(USUAL_NO_QUANTITY.format(what=what), ASK_USUAL_AMOUNT.format(what=what))


def usual_with_no_product() -> NotReadByRules:
    """The question for "the usual order": which products, naming the standing-order page."""
    return NotReadByRules(USUAL_NO_PRODUCT, ASK_USUAL_PRODUCT)
