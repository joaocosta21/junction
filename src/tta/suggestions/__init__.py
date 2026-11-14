"""Suggestions from a customer's past orders and from the catalog, as pure functions (P15 R2, R5, R7; P1 C4, C5).

Counts, shares and medians with named thresholds (`thresholds`); no model picks, ranks or words one. A suggestion
never changes an order: accepting posts its `accept_request` as a new offer, which meets every rule and a person's
confirmation. What is not here yet, and belongs to the gateway's wiring (P15 R3): the guard (the buyer's allergen
exclusions, dietary claims, formula, availability, an order already placed for the date), prices and stock on the
history kinds, and the list on the offer.
"""

from tta.suggestions.companions import forgotten_items
from tta.suggestions.history import OrderHistory, history_of
from tta.suggestions.packs import PackOption, larger_pack
from tta.suggestions.ranking import first_suggestions
from tta.suggestions.trend import quantity_trend
from tta.suggestions.usual import usual_product, usual_product_question, usual_products_for_request, usual_quantity

__all__ = [
    "OrderHistory",
    "PackOption",
    "first_suggestions",
    "forgotten_items",
    "history_of",
    "larger_pack",
    "quantity_trend",
    "usual_product",
    "usual_product_question",
    "usual_products_for_request",
    "usual_quantity",
]
