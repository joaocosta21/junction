"""The "this is one of your regular orders" alert: what a request repeats of what the customer orders regularly, said
at the moment the request is made, from the data.

Scores on the 20% "solving the problem and user need" (a request for a product a standing order already holds is
caught before it is ordered twice; a regular request is offered as a standing order; a quantity far from the usual
one is asked about, so less is corrected by hand afterwards) and on the 20% "autonomy and controls" (the alert orders
nothing and changes nothing, and every finding carries the counts, the quantities and the thresholds it rests on).

Each line of the request is judged on the product it names, or, for a line that names only a product type, on the
product the offer chose for it. A line is regular when its product is part of the regular order (`regular_products`:
in at least `REORDER_MIN_ORDERS` of the last `REORDER_WINDOW_ORDERS` orders) and the line is in the unit the customer
orders it in. Its quantity is "about the usual one" while it differs from the usual quantity (the median of its last
orders) by less than `REGULAR_QUANTITY_TOLERANCE`; from that share on it is clearly more or less.

One finding for the request, the strongest that applies:

- `ALREADY_ON_STANDING_ORDER`: a product of the request is on one of the customer's standing orders. It comes first:
  it is the one that prevents ordering twice.
- `REGULAR_DIFFERENT_QUANTITY`: a regular product at a clearly different quantity, with the request at the usual
  quantities (`usual_request`).
- `REGULAR_NOT_STANDING`: no product is on a standing order, no regular product is at a clearly different quantity,
  and at least one line is regular. It carries the body that sets the regular lines up as a standing order
  (`standing_order_request`, as `POST /v1/standing-orders` takes it), at the usual quantities and the customer's
  rhythm (`rhythm_of`).

A finding that also applies but is not the strongest is in `evidence.also` with its sentence. A request that renews
a standing order is not compared: it is that standing order, not an order on top of it. Nothing here asks the
supplier anything, and no model picks or words anything.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field

from tta.contracts.common import Contract, Number, Quantity, Ratio, Unit
from tta.contracts.customer import CustomerStandingOrder
from tta.contracts.offer import Offer
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.standing import DEFAULT_CADENCE_DAYS, NewStandingOrder, StandingOrder
from tta.contracts.suggestion import EvidenceSource
from tta.suggestions.history import OrderHistory
from tta.suggestions.reorder import RegularProduct, next_delivery, regular_products, rhythm_of
from tta.suggestions.requests import with_line_changed
from tta.suggestions.thresholds import (
    HISTORY_WINDOW_ORDERS,
    REGULAR_QUANTITY_TOLERANCE,
    REORDER_MIN_ORDERS,
    REORDER_WINDOW_ORDERS,
    USUAL_QUANTITY_WINDOW,
    named,
)
from tta.suggestions.wording import (
    ON_TOP_OF_IT,
    ON_TOP_OF_THEM,
    REGULAR_NOTE,
    RENEWAL_NOTE,
    amount,
    counted_clause,
    different_quantity_sentence,
    how_often,
    on_standing_alert,
    regular_alert_sentence,
    sentence,
    short_label,
    short_name,
    standing_order_name,
    tail,
    weekday_name,
)


class Finding(StrEnum):
    ALREADY_ON_STANDING_ORDER = "ALREADY_ON_STANDING_ORDER"
    REGULAR_NOT_STANDING = "REGULAR_NOT_STANDING"
    REGULAR_DIFFERENT_QUANTITY = "REGULAR_DIFFERENT_QUANTITY"


class Comparison(StrEnum):
    """A regular line's quantity against the usual one."""

    USUAL = "USUAL"  # within `REGULAR_QUANTITY_TOLERANCE` of it
    MORE = "MORE"
    LESS = "LESS"


@dataclass(frozen=True)
class HeldLine:
    """One product of one standing order, as the alert reads it."""

    standing_order_id: str
    standing_order_name: str
    cadence_days: int
    product_id: str
    quantity: Decimal
    unit: Unit | None  # None: the unit is not known (a product outside the customer's usual ones)


class RegularLine(Contract):
    """One line of the request whose product is known, and what the past orders say about it."""

    request_line_index: int
    product_id: str
    name: str
    quantity: Quantity = Field(description="What the request asks for")
    unit: Unit
    regular: bool = Field(description="The product is part of the regular order, in this unit")
    usual_quantity: Quantity | None = Field(
        default=None, description="The median of its last orders; None: not regular")
    comparison: Comparison | None = None
    orders_matching: int = Field(description="Of the last `orders_considered` orders, those that hold the product")
    orders_considered: int
    standing_order_id: str | None = None
    standing_order_name: str | None = None
    sentence: str = Field(default="", description='"your usual 40 L", or both quantities when they clearly differ')


class ProductFacts(Contract):
    """What one line's judgement was computed from."""

    request_line_index: int
    product_id: str
    resolved_by: Literal["REQUEST", "OFFER"] = Field(description="OFFER: the line names no product; the offer chose it")
    requested: Quantity
    unit: Unit
    regular: bool
    orders_matching: int = Field(description="Of the last `REORDER_WINDOW_ORDERS` orders: what makes it regular")
    orders_considered: int
    orders_matching_of_history_window: int
    history_window: int
    usual_quantity: Number | None = None
    values: tuple[Number, ...] = Field(default=(), description="The quantities the usual quantity is the median of")
    difference_ratio: Ratio | None = Field(default=None, description="|requested - usual| / usual")
    comparison: Comparison | None = None
    standing_order_id: str | None = None
    standing_quantity: Number | None = Field(default=None, description="What the standing order stores of it")


class OtherFinding(Contract):
    """A finding that also applies and is not the strongest."""

    finding: Finding
    sentence: str


class RegularEvidence(Contract):
    """Everything the alert rests on, so that anyone can compute it again."""

    source: EvidenceSource
    synthetic: bool
    orders_in_history: int
    first_order: date | None = None
    last_order: date | None = None
    thresholds: dict[str, Number]
    findings: tuple[Finding, ...] = Field(default=(), description="Every finding that applies, the strongest first")
    also: tuple[OtherFinding, ...] = ()
    products: tuple[ProductFacts, ...] = ()
    usual_gap_days: Number | None = None
    usual_weekdays: tuple[str, ...] = ()
    today: date
    next_delivery: date | None = Field(default=None, description="The customer's next usual delivery day")


class RegularAlert(Contract):
    """The answer of `regular_alert`. `finding` None: nothing to say, and `sentence` is empty."""

    offer_id: str | None = None
    finding: Finding | None = None
    sentence: str = ""
    lines: tuple[RegularLine, ...] = ()
    standing_order_request: NewStandingOrder | None = Field(
        default=None, description="With REGULAR_NOT_STANDING: the body that sets the regular lines up")
    usual_request: PurchaseRequest | None = Field(
        default=None, description="With REGULAR_DIFFERENT_QUANTITY: the same request at the usual quantities")
    synthetic: bool
    note: str = REGULAR_NOTE
    evidence: RegularEvidence


# --- what the alert reads ---------------------------------------------------------------------------------------


def held_lines(history: OrderHistory,
               standing: Sequence[CustomerStandingOrder | StandingOrder]) -> tuple[HeldLine, ...]:
    """Each product of the standing orders: the customer file's (`CustomerStandingOrder`) and those the order book
    holds (`StandingOrder`, of which only a line that names one product can be read). A standing order given twice
    (the file's, set up in the book under the same id) is read once, as first given."""
    found: list[HeldLine] = []
    seen: set[str] = set()
    for order in standing:
        if order.standing_order_id in seen:
            continue
        seen.add(order.standing_order_id)
        if isinstance(order, StandingOrder):
            pairs = [(line.product_ids[0], line.quantity, line.unit) for line in order.request.lines
                     if len(line.product_ids) == 1]
        else:
            pairs = [(line.product_id, line.quantity, history.unit_of(line.product_id)) for line in order.lines]
        found.extend(HeldLine(standing_order_id=order.standing_order_id, standing_order_name=order.name,
                              cadence_days=order.cadence_days, product_id=product_id, quantity=quantity, unit=unit)
                     for product_id, quantity, unit in pairs)
    return tuple(found)


def chosen_products(offer: Offer) -> dict[int, str]:
    """For each line of the request, the product the offer's first option fills it with (the one that covers the
    most of it); empty for an offer without an option."""
    if not offer.options:
        return {}
    chosen: dict[int, tuple[Decimal, str]] = {}
    for line in offer.options[0].lines:
        best = chosen.get(line.request_line_index)
        if best is None or line.covers > best[0]:
            chosen[line.request_line_index] = (line.covers, line.product_id)
    return {index: product_id for index, (_, product_id) in chosen.items()}


# --- the judgement of one line ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Judged:
    """One line of the request with its product, the regular product it is (or None) and the standing order line
    that holds it (or None)."""

    index: int
    line: RequestLine
    product_id: str
    resolved_by: Literal["REQUEST", "OFFER"]
    regular: RegularProduct | None
    held: HeldLine | None

    @property
    def ratio(self) -> Decimal | None:
        if self.regular is None or self.regular.quantity <= 0:
            return None
        return abs(self.line.quantity - self.regular.quantity) / self.regular.quantity

    @property
    def comparison(self) -> Comparison | None:
        ratio = self.ratio
        if self.regular is None or ratio is None:
            return None
        if ratio < REGULAR_QUANTITY_TOLERANCE:
            return Comparison.USUAL
        return Comparison.MORE if self.line.quantity > self.regular.quantity else Comparison.LESS

    @property
    def differs(self) -> bool:
        return self.comparison in (Comparison.MORE, Comparison.LESS)


def _judged(history: OrderHistory, held: Mapping[str, HeldLine], request: PurchaseRequest,
            chosen: Mapping[int, str]) -> tuple[_Judged, ...]:
    regular = {each.product_id: each for each in regular_products(history)}
    found = []
    for index, line in enumerate(request.lines):
        named_one = len(line.product_ids) == 1
        product_id = line.product_ids[0] if named_one else (None if line.product_ids else chosen.get(index))
        if product_id is None:
            continue
        usual = regular.get(product_id)
        in_its_unit = usual is not None and usual.unit is line.unit
        found.append(_Judged(index=index, line=line, product_id=product_id,
                             resolved_by="REQUEST" if named_one else "OFFER",
                             regular=usual if in_its_unit else None, held=held.get(product_id)))
    return tuple(found)


def _line_sentence(each: _Judged) -> str:
    if each.regular is None:
        return ""
    usual = amount(each.regular.quantity, each.regular.unit)
    if not each.differs:
        return f"your usual {usual}"
    return f"you usually order {usual}; this request says {amount(each.line.quantity, each.line.unit)}"


def _in_window(history: OrderHistory, product_id: str, window: int) -> tuple[int, int]:
    orders = history.last(window)
    return sum(product_id in order.quantities for order in orders), len(orders)


def _line(each: _Judged, history: OrderHistory) -> RegularLine:
    matching, considered = _in_window(history, each.product_id, HISTORY_WINDOW_ORDERS)
    return RegularLine(
        request_line_index=each.index, product_id=each.product_id, name=history.name_of(each.product_id),
        quantity=each.line.quantity, unit=each.line.unit, regular=each.regular is not None,
        usual_quantity=each.regular.quantity if each.regular is not None else None, comparison=each.comparison,
        orders_matching=matching, orders_considered=considered,
        standing_order_id=each.held.standing_order_id if each.held is not None else None,
        standing_order_name=each.held.standing_order_name if each.held is not None else None,
        sentence=_line_sentence(each),
    )


def _facts(each: _Judged, history: OrderHistory) -> ProductFacts:
    matching, considered = _in_window(history, each.product_id, REORDER_WINDOW_ORDERS)
    longer, window = _in_window(history, each.product_id, HISTORY_WINDOW_ORDERS)
    return ProductFacts(
        request_line_index=each.index, product_id=each.product_id, resolved_by=each.resolved_by,
        requested=each.line.quantity, unit=each.line.unit, regular=each.regular is not None,
        orders_matching=matching, orders_considered=considered, orders_matching_of_history_window=longer,
        history_window=window, usual_quantity=each.regular.quantity if each.regular is not None else None,
        values=each.regular.values if each.regular is not None else (), difference_ratio=each.ratio,
        comparison=each.comparison, standing_order_id=each.held.standing_order_id if each.held is not None else None,
        standing_quantity=each.held.quantity if each.held is not None else None,
    )


# --- the three findings -----------------------------------------------------------------------------------------


def _label(history: OrderHistory, product_id: str) -> str:
    return short_label(history.names.get(product_id), product_id)


def _on_standing(judged: Sequence[_Judged], history: OrderHistory, next_for: date | None) -> str | None:
    """One sentence per standing order that holds a product of the request, then that the request is on top."""
    on = [each for each in judged if each.held is not None]
    if not on:
        return None
    by_order: dict[str, list[_Judged]] = {}
    for each in on:
        by_order.setdefault(each.held.standing_order_id, []).append(each)  # type: ignore[union-attr]
    said = []
    for group in by_order.values():
        held = [each.held for each in group if each.held is not None]
        said.append(on_standing_alert(
            [_label(history, each.product_id) for each in group], held[0].standing_order_name,
            [amount(line.quantity, line.unit or each.line.unit) for line, each in zip(held, group, strict=True)],
            held[0].cadence_days, next_for,
        ))
    # The next date is the customer's usual delivery day, read from the past orders: the sentence rests on them.
    return sentence(*said, ON_TOP_OF_IT if len(by_order) == 1 else ON_TOP_OF_THEM,
                    tail(history.synthetic and next_for is not None))


def _different(judged: Sequence[_Judged], history: OrderHistory) -> str | None:
    differing = [each for each in judged if each.differs and each.regular is not None]
    if not differing:
        return None
    usual = [f"{amount(each.regular.quantity, each.regular.unit)} of {_label(history, each.product_id)}"  # type: ignore[union-attr]
             for each in differing]
    asked = [amount(each.line.quantity, each.line.unit) for each in differing]
    return sentence(different_quantity_sentence(usual, asked), tail(history.synthetic))


def _cadence(gap_days: Decimal | None) -> int:
    return max(int(gap_days), 1) if gap_days is not None else DEFAULT_CADENCE_DAYS


def _not_standing(judged: Sequence[_Judged], history: OrderHistory, gap_days: Decimal | None) -> str | None:
    """None when a product is on a standing order, a regular one is at a clearly different quantity, or no line is
    regular."""
    regular = [each for each in judged if each.regular is not None]
    if not regular or any(each.held is not None for each in judged) or any(each.differs for each in regular):
        return None
    counts = [_in_window(history, each.product_id, HISTORY_WINDOW_ORDERS) for each in regular]
    clauses = [
        counted_clause(_label(history, each.product_id), amount(each.regular.quantity, each.regular.unit),  # type: ignore[union-attr]
                       matching, considered, first=index == 0)
        for index, (each, (matching, considered)) in enumerate(zip(regular, counts, strict=True))
    ]
    often = how_often(gap_days, every_order=all(matching == considered for matching, considered in counts))
    return sentence(regular_alert_sentence(clauses, often, _cadence(gap_days)), tail(history.synthetic))


def _set_up(judged: Sequence[_Judged], history: OrderHistory, request: PurchaseRequest,
            gap_days: Decimal | None) -> NewStandingOrder:
    """The regular lines as a standing order: each by its product id at the usual quantity, the request's preference
    kept, no date (each renewal is asked for when it is made)."""
    regular = [each for each in judged if each.regular is not None]
    cadence = _cadence(gap_days)
    lines = []
    for each in regular:
        usual = each.regular
        assert usual is not None  # `regular` holds only lines that have one
        matching, considered = _in_window(history, each.product_id, HISTORY_WINDOW_ORDERS)
        lines.append(RequestLine(
            text=f"Standing order: {amount(usual.quantity, usual.unit)} of {history.label(each.product_id)}, in "
                 f"{matching} of the last {considered} orders",
            product_ids=(each.product_id,), quantity=usual.quantity, unit=usual.unit,
        ))
    names = [short_name(history.names[each.product_id]) if each.product_id in history.names
             else f"product {each.product_id}" for each in regular]
    return NewStandingOrder(name=standing_order_name(names, cadence), cadence_days=cadence,
                            request=PurchaseRequest(lines=tuple(lines), prefer=request.prefer))


def _at_usual(judged: Sequence[_Judged], request: PurchaseRequest) -> PurchaseRequest:
    """The same request with each clearly different line at its usual quantity. It accepts no suggestion: it is a
    new request of its own."""
    changed = request
    for each in judged:
        if each.differs and each.regular is not None:
            changed = with_line_changed(changed, each.index, quantity=each.regular.quantity)
    return changed.model_copy(update={"accepted_suggestion_id": None})


# --- the alert ----------------------------------------------------------------------------------------------------


def regular_alert(history: OrderHistory, standing: Sequence[HeldLine], request: PurchaseRequest, *, today: date,
                  chosen: Mapping[int, str] | None = None, offer_id: str | None = None) -> RegularAlert:
    """What `request` repeats of the customer's regular orders. `standing`: `held_lines` of the customer's standing
    orders. `chosen`: for a line that names no product, the product the offer chose (`chosen_products`). `today`:
    the day the next usual delivery is counted from (the data clock's)."""
    rhythm = rhythm_of(history)
    gap_days = rhythm.gap_days if rhythm is not None else None
    next_for = next_delivery(rhythm, today)
    renewal = request.standing_order_id is not None
    held: dict[str, HeldLine] = {}
    for line in standing:
        held.setdefault(line.product_id, line)
    judged = () if renewal else _judged(history, held, request, chosen or {})
    found = [(finding, said) for finding, said in (
        (Finding.ALREADY_ON_STANDING_ORDER, _on_standing(judged, history, next_for)),
        (Finding.REGULAR_NOT_STANDING, _not_standing(judged, history, gap_days)),
        (Finding.REGULAR_DIFFERENT_QUANTITY, _different(judged, history)),
    ) if said is not None]
    first = found[0][0] if found else None
    evidence = RegularEvidence(
        source=history.source, synthetic=history.synthetic, orders_in_history=len(history.orders),
        first_order=history.orders[0].delivered_on if history.orders else None,
        last_order=history.orders[-1].delivered_on if history.orders else None,
        thresholds=named(
            REORDER_MIN_ORDERS=REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS=REORDER_WINDOW_ORDERS,
            HISTORY_WINDOW_ORDERS=HISTORY_WINDOW_ORDERS, REGULAR_QUANTITY_TOLERANCE=REGULAR_QUANTITY_TOLERANCE,
            USUAL_QUANTITY_WINDOW=USUAL_QUANTITY_WINDOW,
        ),
        findings=tuple(finding for finding, _ in found),
        also=tuple(OtherFinding(finding=finding, sentence=said) for finding, said in found[1:]),
        products=tuple(_facts(each, history) for each in judged),
        usual_gap_days=gap_days,
        usual_weekdays=tuple(weekday_name(weekday) for weekday in rhythm.weekdays) if rhythm is not None else (),
        today=today, next_delivery=next_for,
    )
    return RegularAlert(
        offer_id=offer_id, finding=first, sentence=found[0][1] if found else "",
        lines=tuple(_line(each, history) for each in judged),
        standing_order_request=(_set_up(judged, history, request, gap_days)
                                if first is Finding.REGULAR_NOT_STANDING else None),
        usual_request=_at_usual(judged, request) if first is Finding.REGULAR_DIFFERENT_QUANTITY else None,
        synthetic=history.synthetic, note=RENEWAL_NOTE if renewal else REGULAR_NOTE, evidence=evidence,
    )
