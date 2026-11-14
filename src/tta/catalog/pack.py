"""Pack size in litres or kilograms per sales unit, and the portion-pack detector (SPEC section 3, steps 5 and 6).

Three sources, in this order: the live price ratio, the unit-conversion row of the product file,
the product name. The answer says which one it came from, or that the size is unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from tta.catalog.sizes import InnerUnit, conversion_size, inner_unit, name_size
from tta.contracts.availability import PriceLine
from tta.contracts.common import QUANTITY_PLACES, PackSizeSource, Unit
from tta.contracts.product import PackSize, Product

# A single-serve pack: an inner unit of 5 cl or 50 g or less (SPEC section 3, step 6). Our threshold.
PORTION_MAX_LITRES = Decimal("0.05")
PORTION_MAX_KG = Decimal("0.05")

# Prices have two decimals, so a comparison price is exact to half a cent (AIMO/FINDINGS.md section 4).
HALF_CENT = Decimal("0.005")
_RATIO_QUANTUM = Decimal(1).scaleb(-QUANTITY_PLACES)
_MEASURES = (Unit.L, Unit.KG)
_PORTION_LIMITS = ((Unit.L, PORTION_MAX_LITRES), (Unit.KG, PORTION_MAX_KG))


@dataclass(frozen=True, slots=True)
class PriceRatio:
    """`catalogPrice / comparisonPrice`, and the sizes the rounded comparison price is consistent with."""

    value: Decimal
    low: Decimal
    high: Decimal

    def allows(self, size: Decimal) -> bool:
        return self.low <= size <= self.high


def pack_size(product: Product, price: PriceLine | None, unit: Unit) -> PackSize:
    """Litres (`L`) or kilograms (`KG`) per sales unit. For `UNIT`: whichever measure a source gives first.

    A weight is never turned into a volume or the other way round.
    """
    for measure in _measures_for(price, unit):
        found = _pack_size_in(product, price, measure)
        if found.is_known:
            return found
    return PackSize()


def is_portion_pack(product: Product) -> bool:
    """True when one sales unit holds several inner units of 5 cl or 50 g or less, like 100 x 2 cl.

    Read from the product file alone. A small item sold on its own (a 30 g spice jar) is not a pack of
    portions, and a product whose inner size is not known is not reported as one.
    """
    for measure, limit in _PORTION_LIMITS:
        inner = inner_unit(product, measure)
        if inner is not None and inner.count > 1 and inner.size <= limit:
            return True
    return False


def price_ratio(price: PriceLine | None, measure: Unit) -> PriceRatio | None:
    """The size the live price implies, or `None` without a comparison price in this measure."""
    if price is None or not price.has_price or price.catalog_price is None or price.comparison_price is None:
        return None
    if (price.comparison_unit or "").upper() != measure.value:
        return None
    catalog, comparison = price.catalog_price.value, price.comparison_price.value
    if catalog <= 0 or comparison <= HALF_CENT:
        return None
    value = (catalog / comparison).quantize(_RATIO_QUANTUM, rounding=ROUND_HALF_UP)
    if value <= 0:
        return None
    return PriceRatio(value=value, low=catalog / (comparison + HALF_CENT), high=catalog / (comparison - HALF_CENT))


def _measures_for(price: PriceLine | None, unit: Unit) -> tuple[Unit, ...]:
    if unit in _MEASURES:
        return (unit,)
    compared = (price.comparison_unit or "").upper() if price is not None else ""
    return tuple(sorted(_MEASURES, key=lambda measure: measure.value != compared))  # the price's measure first


def _pack_size_in(product: Product, price: PriceLine | None, measure: Unit) -> PackSize:
    inner = inner_unit(product, measure)
    from_conversion = conversion_size(product, measure)
    from_name = name_size(product, measure)
    ratio = price_ratio(price, measure)
    if ratio is not None:
        # The ratio of two rounded prices is itself rounded (9.943 for a 10-litre box). When the file's
        # own figure is one the prices are consistent with, that figure is the size; otherwise the ratio.
        stated = next((size for size in (from_conversion, from_name) if size is not None and ratio.allows(size)), None)
        return _known(ratio.value if stated is None else stated, measure, PackSizeSource.PRICE_RATIO, inner)
    if from_conversion is not None:
        return _known(from_conversion, measure, PackSizeSource.UNIT_CONVERSION, inner)
    if from_name is not None:
        return _known(from_name, measure, PackSizeSource.NAME, inner)
    return PackSize()


def _known(value: Decimal, measure: Unit, source: PackSizeSource, inner: InnerUnit | None) -> PackSize:
    return PackSize(
        value=value,
        unit=measure,
        source=source,
        inner_units=inner.count if inner is not None else None,
        inner_unit_size=inner.size if inner is not None else None,
    )
