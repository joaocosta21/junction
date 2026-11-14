"""The usual product of a product type and the usual quantity of a product (P1 C4, C5; P15 USUAL_PRODUCT and
USUAL_QUANTITY).

The usual product: of the last 8 orders that hold the type, the product in the largest share, from 3 such orders
and a share of 60%. When no product reaches the share (two milks alternate) there is no usual product, and the
question which one is asked instead of a guess (Valio, V5). The usual quantity: the median of the product's last 6
orders (the window of rule P-08), from 3 orders. Both are suggestions: a person confirms them before anything is
ordered (Valio, V8). A quantity is never a model's guess.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from decimal import Decimal

from tta.contracts.common import Unit
from tta.contracts.customer import PastOrder
from tta.contracts.request import PurchaseRequest
from tta.contracts.suggestion import Suggestion, SuggestionEvidence, SuggestionKind, suggestion_id_for
from tta.suggestions.history import OrderHistory
from tta.suggestions.requests import with_line_changed
from tta.suggestions.thresholds import (
    HISTORY_WINDOW_ORDERS,
    USUAL_PRODUCT_MIN_ORDERS,
    USUAL_PRODUCT_MIN_SHARE,
    USUAL_QUANTITY_MIN_DIFFERENCE,
    USUAL_QUANTITY_MIN_ORDERS,
    USUAL_QUANTITY_WINDOW,
    named,
)
from tta.suggestions.wording import amount, middle, number, sentence, short_label, tail, type_words

MAX_NAMED_IN_A_QUESTION = 3


def _of_type(history: OrderHistory, product_type: str) -> tuple[tuple[PastOrder, ...], list[tuple[str, int]]]:
    """The window's orders that hold the type, and each product of the type with the orders that hold it, most
    first; a tie in the order the products were first ordered."""
    window = history.last(HISTORY_WINDOW_ORDERS)
    orders = tuple(order for order in window
                   if any(history.type_of(product_id) == product_type for product_id in order.quantities))
    first_seen = list(dict.fromkeys(product_id for order in orders for product_id in order.quantities
                                    if history.type_of(product_id) == product_type))
    counts = Counter(product_id for order in orders for product_id in order.quantities
                     if history.type_of(product_id) == product_type)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], first_seen.index(item[0])))
    return orders, ranked


def _usual_id(orders: tuple[PastOrder, ...], ranked: list[tuple[str, int]]) -> str | None:
    if len(orders) < USUAL_PRODUCT_MIN_ORDERS or not ranked:
        return None
    product_id, count = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == count:
        return None  # two products share the largest share: which one is a question
    if count < USUAL_PRODUCT_MIN_SHARE * len(orders):
        return None
    return product_id


def usual_product(history: OrderHistory, product_type: str) -> Suggestion | None:
    """The customer's usual product for a type, at its usual quantity; None when the history does not say."""
    orders, ranked = _of_type(history, product_type)
    product_id = _usual_id(orders, ranked)
    unit = history.unit_of(product_id) if product_id is not None else None
    if product_id is None or unit is None:
        return None
    count = dict(ranked)[product_id]
    values = tuple(order.quantities[product_id] for order in history.orders_with(product_id))
    evidence = SuggestionEvidence(
        source=history.source, synthetic=history.synthetic, orders_considered=len(orders), orders_matching=count,
        first_order=orders[0].delivered_on, last_order=orders[-1].delivered_on,
        values=values[-USUAL_QUANTITY_WINDOW:],
        thresholds=named(USUAL_PRODUCT_MIN_ORDERS=USUAL_PRODUCT_MIN_ORDERS,
                         USUAL_PRODUCT_MIN_SHARE=USUAL_PRODUCT_MIN_SHARE),
    )
    kind = type_words(product_type)
    said = sentence(
        f"You usually buy {short_label(history.names.get(product_id), product_id)}: it was in {count} of your last "
        f"{len(orders)} {kind} orders. Use it?", tail(history.synthetic),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(history.customer_id, SuggestionKind.USUAL_PRODUCT, product_id),
        kind=SuggestionKind.USUAL_PRODUCT, customer_id=history.customer_id, product_id=product_id,
        name=history.name_of(product_id), quantity=middle(values[-USUAL_QUANTITY_WINDOW:]), unit=unit,
        sentence=said, evidence=evidence,
    )


def usual_product_question(history: OrderHistory, product_type: str) -> str | None:
    """The question to ask when the orders of a type hold no usual product; None when there is one, or when the
    history holds too few orders of the type to ask about."""
    orders, ranked = _of_type(history, product_type)
    if len(orders) < USUAL_PRODUCT_MIN_ORDERS or _usual_id(orders, ranked) is not None:
        return None
    named_ones = [f"{history.label(product_id)} {count} {'time' if count == 1 else 'times'}"
                  for product_id, count in ranked[:MAX_NAMED_IN_A_QUESTION]]
    listed = named_ones[0] if len(named_ones) == 1 else f"{', '.join(named_ones[:-1])} and {named_ones[-1]}"
    return f"Your last {len(orders)} orders of {type_words(product_type)} hold {listed}. Which one do you mean?"


def usual_products_for_request(history: OrderHistory, request: PurchaseRequest) -> tuple[Suggestion, ...]:
    """For each line that names a product type and no product: the usual product, at the line's quantity.
    Accepting pins the line to it; every other filter of the line stays, so nothing is widened."""
    return tuple(_for_lines(history, request))


def _for_lines(history: OrderHistory, request: PurchaseRequest) -> Iterator[Suggestion]:
    for index, line in enumerate(request.lines):
        if line.product_ids or not line.product_type:
            continue
        found = usual_product(history, line.product_type)
        if found is None:
            continue
        yield Suggestion.model_validate({
            **found.model_dump(), "request_line_index": index, "quantity": line.quantity, "unit": line.unit,
            "sentence": f"You asked for {type_words(line.product_type)} without naming one. {found.sentence}",
            "accept_request": with_line_changed(request, index, product_ids=[found.product_id]),
        })


def _usually(history: OrderHistory, product_id: str, values: tuple[Decimal, ...], unit: Unit) -> str:
    """ "You usually order about 100 L of Arla Semi skimmed milkdrink (469363): between 98 and 104 L in your
    last 6 orders." The median, and the range it was taken over."""
    quantity, low, high = middle(values), min(values), max(values)
    label = short_label(history.names.get(product_id), product_id)
    if low == high:
        return (f"You usually order {amount(quantity, unit)} of {label}: the same in each of your last "
                f"{len(values)} orders.")
    return (f"You usually order about {amount(quantity, unit)} of {label}: between {number(low)} and "
            f"{amount(high, unit)} in your last {len(values)} orders.")


def usual_quantity(history: OrderHistory, product_id: str) -> Suggestion | None:
    """The median of the product's last 6 orders, from 3; None with fewer."""
    orders = history.orders_with(product_id)[-USUAL_QUANTITY_WINDOW:]
    unit = history.unit_of(product_id)
    if len(orders) < USUAL_QUANTITY_MIN_ORDERS or unit is None:
        return None
    values = tuple(order.quantities[product_id] for order in orders)
    quantity = middle(values)
    said = sentence(_usually(history, product_id, values, unit), tail(history.synthetic))
    evidence = SuggestionEvidence(
        source=history.source, synthetic=history.synthetic, orders_considered=len(orders),
        orders_matching=len(orders), first_order=orders[0].delivered_on, last_order=orders[-1].delivered_on,
        values=values, thresholds=named(USUAL_QUANTITY_WINDOW=USUAL_QUANTITY_WINDOW,
                                        USUAL_QUANTITY_MIN_ORDERS=USUAL_QUANTITY_MIN_ORDERS),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(history.customer_id, SuggestionKind.USUAL_QUANTITY, product_id),
        kind=SuggestionKind.USUAL_QUANTITY, customer_id=history.customer_id, product_id=product_id,
        name=history.name_of(product_id), quantity=quantity, unit=unit, sentence=said, evidence=evidence,
    )


def usual_quantities_for_request(history: OrderHistory, request: PurchaseRequest) -> tuple[Suggestion, ...]:
    """For each line that names one product, in the unit the history holds it in, and asks for a quantity that
    differs from the usual one by `USUAL_QUANTITY_MIN_DIFFERENCE` or more: the usual quantity. Accepting changes
    that line's quantity and nothing else. Below the threshold it stays silent: a kitchen orders a little more or
    less from week to week."""
    return tuple(_quantities_for_lines(history, request))


def _quantities_for_lines(history: OrderHistory, request: PurchaseRequest) -> Iterator[Suggestion]:
    for index, line in enumerate(request.lines):
        if len(line.product_ids) != 1 or history.unit_of(line.product_ids[0]) is not line.unit:
            continue
        found = usual_quantity(history, line.product_ids[0])
        if found is None or abs(line.quantity - found.quantity) < USUAL_QUANTITY_MIN_DIFFERENCE * found.quantity:
            continue
        thresholds = {**found.evidence.thresholds,
                      **named(USUAL_QUANTITY_MIN_DIFFERENCE=USUAL_QUANTITY_MIN_DIFFERENCE)}
        asked, usual = amount(line.quantity, line.unit), amount(found.quantity, line.unit)
        yield found.model_copy(update={
            "request_line_index": index,
            "sentence": sentence(_usually(history, line.product_ids[0], found.evidence.values, line.unit),
                                 f"This request says {asked}. Order {usual} instead?", tail(history.synthetic)),
            "evidence": found.evidence.model_copy(update={"thresholds": thresholds}),
            "accept_request": with_line_changed(request, index, quantity=found.quantity),
        })
