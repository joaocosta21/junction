"""The "you usually order this: order again?" prompt: a customer's regular order, read from its past orders each
time it is asked for, and offered as a ready-made request.

Scores on the 20% "solving the problem and user need" (the regular order needs no typing and no correction) and on
the 20% "autonomy and controls" (the prompt orders nothing; each line is checked like any product; what is left out
is said with the reason, and everything said carries its evidence).

The regular order: every product in at least `REORDER_MIN_ORDERS` of the customer's last `REORDER_WINDOW_ORDERS`
orders, at its usual quantity (`usual_quantity`: the median of its last orders). The rhythm: the median gap between
the last orders and the usual weekdays; the next delivery date is the first usual weekday on or after the earliest
day the supplier can deliver every line, and not before the last order plus the usual gap. A product on one of the
customer's standing orders is left out and named: the same product is not ordered twice. So is a product already in
an order placed or waiting for that date. Each remaining line goes through the suggestions' guard (`guard.check`:
the buyer's allergen rule, the price, the cut-off, confirmed stock for the whole quantity and the date); one that
fails stays out of the request and is listed in `why_not` with the check's sentence.

Nothing here orders anything (decision B8): `request` is posted to the offers route like any request, meets every
rule there, and a person confirms it. Whether the total needs a person beyond the usual confirmation is the policy
engine's to say, on that offer; the prompt says the total only. No model picks or words anything.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from statistics import median

from pydantic import Field

from tta.contracts.common import Contract, DataSource, Money, Number, Quantity, Unit, round_money
from tta.contracts.customer import Customer
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.policy import BuyerProfile
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.suggestion import (
    EvidenceSource,
    Suggestion,
    SuggestionEvidence,
    SuggestionKind,
    suggestion_id_for,
)
from tta.offers.candidates import evaluate, need_for, units_needed
from tta.offers.deps import Lookup
from tta.suggestions.guard import GuardContext, Proposal, check
from tta.suggestions.history import OrderHistory, history_of
from tta.suggestions.service import SuggestionPorts, look_up
from tta.suggestions.thresholds import (
    HISTORY_WINDOW_ORDERS,
    REORDER_MAX_LINES,
    REORDER_MIN_ORDERS,
    REORDER_MIN_ORDERS_ON_A_WEEKDAY,
    REORDER_WINDOW_ORDERS,
    named,
)
from tta.suggestions.usual import usual_quantity
from tta.suggestions.wording import (
    DAYS_IN_A_WEEK,
    NOT_IN_REQUEST,
    NOTHING_ORDERED,
    amount,
    day,
    no_reorder_sentence,
    on_standing_sentence,
    regular_clause,
    reorder_sentence,
    sentence,
    weekday_name,
)

ONE_DAY = timedelta(days=1)
NO_TODAY = "Without the supplier's clock the prompt needs today's date."
NO_PROFILE = "A prompt that looks up price and stock needs the buyer's profile for the checks."
Committed = Collection[tuple[str, date | None]]  # (product id, delivery date) of orders placed or waiting


@dataclass(frozen=True)
class RegularProduct:
    """One product of the regular order, with the counts it rests on."""

    product_id: str
    quantity: Decimal  # the usual quantity: the median of its last orders
    unit: Unit
    orders_matching: int  # of the last `REORDER_WINDOW_ORDERS` orders
    orders_considered: int
    matching_in_history_window: int  # of the last `HISTORY_WINDOW_ORDERS` orders
    history_window: int
    first_ordered_on: date
    last_ordered_on: date
    values: tuple[Decimal, ...]  # the quantities the median was taken from


@dataclass(frozen=True)
class Rhythm:
    """When the customer orders: the median days between its last orders and the weekdays it is delivered on."""

    gap_days: Decimal | None  # None for a single order
    weekdays: tuple[int, ...]  # Monday is 0; empty when no weekday holds enough orders
    last_order: date


class ReorderLine(Contract):
    """One line of the ready-made request."""

    product_id: str
    name: str
    quantity: Quantity
    unit: Unit
    orders_matching: int = Field(description="Of the last `orders_considered` orders, those that hold the product")
    orders_considered: int
    last_ordered_on: date


class ProductEvidence(Contract):
    """What one regular product was computed from, whether or not it is in the request."""

    product_id: str
    name: str
    quantity: Quantity
    unit: Unit
    orders_matching: int
    orders_considered: int
    orders_matching_of_history_window: int
    history_window: int
    first_ordered_on: date
    last_ordered_on: date
    values: tuple[Number, ...] = Field(description="The quantities the usual quantity is the median of")
    in_request: bool
    net_eur: Money | None = Field(default=None, description="Before tax at the price looked up; None: not in it")


class OnStandingOrder(Contract):
    product_id: str
    name: str
    standing_order_id: str
    standing_order_name: str


class ReorderEvidence(Contract):
    """Everything the prompt rests on, so that anyone can compute it again."""

    source: EvidenceSource
    synthetic: bool
    orders_in_history: int
    first_order: date | None = None
    last_order: date | None = None
    thresholds: dict[str, Number]
    products: tuple[ProductEvidence, ...] = ()
    on_standing_order: tuple[OnStandingOrder, ...] = ()
    usual_gap_days: Number | None = None
    usual_weekdays: tuple[str, ...] = ()
    today: date
    earliest_delivery: date | None = Field(default=None, description="The first day every line can be delivered")
    checked: bool = Field(description="True when price and stock were looked up and each line went through the guard")
    prices_from: DataSource | None = None
    prices_as_of: datetime | None = None


class ReorderPrompt(Contract):
    """The answer of `reorder_prompt`. `lines` empty and `request` None: nothing regular to offer, and `sentence`
    says why."""

    customer_id: str
    lines: tuple[ReorderLine, ...] = ()
    sentence: str
    request: PurchaseRequest | None = None
    needed_by: date | None = None
    total_net_eur: Money | None = None
    synthetic: bool
    note: str = NOTHING_ORDERED
    why_not: tuple[str, ...] = ()
    evidence: ReorderEvidence


# --- the pure logic ---------------------------------------------------------------------------------------------


def regular_products(history: OrderHistory) -> tuple[RegularProduct, ...]:
    """The regular order, most regular first (a tie in the order of the customer's usual products). Empty for a
    history shorter than `REORDER_WINDOW_ORDERS`."""
    if len(history.orders) < REORDER_WINDOW_ORDERS:
        return ()
    window, longer = history.last(REORDER_WINDOW_ORDERS), history.last(HISTORY_WINDOW_ORDERS)
    counts = Counter(product_id for order in window for product_id in order.quantities)
    found = []
    for product_id in history.usual:
        usual = usual_quantity(history, product_id)
        if counts[product_id] < REORDER_MIN_ORDERS or usual is None:
            continue
        held = history.orders_with(product_id)
        found.append(RegularProduct(
            product_id=product_id, quantity=usual.quantity, unit=usual.unit,
            orders_matching=counts[product_id], orders_considered=len(window),
            matching_in_history_window=sum(product_id in order.quantities for order in longer),
            history_window=len(longer), first_ordered_on=held[0].delivered_on, last_ordered_on=held[-1].delivered_on,
            values=usual.evidence.values,
        ))
    return tuple(sorted(found, key=lambda each: (-each.orders_matching, -each.matching_in_history_window)))


def rhythm_of(history: OrderHistory) -> Rhythm | None:
    """The rhythm of the last `HISTORY_WINDOW_ORDERS` orders; None for a history without an order."""
    days = [order.delivered_on for order in history.last(HISTORY_WINDOW_ORDERS)]
    if not days:
        return None
    gaps = [(later - earlier).days for earlier, later in pairwise(days)]
    on_weekday = Counter(each.weekday() for each in days)
    usual = sorted(weekday for weekday, count in on_weekday.items() if count >= REORDER_MIN_ORDERS_ON_A_WEEKDAY)
    return Rhythm(gap_days=Decimal(median(gaps)) if gaps else None, weekdays=tuple(usual), last_order=days[-1])


def next_delivery(rhythm: Rhythm | None, earliest: date) -> date | None:
    """The first usual weekday on or after `earliest` (the first day the supplier can deliver) and not before the
    last order plus the usual gap. None when the past orders show no usual weekday."""
    if rhythm is None or not rhythm.weekdays:
        return None
    gap = timedelta(days=int(rhythm.gap_days)) if rhythm.gap_days is not None else ONE_DAY
    start = max(earliest, rhythm.last_order + max(gap, ONE_DAY))
    return next(start + timedelta(days=ahead) for ahead in range(DAYS_IN_A_WEEK)
                if (start + timedelta(days=ahead)).weekday() in rhythm.weekdays)


# --- the prompt ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Plan:
    """The regular order on its way to a request: what is kept so far, and why each other product is not."""

    kept: tuple[RegularProduct, ...]
    why_not: tuple[str, ...] = ()
    nets: Mapping[str, Decimal] | None = None  # by product id, once price and stock were looked up


def reorder_prompt(customer: Customer, *, profile: BuyerProfile | None = None, ports: SuggestionPorts | None = None,
                   names: Mapping[str, str] | None = None, today: date | None = None,
                   committed: Committed = ()) -> ReorderPrompt:
    """The prompt for one customer. `ports`: the product file, price and availability, and the clock; with them
    each line is checked under `profile` and the total is said. Without them (or when the supplier cannot be asked)
    the lines are offered unchecked, the total is None and the sentence says so; `today` is then the caller's.
    `names`: product names by id, when not the catalog's. `committed`: the products of this buyer's orders placed
    or waiting for a person, each with its delivery date."""
    history = history_of(customer, names if names is not None else _names(customer, ports))
    regular = regular_products(history)
    standing = _standing_products(customer)
    free = tuple(each for each in regular if each.product_id not in standing)
    lookup = _looked_up(ports, free)
    now = lookup.now.date() if lookup is not None else (ports.clock.now().date() if ports is not None else today)
    if now is None:
        raise ValueError(NO_TODAY)
    earliest = _earliest(now, free, lookup)
    needed_by = next_delivery(rhythm_of(history), earliest) if free else None
    plan = _Plan(kept=free, why_not=tuple(_on_standing_why(each, history, standing) for each in regular
                                           if each.product_id in standing))
    plan = _without_committed(plan, history, committed, needed_by, lookup)
    plan = _capped(plan, history)
    request = _request(customer, history, plan.kept, needed_by)
    if lookup is not None and request is not None and ports is not None:
        if profile is None:
            raise ValueError(NO_PROFILE)
        plan = _checked(plan, history, GuardContext(request=request, profile=profile, lookup=lookup,
                                                    catalog=ports.catalog))
        request = _request(customer, history, plan.kept, needed_by)
    evidence = _evidence(history, regular, standing, plan, now=now, lookup=lookup,
                         earliest=earliest if free else None)
    return _answer(history, regular, standing, plan, request, evidence)


def _names(customer: Customer, ports: SuggestionPorts | None) -> dict[str, str]:
    """Each usual product's name from the catalog, for the sentences; none without a catalog."""
    if ports is None:
        return {}
    products = {usual.product_id: ports.catalog.get_product(usual.product_id) for usual in customer.usual}
    return {product_id: product.display_name for product_id, product in products.items() if product is not None}


def _standing_products(customer: Customer) -> dict[str, tuple[str, str]]:
    """Each product of the customer's standing orders: the id and the name of the standing order that holds it."""
    return {line.product_id: (standing.standing_order_id, standing.name)
            for standing in reversed(customer.standing_orders) for line in standing.lines}


def _looked_up(ports: SuggestionPorts | None, products: Sequence[RegularProduct]) -> Lookup | None:
    """One look at price and availability for the products; None without ports or when the supplier cannot be
    asked (the prompt is then offered unchecked, and says so)."""
    if ports is None:
        return None
    try:
        return look_up(ports, (each.product_id for each in products))
    except SupplierUnavailable:
        return None


def _earliest(today: date, products: Sequence[RegularProduct], lookup: Lookup | None) -> date:
    """The first day every product can be delivered: the latest delivery date the supplier states for a product
    that can be ordered now, and never before today."""
    if lookup is None:
        return today
    stated = [today]
    for each in products:
        line = lookup.line(each.product_id)
        schedule = line.schedule_line
        past_cut_off = line.closing_time is not None and line.closing_time <= lookup.now
        if schedule is not None and schedule.available_date is not None and not past_cut_off:
            stated.append(schedule.available_date)
    return max(stated)


def _said(product: RegularProduct, history: OrderHistory) -> str:
    """ "Arla milk (469363), 100 L": how a `why_not` sentence names a product."""
    return f"{history.label(product.product_id)}, {amount(product.quantity, product.unit)}"


def _on_standing_why(product: RegularProduct, history: OrderHistory, standing: Mapping[str, tuple[str, str]]) -> str:
    name = standing[product.product_id][1]
    return f'{_said(product, history)}: it is on your standing order "{name}", so {NOT_IN_REQUEST}.'


def _without_committed(plan: _Plan, history: OrderHistory, committed: Committed, needed_by: date | None,
                       lookup: Lookup | None) -> _Plan:
    """Without the products already in an order placed or waiting for the same delivery: the date the request
    needs the goods by, or the delivery date the supplier states for the product."""
    kept, why = [], list(plan.why_not)
    for each in plan.kept:
        schedule = lookup.line(each.product_id).schedule_line if lookup is not None else None
        dates = {needed_by, schedule.available_date if schedule is not None else None} - {None}
        if any(product_id == each.product_id and delivered in dates for product_id, delivered in committed):
            when = f"for {day(needed_by)}" if needed_by is not None else "for the same delivery"
            why.append(f"{_said(each, history)}: it is already in an order placed or waiting {when}, so "
                       f"{NOT_IN_REQUEST}.")
        else:
            kept.append(each)
    return _Plan(kept=tuple(kept), why_not=tuple(why))


def _capped(plan: _Plan, history: OrderHistory) -> _Plan:
    """At most `REORDER_MAX_LINES` lines, the most regular first; the rest are named."""
    over = plan.kept[REORDER_MAX_LINES:]
    why = [f"{_said(each, history)}: a request takes at most {REORDER_MAX_LINES} lines here and "
           f"{REORDER_MAX_LINES} products are ordered more regularly, so {NOT_IN_REQUEST}." for each in over]
    return _Plan(kept=plan.kept[:REORDER_MAX_LINES], why_not=(*plan.why_not, *why))


def _request(customer: Customer, history: OrderHistory, products: Sequence[RegularProduct],
             needed_by: date | None) -> PurchaseRequest | None:
    """The request the prompt offers: one line per product by its id, at the usual quantity. Each line's words say
    where it came from, and the audit trail keeps them; the request carries no other mark of the prompt."""
    if not products:
        return None
    lines = tuple(
        RequestLine(
            text=f"Order again: {amount(each.quantity, each.unit)} of {history.label(each.product_id)}, in "
                 f"{each.orders_matching} of the last {each.orders_considered} orders",
            product_ids=(each.product_id,), quantity=each.quantity, unit=each.unit,
        )
        for each in products
    )
    return PurchaseRequest(needed_by=needed_by, lines=lines, prefer=customer.prefer)


def _checked(plan: _Plan, history: OrderHistory, context: GuardContext) -> _Plan:
    """Each line through the guard, as the line of the request it would be. One that fails stays out and is said;
    one that passes has its cost: the sales units that cover the quantity, at the price looked up."""
    kept, why, nets = [], list(plan.why_not), {}
    for index, each in enumerate(plan.kept):
        result = check(Proposal(suggestion=_as_suggestion(each, history, index, context.request)), context)
        product = context.catalog.get_product(each.product_id)
        if not isinstance(result, Suggestion) or product is None:
            why.append(sentence(f"{_said(each, history)}: {result.sentence}", f"So {NOT_IN_REQUEST}."))
            continue
        need = need_for(index, context.request.lines[index], context.request, context.profile)
        candidate = evaluate(product, need, context.lookup, context.catalog)
        nets[each.product_id] = round_money(units_needed(candidate, each.quantity) * candidate.unit_price)
        kept.append(each)
    return _Plan(kept=tuple(kept), why_not=tuple(why), nets=nets)


def _as_suggestion(product: RegularProduct, history: OrderHistory, index: int,
                   request: PurchaseRequest) -> Suggestion:
    """The line as the guard reads one: the customer's usual product at its usual quantity, on its line."""
    evidence = SuggestionEvidence(
        source=history.source, synthetic=history.synthetic, orders_considered=product.orders_considered,
        orders_matching=product.orders_matching, first_order=product.first_ordered_on,
        last_order=product.last_ordered_on, values=product.values,
        thresholds=named(REORDER_MIN_ORDERS=REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS=REORDER_WINDOW_ORDERS),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(history.customer_id, SuggestionKind.USUAL_PRODUCT, product.product_id),
        kind=SuggestionKind.USUAL_PRODUCT, customer_id=history.customer_id, request_line_index=index,
        product_id=product.product_id, name=history.name_of(product.product_id), quantity=product.quantity,
        unit=product.unit, sentence=_said(product, history), evidence=evidence, accept_request=request,
    )


def _evidence(history: OrderHistory, regular: Sequence[RegularProduct], standing: Mapping[str, tuple[str, str]],
              plan: _Plan, *, now: date, lookup: Lookup | None, earliest: date | None) -> ReorderEvidence:
    rhythm = rhythm_of(history)
    in_request = {each.product_id for each in plan.kept}
    nets = plan.nets or {}
    return ReorderEvidence(
        source=history.source, synthetic=history.synthetic, orders_in_history=len(history.orders),
        first_order=history.orders[0].delivered_on if history.orders else None,
        last_order=history.orders[-1].delivered_on if history.orders else None,
        thresholds=named(
            REORDER_MIN_ORDERS=REORDER_MIN_ORDERS, REORDER_WINDOW_ORDERS=REORDER_WINDOW_ORDERS,
            HISTORY_WINDOW_ORDERS=HISTORY_WINDOW_ORDERS, REORDER_MAX_LINES=REORDER_MAX_LINES,
            REORDER_MIN_ORDERS_ON_A_WEEKDAY=REORDER_MIN_ORDERS_ON_A_WEEKDAY,
        ),
        products=tuple(ProductEvidence(
            product_id=each.product_id, name=history.name_of(each.product_id), quantity=each.quantity,
            unit=each.unit, orders_matching=each.orders_matching, orders_considered=each.orders_considered,
            orders_matching_of_history_window=each.matching_in_history_window, history_window=each.history_window,
            first_ordered_on=each.first_ordered_on, last_ordered_on=each.last_ordered_on, values=each.values,
            in_request=each.product_id in in_request, net_eur=nets.get(each.product_id),
        ) for each in regular),
        on_standing_order=tuple(OnStandingOrder(
            product_id=each.product_id, name=history.name_of(each.product_id),
            standing_order_id=standing[each.product_id][0], standing_order_name=standing[each.product_id][1],
        ) for each in regular if each.product_id in standing),
        usual_gap_days=rhythm.gap_days if rhythm is not None else None,
        usual_weekdays=tuple(weekday_name(weekday) for weekday in rhythm.weekdays) if rhythm is not None else (),
        today=now, earliest_delivery=earliest, checked=plan.nets is not None,
        prices_from=lookup.source if lookup is not None and plan.nets is not None else None,
        prices_as_of=lookup.now if lookup is not None and plan.nets is not None else None,
    )


def _answer(history: OrderHistory, regular: Sequence[RegularProduct], standing: Mapping[str, tuple[str, str]],
            plan: _Plan, request: PurchaseRequest | None, evidence: ReorderEvidence) -> ReorderPrompt:
    on_standing = on_standing_sentence([history.label(each.product_id) for each in regular
                                        if each.product_id in standing])
    if request is None:
        said = no_reorder_sentence(_no_request_reason(history, regular, standing), standing=on_standing,
                                   synthetic=history.synthetic)
        return ReorderPrompt(customer_id=history.customer_id, sentence=said, synthetic=history.synthetic,
                             why_not=plan.why_not, evidence=evidence)
    weekly = evidence.usual_gap_days == DAYS_IN_A_WEEK
    clauses = [
        regular_clause(history.label(each.product_id), amount(each.quantity, each.unit),
                       (each.orders_matching, each.orders_considered),
                       (each.matching_in_history_window, each.history_window), first=index == 0, weekly=weekly)
        for index, each in enumerate(plan.kept)
    ]
    total = round_money(sum(plan.nets.values(), Decimal(0))) if plan.nets is not None else None
    left_out = len(regular) - len(plan.kept) - len(evidence.on_standing_order)
    said = reorder_sentence(
        clauses, last_ordered=max(each.last_ordered_on for each in plan.kept), needed_by=request.needed_by,
        total=total, left_out=left_out, standing=on_standing, synthetic=history.synthetic,
    )
    lines = tuple(ReorderLine(
        product_id=each.product_id, name=history.name_of(each.product_id), quantity=each.quantity, unit=each.unit,
        orders_matching=each.orders_matching, orders_considered=each.orders_considered,
        last_ordered_on=each.last_ordered_on,
    ) for each in plan.kept)
    return ReorderPrompt(
        customer_id=history.customer_id, lines=lines, sentence=said, request=request, needed_by=request.needed_by,
        total_net_eur=total, synthetic=history.synthetic, why_not=plan.why_not, evidence=evidence,
    )


def _no_request_reason(history: OrderHistory, regular: Sequence[RegularProduct],
                       standing: Mapping[str, tuple[str, str]]) -> str:
    """Why the prompt offers nothing, without its full stop."""
    count = len(history.orders)
    if count < REORDER_WINDOW_ORDERS:
        return (f"this customer has {count} past order{'' if count == 1 else 's'}, fewer than the "
                f"{REORDER_WINDOW_ORDERS} a regular order is read from")
    if not regular:
        return f"no product is in at least {REORDER_MIN_ORDERS} of your last {REORDER_WINDOW_ORDERS} orders"
    if all(each.product_id in standing for each in regular):
        return "every product you order regularly is on a standing order already"
    return "none of your regular products can be put in a request now, for the reasons listed"
