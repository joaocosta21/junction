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
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_APPROVERS, Sandbox
from tta.contracts.common import ApprovalStatus, ApproverRole, AuditReader, Identity
from tta.contracts.errors import TtaError
from tta.contracts.order import DecisionRequest
from tta.contracts.request import PurchaseRequest
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
NO_KITCHEN = "Say which kitchen of the shop this is for (the header X-Shop-Kitchen)."
MAX_TEXT = 2000
MAX_KEY = 100
MAX_NAME = 80


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
    # The demo person signing, as the shop shows them ("Marko Heikkinen, Kallio Bakery"). Only the name the
    # audit trail prints changes: the identity, its role and what it may decide stay the book's approver's.
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME, pattern=r"^[\w .,'-]+$")


def _problem(status: int, title: str, detail: str, **extra: Any) -> JSONResponse:
    return JSONResponse({"title": title, "status": status, "detail": detail, **extra}, status, media_type=PROBLEM)


def _refused(error: TtaError) -> JSONResponse:
    extra = {k: v for k, v in error.extensions.items() if isinstance(v, (str, int, float))}
    return _problem(error.status_code, error.title, error.detail, type=error.slug, **extra)


def _json(value: Any) -> JSONResponse:
    if isinstance(value, BaseModel):
        return JSONResponse(value.model_dump(mode="json"))
    return JSONResponse([one.model_dump(mode="json") for one in value])


def _approver(role: ApproverRole) -> Identity | None:
    return next((one for one in KITCHEN_APPROVERS if role in one.roles), None)


def _guard(request: Request) -> JSONResponse | None:
    if request.headers.get(SHOP_HEADER) != "1":
        return _problem(403, "Not for this caller", NO_HEADER)
    if request.headers.get("sec-fetch-site", "same-origin") not in ("same-origin", "none"):
        return _problem(403, "Not for this caller", CROSS_SITE)
    if not KITCHEN_KEY.fullmatch(request.headers.get(KITCHEN_HEADER, "")):
        return _problem(400, "The request cannot be processed", NO_KITCHEN)
    return None


def _book_key(request: Request) -> str:
    """The browser's book key and the kitchen's name: one book per kitchen of the shop in this browser."""
    return f"{security.book_key(request)}.{request.headers[KITCHEN_HEADER]}"


async def _body(request: Request, model: type[BaseModel]) -> BaseModel | JSONResponse:
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
    def book(request: Request) -> Sandbox:
        return site.sandboxes.open(_book_key(request))

    def answer(request: Request, call: Callable[[Sandbox], Any]) -> Response:
        refused = _guard(request)
        if refused is not None:
            return refused
        try:
            return _json(call(book(request)))
        except TtaError as error:
            return _refused(error)

    @app.get(SHOP_PATH, include_in_schema=False)
    @app.get(SHOP_PATH + "/", include_in_schema=False)
    def shop() -> FileResponse:
        return FileResponse(index_file, media_type="text/html", headers={"Cache-Control": "no-store"})

    @app.get(API + "/kitchen")
    def get_kitchen(request: Request) -> Response:
        def call(one: Sandbox) -> Any:
            return one.service.get_authority(KITCHEN_AGENT)

        return answer(request, call)

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
        try:
            one = book(request)
            one.kitchen.set_up(settings)
            return _json(one.service.get_authority(KITCHEN_AGENT))
        except PolicyLoadError as error:
            return _problem(422, "The kitchen settings were refused", str(error))
        except TtaError as error:
            return _refused(error)

    @app.post(API + "/read")
    async def read(request: Request) -> Response:
        body = await _body(request, ReadBody)
        if isinstance(body, JSONResponse):
            return body
        return answer(request, lambda one: one.service.read_request(KITCHEN_AGENT, body.text))

    @app.post(API + "/offers")
    async def offer(request: Request) -> Response:
        body = await _body(request, PurchaseRequest)
        if isinstance(body, JSONResponse):
            return body
        return answer(request, lambda one: one.service.create_offer(KITCHEN_AGENT, body))

    @app.post(API + "/orders")
    async def order(request: Request) -> Response:
        body = await _body(request, OrderBody)
        if isinstance(body, JSONResponse):
            return body
        return answer(
            request, lambda one: one.service.place_order(KITCHEN_AGENT, body.offer_id, body.option_id, body.key)
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
        approver = _approver(body.role)
        if approver is None:
            return _problem(422, "The request cannot be processed", NO_SUCH_ROLE)
        if body.name:
            approver = approver.model_copy(update={"display_name": body.name})
        return answer(request, lambda one: one.service.decide_approval(approver, approval_id, body.decision))

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
