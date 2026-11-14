"""Raw bodies of the Valio mock API become contract models (AIMO/docs/API.md sections 5 to 8).

A body is untrusted input. Every field is checked against the published shape, nothing in it is
executed, and an error names the field that is wrong, never the text that was found in it.
Optional fields are omitted by the API, never `null` (AIMO/docs/API.md section 7); both read as `None`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, NoReturn

from tta.contracts.availability import (
    AvailabilityLine,
    AvailabilityResponse,
    PriceAmount,
    PriceLine,
    PriceResponse,
    ScheduleLine,
)
from tta.contracts.common import DataSource
from tta.contracts.errors import SupplierUnavailable

PRICE_ENDPOINT = "price"
AVAILABILITY_ENDPOINT = "availability"
ENDPOINTS = (AVAILABILITY_ENDPOINT, PRICE_ENDPOINT)

# The widest numbers that are read; an answer with one outside is refused. In the three captures of
# fixtures/valio/ the prices run from 0.3 to 541.5, and the largest amount is the Stock placeholder
# 9,999,999,999 (AIMO/docs/API.md section 8.1).
LOWEST_NUMBER = Decimal(0)
HIGHEST_PRICE = Decimal(1_000_000)  # also the bound of the tax rate and the tax value of a price entry
HIGHEST_AMOUNT = Decimal(100_000_000_000)


def _refuse(what: str) -> NoReturn:
    raise SupplierUnavailable(f"The Valio API answer could not be read: {what}.")


def _no_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not a number")


def load_body(text: str) -> dict[str, Any]:
    """Decode a response body. A number written with a decimal point becomes that exact `Decimal`."""
    try:
        body = json.loads(text, parse_float=Decimal, parse_constant=_no_constant)
    except (ValueError, RecursionError):
        body = None  # refused below, outside the handler: the decoder's error carries the whole text
    if not isinstance(body, dict):
        _refuse("it is not a JSON object")
    return body


def parse_price_body(
    body: Mapping[str, Any], source: DataSource, retrieved_at: datetime | None = None
) -> PriceResponse:
    """One /api/price body. `error` true marks an id for which no price was found."""
    where = "the price answer"
    return PriceResponse(
        currency=_text(body, "currency", where),
        pricing_date=_optional_moment(body, "pricingDate", where),
        lines=tuple(_price_line(entry, f"price entry {number}") for number, entry in _entries(body, where)),
        source=source,
        retrieved_at=retrieved_at,
    )


def parse_availability_body(body: Mapping[str, Any], source: DataSource) -> AvailabilityResponse:
    """One /api/availability body. An unknown id reads like a product that cannot be delivered."""
    where = "the availability answer"
    return AvailabilityResponse(
        time_now=_moment(body, "timeNow", where),
        requested_date=_optional_moment(body, "requestedDate", where),
        lines=tuple(
            _availability_line(entry, f"availability entry {number}") for number, entry in _entries(body, where)
        ),
        source=source,
    )


def _entries(body: Mapping[str, Any], where: str) -> list[tuple[int, Mapping[str, Any]]]:
    products = body.get("products")
    if not isinstance(products, list):
        _refuse(f"{where} has no list in `products`")
    if not all(isinstance(entry, dict) for entry in products):
        _refuse(f"{where} has an entry in `products` that is not an object")
    return list(enumerate(products, start=1))


def _price_line(entry: Mapping[str, Any], where: str) -> PriceLine:
    tax = _optional_object(entry, "tax", where)
    return PriceLine(
        product_id=_text(entry, "productId", where),
        error=_flag(entry, "error", where),
        net_price_found=_flag(entry, "netPriceFound", where),
        catalog_price=_amount(entry, "catalogPrice", where),
        list_price=_amount(entry, "listPrice", where),
        comparison_price=_amount(entry, "comparisonPrice", where),
        comparison_unit=_optional_text(entry, "comparisonUnit", where),
        tax_rate=None if tax is None else _number(tax, "taxRate", f"`tax` of {where}", HIGHEST_PRICE),
        tax_value=None if tax is None else _number(tax, "taxValue", f"`tax` of {where}", HIGHEST_PRICE),
    )


def _amount(entry: Mapping[str, Any], key: str, where: str) -> PriceAmount | None:
    """A `Price` object: `value` excludes tax, `valueWithTax` includes it.

    `priceWithTax` is a different type whose `value` includes tax (AIMO/docs/API.md section 5.4);
    it is not read here.
    """
    price = _optional_object(entry, key, where)
    if price is None:
        return None
    inside = f"`{key}` of {where}"
    return PriceAmount(
        value=_number(price, "value", inside, HIGHEST_PRICE),
        value_with_tax=_number(price, "valueWithTax", inside, HIGHEST_PRICE),
        valid_from=_moment(price, "validFrom", inside),
        valid_to=_moment(price, "validTo", inside),  # open-ended prices say 9999-12-31; kept as it came
        currency=_text(price, "currency", inside),
    )


def _availability_line(entry: Mapping[str, Any], where: str) -> AvailabilityLine:
    return AvailabilityLine(
        product_id=_text(entry, "productId", where),
        sales_block=_flag(entry, "salesBlock", where),
        closing_time=_optional_moment(entry, "closingTime", where),
        logistic_model=_optional_text(entry, "logisticModel", where),
        schedule_line=_schedule_line(entry, where),
    )


def _schedule_line(entry: Mapping[str, Any], where: str) -> ScheduleLine | None:
    lines = entry.get("scheduleLines")
    if not isinstance(lines, list):
        _refuse(f"{where} has no list in `scheduleLines`")
    if not lines:
        return None  # cannot be delivered on any date (AIMO/docs/API.md section 8.4)
    # "If product is available, array has exactly one entry" (AIMO/docs/API.md section 6.2).
    if len(lines) > 1 or not isinstance(lines[0], dict):
        _refuse(f"{where} does not have exactly one object in `scheduleLines`")
    line = lines[0]
    inside = f"the schedule line of {where}"
    return ScheduleLine(
        sales_block=_flag(line, "salesBlock", inside),
        # Raw: 0 and the placeholders included.
        available_amount=_number(line, "availableAmount", inside, HIGHEST_AMOUNT),
        available_date=_optional_day(line, "availableDate", inside),
        sales_unit=_text(line, "salesUnit", inside),  # the API's unit, not the product file's (FINDINGS section 1)
    )


def _optional_object(entry: Mapping[str, Any], key: str, where: str) -> Mapping[str, Any] | None:
    value = entry.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        _refuse(f"{where} has no object in `{key}`")
    return value


def _text(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value:
        _refuse(f"{where} has no text in `{key}`")
    return value


def _optional_text(entry: Mapping[str, Any], key: str, where: str) -> str | None:
    return None if entry.get(key) is None else _text(entry, key, where)


def _flag(entry: Mapping[str, Any], key: str, where: str) -> bool:
    value = entry.get(key)
    if not isinstance(value, bool):
        _refuse(f"{where} has no true or false in `{key}`")
    return value


def _number(entry: Mapping[str, Any], key: str, where: str, highest: Decimal) -> Decimal:
    """A number from 0 to `highest`. One outside that range refuses the answer; the number is not repeated."""
    value = entry.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float | Decimal):
        _refuse(f"{where} has no number in `{key}`")
    number = value if isinstance(value, Decimal) else Decimal(str(value))
    if not number.is_finite():
        _refuse(f"{where} has no finite number in `{key}`")
    if not LOWEST_NUMBER <= number <= highest:
        _refuse(f"{where} has a number outside {LOWEST_NUMBER} to {highest:,} in `{key}`")
    return number


def _moment(entry: Mapping[str, Any], key: str, where: str) -> datetime:
    """A date and time with an offset. The API writes the offset without a colon (`+0200`)."""
    value = entry.get(key)
    try:
        moment = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        moment = None
    if moment is None or moment.utcoffset() is None:
        _refuse(f"{where} has no date and time with an offset in `{key}`")
    return moment


def _optional_moment(entry: Mapping[str, Any], key: str, where: str) -> datetime | None:
    return None if entry.get(key) is None else _moment(entry, key, where)


def _optional_day(entry: Mapping[str, Any], key: str, where: str) -> date | None:
    value = entry.get(key)
    if value is None:
        return None
    try:
        day = date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        day = None
    if day is None:
        _refuse(f"{where} has no date in `{key}`")
    return day
