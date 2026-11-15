"""What the back office's figures are counted from (lane BO): each audit event as Valio Aimo reads it, the steps
of a period, and each order as its latest step leaves it. Only the supplier's view of an event is read
(`tta.audit.views.project`): what Valio Aimo may not see is not in a step.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, NamedTuple

from tta.audit.views import project
from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEvent
from tta.contracts.common import AuditReader, OrderStatus

JsonDict = dict[str, Any]


class Period(StrEnum):
    TODAY = "today"
    ALL = "all"


ZERO = Decimal(0)


class Step(NamedTuple):
    kind: str
    offer_id: str | None
    facts: JsonDict
    time: datetime


class Order(NamedTuple):
    status: str
    placed_by: str | None
    net: Decimal
    offer_id: str | None
    substitute: bool
    valid_until: datetime | None
    substitute_covers: Decimal = ZERO  # what its substitute lines cover, in the unit of the request


def as_dict(value: Any) -> JsonDict:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[JsonDict]:
    return [one for one in value if isinstance(one, dict)] if isinstance(value, list) else []


def as_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value)) if value is not None and not isinstance(value, bool) else ZERO
    except InvalidOperation:
        return ZERO


def as_time(value: Any) -> datetime | None:
    try:
        found = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return found if found is not None and found.tzinfo is not None else None


def steps_of(events: Iterable[AuditEvent]) -> list[Step]:
    """Each event as Valio Aimo reads it: its type, its offer, its facts in the supplier's view, its real time."""
    steps = []
    for event in events:
        facts = project(event, AuditReader.SUPPLIER).facts
        offer_id = event.data.offer_id or as_dict(facts.get("offer")).get("offer_id")
        steps.append(Step(event.type.removeprefix(EVENT_TYPE_PREFIX), offer_id, facts, event.time))
    return steps


def _carried(times: Sequence[datetime | None]) -> list[datetime | None]:
    """Each gap filled with the time before it, and a gap at the start with the first time after it."""
    filled: list[datetime | None] = []
    last = next((time for time in times if time is not None), None)
    for time in times:
        last = time or last
        filled.append(last)
    return filled


def in_period(
    steps: Sequence[Step], offers: dict[str, JsonDict], now: datetime, period: Period, *, recorded: bool = False
) -> list[Step]:
    """The steps of the period. A step is dated by the order book's clock: its order's last change, else its
    offer's creation. A step with neither (a request the reader answered with a question, so no offer was made)
    carries the real time only, which under a recorded or demo clock is never the clock's day: it is dated as
    the step before it in the same trail, else as the first dated step after it. Where a trail holds no step of
    the book's clock at all, such a step counts on the clock's day in a recorded book (`recorded`: its clock
    stands still, so every step was made on that day), and by its real time where the clock is the supplier's."""
    if period is Period.ALL:
        return list(steps)

    def by_the_clock(step: Step) -> datetime | None:
        changed = as_time(as_dict(step.facts.get("order")).get("updated_at"))
        return changed or as_time(offers.get(step.offer_id or "", {}).get("created_at"))

    dated = _carried([by_the_clock(step) for step in steps])
    return [
        step for step, when in zip(steps, dated, strict=True)
        if (when or (now if recorded else step.time)).astimezone(now.tzinfo).date() == now.date()
    ]


def has_substitute(option: JsonDict) -> bool:
    return any(line.get("substitute_for") for line in as_list(option.get("lines")))


def substitute_covers(option: JsonDict) -> Decimal:
    """What the substitute lines of an option cover, in the unit of the request."""
    lines = [line for line in as_list(option.get("lines")) if line.get("substitute_for")]
    return sum((as_decimal(line.get("covers")) for line in lines), ZERO)


def orders_of(steps: Sequence[Step], now: datetime) -> dict[str, Order]:
    """Each order as its latest step leaves it. One still waiting after its approval's time counts as expired."""
    found: dict[str, Order] = {}
    for step in steps:
        order = as_dict(step.facts.get("order"))
        order_id = order.get("order_id")
        if not isinstance(order_id, str):
            continue
        option, before = as_dict(order.get("option")), found.get(order_id)
        valid_until = as_time(as_dict(step.facts.get("approval")).get("valid_until")) or (
            before.valid_until if before else None)
        status = str(order.get("status"))
        if status == OrderStatus.PENDING_APPROVAL and valid_until is not None and valid_until < now:
            status = OrderStatus.EXPIRED.value
        found[order_id] = Order(status, order.get("placed_by"), as_decimal(as_dict(option.get("totals")).get("net")),
                                 order.get("offer_id"), has_substitute(option), valid_until,
                                 substitute_covers(option))
    return found
