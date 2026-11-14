"""`revalidate`: fresh price and availability for an option's lines, and what changed (SPEC section 8).

The re-check before an order is placed. It asks the supplier again (`fresh=True`): a cached answer
cannot show that a price or a stock figure changed. Rule F-04 reads the result.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from tta.availability import classify
from tta.availability.wording import format_amount, format_day, format_moment, format_validity
from tta.contracts.availability import (
    AvailabilityAssessment,
    PriceLine,
    RevalidationChange,
    RevalidationResult,
)
from tta.contracts.common import CURRENCY_EUR, AvailabilityState
from tta.contracts.offer import OfferLine, OfferOption
from tta.offers.deps import OfferDeps, look_up
from tta.offers.wording import eur, plain_name

FIELD_PRICE = "price"
FIELD_PRICE_VALIDITY = "price_validity"
FIELD_TAX_RATE = "tax_rate"
FIELD_STATE = "availability_state"
FIELD_AMOUNT = "available_amount"
FIELD_CUTOFF = "cutoff"
FIELD_DELIVERY_DATE = "delivery_date"
FIELD_SALES_UNIT = "sales_unit"
NO_PRICE = "no price"
ENDED = "ended"
PASSED = "passed"
NOT_STATED = "not stated"

Found = tuple[list[RevalidationChange], bool]  # the changes, and whether something has expired


def revalidate(option: OfferOption, deps: OfferDeps) -> RevalidationResult:
    """Compare what the option stated with a fresh answer. `ok` only when nothing changed and nothing expired."""
    lookup = look_up(deps, option.product_ids, fresh=True)
    now = lookup.now
    changes: list[RevalidationChange] = []
    # A moment equal to now has passed, as for a cut-off (AIMO/docs/API.md section 8.7).
    expired = option.valid_until is not None and option.valid_until <= now
    for product_id in dict.fromkeys(option.product_ids):
        lines = [line for line in option.lines if line.product_id == product_id]
        price_changes, price_expired = _price_changes(lines[0], lookup.price(product_id), now)
        supply_changes, supply_expired = _supply_changes(lines, classify(lookup.line(product_id), now))
        changes.extend((*price_changes, *supply_changes))
        expired = expired or price_expired or supply_expired
    return RevalidationResult(
        ok=not expired and not changes, expired=expired, changes=tuple(changes), checked_at=now, source=lookup.source
    )


def _change(line: OfferLine, field: str, before: str, after: str, sentence: str) -> RevalidationChange:
    return RevalidationChange(product_id=line.product_id, field=field, before=before, after=after, sentence=sentence)


def _name(line: OfferLine) -> str:
    """The product's name as a sentence may carry it: the stored line holds it as the product file has it."""
    return plain_name(line.name)


def _money(value: Decimal, currency: str) -> str:
    return eur(value) if currency == CURRENCY_EUR else f"{value} {currency}"


def _price_changes(line: OfferLine, price: PriceLine | None, now: datetime) -> Found:
    before = eur(line.unit_net_price)
    amount = price.catalog_price if price is not None and price.has_price else None
    if price is None or amount is None:
        sentence = f"Valio no longer returns a price for {_name(line)}; the offer stated {before}."
        return [_change(line, FIELD_PRICE, before, NO_PRICE, sentence)], False
    changes: list[RevalidationChange] = []
    if amount.value != line.unit_net_price or amount.currency != CURRENCY_EUR:
        after = _money(amount.value, amount.currency)
        sentence = f"The price of {_name(line)} changed from {before} to {after} per {line.sales_unit}."
        changes.append(_change(line, FIELD_PRICE, before, after, sentence))
    changes.extend(_tax_rate_change(line, price.tax_rate))
    validity_changes, expired = _validity_change(line, amount.valid_to, now)
    return [*changes, *validity_changes], expired


def _tax_rate_change(line: OfferLine, fresh: Decimal | None) -> list[RevalidationChange]:
    """The gross total of the offer rests on the rate: any other rate, or none, is a change."""
    if fresh == line.tax_rate:
        return []
    before, after = _rate(line.tax_rate), _rate(fresh)
    sentence = f"The tax rate of {_name(line)} changed from {before} to {after}."
    return [_change(line, FIELD_TAX_RATE, before, after, sentence)]


def _rate(value: Decimal | None) -> str:
    return f"{format_amount(value)}%" if value is not None else NOT_STATED


def _validity_change(line: OfferLine, valid_to: datetime, now: datetime) -> Found:
    stated = line.price_valid_to
    before = format_validity(stated) if stated is not None else NOT_STATED
    if valid_to <= now:
        sentence = f"The price of {_name(line)} was valid until {format_validity(valid_to)}, which has passed."
        return [_change(line, FIELD_PRICE_VALIDITY, before, ENDED, sentence)], True
    # A renewed price holds for longer than the offer stated: nothing the order rests on has changed.
    if stated is not None and valid_to >= stated:
        return [], False
    after = format_validity(valid_to)
    sentence = f"The price of {_name(line)} is now valid until {after}; the offer stated {before}."
    return [_change(line, FIELD_PRICE_VALIDITY, before, after, sentence)], False


def _supply_changes(lines: Sequence[OfferLine], fresh: AvailabilityAssessment) -> Found:
    """`lines` are the option's lines of one product; their quantities are checked against the stock together."""
    line = lines[0]
    stated = line.availability
    cutoff = format_moment(stated.closing_time) if stated.closing_time is not None else NOT_STATED
    if fresh.state is AvailabilityState.CUTOFF_PASSED:
        sentence = f"The order cut-off of {_name(line)} passed on {cutoff}, so its delivery can no longer be ordered."
        return [_change(line, FIELD_CUTOFF, cutoff, PASSED, sentence)], True
    if fresh.state is not stated.state:
        before, after = _state_words(stated.state), _state_words(fresh.state)
        sentence = f"The availability of {_name(line)} changed from {before} to {after}. {fresh.sentence}"
        return [_change(line, FIELD_STATE, before, after, sentence)], False
    changes: list[RevalidationChange] = []
    if fresh.closing_time != stated.closing_time:
        after = format_moment(fresh.closing_time) if fresh.closing_time is not None else NOT_STATED
        sentence = f"The order cut-off of {_name(line)} moved from {cutoff} to {after}."
        changes.append(_change(line, FIELD_CUTOFF, cutoff, after, sentence))
    changes.extend(_delivery_date_change(line, fresh.available_date))
    changes.extend(_unit_or_amount_change(lines, fresh))
    return changes, False


def _delivery_date_change(line: OfferLine, fresh: date | None) -> list[RevalidationChange]:
    """A later delivery date is always a change; an earlier one still meets what the offer stated."""
    stated = line.availability.available_date
    if fresh == stated:
        return []
    before = format_day(stated) if stated is not None else NOT_STATED
    after = format_day(fresh) if fresh is not None else NOT_STATED
    if stated is None or fresh is None:
        sentence = f"The delivery date of {_name(line)} changed from {before} to {after}."
        return [_change(line, FIELD_DELIVERY_DATE, before, after, sentence)]
    if fresh < stated:
        return []
    sentence = f"The delivery of {_name(line)} moved from {before} to {after}, later than the offer stated."
    return [_change(line, FIELD_DELIVERY_DATE, before, after, sentence)]


def _unit_or_amount_change(lines: Sequence[OfferLine], fresh: AvailabilityAssessment) -> list[RevalidationChange]:
    line = lines[0]
    if fresh.sales_unit is None or fresh.sales_unit == line.sales_unit:
        return _amount_change(lines, fresh)
    # Price and quantity follow the sales unit of the API line (SPEC section 3, step 7). Stock stated in
    # another unit cannot be compared with the quantity of the option, so only the unit is reported.
    before, after = line.sales_unit, fresh.sales_unit
    sentence = (
        f"The sales unit of {_name(line)} changed from {before} to {after}, so the price and the quantity "
        "of the offer no longer apply."
    )
    return [_change(line, FIELD_SALES_UNIT, before, after, sentence)]


def _amount_change(lines: Sequence[OfferLine], fresh: AvailabilityAssessment) -> list[RevalidationChange]:
    """Stock that moved is a change only when it no longer covers what the option orders.

    The statement the offer relied on is "enough for this line", not the exact figure: stock moves
    with every other buyer's order, and an order must not be refused for a movement that leaves enough.
    """
    line = lines[0]
    needed = sum((each.quantity for each in lines), Decimal(0))
    if fresh.usable_amount is None or fresh.usable_amount >= needed:
        return []
    unit = fresh.sales_unit or line.sales_unit
    stated = line.availability.usable_amount
    before = f"{format_amount(stated)} {unit}" if stated is not None else NOT_STATED
    after = f"{format_amount(fresh.usable_amount)} {unit}"
    sentence = (
        f"Valio now shows {after} of {_name(line)} in stock, fewer than the {format_amount(needed)} {unit} "
        f"of this option; the offer stated {before}."
    )
    return [_change(line, FIELD_AMOUNT, before, after, sentence)]


def _state_words(state: AvailabilityState) -> str:
    return state.value.replace("_", " ").lower()
