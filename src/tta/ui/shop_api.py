"""JSON routes for the shop page (`/shop`), on this browser's own demo order book.

The shop is a single page that looks like a wholesaler's web shop with the buyer's agent built in. It talks
to these routes instead of `/v1`, because `/v1` keeps one order book for every holder of the public demo
tokens: on the public link the daily spend of `hotel-kitchen` fills up after a few visitors, and every
later order goes to finance (P-02). Here each browser has its own book, as on the other pages
(`tta.api.sandbox`), and the kitchen the visitor picks in the shop is that book's "My kitchen" profile, so
the limits and allergen exclusions set in the shop are the ones the policy engine applies. Each kitchen of
the shop (school, hotel, ...) has a book of its own in the browser, so one kitchen's orders never count in
another's daily spend or show on its approvals.

Nothing here decides anything: every call goes to the same gateway service as REST, MCP and the pages, under
the same rules and rate limits. The agent is "My kitchen agent"; the approvers are the book's three
approvers (purchasing manager, finance, dietitian), shown under the name of the shop's demo person who signs.

That an agent cannot approve (F-06) holds over REST and MCP, where a token says who is calling. These routes take
no credential, by design: they serve a demonstration page with no login, on which one visitor acts in turn as each
of a customer's people, so whoever calls the decision route signs as the person of the role it names. They exist
only where the pages are mounted, in the dev and demo environments (`tta.api.app`); in production no page is
mounted, and people sign with their own tokens over REST.

Cross-site requests: every route asks for the header `X-Shop-Request`, which a form or a link on another
site cannot send, and refuses a request the browser marks as cross-site (`Sec-Fetch-Site`).

The shop's customers are the four of the customer files (`tta.customers`): the header `X-Shop-Kitchen` names one
of them, by the page's short name or by its customer id, and nothing else (C2 F7). The person who signs is one
of that customer's people, for the role signed. The book is told which customer it stands for, so its offers carry
the suggestions computed from that customer's past orders, judged under the settings the shop sent
(`GET /suggestions`: what an offer suggests, and what it does not show with the reason; `GET /customer`: the
customer's people, usual products and synthetic history). A book whose settings never arrived answers `409` to
every call that would apply them (C2 F3): before its first `PUT /kitchen` a book holds a copy of the hotel's
profile, and the ward's 1,000 litres of milk would be offered under it.

Two routes answer before the settings arrive, because they read the customer file and judge under the customer's
profile file until the book has settings of its own: `GET /reorder` (the "you usually order this: order again?"
prompt, computed from the customer's past orders on every call by `tta.suggestions.reorder_prompt`; it orders
nothing, its `request` is posted to `POST /offers` like any request) and `GET /standing-orders` (the customer
file's standing orders, each with the trend of its quantities, `tta.suggestions.standing_order_trends`).

Every standing order of a book can be renewed from the page: `POST /standing-orders/{id}/renewal` writes one renewal
as a request, at the stored quantities or at this week's, and offers and orders nothing. The page posts that request
to `POST /offers`, as it posts a trend's, so the renewal is judged against the past renewals (rule P-08) and a
person confirms it.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import weakref
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from tta.agent.dishes import read_dishes
from tta.api.customers import customer_view
from tta.api.insights import Period, insights, is_recorded
from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_APPROVERS, KITCHEN_PROFILE_ID, Sandbox, file_profile
from tta.api.standing_routes import with_set_up_limits
from tta.config import Settings
from tta.contracts.common import ApprovalStatus, ApproverRole, AuditReader, Identity, OrderStatus, Quantity, Unit
from tta.contracts.customer import Customer, CustomerStandingOrder
from tta.contracts.errors import InvalidRequest, SupplierUnavailable, TtaError
from tta.contracts.menu import MenuPlan
from tta.contracts.order import DecisionRequest, Order
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import ValioGateway
from tta.contracts.request import PurchaseRequest
from tta.contracts.standing import NewStandingOrder, RenewStandingOrder, StandingOrder
from tta.customers import shipped_customers
from tta.menus import shipped_recipes
from tta.menus.recipes import dish_names
from tta.menus.sentence import MenuAsk, data_today, plan_from_ask
from tta.policy import PolicyLoadError
from tta.standing import StandingOrders
from tta.standing.demo import NO_PRICE, past_renewals, standing_order_of, standing_request
from tta.standing.service import renewal_request
from tta.suggestions import ReorderPrompt, SuggestionPorts, history_of, reorder_prompt, standing_order_trends
from tta.suggestions.regular import RegularAlert, chosen_products, held_lines, regular_alert
from tta.suggestions.reorder import rhythm_of
from tta.suggestions.wording import set_up_sentence, weekday_name
from tta.ui import security
from tta.ui.shop_evidence import recorded_evidence
from tta.ui.site import Site
from tta.ui.standing_page import StandingBooks, data_clock
from tta.valio import ReplayGateway

SHOP_PATH = "/shop"
API = f"{SHOP_PATH}/api"
SHOP_HEADER = "x-shop-request"
KITCHEN_HEADER = "x-shop-kitchen"
KITCHEN_KEY = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
PROBLEM = "application/problem+json"
OK, CREATED = 200, 201
NO_HEADER = "This route answers the shop page only (the header X-Shop-Request is missing)."
CROSS_SITE = "This route does not answer requests from another site."
NOT_JSON = "The body is not a JSON object."
NO_SUCH_ROLE = "No approver of this kitchen holds that role."
# The page's short name of each customer, and the customer id of its file (`tta.customers`, P1 C2).
SHOP_KITCHENS = {"school": "school-kitchen", "ward": "allergy-ward", "hotel": "hotel-kitchen", "bakery": "bakery-cafe"}
NO_KITCHEN = (
    "Say which customer of the shop this is for (the header X-Shop-Kitchen): school, ward, hotel or bakery."
)
NOT_RECEIVED_TYPE = "settings-not-received"
NOT_RECEIVED_TITLE = "This customer's settings are not in force yet"
NOT_RECEIVED = (
    "Nothing was read, offered or ordered: the gateway has not received this customer's limits and allergen "
    "rules, so it would apply another customer's. Send the settings again, then try once more."
)
NOBODY_HOLDS = "Nobody at {customer} holds the role {role}, so nobody there can sign for it."
NOT_ONE_OF_THEM = "Only {person} signs as {role} for {customer}. Nothing was signed."
COMMITTED = (OrderStatus.ORDERED, OrderStatus.PENDING_APPROVAL)  # an order placed, or waiting for a person
STANDING_NOTE = (
    "From the customer file, which is synthetic. A trend's request renews the standing order once at the suggested "
    "quantity: it is sent for an offer like any request, checked against the past renewals (rule P-08), and a person "
    "confirms it. The quantity the standing order stores does not change."
)
STANDING_NOT_SET_UP = "The standing orders of %s could not be set up in a shop book: %s"
MAX_TEXT = 2000
MAX_KEY = 100

logger = logging.getLogger(__name__)
MAX_NAME = 80
MAX_ID = 64


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadBody(_Body):
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class OrderBody(_Body):
    offer_id: str = Field(min_length=1, max_length=64)
    option_id: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=MAX_KEY, pattern=r"^[A-Za-z0-9._:-]+$")


class DecisionBody(_Body):
    role: ApproverRole
    decision: DecisionRequest
    # The person signing, as the shop shows them ("Marko Heikkinen, Kallio Bakery") or by name alone: the customer's
    # person for the role (`_signer`), never another name. Only the name the audit trail prints changes: the
    # identity, its role and what it may decide stay the book's approver's.
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME, pattern=r"^[\w .,'-]+$")


class StandingLineView(_Body):
    product_id: str
    name: str
    quantity: Quantity
    unit: Unit


class PastOrderView(_Body):
    """One past order of the customer file that holds a product of the standing order: made up, and says so."""

    delivered_on: date
    lines: tuple[StandingLineView, ...]
    synthetic: bool


class TrendView(_Body):
    """What the past orders say about one line: the sentence, and one renewal at the suggested quantity."""

    product_id: str
    sentence: str
    suggested_quantity: Quantity
    unit: Unit
    accept_request: PurchaseRequest | None


class StandingOrderView(_Body):
    standing_order_id: str
    name: str
    cadence_days: int
    lines: tuple[StandingLineView, ...]
    past_orders: tuple[PastOrderView, ...]
    synthetic: bool
    trend: TrendView | None  # the first line that has one
    trends: tuple[TrendView, ...] = ()  # every line that has one


class StandingOrdersView(_Body):
    customer_id: str
    synthetic: bool
    standing_orders: tuple[StandingOrderView, ...]
    note: str = STANDING_NOTE


class StandingSetUp(_Body):
    """Answer of `POST /standing-orders`: the standing order as stored, and what the page says of it."""

    standing_order: StandingOrder
    sentence: str


def _problem(status: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"title": title, "status": status, "detail": detail, **extra}, status, media_type=PROBLEM)


def _refused(error: TtaError) -> JSONResponse:
    """The gateway's problem whole, lists and objects included (a reader's question, the fields it misses)."""
    problem = error.to_problem().model_dump(mode="json", exclude_none=True)
    return JSONResponse({**problem, "type": error.slug}, error.status_code, media_type=PROBLEM)


def _json(value: Any) -> JSONResponse:
    if isinstance(value, dict):
        return JSONResponse(value)
    if isinstance(value, BaseModel):
        return JSONResponse(value.model_dump(mode="json"))
    return JSONResponse([one.model_dump(mode="json") for one in value])


def _approver(role: ApproverRole) -> Identity | None:
    return next((one for one in KITCHEN_APPROVERS if role in one.roles), None)


def _customer_id(request: Request) -> str | None:
    """The customer the header names, by the page's short name or by its customer id; `None` for any other."""
    named = request.headers.get(KITCHEN_HEADER, "")
    if not KITCHEN_KEY.fullmatch(named):
        return None
    return SHOP_KITCHENS.get(named) or (named if named in SHOP_KITCHENS.values() else None)


def _guard(request: Request) -> JSONResponse | None:
    if request.headers.get(SHOP_HEADER) != "1":
        return _problem(403, "Not for this caller", NO_HEADER)
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return _problem(403, "Not for this caller", CROSS_SITE)
    if _customer_id(request) is None:
        return _problem(400, "The request cannot be processed", NO_KITCHEN)
    return None


def _book_key(request: Request) -> str:
    """The browser's book key and the customer's id: one book per customer of the shop in this browser."""
    return f"{security.book_key(request)}.{_customer_id(request)}"


def _not_received() -> JSONResponse:
    return _problem(409, NOT_RECEIVED_TITLE, NOT_RECEIVED, type=NOT_RECEIVED_TYPE)


def _signer(customer: Customer, role: ApproverRole, name: str | None) -> str | JSONResponse:
    """The name the trail prints for this signature: the customer's person for the role, as "Name, Customer".
    The page may send that name, or the person's name alone; any other name is refused."""
    person = customer.people.get(role)
    role_words = role.value.replace("_", " ")
    if person is None:
        return _problem(422, "The request cannot be processed",
                        NOBODY_HOLDS.format(customer=customer.name, role=role_words))
    signed = f"{person}, {customer.name}"
    if name is not None and name not in (person, signed):
        return _problem(422, "The request cannot be processed",
                        NOT_ONE_OF_THEM.format(person=person, role=role_words, customer=customer.name))
    return signed


def _decide_as_one_person(
    one: Sandbox, customer: Customer, body: DecisionBody, signer: str, approval_id: str
) -> Order:
    """One person's decision, signed for every role that person holds and the approval still needs.

    A book has one approver per role, and a customer's person may hold several roles (the customer file's
    `people`: the hotel's purchasing manager and the bakery's owner hold all three). Their one confirmation is the
    whole of their part: after the role the page named, each role still missing that the same person holds is signed
    with the same decision, each checked by the gateway like any signature and written to the log under the person's
    name. A role held by somebody else is never signed here, and a rejection is one decision."""
    person = customer.people.get(body.role)
    signed = {body.role}
    order = one.service.decide_approval(_signing(body.role, signer), approval_id, body.decision)
    while order.status is OrderStatus.PENDING_APPROVAL:
        waiting = one.service.list_approvals(KITCHEN_APPROVERS[0], ApprovalStatus.PENDING)
        approval = next((each for each in waiting if each.approval_id == approval_id), None)
        missing = approval.roles_missing if approval is not None else ()
        role = next((each for each in missing if each not in signed and customer.people.get(each) == person), None)
        if role is None:
            break
        signed.add(role)
        order = one.service.decide_approval(_signing(role, signer), approval_id, body.decision)
    return order


def _signing(role: ApproverRole, signer: str) -> Identity:
    """The book's approver of this role, under the name of the customer's person who signs."""
    approver = _approver(role)
    assert approver is not None  # every role has an approver in a shop book (KITCHEN_APPROVERS)
    return approver.model_copy(update={"display_name": signer})


def _recorded_prices(prices: ValioGateway, product_ids: list[str]) -> dict[str, Decimal]:
    """The recording's net price per sales unit of each product, for the past renewals that state none."""
    found, by_id = prices.price(product_ids).by_id(), {}
    for product_id in product_ids:
        line = found.get(product_id)
        if line is None or not line.has_price or line.catalog_price is None:
            raise SupplierUnavailable(NO_PRICE.format(product_id=product_id))
        by_id[product_id] = line.catalog_price.value
    return by_id


def _hold_standing_orders(standing: StandingOrders, customer: Customer, prices: ValioGateway) -> None:
    """Set up the customer file's standing orders in a shop book, once, with their synthetic past renewals: the
    calls the gateway makes at start (`tta.standing.demo`), for the book's own buyer. A renewal sent from the shop
    is then judged against them like any other (rule P-08)."""
    for entry in customer.standing_orders:
        if standing.find(KITCHEN_AGENT, entry.standing_order_id) is not None:
            continue
        now = standing.now()
        recorded = _recorded_prices(prices, [line.product_id for line in entry.lines])
        renewals = past_renewals(customer, entry, recorded, now)
        order = standing_order_of(customer, entry, KITCHEN_AGENT.id, renewals, now)
        standing.set_up(KITCHEN_AGENT, order.model_copy(update={"profile_id": KITCHEN_PROFILE_ID}), renewals)


def _with_names(one: Sandbox, view: BaseModel, customer: Customer) -> dict[str, Any]:
    """The customer view with the catalog's `name` on each usual product (absent for one the catalog lacks)."""
    names, body = _names(one, customer), view.model_dump(mode="json")
    usual = [{**each, **({"name": names[each["product_id"]]} if each["product_id"] in names else {})}
             for each in body["customer"]["usual"]]
    return {**body, "customer": {**body["customer"], "usual": usual}}


def _ports(one: Sandbox) -> SuggestionPorts | None:
    """What the book's own suggestions read (the product file, price and availability, the data clock); None where
    offers carry no suggestion (live mode: a look at price and stock is spent on offers only)."""
    # The gateway has no public way to them yet (asked of the api lane in RO's hand-back): read from its parts.
    suggesting = one.service._deps.suggestions  # type: ignore[attr-defined]
    return suggesting.ports if suggesting is not None else None


def _names(one: Sandbox, customer: Customer) -> dict[str, str]:
    """The catalog's name of each usual product, for the sentences; a product the catalog lacks keeps its id."""
    names: dict[str, str] = {}
    for usual in customer.usual:
        try:
            names[usual.product_id] = one.service.get_product(KITCHEN_AGENT, usual.product_id).display_name
        except TtaError:
            continue
    return names


def _reorder(one: Sandbox, customer: Customer, profile: BuyerProfile) -> ReorderPrompt:
    """The customer's regular order as a ready-made request, checked under `profile`, without the products of
    this book's orders placed or waiting for the same delivery."""
    committed = [
        (line.product_id, line.availability.available_date)
        for order in one.service.list_orders(KITCHEN_AGENT) if order.status in COMMITTED
        for line in order.option.lines
    ]
    return reorder_prompt(customer, profile=profile, ports=_ports(one), names=_names(one, customer),
                          today=datetime.now(UTC).date(), committed=committed)


def _regular(one: Sandbox, customer: Customer, offer_id: str, standing: StandingOrders) -> RegularAlert:
    """What the request of one offer of this book repeats of the customer's regular orders: its past orders (the
    customer file's), and its standing orders, the file's and any set up in this book since. A line that names only a
    product type is judged on the product the offer chose. Another book's offer is not found."""
    offer = one.service.get_offer(KITCHEN_AGENT, offer_id)
    offered = {line.product_id: line.name for option in offer.options[:1] for line in option.lines}
    history = history_of(customer, {**offered, **_names(one, customer)})
    held = held_lines(history, (*customer.standing_orders, *standing.list(KITCHEN_AGENT)))
    return regular_alert(history, held, offer.request, today=standing.now().date(), chosen=chosen_products(offer),
                         offer_id=offer.offer_id)


def _set_up(standing: StandingOrders, customer: Customer, body: NewStandingOrder) -> StandingSetUp:
    """A standing order of this book's buyer, set up by the book's own service under its limits. It orders nothing:
    a renewal is an offer like any other, judged by every rule, and a person confirms it."""
    made = standing.create(KITCHEN_AGENT, body)
    rhythm = rhythm_of(history_of(customer))
    weekdays = [weekday_name(weekday) for weekday in rhythm.weekdays] if rhythm is not None else []
    return StandingSetUp(standing_order=made, sentence=set_up_sentence(made.name, made.cadence_days, weekdays))


def _standing_order(customer: Customer, entry: CustomerStandingOrder, names: dict[str, str],
                    profile: BuyerProfile) -> StandingOrderView:
    history = history_of(customer, names)
    stored = standing_order_of(customer, entry, KITCHEN_AGENT.id, (), datetime.now(UTC))
    held = {line.product_id for line in entry.lines}

    def line(product_id: str, quantity: Any) -> StandingLineView:
        return StandingLineView(product_id=product_id, name=history.name_of(product_id), quantity=quantity,
                                unit=history.unit_of(product_id) or Unit.UNIT)

    # The trend's request renews the standing order once (`standing_order_id`): the book holds the customer's
    # standing orders with their past renewals (`_hold_standing_orders`), so rule P-08 judges it like any renewal.
    trends = tuple(
        TrendView(product_id=trend.product_id, sentence=trend.sentence, suggested_quantity=trend.quantity,
                  unit=trend.unit, accept_request=trend.accept_request)
        for trend in standing_order_trends(history, stored, tolerance=profile.standing_order_drift_ratio)
    )
    past = tuple(
        PastOrderView(delivered_on=order.delivered_on, synthetic=customer.synthetic, lines=tuple(
            line(product_id, quantity) for product_id, quantity in order.quantities.items() if product_id in held))
        for order in customer.history if held & set(order.quantities)
    )
    return StandingOrderView(
        standing_order_id=entry.standing_order_id, name=entry.name, cadence_days=entry.cadence_days,
        lines=tuple(line(each.product_id, each.quantity) for each in entry.lines), past_orders=past,
        synthetic=customer.synthetic, trend=trends[0] if trends else None, trends=trends,
    )


def _renewal(standing: StandingOrders, customer: Customer, standing_order_id: str,
             body: RenewStandingOrder) -> PurchaseRequest:
    """One renewal of a standing order of this book, written as a request: the stored one, naming the standing order
    it renews, at this week's quantities when given. Nothing is offered or ordered here: the page posts the request
    to `POST /offers`, as it posts a trend's. A standing order of the customer file has its lines written again at
    this week's quantities, so the first step of the order's log says what was asked ("290 litres of product
    469363, every week") and not the stored quantity; one set up on the page keeps the buyer's own words.
    Raises `NotFound` for a standing order this book does not hold, another customer's included."""
    stored = standing.get(KITCHEN_AGENT, standing_order_id).standing_order
    entry = next((each for each in customer.standing_orders if each.standing_order_id == standing_order_id), None)
    quantities = body.quantities
    if entry is not None and quantities is not None and len(quantities) == len(entry.lines):
        lines = tuple(line.model_copy(update={"quantity": quantity})
                      for line, quantity in zip(entry.lines, quantities, strict=True))
        this_week = standing_request(customer, entry.model_copy(update={"lines": lines}))
        stored = stored.model_copy(update={"request": this_week})
    return renewal_request(stored, quantities)


def _name_of(one: Sandbox, product_id: str, otherwise: str) -> str:
    try:
        return one.service.get_product(KITCHEN_AGENT, product_id).display_name
    except TtaError:
        return otherwise


def _set_up_here(one: Sandbox, made: StandingOrder) -> StandingOrderView:
    """A standing order set up in this book (from "this order is regular"), as the page lists it beside the
    customer file's: its lines as its request names them. It is the buyer's own, not synthetic, and has no past
    order and no trend yet."""
    lines = tuple(
        StandingLineView(product_id=line.product_ids[0], name=_name_of(one, line.product_ids[0], line.text),
                         quantity=line.quantity, unit=line.unit)
        for line in made.request.lines if line.product_ids
    )
    return StandingOrderView(standing_order_id=made.standing_order_id, name=made.name,
                             cadence_days=made.cadence_days, lines=lines, past_orders=(), synthetic=False,
                             trend=None)


def _menu_plan(one: Sandbox, body: MenuAsk, settings: Settings) -> MenuPlan:
    """The recipe plan of a sentence ("I want to make a chocolate cake for 20 people") for this book's customer, as
    `POST /v1/menus/plan` answers it: its offer is one of this book's, ordered and confirmed like any other. A refusal
    keeps its `detail` (the sentence to show) and says what the sentence named, so the page holds no dish list:
    `dishes_named`, the dishes of the recipe table it names, and `unknown_dishes`, those it names that the table does
    not have. Both empty: the sentence names no dish, and the reader's question is the one to show."""
    recipes = shipped_recipes()
    try:
        return plan_from_ask(one.service, KITCHEN_AGENT, body, recipes, settings)
    except InvalidRequest as error:
        names = dish_names(recipes)
        reading = read_dishes(body.text, names, data_today(settings)) if body.text else None
        named = [names[dish.dish_id][0] for dish in reading.dishes] if reading is not None else []
        unknown = list(reading.unknown) if reading is not None else []
        said = {**error.extensions, "dishes_named": named, "unknown_dishes": unknown}
        raise InvalidRequest(error.detail, **said) from error


async def _body(request: Request, model: type[BaseModel]) -> BaseModel | JSONResponse:
    """The body as `model`, or the refusal: the guard's first, so a caller that is not the shop page gets its 403
    whatever it sent."""
    refused = _guard(request)
    if refused is not None:
        return refused
    try:
        raw = json.loads(await request.body() or b"null")
    except ValueError:
        return _problem(400, "The request cannot be processed", NOT_JSON)
    if not isinstance(raw, dict):
        return _problem(400, "The request cannot be processed", NOT_JSON)
    try:
        return model.model_validate(raw)
    except ValidationError as error:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in error.errors()})[:5]
        return _problem(422, "The request cannot be processed", "Check these fields: " + ", ".join(fields))


def add_routes(app: FastAPI, site: Site, index_file: str) -> None:
    customers = shipped_customers()  # checked at start: a customer file that cannot be read stops it
    missing = sorted(set(SHOP_KITCHENS.values()) - set(customers))
    if missing:
        raise ValueError(f"The shop's customers have no customer file: {', '.join(missing)}.")

    # The recording's prices build the past renewals, on the same clock as the book's offers (`standing_page`).
    replay = ReplayGateway.from_settings(site.settings)
    standing_books = StandingBooks(data_clock(site.settings, replay))
    setting_up = threading.Lock()  # two first calls of one book must not both set its standing orders up
    # A book's service with the limits of a set-up (the rate limit and the demonstration's lines per request), kept
    # per book so the limit's window lasts from one call to the next. A dropped book takes it along.
    limited: weakref.WeakKeyDictionary[Sandbox, StandingOrders] = weakref.WeakKeyDictionary()

    def limited_standing(one: Sandbox) -> StandingOrders:
        with setting_up:
            if one not in limited:
                limited[one] = with_set_up_limits(standing_books.of(one), site.settings)
            return limited[one]

    def book(request: Request) -> Sandbox:
        """This browser's book of the customer the header names, which the book's suggestions are computed for,
        holding that customer's standing orders."""
        customer_id = str(_customer_id(request))
        one = site.sandboxes.open(_book_key(request))
        one.customer.name(customer_id)
        try:
            with setting_up:
                _hold_standing_orders(standing_books.of(one), customers[customer_id], replay)
        except TtaError as error:  # the book still answers; a renewal then says no standing order is set up
            logger.warning(STANDING_NOT_SET_UP, customer_id, error)
        return one

    def answer(request: Request, call: Callable[[Sandbox], Any], *, needs_settings: bool = False) -> Response:
        """`needs_settings`: the call applies the customer's settings, so it waits for them to arrive."""
        refused = _guard(request)
        if refused is not None:
            return refused
        try:
            one = book(request)
            if needs_settings and not one.kitchen.is_set_up:
                return _not_received()
            return _json(call(one))
        except TtaError as error:
            return _refused(error)

    async def in_a_worker(
        request: Request, call: Callable[[Sandbox], Any], *, needs_settings: bool = False
    ) -> Response:
        """`answer` from a route that had to read its body on the event loop: the gateway's work runs in a worker
        thread, so one slow call does not hold every other visitor's request (the other routes are plain functions,
        which the framework runs in a worker itself)."""
        return await run_in_threadpool(lambda: answer(request, call, needs_settings=needs_settings))

    @app.get(SHOP_PATH, include_in_schema=False)
    @app.get(SHOP_PATH + "/", include_in_schema=False)
    def shop() -> FileResponse:
        return FileResponse(index_file, media_type="text/html", headers={"Cache-Control": "no-store"})

    @app.get(API + "/kitchen")
    def get_kitchen(request: Request) -> Response:
        def call(one: Sandbox) -> Any:
            return one.service.get_authority(KITCHEN_AGENT)

        return answer(request, call, needs_settings=True)

    @app.put(API + "/kitchen")
    async def put_kitchen(request: Request) -> Response:
        """Make these settings this book's kitchen profile, checked exactly as a profile file is."""
        refused = _guard(request)
        if refused is not None:
            return refused
        try:
            settings = json.loads(await request.body() or b"null")
        except ValueError:
            settings = None
        if not isinstance(settings, dict):
            return _problem(400, "The request cannot be processed", NOT_JSON)

        def set_up() -> Response:
            try:
                one = book(request)
                one.kitchen.set_up(settings)
                return _json(one.service.get_authority(KITCHEN_AGENT))
            except PolicyLoadError as error:
                return _problem(422, "The kitchen settings were refused", str(error))
            except TtaError as error:
                return _refused(error)

        return await run_in_threadpool(set_up)

    @app.post(API + "/read")
    async def read(request: Request) -> Response:
        body = await _body(request, ReadBody)
        if isinstance(body, JSONResponse):
            return body
        return await in_a_worker(
            request, lambda one: one.service.read_request(KITCHEN_AGENT, body.text), needs_settings=True
        )

    @app.post(API + "/offers")
    async def offer(request: Request) -> Response:
        body = await _body(request, PurchaseRequest)
        if isinstance(body, JSONResponse):
            return body
        return await in_a_worker(
            request, lambda one: one.service.create_offer(KITCHEN_AGENT, body), needs_settings=True
        )

    @app.post(API + "/menus/plan")
    async def menu_plan(request: Request) -> Response:
        """A dish sentence ("I want to make a chocolate cake for 20 people by Monday") planned for the shop's selected
        customer from the recipe table (`MenuAsk`, as `POST /v1/menus/plan`): the `MenuPlan`, whose `offer_id` is an
        offer of this book (`GET /offers/{offer_id}`), confirmed like any other. The page sends a sentence here only
        when the reader did not read it as a product request."""
        body = await _body(request, MenuAsk)
        if isinstance(body, JSONResponse):
            return body
        return await in_a_worker(request, lambda one: _menu_plan(one, body, site.settings), needs_settings=True)

    @app.get(API + "/offers/{offer_id}")
    def one_offer(request: Request, offer_id: str) -> Response:
        """An offer of this book, as it was made: the approvals page reads its options to offer the safe one (R6)."""
        return answer(request, lambda one: one.service.get_offer(KITCHEN_AGENT, offer_id))

    @app.get(API + "/evidence")
    def evidence(
        request: Request, offer_id: str = Query(min_length=1, max_length=MAX_ID),
        option_id: str = Query(min_length=1, max_length=MAX_ID),
    ) -> Response:
        """What the recorded manufacturer pages say about the products of one option of an offer of this book
        whose data does not rule out an excluded allergen: the `Evidence` an approval would carry, for a question
        asked on the result before any approval exists. Recordings only: nobody is asked, nothing is stored, and
        no status or decision changes."""
        return answer(request, lambda one: recorded_evidence(one, site.settings, offer_id, option_id))

    @app.get(API + "/suggestions")
    def suggestions(request: Request, offer_id: str = Query(min_length=1, max_length=MAX_ID)) -> Response:
        """What an offer of this book suggests (`suggestions`, as on the offer) and what it does not show, each
        with the reason (`dropped[].sentence`, `held_back[].summary`): the buyer's own view. Nothing is added to
        an order: the page posts a suggestion's `accept_request` to `POST /offers`."""
        return answer(request, lambda one: one.service.get_offer_suggestions(KITCHEN_AGENT, offer_id))

    @app.get(API + "/regular")
    def regular(request: Request, offer_id: str = Query(min_length=1, max_length=MAX_ID)) -> Response:
        """"This is one of your regular orders": what the request of an offer of this book repeats of the shop's
        selected customer's regular orders, computed on every call (`tta.suggestions.regular`). `finding`:
        ALREADY_ON_STANDING_ORDER (a product is on a standing order: the request would be on top of it),
        REGULAR_NOT_STANDING (with `standing_order_request`, the body `POST /standing-orders` takes),
        REGULAR_DIFFERENT_QUANTITY (with `usual_request`, the same request at the usual quantities, for
        `POST /offers`), or null with an empty `sentence`. Nothing is ordered or changed."""
        customer_id = str(_customer_id(request))
        return answer(request, lambda one: _regular(one, customers[customer_id], offer_id, standing_books.of(one)))

    @app.post(API + "/standing-orders")
    async def set_up_standing_order(request: Request) -> Response:
        """Set up a standing order for the shop's selected customer (`NewStandingOrder`, as `POST /v1/standing-orders`)
        in this book. Nothing is ordered: each renewal is an offer a person confirms. A buyer holds at most 20, a
        set-up is counted by the rate limit as an offer is, and its request takes the demonstration's 5 lines."""
        body = await _body(request, NewStandingOrder)
        if isinstance(body, JSONResponse):
            return body
        customer_id = str(_customer_id(request))
        made = await in_a_worker(
            request, lambda one: _set_up(limited_standing(one), customers[customer_id], body), needs_settings=True
        )
        if made.status_code == OK:
            made.status_code = CREATED
        return made

    @app.post(API + "/standing-orders/{standing_order_id}/renewal")
    async def renewal(request: Request, standing_order_id: str) -> Response:
        """One renewal of a standing order of this book as a `PurchaseRequest` that names it (`RenewStandingOrder`,
        as `POST /v1/standing-orders/{id}/renew` takes it: `quantities`, one per line in order, or none for the
        stored ones). It offers and orders nothing: the page posts the request to `POST /offers`, where it is
        judged against the past renewals like any renewal, and a person confirms the offer."""
        body = await _body(request, RenewStandingOrder)
        if isinstance(body, JSONResponse):
            return body
        customer_id = str(_customer_id(request))
        return await in_a_worker(
            request, lambda one: _renewal(standing_books.of(one), customers[customer_id], standing_order_id, body)
        )

    @app.get(API + "/customer")
    def customer(request: Request) -> Response:
        """The shop's selected customer as `GET /v1/customers/{id}` answers it: people, usual products, synthetic
        history and standing orders from the customer file. The limits are the book's own once the shop sent its
        settings, and the customer's profile file until then."""
        customer_id = str(_customer_id(request))

        def call(one: Sandbox) -> Any:
            own = one.kitchen.profile if one.kitchen.is_set_up else file_profile(customer_id)
            view = customer_view(KITCHEN_AGENT, lambda _: own, customers=lambda _: customers[customer_id])
            return _with_names(one, view, customers[customer_id])

        return answer(request, call)

    @app.get(API + "/learned")
    def learned(request: Request) -> Response:
        """Where the recipe matters for the shop's selected customer, as the gateway learns it now from the book's
        decisions on substitutes, its past requests and the customer file (`tta.customers.learned`): the mode in
        force, one finding per usual product with its source and evidence, and one line for the side card."""
        return answer(request, lambda one: one.service.get_learned(KITCHEN_AGENT), needs_settings=True)

    def own_profile(one: Sandbox, customer_id: str) -> BuyerProfile:
        """The book's own settings once the shop sent them; the customer's profile file until then."""
        return one.kitchen.profile if one.kitchen.is_set_up else file_profile(customer_id)

    @app.get(API + "/reorder")
    def reorder(request: Request) -> Response:
        """"You usually order this: order again?" for the shop's selected customer, computed from its past orders
        on every call. `lines` empty and `request` null: nothing regular, and `sentence` says why. Nothing is
        ordered: the page posts `request` to `POST /offers`, and a person confirms the offer as always."""
        customer_id = str(_customer_id(request))
        return answer(request, lambda one: _reorder(one, customers[customer_id], own_profile(one, customer_id)))

    @app.get(API + "/standing-orders")
    def standing_orders(request: Request) -> Response:
        """The standing orders of the shop's selected customer: those of its customer file, each with its synthetic
        past orders and the trend of its quantities (`trend` null: no change is suggested), then those set up in
        this book since (`POST /standing-orders`), which have no past order yet."""
        customer_id = str(_customer_id(request))

        def call(one: Sandbox) -> Any:
            customer = customers[customer_id]  # after the guard: the header names one of the shop's customers
            names, profile = _names(one, customer), own_profile(one, customer_id)
            of_the_file = {entry.standing_order_id for entry in customer.standing_orders}
            set_up_here = (made for made in standing_books.of(one).list(KITCHEN_AGENT)
                           if made.standing_order_id not in of_the_file)
            return StandingOrdersView(customer_id=customer_id, synthetic=customer.synthetic, standing_orders=(
                *(_standing_order(customer, entry, names, profile) for entry in customer.standing_orders),
                *(_set_up_here(one, made) for made in set_up_here),
            ))

        return answer(request, call)

    @app.post(API + "/orders")
    async def order(request: Request) -> Response:
        body = await _body(request, OrderBody)
        if isinstance(body, JSONResponse):
            return body
        return await in_a_worker(
            request, lambda one: one.service.place_order(KITCHEN_AGENT, body.offer_id, body.option_id, body.key),
            needs_settings=True,
        )

    @app.get(API + "/orders")
    def orders(request: Request) -> Response:
        return answer(request, lambda one: one.service.list_orders(KITCHEN_AGENT))

    @app.get(API + "/orders/{order_id}")
    def one_order(request: Request, order_id: str) -> Response:
        return answer(request, lambda one: one.service.get_order(KITCHEN_AGENT, order_id))

    @app.get(API + "/approvals")
    def approvals(request: Request, pending: bool = True) -> Response:
        status = ApprovalStatus.PENDING if pending else None
        return answer(request, lambda one: one.service.list_approvals(KITCHEN_APPROVERS[0], status))

    @app.post(API + "/approvals/{approval_id}/decision")
    async def decide(request: Request, approval_id: str) -> Response:
        body = await _body(request, DecisionBody)
        if isinstance(body, JSONResponse):
            return body
        refused = _guard(request)
        if refused is not None:
            return refused
        approver = _approver(body.role)
        if approver is None:
            return _problem(422, "The request cannot be processed", NO_SUCH_ROLE)
        customer = customers[str(_customer_id(request))]
        signer = _signer(customer, body.role, body.name)
        if isinstance(signer, JSONResponse):
            return signer
        return await in_a_worker(
            request, lambda one: _decide_as_one_person(one, customer, body, signer, approval_id)
        )

    @app.get(API + "/audit")
    def audit(request: Request, order_id: str, reader: AuditReader = AuditReader.BUYER) -> Response:
        return answer(
            request, lambda one: one.service.get_audit(KITCHEN_APPROVERS[0], reader=reader, order_id=order_id)
        )

    @app.get(API + "/backoffice")
    def backoffice(request: Request, period: Period = Period.TODAY) -> Response:
        """Valio Aimo's back office of this demonstration (`tta.api.insights`, as `GET /v1/insights`): the figures of
        this browser's order books of the shop's four customers together, counted from Valio Aimo's view of each
        event, as "What Valio Aimo sees" reads one order. It is Valio Aimo's screen, not the customer's. It opens no
        book: a customer nobody shopped as adds nothing."""
        refused = _guard(request)
        if refused is not None:
            return refused
        books = [site.sandboxes.find(f"{security.book_key(request)}.{each}") for each in SHOP_KITCHENS.values()]
        events = [event for one in books if one is not None for event in one.store.list_audit_events()]
        now = data_clock(site.settings, replay).now()
        return _json(insights(events, now=now, period=period, recorded=is_recorded(site.settings)))

    @app.post(API + "/start-again")
    def start_again(request: Request) -> Response:
        refused = _guard(request)
        if refused is not None:
            return refused
        site.sandboxes.drop(_book_key(request))
        return JSONResponse({"ok": True})
