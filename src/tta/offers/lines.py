"""Offer lines and what is summed from them: totals, coverage, validity (SPEC section 5, step 4)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from tta.contracts.common import round_money
from tta.contracts.offer import Coverage, OfferLine, SubstituteInfo, Totals
from tta.contracts.request import RequestLine
from tta.offers.candidates import Candidate, Need, claims_of

PERCENT = Decimal(100)
ZERO = Decimal(0)


def line_for(
    candidate: Candidate,
    need: Need,
    units: Decimal,
    covers: Decimal,
    now: datetime,
    substitute: SubstituteInfo | None = None,
) -> OfferLine:
    """`units` sales units of the candidate, with the statements the offer relies on and all five claims."""
    net = round_money(units * candidate.unit_price)
    tax = _tax(candidate, units, net)
    product = candidate.product
    return OfferLine(
        product_id=product.id,
        name=product.display_name,
        vendor_name=product.vendor_name,
        category=product.category,
        request_line_index=need.index,
        quantity=units,
        sales_unit=candidate.sales_unit,
        pack_size=candidate.pack,
        covers=covers,
        unit_net_price=candidate.unit_price,
        tax_rate=candidate.price.tax_rate if candidate.price is not None else None,
        net=net,
        tax=tax,
        gross=net + tax,
        price_valid_to=_price_valid_to(candidate),
        availability=candidate.assessment,
        claims=claims_of(candidate, need, units, now),
        allergen_check=candidate.allergen_check,
        variable_weight=product.variable_weight,  # None stays None: a missing fact for the policy
        has_deposits=product.has_deposits,
        country_of_origin=product.country_of_origin,
        substitute=substitute,
    )


def totals_of(lines: Sequence[OfferLine]) -> Totals:
    """Sums of the rounded lines, so the lines a person reads add up to the total."""
    net = sum((line.net for line in lines), ZERO)
    tax = sum((line.tax for line in lines), ZERO)
    return Totals(
        net=net,
        tax=tax,
        gross=net + tax,
        excludes_deposits=any(line.has_deposits for line in lines),
        # Variable weight: the price is per kilogram and the weight delivered can be lower, never higher.
        is_ceiling=any(line.variable_weight is True for line in lines),
    )


def coverage_of(request_lines: Sequence[RequestLine], lines: Sequence[OfferLine]) -> tuple[Coverage, ...]:
    """One entry per request line: how much of what was asked the option's lines cover."""
    return tuple(_coverage(index, asked, lines) for index, asked in enumerate(request_lines))


def lowest_fill_ratio(coverage: Sequence[Coverage]) -> Decimal:
    return min((entry.fill_ratio for entry in coverage), default=ZERO)


def valid_until_of(lines: Sequence[OfferLine]) -> datetime | None:
    """The earliest price validity and order cut-off of the lines: after it the option cannot be ordered."""
    moments = [line.price_valid_to for line in lines] + [line.availability.closing_time for line in lines]
    return min((moment for moment in moments if moment is not None), default=None)


def _tax(candidate: Candidate, units: Decimal, net: Decimal) -> Decimal:
    price = candidate.price
    if price is not None and price.tax_rate is not None:
        return round_money(net * price.tax_rate / PERCENT)  # `tax.taxRate` of the price answer, in percent
    if price is not None and price.catalog_price is not None:
        # No rate on the line: the tax is the difference between the two prices Valio states.
        return round_money(units * (price.catalog_price.value_with_tax - price.catalog_price.value))
    return ZERO


def _price_valid_to(candidate: Candidate) -> datetime | None:
    price = candidate.price
    return price.catalog_price.valid_to if price is not None and price.catalog_price is not None else None


def _coverage(index: int, asked: RequestLine, lines: Sequence[OfferLine]) -> Coverage:
    covered = sum((line.covers for line in lines if line.request_line_index == index), ZERO)
    return Coverage(
        request_line_index=index,
        requested=asked.quantity,
        covered=covered,
        unit=asked.unit,
        fill_ratio=covered / asked.quantity,
        missing=asked.quantity - covered,
    )
