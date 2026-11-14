"""Suggestions from a customer's past orders and from the catalog, as pure functions (P15 R2, R5, R7; P1 C4, C5).

Counts, shares and medians with named thresholds (`thresholds`); no model picks, ranks or words one. A suggestion
never changes an order: accepting posts its `accept_request` as a new offer, which meets every rule and a person's
confirmation. `suggestions_for` is the one function the gateway calls: it gathers every kind, puts each through
the guard (`guard`: the buyer's allergen exclusions, dietary claims, formula, confirmed stock for the date, an order
already placed) and returns the at most three to show with what was dropped and why. `events` builds the audit
facts. What is the gateway's: the list on the offer, the routes, and writing the events.
"""

from tta.suggestions.cheaper import CheaperOption, cheaper_same_formula
from tta.suggestions.companions import forgotten_items
from tta.suggestions.events import (
    suggestion_accepted_facts,
    suggestion_accepted_supplier_facts,
    suggestions_shown_facts,
    suggestions_shown_supplier_facts,
)
from tta.suggestions.guard import DroppedSuggestion, DropReason
from tta.suggestions.history import OrderHistory, history_of
from tta.suggestions.packs import PackOption, larger_pack
from tta.suggestions.ranking import first_suggestions
from tta.suggestions.service import SuggestionList, SuggestionPorts, suggestions_for
from tta.suggestions.trend import quantity_trend, standing_order_trends
from tta.suggestions.usual import (
    usual_product,
    usual_product_question,
    usual_products_for_request,
    usual_quantities_for_request,
    usual_quantity,
)

__all__ = [
    "CheaperOption",
    "DropReason",
    "DroppedSuggestion",
    "OrderHistory",
    "PackOption",
    "SuggestionList",
    "SuggestionPorts",
    "cheaper_same_formula",
    "first_suggestions",
    "forgotten_items",
    "history_of",
    "larger_pack",
    "quantity_trend",
    "standing_order_trends",
    "suggestion_accepted_facts",
    "suggestion_accepted_supplier_facts",
    "suggestions_for",
    "suggestions_shown_facts",
    "suggestions_shown_supplier_facts",
    "usual_product",
    "usual_product_question",
    "usual_products_for_request",
    "usual_quantities_for_request",
    "usual_quantity",
]
