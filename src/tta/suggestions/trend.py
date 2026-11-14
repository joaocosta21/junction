"""The quantity trend of a standing order's product (P15 R7, QUANTITY_TREND): "your order has grown".

Over the product's last 6 orders: the median of the last 3 against the median of the 3 before. It speaks from a
change of 15% and 4 of the 5 steps in the same direction, so one unusual week does not make a trend. Silent when the
stored quantity is already within the profile's drift tolerance of the recent median (rule P-08's tolerance; with
none set, only an equal quantity is silent). Accepting changes the stored quantity: a person's action, with its own
event. P-08 keeps its window, its median and its tolerance, so the trend cannot launder drift (P15 section 7).
"""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

from tta.contracts.request import PurchaseRequest
from tta.contracts.standing import StandingOrder
from tta.contracts.suggestion import Suggestion, SuggestionEvidence, SuggestionKind, suggestion_id_for
from tta.suggestions.history import OrderHistory
from tta.suggestions.requests import with_line_changed
from tta.suggestions.thresholds import TREND_MIN_CHANGE, TREND_MIN_STEPS_ONE_WAY, TREND_WINDOW, named
from tta.suggestions.wording import amount, middle, percent, sentence, tail

HALF = TREND_WINDOW // 2
RENEWS_ONCE = (
    "Accepting sends one renewal at this quantity, which meets every rule and a person's confirmation. The quantity "
    "the standing order stores changes only when a person changes it."
)


def quantity_trend(history: OrderHistory, product_id: str, *, standing_order_id: str, stored_quantity: Decimal,
                   tolerance: Decimal | None) -> Suggestion | None:
    """A suggestion to store the recent median, or None. `tolerance` is the profile's standing_order_drift_ratio."""
    orders = history.orders_with(product_id)[-TREND_WINDOW:]
    unit = history.unit_of(product_id)
    if len(orders) < TREND_WINDOW or unit is None:
        return None
    values = tuple(order.quantities[product_id] for order in orders)
    before, recent = middle(values[:HALF]), middle(values[HALF:])
    if before == 0 or recent == 0:
        return None  # a median of 0 has no ratio to measure: no trend is said (Python review, item P11)
    change = (recent - before) / before
    rising = change > 0
    steps = [later - earlier for earlier, later in pairwise(values)]
    one_way = sum(1 for step in steps if (step > 0 if rising else step < 0))
    if abs(change) < TREND_MIN_CHANGE or one_way < TREND_MIN_STEPS_ONE_WAY:
        return None
    if _within(stored_quantity, recent, tolerance):
        return None
    if one_way == len(steps):
        how = f"each {'higher' if rising else 'lower'} than the last"
    else:
        how = f"{one_way} of the last {len(steps)} changes were {'increases' if rising else 'decreases'}"
    said = sentence(
        f"Your last {HALF} orders of {history.label(product_id)} have a median of {amount(recent, unit)} against "
        f"{amount(before, unit)} for the {HALF} before ({percent(change)}), {how}.",
        f"The standing order still says {amount(stored_quantity, unit)}. Store {amount(recent, unit)}?",
        tail(history.synthetic),
    )
    evidence = SuggestionEvidence(
        source=history.source, synthetic=history.synthetic, orders_considered=len(orders), orders_matching=len(orders),
        first_order=orders[0].delivered_on, last_order=orders[-1].delivered_on, values=values,
        thresholds=named(TREND_WINDOW=TREND_WINDOW, TREND_MIN_CHANGE=TREND_MIN_CHANGE,
                         TREND_MIN_STEPS_ONE_WAY=TREND_MIN_STEPS_ONE_WAY),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(history.customer_id, SuggestionKind.QUANTITY_TREND, product_id),
        kind=SuggestionKind.QUANTITY_TREND, customer_id=history.customer_id, standing_order_id=standing_order_id,
        product_id=product_id, name=history.name_of(product_id), quantity=recent, unit=unit, sentence=said,
        evidence=evidence,
    )


def _within(stored: Decimal, recent: Decimal, tolerance: Decimal | None) -> bool:
    """True when the stored quantity is within the tolerance of the recent median, as rule P-08 measures it."""
    if recent == 0:
        return stored == 0  # no ratio to measure: only the same quantity is within any tolerance
    drift = abs(stored - recent) / recent
    return drift == 0 if tolerance is None else drift <= tolerance


def standing_order_trends(history: OrderHistory, standing: StandingOrder, *,
                          tolerance: Decimal | None) -> tuple[Suggestion, ...]:
    """The trend of each line of a standing order, for the standing-order page and for an offer that renews it.

    A line speaks when it names exactly one product, in the unit the history holds it in. Its `accept_request` is
    one renewal of the standing order with that line at the recent median: a request like any other, judged by
    every rule (P-08 among them) and confirmed by a person. Nothing here changes the stored quantity."""
    found = []
    for index, line in enumerate(standing.request.lines):
        if len(line.product_ids) != 1 or history.unit_of(line.product_ids[0]) is not line.unit:
            continue
        trend = quantity_trend(history, line.product_ids[0], standing_order_id=standing.standing_order_id,
                               stored_quantity=line.quantity, tolerance=tolerance)
        if trend is None:
            continue
        renewal = with_line_changed(standing.request, index, quantity=trend.quantity)
        accept = PurchaseRequest.model_validate({
            **renewal.model_dump(exclude_unset=True), "standing_order_id": standing.standing_order_id,
        })
        found.append(trend.model_copy(update={
            "request_line_index": index, "accept_request": accept, "checks": (*trend.checks, RENEWS_ONCE),
        }))
    return tuple(found)
