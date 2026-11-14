"""The forgotten item: a product usually ordered with one of the request, and not in it (P15 R2, FORGOTTEN_ITEM).

For a product A of the request and a product B not in it, over the last 8 orders: support = the orders that hold
both, confidence = support / the orders that hold A, and the quantity is the median of B in those orders (the
textbook market-basket measure; confidence, not lift, because an item in every order is exactly the one a kitchen
must not forget). It speaks from support 4 and confidence 0.75.

It stays silent when the buyer already chose: B is in the request; a line of the request names B's product type and
no product of that type is known for it; or the request holds another product of B's type that is not ordered
together with B (an alternative, like another milk). A product of B's type that is ordered together with B often
enough to pass the support (the ward's soya and rice drinks) is a companion and does not silence it.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tta.contracts.common import Unit
from tta.contracts.customer import PastOrder
from tta.contracts.request import MAX_REQUEST_LINES, PurchaseRequest, RequestLine
from tta.contracts.suggestion import Suggestion, SuggestionEvidence, SuggestionKind, suggestion_id_for
from tta.suggestions.history import OrderHistory
from tta.suggestions.requests import with_line_added
from tta.suggestions.thresholds import (
    COMPANION_MIN_CONFIDENCE,
    COMPANION_MIN_SUPPORT,
    HISTORY_WINDOW_ORDERS,
    named,
)
from tta.suggestions.wording import amount, middle, sentence, short_label, tail, type_words


@dataclass(frozen=True)
class _Pair:
    """Product `other` in the orders of the window that hold the requested product `asked`."""

    asked: str
    other: str
    holding: tuple[PastOrder, ...]  # the orders of the window that hold `asked`
    matching: tuple[PastOrder, ...]  # of those, the orders that also hold `other`

    @property
    def confidence(self) -> Decimal:
        return Decimal(len(self.matching)) / Decimal(len(self.holding))

    @property
    def strength(self) -> tuple[Decimal, int]:
        return self.confidence, len(self.matching)


def forgotten_items(history: OrderHistory, request: PurchaseRequest, *,
                    offered_product_ids: Collection[str] = ()) -> tuple[Suggestion, ...]:
    """Every forgotten item the history supports, strongest first. `offered_product_ids` are the products an offer
    chose for the request's lines that name only a type; without them such a line has no product to start from."""
    if len(request.lines) >= MAX_REQUEST_LINES:
        return ()  # accepting would need one more line than a request may hold
    window = history.last(HISTORY_WINDOW_ORDERS)
    asked = tuple(dict.fromkeys([*(pid for line in request.lines for pid in line.product_ids), *offered_product_ids]))
    best: dict[str, _Pair] = {}
    for pair in _pairs(window, asked):
        if not _passes(pair, history) or _buyer_chose(pair.other, request, asked, window, history):
            continue
        if pair.other not in best or pair.strength > best[pair.other].strength:
            best[pair.other] = pair
    ranked = sorted(best.values(), key=lambda pair: (-pair.confidence, -len(pair.matching), pair.other))
    return tuple(_suggestion(pair, history, request, len(window)) for pair in ranked)


def _pairs(window: Sequence[PastOrder], asked: Sequence[str]) -> list[_Pair]:
    pairs: list[_Pair] = []
    for product_id in asked:
        holding = tuple(order for order in window if product_id in order.quantities)
        others = dict.fromkeys(other for order in holding for other in order.quantities if other != product_id)
        for other in others:
            matching = tuple(order for order in holding if other in order.quantities)
            pairs.append(_Pair(asked=product_id, other=other, holding=holding, matching=matching))
    return pairs


def _passes(pair: _Pair, history: OrderHistory) -> bool:
    """Both thresholds met, and a unit to say the quantity in (a product the history knows)."""
    enough = len(pair.matching) >= COMPANION_MIN_SUPPORT and pair.confidence >= COMPANION_MIN_CONFIDENCE
    return enough and history.unit_of(pair.other) is not None


def _buyer_chose(other: str, request: PurchaseRequest, asked: Sequence[str], window: Sequence[PastOrder],
                 history: OrderHistory) -> bool:
    """True when the request already says what the buyer wants of `other` or of its product type."""
    if other in asked:
        return True
    kind = history.type_of(other)
    if kind is None:
        return False
    same_type = [product_id for product_id in asked if history.type_of(product_id) == kind]
    if any(line.product_type == kind and not line.product_ids for line in request.lines) and not same_type:
        return True
    together = {product_id: sum(1 for order in window if {product_id, other} <= order.quantities.keys())
                for product_id in same_type}
    return any(count < COMPANION_MIN_SUPPORT for count in together.values())


def _said(pair: _Pair, history: OrderHistory, window_size: int, quantity: Decimal, unit: Unit,
          values: tuple[Decimal, ...]) -> str:
    """ "With this milk you usually also order Arla Pro Cooking cream 10% (463797): it was in 7 of your last 8
    orders, 10 L each time, and it is not in this request." The reason first, from what the customer buys."""
    holding, matching = len(pair.holding), len(pair.matching)
    kind = history.type_of(pair.asked)
    asked = f"this {type_words(kind)}" if kind else short_label(history.names.get(pair.asked), pair.asked)
    if holding == window_size:
        counted = f"it was in {matching} of your last {holding} orders"
    else:
        counted = f"it was in {matching} of the {holding} orders with {asked} among your last {window_size}"
    each = f"{amount(quantity, unit)} each time" if min(values) == max(values) else (
        f"about {amount(quantity, unit)} each time")
    other = short_label(history.names.get(pair.other), pair.other)
    return f"With {asked} you usually also order {other}: {counted}, {each}, and it is not in this request."


def _suggestion(pair: _Pair, history: OrderHistory, request: PurchaseRequest, window_size: int) -> Suggestion:
    values = tuple(order.quantities[pair.other] for order in pair.matching)
    quantity, unit = middle(values), history.unit_of(pair.other) or Unit.UNIT  # a unit is known: see _passes
    holding, matching = len(pair.holding), len(pair.matching)
    usually = f"{amount(quantity, unit)} of {history.label(pair.other)}"
    said = sentence(_said(pair, history, window_size, quantity, unit, values), tail(history.synthetic))
    line = RequestLine(text=f"{usually}, suggested from your order history", product_ids=(pair.other,),
                       quantity=quantity, unit=unit)
    evidence = SuggestionEvidence(
        source=history.source, synthetic=history.synthetic, orders_considered=holding, orders_matching=matching,
        first_order=pair.holding[0].delivered_on, last_order=pair.holding[-1].delivered_on, values=values,
        thresholds=named(COMPANION_MIN_SUPPORT=COMPANION_MIN_SUPPORT,
                         COMPANION_MIN_CONFIDENCE=COMPANION_MIN_CONFIDENCE),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(history.customer_id, SuggestionKind.FORGOTTEN_ITEM, pair.other),
        kind=SuggestionKind.FORGOTTEN_ITEM, customer_id=history.customer_id, product_id=pair.other,
        name=history.name_of(pair.other), quantity=quantity, unit=unit, sentence=said, evidence=evidence,
        accept_request=with_line_added(request, line),
    )
