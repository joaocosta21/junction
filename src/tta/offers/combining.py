"""Combining confirmed products into one fill (SPEC section 5, BEST_CONFIRMED). Pure `Decimal` arithmetic.

The cheapest single product that covers the whole quantity; if none does, the cheapest first until the
quantity is covered; if confirmed stock still falls short, a partial fill that says how much is missing.
Only confirmed stock is ever a `Supply`: a placeholder amount cannot reach these sums.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal


@dataclass(frozen=True)
class Supply:
    """One confirmed product as the combiner sees it."""

    product_id: str
    per_unit: Decimal  # how much of the request's unit one sales unit holds (1 for a request in sales units)
    unit_price: Decimal  # net, per sales unit
    usable: Decimal  # confirmed stock, in sales units
    lot_step: Decimal  # a quantity moves in multiples of this, in sales units

    @property
    def price_per_requested_unit(self) -> Decimal:
        return self.unit_price / self.per_unit


@dataclass(frozen=True)
class Pick:
    product_id: str
    units: Decimal  # sales units, a multiple of the lot step
    covers: Decimal  # in the request's unit; never more than was still missing


@dataclass(frozen=True)
class Fill:
    requested: Decimal
    picks: tuple[Pick, ...] = ()

    @property
    def covered(self) -> Decimal:
        return sum((pick.covers for pick in self.picks), Decimal(0))

    @property
    def missing(self) -> Decimal:
        return self.requested - self.covered


def ceil_to_step(quantity: Decimal, step: Decimal) -> Decimal:
    """The smallest multiple of `step` that is not below `quantity`."""
    return int((quantity / step).to_integral_value(rounding=ROUND_CEILING)) * step


def floor_to_step(quantity: Decimal, step: Decimal) -> Decimal:
    """The largest multiple of `step` that is not above `quantity`."""
    return int((quantity / step).to_integral_value(rounding=ROUND_FLOOR)) * step


def units_for(quantity: Decimal, supply: Supply) -> Decimal:
    """Sales units that cover `quantity` of the request's unit, rounded up to the lot step."""
    return ceil_to_step(quantity / supply.per_unit, supply.lot_step)


def fill(requested: Decimal, supplies: Sequence[Supply]) -> Fill:
    """Cover `requested` from the supplies given: one product if one can, else the cheapest first."""
    alone = [supply for supply in supplies if units_for(requested, supply) <= supply.usable]
    if alone:
        cheapest = min(alone, key=lambda supply: (units_for(requested, supply) * supply.unit_price, supply.product_id))
        return Fill(requested, (Pick(cheapest.product_id, units_for(requested, cheapest), requested),))
    return _combine(requested, supplies)


def _combine(requested: Decimal, supplies: Sequence[Supply]) -> Fill:
    picks: list[Pick] = []
    remaining = requested
    for supply in sorted(supplies, key=lambda each: (each.price_per_requested_unit, each.product_id)):
        if remaining <= 0:
            break
        # Stock off the lot step cannot be ordered: 10 kg in stock with a 3 kg step gives 9 kg.
        units = min(units_for(remaining, supply), floor_to_step(supply.usable, supply.lot_step))
        if units <= 0:
            continue
        covers = min(units * supply.per_unit, remaining)
        picks.append(Pick(supply.product_id, units, covers))
        remaining -= covers
    return Fill(requested, tuple(picks))
