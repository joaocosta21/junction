"""`revalidate`: fresh price and availability for an option's lines, and what changed (SPEC section 8).

The re-check before an order is placed. It asks the supplier again (`fresh=True`): a cached answer
cannot show that a price or a stock figure changed. Rule F-04 reads the result.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from tta.availability import classify
from tta.availability.wording import format_amount, format_moment, format_validity
from tta.contracts.availability import (
    AvailabilityAssessment,
    PriceLine,
    RevalidationChange,
    RevalidationResult,
)
from tta.contracts.common import CURRENCY_EUR, AvailabilityState
from tta.contracts.offer import OfferLine, OfferOption
from tta.offers.deps import OfferDeps, look_up
from tta.offers.wording import eur

FIELD_PRICE = "price"
FIELD_PRICE_VALIDITY = "price_validity"
FIELD_STATE = "availability_state"
FIELD_AMOUNT = "available_amount"
FIELD_CUTOFF = "cutoff"
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


def _money(value: Decimal, currency: str) -> str:
    return eur(value) if currency == CURRENCY_EUR else f"{value} {currency}"


def _price_changes(line: OfferLine, price: PriceLine | None, now: datetime) -> Found:
    before = eur(line.unit_net_price)
    amount = price.catalog_price if price is not None and price.has_price else None
    if amount is None:
        sentence = f"Valio no longer returns a price for {line.name}; the offer stated {before}."
        return [_change(line, FIELD_PRICE, before, NO_PRICE, sentence)], False
    changes: list[RevalidationChange] = []
    if amount.value != line.unit_net_price or amount.currency != CURRENCY_EUR:
        after = _money(amount.value, amount.currency)
        sentence = f"The price of {line.name} changed from {before} to {after} per {line.sales_unit}."
        changes.append(_change(line, FIELD_PRICE, before, after, sentence))
    stated = format_validity(line.price_valid_to) if line.price_valid_to is not None else NOT_STATED
    if amount.valid_to <= now:
        sentence = f"The price of {line.name} was valid until {format_validity(amount.valid_to)}, which has passed."
        return [*changes, _change(line, FIELD_PRICE_VALIDITY, stated, ENDED, sentence)], True
    if amount.valid_to != line.price_valid_to:
        after = format_validity(amount.valid_to)
        sentence = f"The price of {line.name} is now valid until {after}; the offer stated {stated}."
        changes.append(_change(line, FIELD_PRICE_VALIDITY, stated, after, sentence))
    return changes, False


def _supply_changes(lines: Sequence[OfferLine], fresh: AvailabilityAssessment) -> Found:
    """`lines` are the option's lines of one product; their quantities are checked against the stock together."""
    line = lines[0]
    stated = line.availability
    cutoff = format_moment(stated.closing_time) if stated.closing_time is not None else NOT_STATED
    if fresh.state is AvailabilityState.CUTOFF_PASSED:
        sentence = f"The order cut-off of {line.name} passed on {cutoff}, so its delivery can no longer be ordered."
        return [_change(line, FIELD_CUTOFF, cutoff, PASSED, sentence)], True
    if fresh.state is not stated.state:
        before, after = _state_words(stated.state), _state_words(fresh.state)
        sentence = f"The availability of {line.name} changed from {before} to {after}. {fresh.sentence}"
        return [_change(line, FIELD_STATE, before, after, sentence)], False
    changes: list[RevalidationChange] = []
    if fresh.closing_time != stated.closing_time:
        after = format_moment(fresh.closing_time) if fresh.closing_time is not None else NOT_STATED
        sentence = f"The order cut-off of {line.name} moved from {cutoff} to {after}."
        changes.append(_change(line, FIELD_CUTOFF, cutoff, after, sentence))
    changes.extend(_amount_change(lines, fresh))
    return changes, False


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
        f"Valio now shows {after} of {line.name} in stock, fewer than the {format_amount(needed)} {unit} "
        f"of this option; the offer stated {before}."
    )
    return [_change(line, FIELD_AMOUNT, before, after, sentence)]


def _state_words(state: AvailabilityState) -> str:
    return state.value.replace("_", " ").lower()
