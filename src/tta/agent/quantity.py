"""The number a buyer's digits give, read by fixed rules, and the numbers that are asked about (replan A2b C2, H3, M1).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": a quantity is never
guessed. Measured in replay on 14 Nov 2026 (the review's runs): "0.100 l" was read as 100 litres and ordered,
"Ward 4 200 litres" as 4,200 litres.
- A comma or a space before three digits groups thousands: "1,000", "1 000". A dot does so only in a longer
  number ("1.000.000"). One dot before exactly three digits can be read two ways ("1.250 kg": 1,250 or 1.25)
  and is asked about.
- A comma is never read silently (review finding P6): a Finnish buyer's "1,250" means 1.25. The reading says how
  it was read (`comma_note`): before exactly three digits as thousands (the brief's own "1,000 litres"), before
  one or two digits as a decimal comma, as Finnish writes it ("1,5 l").
- A number that starts with 0 is a decimal: "0.100" and "0,250" are never thousands.
- Digits joined by a space right after a word that is not a plain order word ("Ward 4 200 litres") may be two
  numbers, and are asked about. A group of "000" can only be thousands ("milk 1 000 l").
- A small unit (dl, cl, ml, g) is not read: the question offers its conversion to litres or kilograms.
- A number with a minus is never read as the number without it (review C4-F9: "-5 litres of milk" was read as 5
  litres): a sign right before the digits ("-5"; the minus sign itself also with a space, "− 5"), or the word
  "minus". A dash after a letter or a digit is a hyphen or a range ("lactose-free", "10-12"), and a dash followed
  by a space is a list mark ("- 5 litres of milk"): neither is a minus.
"""

from __future__ import annotations

import re
from decimal import Decimal

from tta.agent.textcheck import DIGIT_RUN, SEPARATOR, SMALL_UNITS, SPACES, all_thousands
from tta.agent.unread import NotReadByRules
from tta.contracts.common import Unit
from tta.contracts.request import MAX_QUANTITY, MAX_QUANTITY_DECIMALS

ONE_SEPARATOR_GROUPS = 2  # "1.5": the digits on either side of one separator
THOUSANDS_DIGITS = 3
ONLY_THOUSANDS = "000"  # a group that cannot be a quantity of its own
UNIT_NAMES = {Unit.L: "litres", Unit.KG: "kilograms"}

UNREADABLE_NUMBER = "line {line} gives a quantity that is not read as one number ({run})"
ASK_PLAIN_DIGITS = "What is the quantity? Write it in plain digits, for example 1500 or 1,5."
TWO_READINGS = 'line {line} gives "{run}", which can be read two ways'
ASK_WHICH_READING = "Is it {thousands:,} or {decimal}? Write {plain} for the first, or {comma} for the second."
OUT_OF_RANGE = "line {line} asks for a quantity above zero, at most {most:,} with at most {places} decimals"
ASK_IN_RANGE = "What quantity is needed? Write a number above zero in litres, kilograms or packs."
SPLIT_NUMBER = 'it gives "{run}" right after "{word}", which can be one number or two'
ASK_SPLIT = "Is the quantity {joined:,}, or {last}? Write it without a space, for example {joined}."
COMMA_IS_THOUSANDS = (
    '"{run}" is read as {value} (a comma before three digits groups thousands here); for {decimal} write '
    '"{decimal}".'
)
COMMA_IS_DECIMAL = '"{run}" is read as {value} (a comma before one or two digits is a decimal comma).'
SMALL_UNIT = 'it gives a quantity in "{word}", a unit the rules do not read ("{said}")'
ASK_CONVERTED = '"{said}" is {converted} {unit}. Is that the quantity? Then write "{converted} {unit}".'
ASK_LARGER_UNIT = "What is the quantity in litres, kilograms or packs?"
# A hyphen, the minus sign, an en dash and a figure dash typed for one.
MINUS_SIGNS = ("-", "\u2212", "\u2013", "\u2012")
TRUE_MINUS = "\u2212"  # nobody marks a list with the minus sign: it is a minus with a space after it too
MINUS_WORDS = frozenset({"minus", "negative", "miinus"})
BELOW_ZERO = 'it gives a number with a minus sign ("{said}"), and a quantity to order is above zero'
NOTHING_TAKEN_BACK = (
    "Nothing was ordered: the rules only read what is needed now, never a return or a change to an earlier order."
)
ASK_ABOVE_ZERO = 'Is {plain} meant? Then write "{plain}" without the minus sign. ' + NOTHING_TAKEN_BACK
ASK_WHAT_IS_BELOW_ZERO = (
    'What does "{said}" stand for? Write each quantity above zero with its unit, for example 200 litres. '
    + NOTHING_TAKEN_BACK
)


def plain(value: Decimal) -> str:
    """The number without trailing zeros and never with an exponent: 0.100 is "0.1", 1000 stays "1000"."""
    return f"{value.normalize():f}"


def quantity(digits: str, line: int) -> Decimal:
    """The number the digits give by the rules above. Raises `NotReadByRules` with a question otherwise."""
    groups, separators = SEPARATOR.split(digits), SEPARATOR.findall(digits)
    one_decimal_mark = len(separators) == 1 and separators[0] in ".,"
    if not separators:
        value = Decimal(digits)
    elif groups[0].startswith("0"):  # "0.100": a number that starts with 0 has no thousands group
        if not one_decimal_mark:
            raise NotReadByRules(UNREADABLE_NUMBER.format(line=line, run=digits), ASK_PLAIN_DIGITS)
        value = Decimal(f"{groups[0]}.{groups[1]}")
    elif one_decimal_mark and separators[0] == "." and len(groups[1]) == THOUSANDS_DIGITS:
        raise _two_readings(digits, groups, line)
    elif all_thousands(groups):
        value = Decimal("".join(groups))
    elif separators[-1] in ".," and (len(groups) == ONE_SEPARATOR_GROUPS or all_thousands(groups[:-1])):
        value = Decimal(f"{''.join(groups[:-1])}.{groups[-1]}")
    else:
        raise NotReadByRules(UNREADABLE_NUMBER.format(line=line, run=digits), ASK_PLAIN_DIGITS)
    value = Decimal(plain(value))
    exponent = value.as_tuple().exponent
    places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if not Decimal(0) < value <= MAX_QUANTITY or places > MAX_QUANTITY_DECIMALS:
        why = OUT_OF_RANGE.format(line=line, most=MAX_QUANTITY, places=MAX_QUANTITY_DECIMALS)
        raise NotReadByRules(why, ASK_IN_RANGE)
    return value


def _two_readings(digits: str, groups: list[str], line: int) -> NotReadByRules:
    thousands, decimal = int("".join(groups)), plain(Decimal(f"{groups[0]}.{groups[1]}"))
    ask = ASK_WHICH_READING.format(
        thousands=thousands, decimal=decimal, plain=thousands, comma=decimal.replace(".", ",")
    )
    return NotReadByRules(TWO_READINGS.format(line=line, run=digits), ask)


def comma_readings(text: str) -> list[tuple[str, Decimal, bool]]:
    """Each number of the text written with one comma, as written, with the number it is read as and whether the
    comma was read as grouping thousands ("1,250": 1250) or as a decimal comma ("1,5": 1.5; "0,250": 0.25). A
    number the rules do not read is left out."""
    found = []
    for run in DIGIT_RUN.findall(text):
        if SEPARATOR.findall(run) != [","]:
            continue
        whole, rest = run.split(",")
        try:
            value = quantity(run, 1)
        except NotReadByRules:
            continue
        found.append((run, value, len(rest) == THOUSANDS_DIGITS and not whole.startswith("0")))
    return found


def comma_note(run: str, value: Decimal, thousands: bool) -> str:
    """The sentence that says how a comma was read (review finding P6): never silently."""
    if not thousands:
        return COMMA_IS_DECIMAL.format(run=run, value=plain(value))
    decimal = plain(Decimal(run.replace(",", ".")))
    return COMMA_IS_THOUSANDS.format(run=run, value=plain(value), decimal=decimal)


def refuse_a_split_number(run: str, word_before: str | None, plain_words: frozenset[str]) -> None:
    """"Ward 4 200 litres": digits joined by a space, right after a word that is not a plain order word."""
    groups = re.split(f"[{SPACES}]", run)
    if len(groups) == 1 or word_before is None or word_before in plain_words:
        return
    if all(group == ONLY_THOUSANDS for group in groups[1:]):
        return
    joined = "".join(SEPARATOR.split(run))
    if not joined.isdigit():
        return  # a decimal mark too: `quantity` reads or refuses it
    ask = ASK_SPLIT.format(joined=int(joined), last=groups[-1])
    raise NotReadByRules(SPLIT_NUMBER.format(run=run, word=word_before), ask)


def small_unit(digits: str, word: str) -> NotReadByRules:
    """The question for "5 dl": the unit is not read, and the conversion is offered when the digits are plain."""
    unit, per_larger = SMALL_UNITS[word]
    said = f"{digits} {word}"
    try:
        converted = quantity(digits, 1) / per_larger
    except NotReadByRules:
        return NotReadByRules(SMALL_UNIT.format(word=word, said=said), ASK_LARGER_UNIT)
    ask = ASK_CONVERTED.format(said=said, converted=plain(converted), unit=UNIT_NAMES[unit])
    return NotReadByRules(SMALL_UNIT.format(word=word, said=said), ask)


def below_zero(said: str, digits: str, unit_word: str | None) -> NotReadByRules:
    """The question for "-5 litres": the number is not read without its minus. `said` is the minus and the number
    as written; `unit_word` the unit word after the digits, if any."""
    said = " ".join(said.split())
    if unit_word is None:
        return NotReadByRules(BELOW_ZERO.format(said=said), ASK_WHAT_IS_BELOW_ZERO.format(said=said))
    said = f"{said} {unit_word}"
    return NotReadByRules(BELOW_ZERO.format(said=said), ASK_ABOVE_ZERO.format(plain=f"{digits} {unit_word}"))
