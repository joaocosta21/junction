"""Numbers and words shared by the suggestions' sentences. Plain English, with the number and the reason."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from tta.contracts.common import QUANTITY_PLACES, Unit, round_money

UNIT_WORDS = {Unit.L: "L", Unit.KG: "kg", Unit.UNIT: "units"}
MEASURE_WORDS = {Unit.L: "litre", Unit.KG: "kg"}
SYNTHETIC_TAIL = "From a synthetic order history."
CONFIRM_IT = "Confirm it before it is ordered."
CONFIRM_THE_QUANTITY = "Confirm the quantity before it is ordered."
_QUANTUM = Decimal(1).scaleb(-QUANTITY_PLACES)
_PERCENT = Decimal(100)


def middle(values: Sequence[Decimal]) -> Decimal:
    """The median, rounded half up to the three decimals a request line takes."""
    return Decimal(median(values)).quantize(_QUANTUM, rounding=ROUND_HALF_UP)


def number(value: Decimal) -> str:
    """100, 1.5, 1,000: no trailing zeros, no exponent."""
    return f"{value.normalize():,f}"


def amount(value: Decimal, unit: Unit) -> str:
    """"10 L", "9 kg", "1 unit"."""
    word = "unit" if unit is Unit.UNIT and value == 1 else UNIT_WORDS[unit]
    return f"{number(value)} {word}"


def euros(value: Decimal) -> str:
    return f"€{round_money(abs(value)):,.2f}"


def percent(ratio: Decimal) -> str:
    """+20%, -17%."""
    whole = (ratio * _PERCENT).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{'+' if whole > 0 else ''}{whole}%"


def day(value: date) -> str:
    """Monday 16 November."""
    return f"{value:%A} {value.day} {value:%B}"


def type_words(product_type: str) -> str:
    """plant_drink: "plant drink"."""
    return product_type.replace("_", " ")


def sentence(*parts: str) -> str:
    """The parts that say something, one space apart."""
    return " ".join(part for part in parts if part)


def tail(synthetic: bool) -> str:
    return SYNTHETIC_TAIL if synthetic else ""


# --- short names, prices and stock as a person says them (every kind's sentence) -------------------------------

# The first pack size of a product name ("1 L", "0,5L", "100x2 cl", "5KG") and all that follows it: the pack and
# its treatment ("1 L UHT lactose free Suomesta"). The words before it are the brand and the product.
_PACK_AND_AFTER = re.compile(r"\s+\d+(?:[.,]\d+)?\s*(?:x\s*\d+(?:[.,]\d+)?\s*)?(?:ml|cl|dl|l|kg|g)\b.*$",
                             re.IGNORECASE)
_MIN_SHORT_WORDS = 2
PACKS = "packs"  # the sales unit in words: its codes (ST, KI) are not documented (AIMO/docs/SCHEMA-AND-CODES.md 2.11)


def short_name(name: str) -> str:
    """ "Arla Pro Cooking cream 10% 1 L UHT lactose free" reads "Arla Pro Cooking cream 10%": the words before the
    first pack size. The whole name when it states no size or fewer than two words are left."""
    short = _PACK_AND_AFTER.sub("", name).rstrip(" ,;-")
    return short if len(short.split()) >= _MIN_SHORT_WORDS else name


def short_label(name: str | None, product_id: str) -> str:
    """ "Arla Pro Cooking cream 10% (463797)"; "product 463797" when no name is known."""
    return f"{short_name(name)} ({product_id})" if name else f"product {product_id}"


def per_measure(value: Decimal, measure: Unit) -> str:
    """ "€1.48 a litre", "€9.10 a kg"."""
    return f"{euros(value)} a {MEASURE_WORDS[measure]}"


def packs(count: Decimal) -> str:
    """ "1 pack", "20 packs"."""
    return f"{number(count)} pack{'' if count == 1 else 's'}"


def stock_amount(usable: Decimal, per_unit: Decimal | None, unit: Unit) -> str:
    """Confirmed stock in the line's measure when the pack size is known ("114 L"), else in packs ("2 packs")."""
    if unit is not Unit.UNIT and per_unit is not None:
        return amount(usable * per_unit, unit)
    return packs(usable)


def confirmed_words(stock: str, when: date | None) -> str:
    """ "114 L confirmed for Monday 16 November."; without a date "114 L confirmed."."""
    return f"{stock} confirmed for {day(when)}." if when is not None else f"{stock} confirmed."


def more_or_less(change: Decimal) -> str:
    """ "€1.90 more", "€6.00 less", "the same price"."""
    if change == 0:
        return "the same price"
    return f"{euros(change)} {'more' if change > 0 else 'less'}"


def last_tail(said: str, *parts: str) -> str:
    """`said` with `parts` added, and "From a synthetic order history." moved to the end when it is there."""
    if said.endswith(SYNTHETIC_TAIL):
        return sentence(said[: -len(SYNTHETIC_TAIL)].rstrip(), *parts, SYNTHETIC_TAIL)
    return sentence(said, *parts)


# --- the "you usually order this: order again?" prompt (`tta.suggestions.reorder`) -------------------------------

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
DAYS_IN_A_WEEK = 7
NOT_LOOKED_UP = "Prices and stock were not looked up here: the offer checks them."
NO_USUAL_DAY = "Your past orders show no usual delivery day, so the request carries no date."
NOTHING_ORDERED = (
    "Nothing is ordered by this: the request is sent for an offer at today's prices and stock, and a person "
    "confirms it. The offer says whether the total needs anyone beyond the usual confirmation."
)
NOT_IN_REQUEST = "it is not in the ready-made request"


def listed(parts: Sequence[str]) -> str:
    """ "a", "a and b", "a, b and c"."""
    if len(parts) <= 1:
        return "".join(parts)
    return f"{', '.join(parts[:-1])} and {parts[-1]}"


def regular_clause(label: str, quantity: str, counts: tuple[int, int], long_counts: tuple[int, int], *,
                   first: bool, weekly: bool) -> str:
    """ "Arla milk (469363), 100 L, in 4 of your last 4 weekly orders (8 of the last 8)"; after the first product
    the same counts without their words: "in 3 of 4 (6 of 8)". The longer window is said only when it is longer."""
    matching, considered = counts
    longer = long_counts[1] > considered
    if first:
        said = f"in {matching} of your last {considered} {'weekly ' if weekly else ''}orders"
        said += f" ({long_counts[0]} of the last {long_counts[1]})" if longer else ""
    else:
        said = f"in {matching} of {considered}" + (f" ({long_counts[0]} of {long_counts[1]})" if longer else "")
    return f"{label}, {quantity}, {said}"


def reorder_sentence(clauses: Sequence[str], *, last_ordered: date, needed_by: date | None,
                     total: Decimal | None, left_out: int, standing: str, synthetic: bool) -> str:
    """What the prompt says when it has a request to offer. `clauses`: one `regular_clause` per line of the request.
    `total`: None when price and stock were not looked up. `left_out`: regular products the checks kept out.
    `standing`: `on_standing_sentence` of the products a standing order already holds."""
    products = clauses[0] if len(clauses) == 1 else f"{', '.join(clauses[:-1])}, and {clauses[-1]}"
    ask = f"Order the same again for {day(needed_by)}?" if needed_by is not None else (
        f"Order the same again? {NO_USUAL_DAY}")
    price = NOT_LOOKED_UP if total is None else f"About {euros(total)} before tax at today's prices."
    out = "" if not left_out else (
        f"{left_out} more regular product{' is' if left_out == 1 else 's are'} not in it, for the "
        f"reason{'' if left_out == 1 else 's'} listed.")
    return sentence(f"You ordered {products}, most recently on {day(last_ordered)}.", ask, price, out, standing,
                    tail(synthetic))


def no_reorder_sentence(reason: str, *, standing: str = "", synthetic: bool) -> str:
    """What the prompt says when it offers nothing: the reason, then what a standing order already holds."""
    return sentence(f"No order is suggested: {reason}.", standing, tail(synthetic))


def on_standing_sentence(labels: Sequence[str]) -> str:
    """ "Arla milk (469363) is on your standing order, so it is not repeated here."; empty for no product."""
    if not labels:
        return ""
    one = len(labels) == 1
    return (f"{listed(labels)} {'is' if one else 'are'} on your standing order, so "
            f"{'it is' if one else 'they are'} not repeated here.")


def weekday_name(weekday: int) -> str:
    return WEEKDAYS[weekday]
