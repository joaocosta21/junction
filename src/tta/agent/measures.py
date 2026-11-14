"""How a quantity's unit was taken, said in the reading: sales units, and a drink by weight (REVIEW C2-8).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for" and the 15% "clear visibility
of assumptions". The checks of 15 Nov 2026 found two readings made without a word:
- "50 packs of milk" is 50 sales units, and a sales unit is whatever Valio Aimo sells the product in. Counted over
  the whole product file (17,546 products) on 15 Nov 2026 with the catalog's own pack sizes: 8,005 have the sales
  unit `KI`, which holds more than one pack for 5,816 of them (471690: ten 1-litre packs), and 5,607 `ST`, which
  holds one pack for 4,851 (464306: one 1-litre pack). So the reading says what a pack was taken to be. A word for
  a container whose content differs by product (a carton, a case, a pallet) is not read at all: `tta.agent.asking`.
- "5 kg of milk" is 5 kilograms, and the offer then counts packs by each product's own weight (measured in replay
  at the recording's clock, Sat 14 Nov 2026 02:52 Helsinki: five 1-litre packs of 1.029 kg cover the 5 kg). The
  reading says it was read by weight and how to ask for litres. `LITRE_TYPES` are the types of the product-type
  table that a kitchen measures in litres; the list is ours.
Both notes are made from the typed request and the buyer's words, so they hold whoever read the text.
"""

from __future__ import annotations

import re

from tta.agent.quantity import plain, quantity
from tta.agent.textcheck import DIGIT_RUN, unit_of
from tta.agent.unread import NotReadByRules
from tta.contracts.common import Unit
from tta.contracts.request import PurchaseRequest

LITRE_TYPES = frozenset({
    "milk", "coffee_milk", "sour_milk", "cream", "vegetable_cream", "plant_drink", "juice", "soft_drink",
    "mineral_water", "olive_oil",
})
_QUANTITY_SAID = re.compile(rf"({DIGIT_RUN.pattern})\s*([^\W\d_]+)")

READ_AS_SALES_UNITS = (
    '"{said}" is read as {quantity} sales units. A sales unit is the pack Valio Aimo sells a product in: a single '
    "pack for some products, a case of several for others. For an exact amount, write litres or kilograms."
)
READ_BY_WEIGHT = (
    "{quantity} kg of {what} is read by weight, as kilograms and not as litres. If litres are meant, write "
    '"{quantity} litres".'
)


def sales_unit_notes(request: PurchaseRequest, text: str) -> list[str]:
    """One note per quantity of the text said with a pack word ("50 packs") that a line of the request holds in
    sales units. A quantity the fixed rules would not read as one number gives no note."""
    in_sales_units = {line.quantity for line in request.lines if line.unit is Unit.UNIT}
    notes = []
    for digits, word in _QUANTITY_SAID.findall(text.casefold()) if in_sales_units else ():
        if unit_of(word) is not Unit.UNIT:
            continue
        try:
            value = quantity(digits, 1)
        except NotReadByRules:
            continue
        if value in in_sales_units:
            notes.append(READ_AS_SALES_UNITS.format(said=f"{digits} {word}", quantity=plain(value)))
    return list(dict.fromkeys(notes))


def by_weight_notes(request: PurchaseRequest) -> list[str]:
    """One note per line that asks for a type measured in litres by the kilogram."""
    notes = []
    for line in request.lines:
        if line.unit is Unit.KG and line.product_type is not None and line.product_type in LITRE_TYPES:
            what = line.product_type.replace("_", " ")
            notes.append(READ_BY_WEIGHT.format(quantity=plain(line.quantity), what=what))
    return list(dict.fromkeys(notes))
