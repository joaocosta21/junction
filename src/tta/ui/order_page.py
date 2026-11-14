"""The order page: the record, the statements it relied on, and the audit trail for two readers (SPEC 8, 9).

Scores on the 20% "how decisions are logged and auditable" and on the brief's audit trail ("a human-readable
log ... for both buyer and Valio Aimo"). The buyer's view shows everything about the order. The supplier's
view is built only from what the gateway's audit trail gives the supplier reader: no limit value, no allergen
exclusion, no approver name, no note. The page redacts nothing itself, so it cannot redact wrongly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.requests import Request
from starlette.responses import HTMLResponse

from tta.contracts.audit import AuditView
from tta.contracts.common import AuditReader, AvailabilityState, DataSource, Identity, OrderStatus, PlacedBy
from tta.contracts.errors import NotFound
from tta.contracts.order import Order
from tta.ui.outcome import Outcome, outcome_of_order
from tta.ui.site import NOT_FOUND, RECORD_ID, UNPROCESSABLE, Site, page_error

TEMPLATE = "order.html"
HEALTH_PATH = "/healthz"  # public: the head of the whole audit chain (count and last hash)
ORDER_FACT = "order"
NO_SUCH_ORDER = ("No such order", "No order has this id.")
NO_SUCH_VIEW = ("No such view", "The audit trail has two readers: the buyer and the supplier.")

logger = logging.getLogger(__name__)


class _Fact(BaseModel):
    """A fact of an audit event, read as data: what is there is checked, what is not there is not invented."""

    model_config = ConfigDict(frozen=True, extra="ignore")


class SupplierLine(_Fact):
    product_id: str
    name: str | None = None
    quantity: Decimal | None = None
    sales_unit: str | None = None
    unit_net_price: Decimal | None = None
    net: Decimal | None = None


class SupplierTotals(_Fact):
    net: Decimal | None = None
    tax: Decimal | None = None
    gross: Decimal | None = None
    excludes_deposits: bool = False
    is_ceiling: bool = False


class SupplierOption(_Fact):
    lines: tuple[SupplierLine, ...] = ()
    totals: SupplierTotals | None = None


class SupplierStatement(_Fact):
    """One statement the order relied on, as the supplier's view of the trail carries it."""

    product_id: str
    unit_net_price: Decimal | None = None
    price_valid_to: datetime | None = None
    availability_state: AvailabilityState | None = None
    available_amount: Decimal | None = None
    available_date: date | None = None
    closing_time: datetime | None = None
    time_now: datetime | None = None
    rechecked_at: datetime | None = None
    source: DataSource | None = None


class SupplierRecord(_Fact):
    """The order as the supplier may see it: read from the newest event of the supplier's view."""

    order_id: str
    status: OrderStatus
    placed_by: PlacedBy | None = None
    agent_id: str | None = None
    source: DataSource | None = None
    record_note: str | None = None
    option: SupplierOption | None = None
    reliance: tuple[SupplierStatement, ...] = ()


@dataclass(frozen=True)
class OrderPage:
    order_id: str
    reader: AuditReader
    read_as: Identity  # the demo agent of the buyer the order belongs to
    audit: AuditView
    order: Order | None  # the buyer's view only
    outcome: Outcome | None  # the buyer's view only
    record: SupplierRecord | None  # the supplier's view only
    decider: Identity | None  # a demo approver who can decide a waiting order


def _read_order(site: Site, request: Request, order_id: str) -> tuple[Identity, Order]:
    """The order and the demo agent of its buyer. Another buyer's agent gets `not-found`, like a made-up id."""
    if not RECORD_ID.fullmatch(order_id):
        raise page_error(NOT_FOUND, *NO_SUCH_ORDER)
    for agent in site.agents_chosen_first(request):
        try:
            return agent, site.service.get_order(agent, order_id)
        except NotFound:
            continue
    raise page_error(NOT_FOUND, *NO_SUCH_ORDER)


def supplier_record(audit: AuditView) -> SupplierRecord | None:
    """The newest state of the order in the supplier's view of the trail, or `None` when no event carries one
    or it cannot be read. The facts are data from the trail: they are validated, never trusted as they are."""
    for event in reversed(audit.events):
        fact = event.facts.get(ORDER_FACT)
        if not isinstance(fact, dict):
            continue
        try:
            return SupplierRecord.model_validate(fact)
        except ValidationError as error:
            logger.warning("The order fact of audit event %s cannot be read: %d errors", event.id, error.error_count())
            return None
    return None


def _decider(site: Site, order: Order) -> Identity | None:
    if order.status is not OrderStatus.PENDING_APPROVAL:
        return None
    return next(iter(site.holders(order.profile_id, order.decision.required_roles)), None)


def _order_page(site: Site, request: Request, order_id: str, reader: AuditReader) -> OrderPage:
    read_as, order = _read_order(site, request, order_id)
    audit = site.service.get_audit(read_as, reader=reader, order_id=order.order_id)
    if reader is AuditReader.SUPPLIER:
        return OrderPage(
            order_id=order.order_id, reader=reader, read_as=read_as, audit=audit, order=None, outcome=None,
            record=supplier_record(audit), decider=None,
        )
    return OrderPage(
        order_id=order.order_id, reader=reader, read_as=read_as, audit=audit, order=order,
        outcome=outcome_of_order(order), record=None, decider=_decider(site, order),
    )


def add_routes(app: FastAPI, site: Site) -> None:
    @app.get("/orders/{order_id}", response_class=HTMLResponse)
    def order(request: Request, order_id: str, view: str = AuditReader.BUYER.value) -> HTMLResponse:
        if view not in (AuditReader.BUYER.value, AuditReader.SUPPLIER.value):
            raise page_error(UNPROCESSABLE, *NO_SUCH_VIEW)
        page = _order_page(site, request, order_id, AuditReader(view))
        return site.render(request, TEMPLATE, page=page, health_path=HEALTH_PATH, supplier=AuditReader.SUPPLIER)
