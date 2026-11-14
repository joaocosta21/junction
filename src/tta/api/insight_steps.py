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


def in_period(steps: Sequence[Step], offers: dict[str, JsonDict], now: datetime, period: Period) -> list[Step]:
    """The steps of the period. A step is dated by the order book's clock: its order's last change, else its
    offer's creation, else the real time it was stamped with."""
    if period is Period.ALL:
        return list(steps)

    def when(step: Step) -> datetime:
        changed = as_time(as_dict(step.facts.get("order")).get("updated_at"))
        return changed or as_time(offers.get(step.offer_id or "", {}).get("created_at")) or step.time

    return [step for step in steps if when(step).astimezone(now.tzinfo).date() == now.date()]


def has_substitute(option: JsonDict) -> bool:
    return any(line.get("substitute_for") for line in as_list(option.get("lines")))


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
                                 order.get("offer_id"), has_substitute(option), valid_until)
    return found
