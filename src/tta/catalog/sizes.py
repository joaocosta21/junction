"""What the product file itself says about the size of one sales unit, in litres or kilograms.

The logic for litres is Sofia's Friday work (`AIMO/catalog_search.py`, branch `bio1`): the single
unit-conversion row describes the trade item with the Synkka GTIN, so it is used as it is when that
GTIN is the sales unit's and multiplied by the units per sales unit when it is the base unit's; a
size in the name counts only when the name holds exactly one, and a leading "6 x" must agree with
the units per sales unit. Here the same rules also read weights, case rows and "100x2 cl" names.

Checked on 14 Nov against the price ratio of the 1,321 captured price lines (three captures, a
sample, not the catalog) that have a comparison price and are not sold by the kilogram. Where these
rules give a figure, it is within 3% of the ratio on 188 of 190 (litres, conversion row), 486 of 513
(kg, conversion row), 400 of 409 (litres, name) and 771 of 803 (kg, name). Among the misses are
drained weights (466382, feta in brine: 3.39 kg net, priced as 2 kg) and products the API prices
in another unit than the file's (460657).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from tta.contracts.common import Unit
from tta.contracts.product import Product

WEIGHT_SALES_UNIT = "KG"  # one sales unit is one kilogram (AIMO/FINDINGS.md section 4)
BASE_ROW = "BASE_UNIT_OR_EACH"
CASE_ROW = "CASE"

# Units a name can state, as (measure, litres or kg per unit).
_NAME_UNITS: dict[str, tuple[Unit, Decimal]] = {
    "ml": (Unit.L, Decimal("0.001")),
    "cl": (Unit.L, Decimal("0.01")),
    "dl": (Unit.L, Decimal("0.1")),
    "l": (Unit.L, Decimal(1)),
    "g": (Unit.KG, Decimal("0.001")),
    "kg": (Unit.KG, Decimal(1)),
}
_AMOUNT = r"(\d+(?:[.,]\d+)?)\s*(ml|cl|dl|kg|l|g)\b"
# "1 l", "0,33 L", "500g". Not preceded by a letter, digit, dot or comma: "c3kg" and "x2 cl" do not count.
_SINGLE_SIZE = re.compile(rf"(?<![\w.,]){_AMOUNT}", re.IGNORECASE)
# "100x2 cl", "12 x 55g", "10*160g": a count of inner items and the size of one.
_MULTIPACK_SIZE = re.compile(rf"(?<![\w.,])(\d+)\s*[x×*]\s*{_AMOUNT}", re.IGNORECASE)
# A leading "6 x": the name describes a pack of six.
_MULTIPACK_PREFIX = re.compile(r"^\s*(\d+)\s*[x×]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class InnerUnit:
    """The single items inside one sales unit: how many, and the size of one in litres or kilograms."""

    count: int
    size: Decimal


def units_per_sales_unit(product: Product) -> Decimal | None:
    """Base units in one sales unit: `units[unitId == salesUnit].sizeInBaseUnits`, a count, not a size."""
    if product.sales_unit == product.base_unit:
        return Decimal(1)
    size = next((unit.size_in_base_units for unit in product.units if unit.unit_id == product.sales_unit), None)
    return size if size is not None and size > 0 else None


def conversion_size(product: Product, measure: Unit) -> Decimal | None:
    """Litres or kg per sales unit from the unit-conversion row, when the row can be tied to a unit."""
    if product.sales_unit == WEIGHT_SALES_UNIT:
        return Decimal(1) if measure is Unit.KG else None
    multiplier = units_per_sales_unit(product)
    if multiplier is None:
        return None
    for row in product.unit_conversions:  # the file never has more than one row per product
        amount = row.volume_l if measure is Unit.L else row.net_weight_kg
        scale = _row_scale(product, row.packaging_type, multiplier)
        if amount is not None and scale is not None:
            return amount * scale
    return None


def _row_scale(product: Product, packaging_type: str, multiplier: Decimal) -> Decimal | None:
    """What to multiply the row by to get one sales unit, or `None` when the row's level is not known."""
    if packaging_type not in (BASE_ROW, CASE_ROW):
        return None  # a pallet row says nothing about one sales unit
    if product.synkka_gtin and product.synkka_gtin == product.sales_unit_gtin:
        return Decimal(1)  # the row measures the sales unit itself
    if packaging_type == CASE_ROW:
        return Decimal(1) if multiplier > 1 else None  # the row measures the case the product is sold by
    base_gtins = {unit.gtin for unit in product.units if unit.unit_id == product.base_unit}
    return multiplier if product.synkka_gtin and product.synkka_gtin in base_gtins else None


def name_size(product: Product, measure: Unit) -> Decimal | None:
    """Litres or kg per sales unit from the product name (English, else Finnish), or `None` when unclear."""
    if product.sales_unit == WEIGHT_SALES_UNIT:
        return None
    multiplier = units_per_sales_unit(product)
    name = product.name_en or product.name_fi or ""
    if multiplier is None or not name:
        return None
    singles = _single_sizes(name, measure)
    multipacks = _multipack_sizes(name, measure)
    if len(multipacks) == 1 and not singles:
        inner = multipacks[0]
        agrees = inner.count == multiplier or multiplier == 1
        return inner.count * inner.size if agrees else None
    if len(singles) == 1 and not multipacks:
        prefix = _MULTIPACK_PREFIX.match(name)
        if prefix and int(prefix[1]) != multiplier:
            return None
        return singles[0] * multiplier
    return None


def inner_unit(product: Product, measure: Unit) -> InnerUnit | None:
    """The inner items of one sales unit: from a "100x2 cl" name, else the size divided by the unit count."""
    if product.sales_unit == WEIGHT_SALES_UNIT:
        return None
    multipacks = _multipack_sizes(product.name_en or product.name_fi or "", measure)
    if len(multipacks) == 1:
        return multipacks[0]
    multiplier = units_per_sales_unit(product)
    if multiplier is None or multiplier != multiplier.to_integral_value():
        return None
    size = conversion_size(product, measure)
    if size is None:
        size = name_size(product, measure)
    if size is None:
        return None
    return InnerUnit(count=int(multiplier), size=size / multiplier)


def _single_sizes(name: str, measure: Unit) -> list[Decimal]:
    """Sizes that stand alone: the "10 g" of "200 x 10 g" belongs to the multipack and is not one of them."""
    return [
        size
        for amount, unit in _SINGLE_SIZE.findall(_MULTIPACK_SIZE.sub(" ", name))
        if (size := _to_measure(amount, unit, measure)) is not None
    ]


def _multipack_sizes(name: str, measure: Unit) -> list[InnerUnit]:
    return [
        InnerUnit(count=int(count), size=size)
        for count, amount, unit in _MULTIPACK_SIZE.findall(name)
        if int(count) > 0 and (size := _to_measure(amount, unit, measure)) is not None
    ]


def _to_measure(amount: str, unit: str, measure: Unit) -> Decimal | None:
    """The amount in litres or kilograms, or `None` when the unit is of the other measure or the amount is 0."""
    unit_measure, factor = _NAME_UNITS[unit.lower()]
    value = Decimal(amount.replace(",", ".")) * factor
    return value if unit_measure is measure and value > 0 else None
