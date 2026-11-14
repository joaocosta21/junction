"""The named thresholds of the suggestions (P15 section 4.1). Every value is ours, a proposal: shown on the
assumptions page with the method (P15 R12). A suggestion that passes one names it in `evidence.thresholds`.
"""

from __future__ import annotations

from decimal import Decimal

HISTORY_WINDOW_ORDERS = 8  # one window for all signals: the customer's last 8 orders (P1 generates 8 weeks)

COMPANION_MIN_SUPPORT = 4  # past orders that hold both the requested product and the forgotten one
COMPANION_MIN_CONFIDENCE = Decimal("0.75")  # of the past orders that hold the requested product

USUAL_PRODUCT_MIN_ORDERS = 3  # past orders of the product type
USUAL_PRODUCT_MIN_SHARE = Decimal("0.6")  # of those orders, the share that holds the usual product

# The window and the minimum of rule P-08 (src/tta/policy/drift.py, DRIFT_WINDOW and MIN_RENEWALS_TO_JUDGE),
# repeated here so the suggestions do not import the policy package.
USUAL_QUANTITY_WINDOW = 6
USUAL_QUANTITY_MIN_ORDERS = 3

TREND_WINDOW = 6  # the last 6 orders of a product: the median of the last 3 against the 3 before
TREND_MIN_CHANGE = Decimal("0.15")
TREND_MIN_STEPS_ONE_WAY = 4  # of the 5 steps between the 6 orders

LARGER_PACK_MIN_SAVING = Decimal("0.05")  # cheaper per litre or kilogram by at least 5%
LARGER_PACK_MAX_OVER = Decimal("0.10")  # whole packs may hold at most 10% more than asked

# A request line that names a product is told the usual quantity only when it differs from it by this share of
# the usual quantity or more: below it the buyer simply ordered a little more or less, as a kitchen does.
USUAL_QUANTITY_MIN_DIFFERENCE = Decimal("0.25")

CHEAPER_MIN_SAVING = Decimal("0.05")  # P10 F6: cheaper per litre or kilogram by at least 5%, the formula kept
# The most products of one type the cheaper line and the larger pack compare with the offered product. The
# formula, the type, the flavour and the claims are judged from the product file first; price and stock are
# asked only for the products that pass, so this bounds the catalog work and not the supplier calls.
ALTERNATIVES_MAX_POOL = 400

MAX_SUPPLIER_SUGGESTIONS = 1  # P15 section 4.2: the supplier's own suggestion is the last, and never more than one
# The most related products the supplier's suggestion asks price and stock for, and the most it puts before the
# guard: the first that passes is the one shown.
SUPPLIER_MAX_POOL = 60
SUPPLIER_MAX_TRIES = 5

MAX_SUGGESTIONS = 3  # on one offer (P15 section 4.2: a page of offers is the shop the brief says this is not)


def named(**values: int | Decimal) -> dict[str, Decimal]:
    """The thresholds a suggestion passed, by name, for its evidence."""
    return {name: Decimal(value) for name, value in values.items()}
