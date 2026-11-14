"""The page "Standing orders": a kitchen's recurring order, its history, and a renewal checked for drift (STAND-1).

Scores on the 20% "autonomy and controls" and on Valio Aimo's scenario "the agent learns a kitchen's recurring weekly
order and flags anomalies (portion counts creeping up, cost drifting) before auto-renewing it". The visitor loads
the standing orders of the demo customers' files (the hotel's: 100 L of 469363 a week) with their synthetic past
orders, renews one with this week's quantity, and sees the drift found and the outcome: ordered alone, or the
approval it waits for (rule P-08). Under each standing order the page says what the customer's past orders show
(`tta.suggestions.standing_order_trends`: the school's oat drink has grown to a median of 84 L against a stored
60 L), with one button that renews once at that quantity: a renewal like any other, under every rule.

The history the Valio Aimo mock cannot give is synthetic, and the page says so on every such row. Everything is in
the visitor's own order book; the standing-order service of a book is built on its first use (`StandingBooks`).
"""

from __future__ import annotations

import threading
import weakref
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.api.sandbox import Sandbox, file_profile
from tta.config import Settings
from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEventType
from tta.contracts.common import DataSource, Identity
from tta.contracts.errors import TtaError
from tta.contracts.order import Order
from tta.contracts.policy import RuleSummary
from tta.contracts.ports import Clock, ValioGateway
from tta.contracts.standing import Renewal, RenewStandingOrder, StandingOrder
from tta.contracts.suggestion import Suggestion
from tta.customers import shipped_customer
from tta.standing import StandingOrders
from tta.standing.demo import DEMO_PROFILE_ID, DEMO_STANDING_ORDER_ID, load_customer_standing_orders
from tta.standing.models import RenewalOutcome
from tta.suggestions import history_of, standing_order_trends
from tta.ui.site import NOT_FOUND, RECORD_ID, UNPROCESSABLE, Site, page_error
from tta.valio import ReplayGateway

STANDING_PATH = "/standing-orders"
DEMO_PATH = f"{STANDING_PATH}/demo"
TEMPLATE = "standing.html"
SEE_OTHER = 303
DRIFT_RULE = "P-08"
RENEWED_TYPE = f"{EVENT_TYPE_PREFIX}{AuditEventType.STANDING_ORDER_RENEWED.value}"
QUANTITY_FIELD = "quantity_{index}"
NOT_A_QUANTITY = ("Not a quantity", "Write this week's quantity of each line as a number, for example 290. "
                  "Nothing was ordered.")
NO_SUCH_STANDING_ORDER = ("No such standing order", "This order book has no standing order with this id.")
NO_DEMO_AGENT = ("No demo agent", "The demonstration's standing order belongs to the hotel kitchen, and its demo "
                 "agent is not set up here.")


class MachineClock:
    """The machine's time, for live mode: the live data clock is the later of it and the server's time."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class StandingBooks:
    """One standing-order service per order book, built on first use. A dropped book takes its service with it."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._services: weakref.WeakKeyDictionary[Sandbox, StandingOrders] = weakref.WeakKeyDictionary()

    def of(self, book: Sandbox) -> StandingOrders:
        with self._lock:
            found = self._services.get(book)
            if found is None:
                found = self._services[book] = StandingOrders(
                    store=book.store, audit=book.audit, gateway=book.service, clock=self._clock
                )
            return found


@dataclass(frozen=True)
class Trend:
    """What the customer's past orders say about one line of a standing order, and the quantities of the one
    renewal its button sends: the suggested quantity on that line, the stored quantity on every other."""

    suggestion: Suggestion
    quantities: tuple[Decimal, ...]


@dataclass(frozen=True)
class DemoCustomer:
    """A demo customer whose file holds standing orders, for the sentence beside the load button."""

    name: str
    standing_orders: int
    past_orders: int  # synthetic, counted from the customer file


@dataclass(frozen=True)
class Row:
    """One standing order as the page shows it."""

    standing: StandingOrder
    agent: Identity
    renewals: tuple[Renewal, ...]
    rule: RuleSummary | None  # P-08 with this buyer's tolerance
    last_order: Order | None  # the order of the newest renewal that placed one
    last_drift: str | None  # the drift found then, as the audit trail recorded it
    trends: tuple[Trend, ...] = ()  # from the customer file's synthetic history; empty for a buyer without a file


def data_clock(settings: Settings, replay: ReplayGateway) -> Clock:
    """The capture's pinned clock in replay, as every offer of the book uses; the machine's in live mode."""
    return replay.clock if settings.tta_mode is DataSource.REPLAY else MachineClock()


def _agent_of(site: Site, profile_id: str) -> Identity | None:
    return next((agent for agent in site.agents if agent.profile_id == profile_id), None)


def _drift_recorded(book: Sandbox, order_id: str) -> str | None:
    events = book.store.list_audit_events(order_id=order_id)
    found = next((event for event in reversed(events) if event.type == RENEWED_TYPE), None)
    sentence = found.data.facts.get("drift_sentence") if found is not None else None
    return sentence if isinstance(sentence, str) else None


def _product_names(book: Sandbox, agent: Identity, product_ids: tuple[str, ...]) -> dict[str, str]:
    """The catalog's name of each product, for the trend's sentence; a product the catalog lacks keeps its id."""
    names: dict[str, str] = {}
    for product_id in product_ids:
        try:
            names[product_id] = book.service.get_product(agent, product_id).display_name
        except TtaError:
            continue
    return names


def _trends(book: Sandbox, agent: Identity, order: StandingOrder) -> tuple[Trend, ...]:
    """The trend of each line, from the synthetic history of the buyer's customer file, against the tolerance of
    the buyer's profile file (rule P-08's). None for a buyer with no customer file or no profile file."""
    customer = shipped_customer(order.profile_id)
    if customer is None:
        return ()
    try:
        tolerance = file_profile(order.profile_id).standing_order_drift_ratio
    except TtaError:  # no profile file with this id
        return ()
    history = history_of(customer, _product_names(book, agent, tuple(usual.product_id for usual in customer.usual)))
    stored = tuple(line.quantity for line in order.request.lines)
    return tuple(
        Trend(suggestion=trend, quantities=tuple(
            trend.quantity if index == trend.request_line_index else quantity for index, quantity in enumerate(stored)
        ))
        for trend in standing_order_trends(history, order, tolerance=tolerance)
    )


def demo_customers(site: Site) -> tuple[DemoCustomer, ...]:
    """The demo agents' customers that have standing orders on file, with the number of their past orders."""
    found = (shipped_customer(agent.profile_id or "") for agent in site.agents)
    return tuple(
        DemoCustomer(name=customer.name, standing_orders=len(customer.standing_orders),
                     past_orders=len(customer.history))
        for customer in found if customer is not None and customer.standing_orders
    )


def _row(book: Sandbox, standing: StandingOrders, agent: Identity, order: StandingOrder) -> Row:
    renewals = standing.get(agent, order.standing_order_id).renewals
    placed = [renewal for renewal in renewals if renewal.order_id is not None]
    last = book.service.get_order(agent, placed[-1].order_id) if placed and placed[-1].order_id else None
    rules = book.service.get_authority(agent).rules
    return Row(
        standing=order, agent=agent, renewals=renewals,
        rule=next((rule for rule in rules if rule.rule_id == DRIFT_RULE), None), last_order=last,
        last_drift=_drift_recorded(book, last.order_id) if last is not None else None,
        trends=_trends(book, agent, order),
    )


def _rows(site: Site, book: Sandbox, standing: StandingOrders) -> tuple[Row, ...]:
    """Every standing order of the book, for each demo agent's buyer, as that agent reads it."""
    rows: list[Row] = []
    for profile_id in dict.fromkeys(agent.profile_id for agent in site.agents if agent.profile_id):
        agent = _agent_of(site, profile_id)
        if agent is not None:
            rows.extend(_row(book, standing, agent, order) for order in standing.list(agent))
    return tuple(rows)


def _quantities(form: FormData, standing: StandingOrder) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for index in range(len(standing.request.lines)):
        text = form.get(QUANTITY_FIELD.format(index=index))
        try:
            value = Decimal(text.strip()) if isinstance(text, str) else None
        except InvalidOperation:
            value = None
        if value is None or not value.is_finite():
            raise page_error(UNPROCESSABLE, *NOT_A_QUANTITY)
        values.append(value)
    return tuple(values)


def add_routes(app: FastAPI, site: Site) -> None:
    # The capture's prices build the demo's history, on the same clock as the book's offers (the demo clock
    # when one is set).
    replay = ReplayGateway.from_settings(site.settings)
    books = StandingBooks(data_clock(site.settings, replay))
    prices: ValioGateway = replay

    def page(request: Request, outcome: RenewalOutcome | None = None) -> HTMLResponse:
        book = site.book(request)
        return site.render(
            request, TEMPLATE, rows=_rows(site, book, books.of(book)), outcome=outcome,
            quantity_field=QUANTITY_FIELD, has_demo_agent=_agent_of(site, DEMO_PROFILE_ID) is not None,
            demo_customers=demo_customers(site), hotel_standing_order_id=DEMO_STANDING_ORDER_ID,
        )

    @app.get(STANDING_PATH, response_class=HTMLResponse)
    def standing_orders(request: Request) -> HTMLResponse:
        return page(request)

    def load(request: Request, csrf: str) -> Response:
        site.check_form(request, csrf)
        agent = _agent_of(site, DEMO_PROFILE_ID)
        if agent is None:
            raise page_error(UNPROCESSABLE, *NO_DEMO_AGENT)
        standing = books.of(site.own_book(request))
        for each in site.agents:  # every demo customer's standing orders, each once (P1 C3)
            load_customer_standing_orders(standing, each, prices)
        return RedirectResponse(STANDING_PATH, status_code=SEE_OTHER)

    @app.post(DEMO_PATH, response_class=HTMLResponse)
    async def load_the_demo(request: Request) -> Response:
        form = await request.form()
        token = form.get("csrf")
        return await run_in_threadpool(load, request, token if isinstance(token, str) else "")

    def renew(request: Request, standing_order_id: str, form: FormData) -> Response:
        token = form.get("csrf")
        site.check_form(request, token if isinstance(token, str) else "")
        if RECORD_ID.fullmatch(standing_order_id) is None:
            raise page_error(NOT_FOUND, *NO_SUCH_STANDING_ORDER)
        book = site.own_book(request)
        standing = books.of(book)
        found = next(
            ((agent, order) for agent in site.agents if (order := standing.find(agent, standing_order_id))), None
        )
        if found is None:
            raise page_error(NOT_FOUND, *NO_SUCH_STANDING_ORDER)
        agent, order = found
        try:
            body = RenewStandingOrder(quantities=_quantities(form, order))
        except ValidationError as error:  # zero, negative, too large or too many decimals
            raise page_error(UNPROCESSABLE, *NOT_A_QUANTITY) from error
        outcome = standing.renew(agent, standing_order_id, body)
        if outcome.order is not None:
            return RedirectResponse(f"{STANDING_PATH}#{standing_order_id}", status_code=SEE_OTHER)
        return page(request, outcome)  # nothing was ordered: the reason is shown here, there is no order to link

    @app.post(STANDING_PATH + "/{standing_order_id}/renew", response_class=HTMLResponse)
    async def renew_one(request: Request, standing_order_id: str) -> Response:
        form = await request.form()
        return await run_in_threadpool(renew, request, standing_order_id, form)
