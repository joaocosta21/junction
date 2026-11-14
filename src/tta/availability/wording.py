"""Plain-English formatting shared by the state sentences and the claim sentences.

Day and month names are fixed here, so a sentence never depends on the locale of the machine.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from tta.contracts.availability import PriceAmount
from tta.contracts.common import CURRENCY_EUR, MONEY_PLACES

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
EURO_SIGN = "€"
# An open-ended price carries validTo 9999-12-31 (AIMO/docs/API.md section 8.9).
OPEN_ENDED_YEAR = 9999


def format_day(value: date) -> str:
    """`Monday 16 Nov`."""
    return f"{WEEKDAYS[value.weekday()]} {value.day} {MONTHS[value.month - 1]}"


def format_moment(value: datetime) -> str:
    """`Thursday 12 Nov at 15:00`, in the offset Valio gave (Helsinki time, AIMO/docs/API.md section 6.1)."""
    return f"{format_day(value.date())} at {value:%H:%M}"


def format_validity(value: datetime) -> str:
    """`31 Dec 2026 at 00:00`: a price validity can be months away, so it names the year."""
    return f"{value.day} {MONTHS[value.month - 1]} {value.year} at {value:%H:%M}"


def is_open_ended(valid_to: datetime) -> bool:
    return valid_to.year == OPEN_ENDED_YEAR


def format_amount(value: Decimal) -> str:
    """`384`, `9,999,999,999`, `12.5`: a whole number shows no decimals."""
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return f"{value.normalize():,f}"


def format_price(amount: PriceAmount) -> str:
    """`€2.48`, or `2.48 SEK` for another currency. Never rounds: extra decimals of the API value are kept."""
    exact = amount.value.normalize()
    places = max(MONEY_PLACES, -int(exact.as_tuple().exponent))
    figure = f"{exact:,.{places}f}"
    return f"{EURO_SIGN}{figure}" if amount.currency == CURRENCY_EUR else f"{figure} {amount.currency}"
