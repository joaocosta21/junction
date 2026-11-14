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
from decimal import Decimal
from typing import Any

from tta.api.insight_missed import missed
from tta.api.insight_models import Demand, HowCounted, Insights, KindRow, SuggestionFigures
from tta.api.insight_steps import (
    ZERO,
    JsonDict,
    Order,
    Period,
    Step,
    as_decimal,
    as_dict,
    as_list,
    in_period,
    orders_of,
    steps_of,
)
from tta.audit.phrases import count, day, money, percent
from tta.audit.suggestion_sentences import KIND_WORDS, OWN_KIND, OWN_WORDS
from tta.config import Settings
from tta.contracts.audit import AuditEvent, AuditEventType
from tta.contracts.common import DataSource, OrderStatus, PlacedBy

__all__ = ["Period", "insights", "is_recorded"]

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


def _demand(steps: Sequence[Step], orders: dict[str, Order]) -> Demand:
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
    options = as_list(as_dict(offer).get("options"))
    return options[0] if options else {}


def _net_of(offer: JsonDict | None, product_id: Any) -> Decimal | None:
    """The net value of one product in the first option of an offer; None when the option does not hold it."""
    lines = [line for line in as_list(_first_option(offer).get("lines")) if line.get("product_id") == product_id]
    return sum((as_decimal(line.get("net")) for line in lines), ZERO) if lines else None


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


def _suggestions(steps: Sequence[Step], offers: dict[str, JsonDict], orders: dict[str, Order]) -> SuggestionFigures:
    accepted_steps = [as_dict(step.facts.get("suggestion")) for step in steps
                      if step.kind == AuditEventType.SUGGESTION_ACCEPTED]
    amended: dict[str, list[str]] = defaultdict(list)
    for one in accepted_steps:
        amended[str(one.get("offer_id"))].append(str(one.get("new_offer_id")))
    ordered_offers = {o.offer_id for o in orders.values() if o.status == OrderStatus.ORDERED and o.offer_id}
    shown: Counter[str] = Counter(
        str(each.get("kind")) for step in steps if step.kind == AuditEventType.SUGGESTIONS_SHOWN
        for each in as_list(as_dict(step.facts.get("suggestions")).get("shown")))
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


def is_recorded(settings: Settings) -> bool:
    """Whether prices come from a recording of Valio Aimo's data (replay) and not from the mock API as it answers."""
    return settings.tta_mode is DataSource.REPLAY


def insights(
    events: Iterable[AuditEvent], *, now: datetime, period: Period = Period.TODAY, recorded: bool = True,
) -> Insights:
    """The figures of one order book's audit trail for Valio Aimo's reader. `now`: the clock in force, which says
    what "today" is. `recorded`: whether prices come from a recording (replay) or from the mock API as it answers."""
    steps = steps_of(events)
    offers = {str(step.offer_id): as_dict(step.facts.get("offer")) for step in steps
              if step.kind == AuditEventType.OFFER_CREATED}
    requests = {str(step.offer_id): as_dict(step.facts.get("request")) for step in steps
                if step.kind == AuditEventType.REQUEST_PARSED}
    chosen = in_period(steps, offers, now, period)
    orders = orders_of(chosen, now)
    demand = _demand(chosen, orders)
    return Insights(
        period=period.value, as_of=now,
        period_sentence=(TODAY_SENTENCE if period is Period.TODAY else ALL_SENTENCE).format(day=day(now.date())),
        note=NOTE.format(prices=RECORDED_PRICES if recorded else MOCK_PRICES), never_here=NEVER_HERE,
        empty=not (demand.requests or demand.offers or demand.orders_prepared), empty_sentence=NOTHING_YET,
        demand=demand, suggestions=_suggestions(chosen, offers, orders), missed=missed(chosen, requests, orders),
    )
