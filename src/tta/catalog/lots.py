"""Lot rounding: a quantity in sales units goes up to the product's step (SPEC section 3, step 7).

Always `Decimal`: the fractional steps of the file (1.5, 1.8, 0.9 ...) do not survive binary floats
(AIMO/docs/PRODUCT-DATA.md section 4, `allowedLotSize`).
"""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from tta.catalog.sizes import WEIGHT_SALES_UNIT
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import Product

# `allowedLotSize` is 0.01 on 96.16% of products: the file sets no step (AIMO/FINDINGS.md section 4).
NO_STEP_IN_FILE = Decimal("0.01")
# Our assumption for those products: a countable sales unit (carton, case, bag ...) is ordered whole.
# In the three captures no availableAmount of any unit has a fraction.
WHOLE_UNIT = Decimal(1)


def lot_step(product: Product) -> Decimal:
    """The step a quantity of this product moves in, in sales units."""
    if product.allowed_lot_size > NO_STEP_IN_FILE:
        return product.allowed_lot_size
    if product.sales_unit == WEIGHT_SALES_UNIT:
        return NO_STEP_IN_FILE  # sold by weight with no step: 10 g is the finest the file allows
    return WHOLE_UNIT


def round_to_lot(product: Product, quantity: Decimal) -> Decimal:
    """The smallest multiple of the product's step that is not below `quantity`."""
    if not quantity.is_finite() or quantity <= 0:
        raise InvalidRequest("A quantity to order must be a number above zero.", product_id=product.id)
    step = lot_step(product)
    steps = int((quantity / step).to_integral_value(rounding=ROUND_CEILING))
    return steps * step  # an int times the step: "50", never the "5E+1" a Decimal count would print as
