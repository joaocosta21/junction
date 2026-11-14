"""Valio Aimo's back office: what the agent channel brought, and where it is losing sales (lane BO).

Scores on the 20% "how decisions are logged and auditable" (the log read as figures, each saying how it was counted)
and on the 15% "exception situations" (the quantity asked for that confirmed stock did not cover, with the reason).

Nothing is stored and nothing is typed in: every figure is counted, each time it is asked, from the audit trail of
one order book. Only Valio Aimo's view of each event is read (`tta.audit.views.project`), so a limit amount, an
excluded allergen, a name, a note, a buyer's own words and the products left out for a buyer's requirement cannot
reach a figure: they are not in what is read. No figure is given per buyer, so a book with one buyer shows the same
totals and no breakdown that names it. How often Valio Aimo's own suggestion stayed silent is not counted: its view
does not hold it (decision B32).

Cost: one read of the whole trail per answer, as `GET /v1/audit` does up to 1,000 events. A deployment would keep
these counts as a view of the database.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, NamedTuple

from tta.api.insight_models import (
    Demand,
    HowCounted,
    Insights,
    KindRow,
    Missed,
    MissedProduct,
    ReasonCount,
    Shortfall,
    Substitutes,
    SuggestionFigures,
    UnitTotal,
)
from tta.audit.phrases import count, day, joined, money, number, percent
from tta.audit.suggestion_sentences import KIND_WORDS, OWN_KIND, OWN_WORDS
from tta.audit.views import project
from tta.config import Settings
from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEvent, AuditEventType
from tta.contracts.common import AuditReader, AvailabilityState, DataSource, OptionKind, OrderStatus, PlacedBy

JsonDict = dict[str, Any]


class Period(StrEnum):
    TODAY = "today"
    ALL = "all"


ZERO = Decimal(0)
MAX_TOP_PRODUCTS = 5
# Why a quantity could not be confirmed, where the reason is in Valio Aimo's own data. "Closing time" is the word
# of Valio's own webshop (AIMO/build/replan/P3-webshop.md, the mapping table).
OWN_REASONS = {
    "QUANTITY_NOT_CONFIRMED": "quantity not confirmed in the data",
    "CUTOFF_PASSED": "closing time passed",
    "NOT_DELIVERABLE": "cannot be delivered",
    "OUT_OF_STOCK": "out of stock",
}
UNIT_WORDS = {"L": "L", "KG": "kg", "UNIT": "units"}
FREE_FROM = "FREE_FROM_"
NOTHING_YET = "Nothing has been ordered in this demonstration yet. Make a request as a customer, then come back."
NOTE = (
    "Everything here is counted from this demonstration's own activity: the customers and their order history are "
    "synthetic, and prices are {prices}."
)
RECORDED_PRICES, MOCK_PRICES = "from the recording of Valio Aimo's data", "the answers of Valio Aimo's mock API"
NEVER_HERE = (
    "No figure is given per buyer. A buyer's limits, excluded allergens, names, notes and own words, and the "
    "products left out for a buyer's requirement, are not in what is counted."
)
TODAY_SENTENCE = (
    "Today by the clock in force, {day}: a step counts on the day the order book's clock gave it (the audit trail "
    "itself is stamped with the real time)."
)
ALL_SENTENCE = "All time: every step in this order book's audit trail, as the clock stood on {day}."
OWN_SILENT = (
    "How often Valio Aimo's own suggestion stayed silent is not counted: Valio Aimo's view of the log does not hold "
    "it, because a silence can follow from a buyer's requirement."
)
EVERYTHING_COVERED = "Every quantity asked for was covered by confirmed stock."
NO_SUGGESTION = "No suggestion was shown with an offer."
DEMAND_COUNTED = (
    HowCounted(figure="Requests and offers", how="One per \"request received\" and per \"offer made\" step. A "
               "suggestion that was accepted is sent as a new request and counts as one."),
    HowCounted(figure="Orders", how="Each order once, by its latest step: confirmed by a person, placed by the "
               "agent alone, rejected, expired (also when its approval's time has passed), or still waiting."),
    HowCounted(figure="Euros", how="The net total, before tax, of the option as ordered, at the fixed prices of "
               "the offer: confirmed orders, and orders still waiting for a person."),
)
SUGGESTIONS_COUNTED = (
    HowCounted(figure="Shown and accepted", how="Each suggestion of each \"suggestions shown\" step, by kind, and "
               "each \"suggestion accepted\" step. The rate is accepted over shown."),
    HowCounted(figure="Ordered", how="An accepted suggestion whose amended offer, or an offer amended from it, "
               "has an order confirmed by a person or placed by the agent."),
    HowCounted(figure="Added and saved", how="For an accepted suggestion, the net value of its product in the "
               "amended offer minus the net value of the product it replaces (or of the same product) in the "
               "offer before. Rises are summed as added, falls as saved for the buyer; the two are never netted."),
)
MISSED_COUNTED = (
    HowCounted(figure="Not confirmed", how="Per requested line of each offer: the quantity asked for minus what "
               "the best confirmed option covers. An offer replaced by an accepted suggestion is counted once, "
               "as the amended offer."),
    HowCounted(figure="Euros", how="The quantity not confirmed at the average net price of what the same offer "
               "did cover. Counted for one-line requests; a line with no offered price has no value."),
    HowCounted(figure="Reasons and products", how="Products that matched a request and were left out for a reason "
               "in Valio Aimo's own data, or offered with a quantity that is not confirmed. Products left out for "
               "a requirement of the buyer's are not shown or counted."),
    HowCounted(figure="Substitutes", how="Offers with a substitute line; orders with one that a person confirmed, "
               "or rejected."),
)


class _Step(NamedTuple):
    kind: str
    offer_id: str | None
    facts: JsonDict
    time: datetime


class _Order(NamedTuple):
    status: str
    placed_by: str | None
    net: Decimal
    offer_id: str | None
    substitute: bool
    valid_until: datetime | None


def _dict(value: Any) -> JsonDict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[JsonDict]:
    return [one for one in value if isinstance(one, dict)] if isinstance(value, list) else []


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None and not isinstance(value, bool) else ZERO
    except InvalidOperation:
        return ZERO


def _time(value: Any) -> datetime | None:
    try:
        found = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return found if found is not None and found.tzinfo is not None else None


def _steps(events: Iterable[AuditEvent]) -> list[_Step]:
    """Each event as Valio Aimo reads it: its type, its offer, its facts in the supplier's view, its real time."""
    steps = []
    for event in events:
        facts = project(event, AuditReader.SUPPLIER).facts
        offer_id = event.data.offer_id or _dict(facts.get("offer")).get("offer_id")
        steps.append(_Step(event.type.removeprefix(EVENT_TYPE_PREFIX), offer_id, facts, event.time))
    return steps


def _in_period(steps: Sequence[_Step], offers: dict[str, JsonDict], now: datetime, period: Period) -> list[_Step]:
    """The steps of the period. A step is dated by the order book's clock: its order's last change, else its
    offer's creation, else the real time it was stamped with."""
    if period is Period.ALL:
        return list(steps)

    def when(step: _Step) -> datetime:
        changed = _time(_dict(step.facts.get("order")).get("updated_at"))
        return changed or _time(offers.get(step.offer_id or "", {}).get("created_at")) or step.time

    return [step for step in steps if when(step).astimezone(now.tzinfo).date() == now.date()]


def _has_substitute(option: JsonDict) -> bool:
    return any(line.get("substitute_for") for line in _list(option.get("lines")))


def _orders(steps: Sequence[_Step], now: datetime) -> dict[str, _Order]:
    """Each order as its latest step leaves it. One still waiting after its approval's time counts as expired."""
    found: dict[str, _Order] = {}
    for step in steps:
        order = _dict(step.facts.get("order"))
        order_id = order.get("order_id")
        if not isinstance(order_id, str):
            continue
        option, before = _dict(order.get("option")), found.get(order_id)
        valid_until = _time(_dict(step.facts.get("approval")).get("valid_until")) or (
            before.valid_until if before else None)
        status = str(order.get("status"))
        if status == OrderStatus.PENDING_APPROVAL and valid_until is not None and valid_until < now:
            status = OrderStatus.EXPIRED.value
        found[order_id] = _Order(status, order.get("placed_by"), _dec(_dict(option.get("totals")).get("net")),
                                 order.get("offer_id"), _has_substitute(option), valid_until)
    return found


def _demand(steps: Sequence[_Step], orders: dict[str, _Order]) -> Demand:
    kinds = Counter(step.kind for step in steps)
    ordered = [order for order in orders.values() if order.status == OrderStatus.ORDERED]
    waiting = [order for order in orders.values() if order.status == OrderStatus.PENDING_APPROVAL]
    by_person = sum(order.placed_by == PlacedBy.HUMAN_APPROVAL for order in ordered)
    by_agent = sum(order.placed_by == PlacedBy.AGENT for order in ordered)
    statuses = Counter(order.status for order in orders.values())
    rejected, expired = statuses[OrderStatus.REJECTED], statuses[OrderStatus.EXPIRED]
    confirmed_net, waiting_net = sum((o.net for o in ordered), ZERO), sum((o.net for o in waiting), ZERO)
    requests, offers = kinds[AuditEventType.REQUEST_RECEIVED], kinds[AuditEventType.OFFER_CREATED]
    sentence = (
        f"{count(requests, 'request')} came in through the agent channel and {count(offers, 'offer')} went out. "
        f"{count(len(orders), 'order')} {'was' if len(orders) == 1 else 'were'} prepared: {by_person} confirmed by "
        f"a person ({money(confirmed_net)} before tax), {by_agent} placed by the agent alone, {len(waiting)} waiting "
        f"for a person ({money(waiting_net)}), {rejected} rejected and {expired} expired."
    )
    return Demand(
        requests=requests, offers=offers, orders_prepared=len(orders), confirmed_by_person=by_person,
        placed_by_agent=by_agent, waiting=len(waiting), rejected=rejected, expired=expired,
        confirmed_net_eur=confirmed_net, waiting_net_eur=waiting_net, sentence=sentence, counted=DEMAND_COUNTED,
    )


# --- suggestions --------------------------------------------------------------------------------------------


def _first_option(offer: JsonDict | None) -> JsonDict:
    options = _list(_dict(offer).get("options"))
    return options[0] if options else {}


def _net_of(offer: JsonDict | None, product_id: Any) -> Decimal | None:
    """The net value of one product in the first option of an offer; None when the option does not hold it."""
    lines = [line for line in _list(_first_option(offer).get("lines")) if line.get("product_id") == product_id]
    return sum((_dec(line.get("net")) for line in lines), ZERO) if lines else None


def _value_change(accepted: JsonDict, offers: dict[str, JsonDict]) -> Decimal | None:
    """What accepting changed in the basket, before tax; None when the two offers do not let it be valued."""
    after = _net_of(offers.get(str(accepted.get("new_offer_id"))), accepted.get("product_id"))
    if after is None:
        return None
    old, replaced = offers.get(str(accepted.get("offer_id"))), accepted.get("replaces_product_id")
    if replaced is None:
        return after - (_net_of(old, accepted.get("product_id")) or ZERO)
    before = _net_of(old, replaced)
    return None if before is None else after - before


def _led_to_an_order(offer_id: str, amended: dict[str, list[str]], ordered_offers: set[str]) -> bool:
    """Whether this offer, or an offer amended from it by a later accepted suggestion, has a confirmed order."""
    waiting, seen = [offer_id], set()
    while waiting:
        one = waiting.pop()
        if one in ordered_offers:
            return True
        if one not in seen:
            seen.add(one)
            waiting.extend(amended.get(one, ()))
    return False


def _kind_label(kind: str) -> str:
    return OWN_WORDS if kind == OWN_KIND else KIND_WORDS.get(kind, kind.lower().replace("_", " ")).capitalize()


def _suggestions(steps: Sequence[_Step], offers: dict[str, JsonDict], orders: dict[str, _Order]) -> SuggestionFigures:
    accepted_steps = [_dict(step.facts.get("suggestion")) for step in steps
                      if step.kind == AuditEventType.SUGGESTION_ACCEPTED]
    amended: dict[str, list[str]] = defaultdict(list)
    for one in accepted_steps:
        amended[str(one.get("offer_id"))].append(str(one.get("new_offer_id")))
    ordered_offers = {o.offer_id for o in orders.values() if o.status == OrderStatus.ORDERED and o.offer_id}
    shown: Counter[str] = Counter(
        str(each.get("kind")) for step in steps if step.kind == AuditEventType.SUGGESTIONS_SHOWN
        for each in _list(_dict(step.facts.get("suggestions")).get("shown")))
    accepted: Counter[str] = Counter()
    ordered: Counter[str] = Counter()
    added: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    saved: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    not_valued = 0
    for one in accepted_steps:
        kind, change = str(one.get("kind")), _value_change(one, offers)
        accepted[kind] += 1
        ordered[kind] += _led_to_an_order(str(one.get("new_offer_id")), amended, ordered_offers)
        not_valued += change is None
        added[kind] += max(change or ZERO, ZERO)
        saved[kind] += max(-(change or ZERO), ZERO)
    order = [*KIND_WORDS, *sorted((set(shown) | set(accepted)) - set(KIND_WORDS) - {OWN_KIND}), OWN_KIND]
    rows = tuple(
        KindRow(kind=kind, label=_kind_label(kind), own=kind == OWN_KIND, shown=shown[kind], accepted=accepted[kind],
                ordered=ordered[kind], added_net_eur=added[kind], saved_net_eur=saved[kind])
        for kind in dict.fromkeys(order) if shown[kind] or accepted[kind]
    )
    return _suggestion_figures(rows, not_valued)


def _suggestion_figures(rows: tuple[KindRow, ...], not_valued: int) -> SuggestionFigures:
    shown, accepted = sum(row.shown for row in rows), sum(row.accepted for row in rows)
    ordered = sum(row.ordered for row in rows)
    added = sum((row.added_net_eur for row in rows), ZERO)
    saved = sum((row.saved_net_eur for row in rows), ZERO)
    rate = Decimal(accepted) / Decimal(shown) if shown else None
    sentence = NO_SUGGESTION if not shown else (
        f"{count(shown, 'suggestion')} {'was' if shown == 1 else 'were'} shown with offers and {accepted} "
        f"{'was' if accepted == 1 else 'were'} accepted ({percent(rate or ZERO)}); {ordered} of those ended in a "
        f"confirmed order. Accepted suggestions added {money(added)} to baskets and saved buyers {money(saved)}."
    )
    return SuggestionFigures(
        shown=shown, accepted=accepted, ordered=ordered, acceptance_rate=rate, added_net_eur=added,
        saved_net_eur=saved, not_valued=not_valued, by_kind=rows, own_silent=OWN_SILENT, sentence=sentence,
        counted=SUGGESTIONS_COUNTED,
    )


# --- sales not made -----------------------------------------------------------------------------------------


def _claim_words(code: str) -> str:
    """FREE_FROM_LACTOSE -> lactose-free; any other claim in lower case."""
    if code.startswith(FREE_FROM):
        return f"{code.removeprefix(FREE_FROM).lower().replace('_', ' ')}-free"
    return code.lower().replace("_", " ")


def _line_label(line: JsonDict, names: dict[str, str]) -> str:
    """What a requested line asked for, in Valio Aimo's own terms: the product type with its claims, or the
    product by name. Never the buyer's own words, which Valio Aimo's view does not hold."""
    kind = line.get("product_type")
    if isinstance(kind, str) and kind:
        claims = [_claim_words(str(code)) for code in line.get("required_claims") or ()]
        return " ".join([*claims, kind.replace("_", " ")])
    ids = [str(one) for one in line.get("product_ids") or ()]
    if not ids:
        return "a product named in words"
    return f"{names[ids[0]]} ({ids[0]})" if ids[0] in names else f"product {ids[0]}"


class _Short:
    """What one product type, in one unit, was asked for and not confirmed, summed over the offers of the period."""

    def __init__(self) -> None:
        self.asked = self.confirmed = self.missing = ZERO
        self.value: Decimal | None = None
        self.requests = 0
        self.products: defaultdict[str, set[str]] = defaultdict(set)  # reason -> the products it kept out


def _unit_price(offer: JsonDict) -> Decimal | None:
    """The average net price per requested unit of what an offer covers: of its best confirmed option, else of
    the first option that covers anything."""
    options = _list(offer.get("options"))
    for option in sorted(options, key=lambda one: one.get("kind") != OptionKind.BEST_CONFIRMED):
        covered = sum((_dec(part.get("covered")) for part in _list(option.get("coverage"))), ZERO)
        if covered > ZERO:
            return _dec(_dict(option.get("totals")).get("net")) / covered
    return None


def _coverage(offer: JsonDict, lines: Sequence[JsonDict]) -> list[JsonDict]:
    """What the best confirmed option covers of each requested line; nothing of any line when there is none."""
    best = next((one for one in _list(offer.get("options")) if one.get("kind") == OptionKind.BEST_CONFIRMED), None)
    if best is not None:
        return _list(best.get("coverage"))
    return [{"request_line_index": index, "requested": line.get("quantity"), "covered": 0, "unit": line.get("unit"),
             "missing": line.get("quantity")} for index, line in enumerate(lines)]


def _not_confirmed_products(offer: JsonDict) -> dict[str, str | None]:
    """Product id -> name of the lines offered with a quantity that is not confirmed."""
    return {str(line.get("product_id")): line.get("name")
            for option in _list(offer.get("options")) for line in _list(option.get("lines"))
            if _dict(line.get("availability")).get("state") == AvailabilityState.QUANTITY_NOT_CONFIRMED}


def _names(offer: JsonDict) -> dict[str, str]:
    named = [*_list(offer.get("left_out")), *(line for option in _list(offer.get("options"))
                                              for line in _list(option.get("lines")))]
    return {str(one["product_id"]): str(one["name"]) for one in named if one.get("product_id") and one.get("name")}


def _missed(steps: Sequence[_Step], requests: dict[str, JsonDict], orders: dict[str, _Order]) -> Missed:
    replaced = {str(_dict(step.facts.get("suggestion")).get("offer_id")) for step in steps
                if step.kind == AuditEventType.SUGGESTION_ACCEPTED}
    offers = [_dict(step.facts.get("offer")) for step in steps
              if step.kind == AuditEventType.OFFER_CREATED and step.offer_id not in replaced]
    shorts: defaultdict[tuple[str, str], _Short] = defaultdict(_Short)
    times: Counter[tuple[str, str]] = Counter()
    names: dict[str, str | None] = {}
    for offer in offers:
        lines = _list(_dict(requests.get(str(offer.get("offer_id")))).get("lines"))
        unconfirmed = _not_confirmed_products(offer)
        left_out = [one for one in _list(offer.get("left_out")) if one.get("reason") in OWN_REASONS]
        for product_id, reason in {*((str(one.get("product_id")), str(one.get("reason"))) for one in left_out),
                                   *((product_id, "QUANTITY_NOT_CONFIRMED") for product_id in unconfirmed)}:
            times[product_id, reason] += 1
        names.update({str(one.get("product_id")): one.get("name") for one in left_out} | unconfirmed)
        short = [part for part in _coverage(offer, lines) if _dec(part.get("missing")) > ZERO]
        price = _unit_price(offer) if len(lines) == 1 else None
        for part in short:
            index = part.get("request_line_index")
            line = lines[index] if isinstance(index, int) and 0 <= index < len(lines) else {}
            entry = shorts[_line_label(line, _names(offer)), str(part.get("unit"))]
            entry.requests += 1
            entry.asked += _dec(part.get("requested"))
            entry.confirmed += _dec(part.get("covered"))
            entry.missing += _dec(part.get("missing"))
            if price is not None:
                entry.value = (entry.value or ZERO) + price * _dec(part.get("missing"))
            for one in left_out:
                if one.get("request_line_index") == index:
                    entry.products[str(one.get("reason"))].add(str(one.get("product_id")))
            if len(short) == 1:  # an option line does not say which requested line it serves
                entry.products["QUANTITY_NOT_CONFIRMED"].update(unconfirmed)
    return _missed_figures(shorts, times, names, offers, orders)


def _shortfall(label: str, unit: str, short: _Short) -> Shortfall:
    word = UNIT_WORDS.get(unit, unit.lower())
    valued = f", about €{short.value:,.0f} at the offered price," if short.value is not None else ""
    sentence = (
        f"{number(short.confirmed)} of {number(short.asked)} {word} of {label} could be confirmed: "
        f"{number(short.missing)} {word}{valued} {'was' if short.missing == 1 else 'were'} not."
    )
    reasons = tuple(ReasonCount(reason=reason, label=OWN_REASONS[reason], products=len(short.products[reason]))
                    for reason in OWN_REASONS if short.products.get(reason))
    return Shortfall(label=label, unit=unit, requests=short.requests, asked=short.asked, confirmed=short.confirmed,
                     not_confirmed=short.missing, value_net_eur=short.value, reasons=reasons, sentence=sentence)


def _missed_figures(
    shorts: dict[tuple[str, str], _Short], times: Counter[tuple[str, str]], names: dict[str, str | None],
    offers: Sequence[JsonDict], orders: dict[str, _Order],
) -> Missed:
    rows = sorted((_shortfall(label, unit, short) for (label, unit), short in shorts.items()),
                  key=lambda row: (-(row.value_net_eur or ZERO), -row.not_confirmed, row.label))
    by_unit: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        by_unit[row.unit] += row.not_confirmed
    value = sum((row.value_net_eur or ZERO for row in rows), ZERO)
    top = tuple(
        MissedProduct(product_id=product_id, name=names.get(product_id), times=number_of, reason=reason,
                      reason_label=OWN_REASONS[reason])
        for (product_id, reason), number_of in sorted(times.items(), key=lambda one: (-one[1], one[0]))
    )[:MAX_TOP_PRODUCTS]
    with_substitute = [order for order in orders.values() if order.substitute]
    substitutes = Substitutes(
        offered=sum(any(_has_substitute(option) for option in _list(offer.get("options"))) for offer in offers),
        accepted=sum(o.status == OrderStatus.ORDERED and o.placed_by == PlacedBy.HUMAN_APPROVAL
                     for o in with_substitute),
        refused=sum(o.status == OrderStatus.REJECTED for o in with_substitute),
    )
    amounts = joined(f"{number(amount)} {UNIT_WORDS.get(unit, unit.lower())}" for unit, amount in by_unit.items())
    sentence = EVERYTHING_COVERED if not rows else (
        f"{amounts} asked for could not be covered by confirmed stock: about €{value:,.0f} at offered prices."
    )
    return Missed(
        shortfalls=tuple(rows), value_net_eur=value, top_products=top, substitutes=substitutes, sentence=sentence,
        not_confirmed=tuple(UnitTotal(unit=unit, quantity=amount) for unit, amount in by_unit.items()),
        counted=MISSED_COUNTED,
    )


def is_recorded(settings: Settings) -> bool:
    """Whether prices come from a recording of Valio Aimo's data (replay) and not from the mock API as it answers."""
    return settings.tta_mode is DataSource.REPLAY


def insights(
    events: Iterable[AuditEvent], *, now: datetime, period: Period = Period.TODAY, recorded: bool = True,
) -> Insights:
    """The figures of one order book's audit trail for Valio Aimo's reader. `now`: the clock in force, which says
    what "today" is. `recorded`: whether prices come from a recording (replay) or from the mock API as it answers."""
    steps = _steps(events)
    offers = {str(step.offer_id): _dict(step.facts.get("offer")) for step in steps
              if step.kind == AuditEventType.OFFER_CREATED}
    requests = {str(step.offer_id): _dict(step.facts.get("request")) for step in steps
                if step.kind == AuditEventType.REQUEST_PARSED}
    chosen = _in_period(steps, offers, now, period)
    orders = _orders(chosen, now)
    demand = _demand(chosen, orders)
    return Insights(
        period=period.value, as_of=now,
        period_sentence=(TODAY_SENTENCE if period is Period.TODAY else ALL_SENTENCE).format(day=day(now.date())),
        note=NOTE.format(prices=RECORDED_PRICES if recorded else MOCK_PRICES), never_here=NEVER_HERE,
        empty=not (demand.requests or demand.offers or demand.orders_prepared), empty_sentence=NOTHING_YET,
        demand=demand, suggestions=_suggestions(chosen, offers, orders), missed=_missed(chosen, requests, orders),
    )
