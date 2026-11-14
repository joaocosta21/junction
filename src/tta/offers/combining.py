"""Combining confirmed products into one fill (SPEC section 5, BEST_CONFIRMED). Pure `Decimal` arithmetic.

The cheapest single product that covers the whole quantity; if none does, the cheapest first until the
quantity is covered; if confirmed stock still falls short, a partial fill that says how much is missing.
Only confirmed stock is ever a `Supply`: a placeholder amount cannot reach these sums.

A buyer's preference (task SUST-1) gives each supply a tier, 0 the best. The fill then uses the products of the
best tier alone if they can cover the quantity, else those of the two best tiers, and so on; within that set the
rule above holds with the tier before the price. Under price every supply has tier 0: the rule above, unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
    tier: int = 0  # rank of the product's value for the buyer's preference, 0 the best (task SUST-1)

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
    """Cover `requested` from the best tiers that can: one product if one can, else in tier and price order."""
    result = Fill(requested)
    for tier in sorted({supply.tier for supply in supplies}):
        result = _fill_from(requested, [supply for supply in supplies if supply.tier <= tier])
        if result.missing <= 0:
            return result
    return result


def _fill_from(requested: Decimal, supplies: Sequence[Supply]) -> Fill:
    alone = [supply for supply in supplies if units_for(requested, supply) <= supply.usable]
    if alone:
        best = min(
            alone, key=lambda supply: (supply.tier, units_for(requested, supply) * supply.unit_price, supply.product_id)
        )
        return Fill(requested, (Pick(best.product_id, units_for(requested, best), requested),))
    return _combine(requested, supplies)


def _combine(requested: Decimal, supplies: Sequence[Supply]) -> Fill:
    picks: list[Pick] = []
    remaining = requested
    for supply in sorted(supplies, key=lambda each: (each.tier, each.price_per_requested_unit, each.product_id)):
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


def with_picks(used: Mapping[str, Decimal], picked: Fill) -> Mapping[str, Decimal]:
    """Sales units taken per product, with the picks of one more fill added."""
    added = {pick.product_id: used.get(pick.product_id, Decimal(0)) + pick.units for pick in picked.picks}
    return {**used, **added}
