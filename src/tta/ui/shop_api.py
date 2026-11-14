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
approvers (purchasing manager, finance, dietitian), shown under the name of the shop's demo person who signs. An
agent still cannot approve (F-06): the decision route acts as the approver of the role asked for, never as the
agent.

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
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from tta.api.customers import customer_view
from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_APPROVERS, Sandbox, file_profile
from tta.contracts.common import ApprovalStatus, ApproverRole, AuditReader, Identity
from tta.contracts.customer import Customer
from tta.contracts.errors import TtaError
from tta.contracts.order import DecisionRequest
from tta.contracts.request import PurchaseRequest
from tta.customers import shipped_customers
from tta.policy import PolicyLoadError
from tta.ui import security
from tta.ui.site import Site

SHOP_PATH = "/shop"
API = f"{SHOP_PATH}/api"
SHOP_HEADER = "x-shop-request"
KITCHEN_HEADER = "x-shop-kitchen"
KITCHEN_KEY = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
PROBLEM = "application/problem+json"
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
MAX_TEXT = 2000
MAX_KEY = 100
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


def _problem(status: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"title": title, "status": status, "detail": detail, **extra}, status, media_type=PROBLEM)


def _refused(error: TtaError) -> JSONResponse:
    """The gateway's problem whole, lists and objects included (a reader's question, the fields it misses)."""
    problem = error.to_problem().model_dump(mode="json", exclude_none=True)
    return JSONResponse({**problem, "type": error.slug}, error.status_code, media_type=PROBLEM)


def _json(value: Any) -> JSONResponse:
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

    def book(request: Request) -> Sandbox:
        """This browser's book of the customer the header names, which the book's suggestions are computed for."""
        one = site.sandboxes.open(_book_key(request))
        one.customer.name(str(_customer_id(request)))
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

    @app.get(API + "/offers/{offer_id}")
    def one_offer(request: Request, offer_id: str) -> Response:
        """An offer of this book, as it was made: the approvals page reads its options to offer the safe one (R6)."""
        return answer(request, lambda one: one.service.get_offer(KITCHEN_AGENT, offer_id))

    @app.get(API + "/suggestions")
    def suggestions(request: Request, offer_id: str = Query(min_length=1, max_length=MAX_ID)) -> Response:
        """What an offer of this book suggests (`suggestions`, as on the offer) and what it does not show, each
        with the reason (`dropped[].sentence`, `held_back[].summary`): the buyer's own view. Nothing is added to
        an order: the page posts a suggestion's `accept_request` to `POST /offers`."""
        return answer(request, lambda one: one.service.get_offer_suggestions(KITCHEN_AGENT, offer_id))

    @app.get(API + "/customer")
    def customer(request: Request) -> Response:
        """The shop's selected customer as `GET /v1/customers/{id}` answers it: people, usual products, synthetic
        history and standing orders from the customer file. The limits are the book's own once the shop sent its
        settings, and the customer's profile file until then."""
        customer_id = str(_customer_id(request))

        def call(one: Sandbox) -> Any:
            own = one.kitchen.profile if one.kitchen.is_set_up else file_profile(customer_id)
            return customer_view(KITCHEN_AGENT, lambda _: own, customers=lambda _: customers[customer_id])

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
        signer = _signer(customers[str(_customer_id(request))], body.role, body.name)
        if isinstance(signer, JSONResponse):
            return signer
        signing = approver.model_copy(update={"display_name": signer})
        return await in_a_worker(
            request, lambda one: one.service.decide_approval(signing, approval_id, body.decision)
        )

    @app.get(API + "/audit")
    def audit(request: Request, order_id: str, reader: AuditReader = AuditReader.BUYER) -> Response:
        return answer(
            request, lambda one: one.service.get_audit(KITCHEN_APPROVERS[0], reader=reader, order_id=order_id)
        )

    @app.post(API + "/start-again")
    def start_again(request: Request) -> Response:
        refused = _guard(request)
        if refused is not None:
            return refused
        site.sandboxes.drop(_book_key(request))
        return JSONResponse({"ok": True})
