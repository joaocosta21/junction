"""An amount of money in a buyer's text: read as the most to spend on that one request, or asked about (lane FP-B).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for". "1,000 litres of
lactose-free milk by Monday, under €1,000" names the most the buyer wants to spend on this request: the typed
request carries it (`PurchaseRequest.max_net_eur`, euros before tax, as every total and every limit of the
gateway is), and rule P-01 sends an option above it to a person (`tta.policy.spend_limit_facts`). Until 15 Nov
2026 such a sentence was refused, because the typed request had no place for the amount.

Read, and only this: one amount, in euros ("€", "EUR", "euro", "euros", or no currency right after the word
"budget"), with a word that makes it a limit: "under", "below", "less than", "within", "at most", "up to", "max",
"maximum", "no more than", "not above", "not over", "a budget of", "budget:", "a limit of", or "budget", "max",
"at most", "or less" right after it. The number is read as a quantity is (`tta.agent.quantity`): "1,000" and
"1 000" are 1000, "999,50" and "999.50" are 999.50; at most two decimals. The reading's sentence says the amount
and how it is used (`tta.agent.notes`).

Asked about, never guessed and never dropped:
- an amount with no word that makes it a limit ("for €400", "at least €400", "no less than 400 euros"): a price
  is not agreed in a request, and a minimum is not this;
- an amount per unit ("under €2 a litre", "max 2 euros per litre"): a limit on a unit price is not applied;
- more than one amount; a currency other than the euro; a number that is not read as one number ("€1.000") or is
  not above zero.
A number with no currency and no "budget" before it is no amount of money: the reader asks what it stands for,
as before ("max 1000"). "2 EUR pallets" is a kind of pallet, not two euros.

The words that say the amount are then blanked, so that nothing else reads them: "no more than" is no exclusion,
"within" no deadline, "under" no word after a product type, and the amount no second quantity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from tta.agent.quantity import quantity
from tta.agent.textcheck import SMALL_UNITS, SPACES, unit_of
from tta.agent.unread import NotReadByRules
from tta.agent.wording import Span
from tta.contracts.request import MAX_NET_EUR, MONEY_DECIMALS

_AMOUNT = rf"\d+(?:[.,{SPACES}]\d+)*"
EURO_SIGN = "€"
_SIGNS = "€$£"
_EURO_WORDS = frozenset({"eur", "euro", "euros", "euroa", "euron"})
_WORDS = r"(?:eur|euros?|euroa|euron|usd|dollars?|gbp|sek|kr|kronor)"
_WITH_CURRENCY = re.compile(
    rf"(?P<before>[{_SIGNS}]|\b{_WORDS})\s?(?P<first>{_AMOUNT})"
    rf"|(?P<second>{_AMOUNT})\s?(?P<after>[{_SIGNS}]|{_WORDS}\b(?![\s-]*pallet))"
)
_BUDGET = r"budget(?:\s+(?:of|is|limit|cap|max|maximum|at most|up to|under|below))*"
_BUDGET_ALONE = re.compile(rf"\b{_BUDGET}\s*[:=]?\s*(?P<amount>{_AMOUNT})")
# The words that make an amount a limit, right before it. "No less than" and "not under" name a minimum.
_LIMIT_BEFORE = re.compile(
    r"(?:(?<!\bno\s)(?<!\bnot\s)\b(?:under|below|less than|within)"
    r"|\b(?:no|not) (?:more|higher) than|\bnot (?:above|over|exceeding)"
    r"|\bat (?:the )?most|\bup to|\bmax\.?|\bmaximum(?: of)?"
    rf"|\b{_BUDGET}|\b(?:limit|cap) (?:of|is)|\b(?:limited|capped) (?:to|at))\s*[:=]?\s*$"
)
_LIMIT_AFTER = re.compile(r"\s*(?:budget|max(?:imum)?|at (?:the )?most|or less|tops)\b")
_PER_UNIT = re.compile(
    r"\s*(?:(?:each|apiece)\b|(?:/\s*|(?:per|every)\s+)[^\W\d_]+|an?\s+(?P<unit>[^\W\d_]+))"
)
_PER_WORDS = frozenset({"head", "person", "guest", "item", "serving", "litre", "liter", "kilo", "kilogram"})
_LAST_WORD = re.compile(r"([^\W\d_]+)\s+$")
# Words that lead into the limit and say nothing by themselves: "with a budget of", "the total must stay under".
_LEAD_IN = frozenset({
    "with", "within", "for", "at", "on", "in", "to", "a", "an", "the", "our", "my", "total", "overall", "whole",
    "all", "it", "that", "must", "should", "be", "is", "stay", "staying", "keep", "keeping", "cost", "costs",
    "costing", "spend", "spending", "of", "price", "order",
})

NO_LIMIT_WORD = 'it gives an amount of money ("{said}") without saying that it is the most to spend'
ASK_IF_THE_MOST = (
    'Is {said} the most to spend on this request, before tax? Then write "under {said}". A price is not agreed in '
    "a request: every option of the offer states its total before tax."
)
PER_UNIT = 'it gives an amount of money per unit ("{said}"), and a limit on a unit price is not applied'
ASK_THE_WHOLE = (
    'What is the most to spend on the whole request, before tax? Write it as "under €400". Every option of the '
    "offer states each product's unit price and its total before tax."
)
TWO_AMOUNTS = 'it gives more than one amount of money ("{first}" and "{second}")'
ASK_ONE_AMOUNT = (
    'Which one amount is the most to spend on the whole request, before tax? Write it once, as "under €400". A '
    "limit per product is not applied."
)
NOT_EUROS = (
    'it gives an amount of money in a currency other than the euro ("{said}"), and every price here is in euros'
)
ASK_IN_EUROS = 'What is the most to spend on this request in euros, before tax? Write it as "under €400".'
NOT_ONE_NUMBER = 'it gives an amount of money that is not read as one number ("{said}")'
ASK_PLAIN_AMOUNT = (
    "What is the most to spend on this request, in euros before tax? Write it in plain digits, for example "
    '"under €1000" or "under €999.50".'
)
BUDGET_READ = (
    "€{amount} is read as the most to spend on this request, before tax: an option above it goes to a person."
)


@dataclass(frozen=True)
class _Found:
    """One amount of money of the text: where it stands, its digits and its currency sign or word, if any."""

    span: Span
    digits: str
    currency: str | None

    def said(self, folded: str) -> str:
        return " ".join(folded[self.span[0]:self.span[1]].split())


def _amounts(folded: str) -> list[_Found]:
    """Every amount of money, in the order written: digits with a currency, or digits right after "budget"."""
    found = [
        _Found(match.span(), match.group("first") or match.group("second"),
               match.group("before") or match.group("after"))
        for match in _WITH_CURRENCY.finditer(folded)
    ]
    for match in _BUDGET_ALONE.finditer(folded):
        at = match.span("amount")
        if not any(start < at[1] and at[0] < end for (start, end) in (each.span for each in found)):
            found.append(_Found(at, match.group("amount"), None))
    return sorted(found, key=lambda each: each.span)


def amounts_said(folded: str) -> tuple[str, ...]:
    """Every amount of money of the casefolded text, as written. For a reader that cannot carry one and must
    not drop it (`tta.agent.dishes`)."""
    return tuple(found.said(folded) for found in _amounts(folded))


def _per_unit_end(folded: str, end: int) -> int | None:
    """Where the words that make the amount a unit price end ("a litre", "per kg", "each"), or None."""
    match = _PER_UNIT.match(folded, end)
    if match is None:
        return None
    unit = match.group("unit")
    named = unit is None or unit_of(unit) is not None or unit in SMALL_UNITS or unit in _PER_WORDS
    return match.end() if named else None


def _euros(digits: str) -> Decimal | None:
    """The amount the digits give, above zero with at most two decimals, or None."""
    try:
        value = quantity(digits, 1)
    except NotReadByRules:
        return None
    exponent = value.as_tuple().exponent
    places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    return value if places <= MONEY_DECIMALS and value <= MAX_NET_EUR else None


def _start_of_the_words(folded: str, start: int) -> int:
    """Where the words that lead into the limit start: "with a" of "with a budget of"."""
    while (word := _LAST_WORD.search(folded[:start])) is not None and word.group(1) in _LEAD_IN:
        start = word.start()
    return start


def split_budget(folded: str) -> tuple[Decimal | None, str]:
    """The most to spend the casefolded text names, in euros, and the text with the words that say it blanked
    (same length, so every position still holds); `(None, folded)` for a text that gives no amount of money.
    Raises `NotReadByRules`, with the question to put, for an amount that is not clearly that."""
    found = _amounts(folded)
    if not found:
        return None, folded
    if len(found) > 1:
        raise NotReadByRules(
            TWO_AMOUNTS.format(first=found[0].said(folded), second=found[1].said(folded)), ASK_ONE_AMOUNT
        )
    money = found[0]
    said, (start, end) = money.said(folded), money.span
    if money.currency is not None and money.currency != EURO_SIGN and money.currency not in _EURO_WORDS:
        raise NotReadByRules(NOT_EUROS.format(said=said), ASK_IN_EUROS)
    per_unit = _per_unit_end(folded, end)
    if per_unit is not None:
        raise NotReadByRules(PER_UNIT.format(said=" ".join(folded[start:per_unit].split())), ASK_THE_WHOLE)
    before, after = _LIMIT_BEFORE.search(folded[:start]), _LIMIT_AFTER.match(folded, end)
    if before is None and after is None:
        raise NotReadByRules(NO_LIMIT_WORD.format(said=said), ASK_IF_THE_MOST.format(said=said))
    amount = _euros(money.digits)
    if amount is None:
        raise NotReadByRules(NOT_ONE_NUMBER.format(said=said), ASK_PLAIN_AMOUNT)
    start = _start_of_the_words(folded, before.start() if before is not None else start)
    end = after.end() if after is not None else end
    return amount, f"{folded[:start]}{' ' * (end - start)}{folded[end:]}"


def budget_stated(text: str) -> tuple[Decimal | None, bool]:
    """What a reading is held to: the most to spend the text names, and whether the text gives an amount of
    money at all. An amount that is not clearly the most to spend is `(None, True)`: no reading may carry one,
    and none may leave it out."""
    try:
        amount, _ = split_budget(text.casefold())
    except NotReadByRules:
        return None, True
    return amount, amount is not None


def without_budget(text: str) -> str:
    """The text with the words that say the most to spend blanked, casefolded; the text itself when it names
    none or its amount is not clear. The other facts a reading is held to are taken from this: the amount is
    no quantity."""
    try:
        amount, rest = split_budget(text.casefold())
    except NotReadByRules:
        return text
    return rest if amount is not None else text


def budget_note(amount: Decimal) -> str:
    """ "€1,000 is read as the most to spend on this request, before tax: an option above it goes to a person." """
    whole = amount == amount.to_integral_value()
    return BUDGET_READ.format(amount=format(amount, ",.0f" if whole else ",.2f"))
