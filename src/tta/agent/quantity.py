"""The number a buyer's digits give, read by fixed rules, and the numbers that are asked about (replan A2b C2, H3, M1).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": a quantity is never
guessed. Measured in replay on 14 Nov 2026 (the review's runs): "0.100 l" was read as 100 litres and ordered,
"Ward 4 200 litres" as 4,200 litres.
- A comma or a space before three digits groups thousands: "1,000", "1 000". A dot does so only in a longer
  number ("1.000.000"). One dot before exactly three digits can be read two ways ("1.250 kg": 1,250 or 1.25)
  and is asked about.
- A number that starts with 0 is a decimal: "0.100" and "0,250" are never thousands.
- Digits joined by a space right after a word that is not a plain order word ("Ward 4 200 litres") may be two
  numbers, and are asked about. A group of "000" can only be thousands ("milk 1 000 l").
- A small unit (dl, cl, ml, g) is not read: the question offers its conversion to litres or kilograms.
"""

from __future__ import annotations

import re
from decimal import Decimal

from tta.agent.textcheck import SEPARATOR, SMALL_UNITS, SPACES, all_thousands
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
SMALL_UNIT = 'it gives a quantity in "{word}", a unit the rules do not read ("{said}")'
ASK_CONVERTED = '"{said}" is {converted} {unit}. Is that the quantity? Then write "{converted} {unit}".'
ASK_LARGER_UNIT = "What is the quantity in litres, kilograms or packs?"


def _plain(value: Decimal) -> str:
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
    value = Decimal(_plain(value))
    exponent = value.as_tuple().exponent
    places = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if not Decimal(0) < value <= MAX_QUANTITY or places > MAX_QUANTITY_DECIMALS:
        why = OUT_OF_RANGE.format(line=line, most=MAX_QUANTITY, places=MAX_QUANTITY_DECIMALS)
        raise NotReadByRules(why, ASK_IN_RANGE)
    return value


def _two_readings(digits: str, groups: list[str], line: int) -> NotReadByRules:
    thousands, decimal = int("".join(groups)), _plain(Decimal(f"{groups[0]}.{groups[1]}"))
    ask = ASK_WHICH_READING.format(
        thousands=thousands, decimal=decimal, plain=thousands, comma=decimal.replace(".", ",")
    )
    return NotReadByRules(TWO_READINGS.format(line=line, run=digits), ask)


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
    ask = ASK_CONVERTED.format(said=said, converted=_plain(converted), unit=UNIT_NAMES[unit])
    return NotReadByRules(SMALL_UNIT.format(word=word, said=said), ask)
