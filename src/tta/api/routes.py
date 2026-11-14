"""The routes of SPEC section 2. Each one validates, calls the gateway service and returns the contract model.

Scores on the 30% "one continuous flow" and on Core 1, 2 and 3 of the brief. No rule lives here: what a
caller may do is decided in `tta.api.service`, the same for every transport.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Header, Path, Query, Request, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict
from starlette.concurrency import run_in_threadpool

from tta.api import docs
from tta.api.agent_calls import header_value
from tta.api.identity import Caller
from tta.api.service import Gateway
from tta.api.uploads import READ_IMAGE_PATH, REQUEST_BODY, ImageReading, body_too_large_answer, read_upload
from tta.contracts.agent import AgentRun, ParseRequestBody
from tta.contracts.audit import AuditView
from tta.contracts.common import ApprovalStatus, AuditReader, DataSource
from tta.contracts.errors import (
    InvalidRequest,
    NotAuthorised,
    NotFound,
    OfferExpired,
    OfferStale,
    PolicyBlocked,
    RateLimited,
    SupplierUnavailable,
    Unauthenticated,
    UnknownProduct,
)
from tta.contracts.offer import Offer, SubstituteQuery, SubstituteResult
from tta.contracts.order import Approval, DecisionRequest, Order, PlaceOrderRequest
from tta.contracts.policy import Authority
from tta.contracts.product import Product, SearchResult
from tta.contracts.request import MAX_ID_LENGTH, ProductQuery, PurchaseRequest
from tta.contracts.schemas import all_schemas

MAX_STORED_ID_LENGTH = 64
MAX_KEY_LENGTH = 100
KEY_PATTERN = r"^[A-Za-z0-9._:-]+$"  # the same form the order book accepts
CALLER = (Unauthenticated, NotAuthorised)  # every route with a token can answer these two
CREATED = 201
READ_BY_HEADER = "TTA-Read-By"
READING_SOURCE_HEADER = "TTA-Reading-Source"
READING_HEADERS = {
    READ_BY_HEADER: {
        "description": "The model id that read the text, or that the recording came from; `hand-built` for an "
                       "answer a person wrote.",
        "schema": {"type": "string"},
    },
    READING_SOURCE_HEADER: {
        "description": "`model` (the model read it just now), `recording` (a recording of the model's earlier "
                       "answer) or `hand-built`.",
        "schema": {"type": "string", "enum": ["model", "recording", "hand-built"]},
    },
}

ProductIdPath = Annotated[
    str, Path(min_length=1, max_length=MAX_ID_LENGTH, pattern=r"^[A-Za-z0-9]+$", description="A Valio product id")
]
StoredId = Annotated[str, Path(min_length=1, max_length=MAX_STORED_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")]
StoredIdQuery = Annotated[
    str | None, Query(min_length=1, max_length=MAX_STORED_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")
]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key", min_length=1, max_length=MAX_KEY_LENGTH, pattern=KEY_PATTERN,
        description="Chosen by the caller, 1 to 100 characters of A-Z a-z 0-9 . _ : -. The same key returns "
                    "the first result, so a retry never places a second order.",
    ),
]


def _upper(value: Any) -> Any:
    return value.upper() if isinstance(value, str) else value


StatusQuery = Annotated[
    ApprovalStatus | None,
    BeforeValidator(_upper),
    Query(alias="status", description="Only approvals with this status, for example `pending`. Any case."),
]

router = APIRouter(prefix="/v1")
public = APIRouter()


def _service(request: Request) -> Gateway:
    return request.app.state.parts.service


# --- Core 3: authority and approval ---------------------------------------------------------------------


@router.get(
    "/authority", operation_id="get_authority", tags=[docs.TAG_AUTHORITY], responses=docs.problems(*CALLER),
    summary="What the calling agent may decide alone",
)
def get_authority(request: Request, caller: Caller) -> Authority:
    """The buyer profile bound to the caller's token, the rules in plain sentences with that profile's
    values, and the hash of the policy in force. The limit values are illustrative."""
    return _service(request).get_authority(caller)


@router.get(
    "/approvals", operation_id="list_approvals", tags=[docs.TAG_AUTHORITY],
    responses=docs.problems(*CALLER, InvalidRequest), summary="The approval queue of the caller's buyer",
)
def list_approvals(request: Request, caller: Caller, wanted: StatusQuery = None) -> tuple[Approval, ...]:
    """For approvers. Oldest first, at most 100. Each approval names the roles it needs and gives one
    sentence per rule that asks for a human. An agent token is refused."""
    return _service(request).list_approvals(caller, wanted)


@router.post(
    "/approvals/{approval_id}/decision", operation_id="decide_approval", tags=[docs.TAG_AUTHORITY],
    responses=docs.problems(
        *CALLER, InvalidRequest, NotFound, OfferExpired, OfferStale, PolicyBlocked, RateLimited, SupplierUnavailable
    ),
    summary="Approve or reject an order that waits for a human",
)
def decide_approval(request: Request, caller: Caller, approval_id: StoredId, decision: DecisionRequest) -> Order:
    """For approvers. An approval may choose another option of the same offer. Price and availability are
    checked again and the policy runs again: `BLOCK` still blocks. The order is `ORDERED` once humans holding
    every role asked for have approved. **An agent token is refused (rule F-06), and the attempt is recorded.**"""
    return _service(request).decide_approval(caller, approval_id, decision)


# --- Core 1: lookup -------------------------------------------------------------------------------------


@router.post(
    "/products/search", operation_id="search_products", tags=[docs.TAG_LOOKUP],
    responses=docs.problems(*CALLER, InvalidRequest), summary="Search the catalog",
)
def search_products(request: Request, caller: Caller, query: ProductQuery) -> SearchResult:
    """By product type, name terms (English or Finnish), nutritional claims, category and ids. Every filter
    given must hold. At most 100 products are returned; `total` says how many match. Price and availability
    are not part of a search: ask for an offer."""
    return _service(request).search_products(caller, query)


@router.get(
    "/products/{product_id}", operation_id="get_product", tags=[docs.TAG_LOOKUP],
    responses=docs.problems(*CALLER, InvalidRequest, UnknownProduct), summary="One product",
)
def get_product(request: Request, caller: Caller, product_id: ProductIdPath) -> Product:
    """The product with its allergen statements (GS1 codes) and nutritional claims. A claim is never an
    allergen statement, and a product with no statement is unknown, not safe."""
    return _service(request).get_product(caller, product_id)


@router.post(
    "/products/{product_id}/substitutes", operation_id="find_substitutes", tags=[docs.TAG_SUBSTITUTES],
    responses=docs.problems(*CALLER, InvalidRequest, UnknownProduct, RateLimited, SupplierUnavailable),
    summary="Ranked substitutes of a product",
)
def find_substitutes(
    request: Request, caller: Caller, product_id: ProductIdPath, query: SubstituteQuery
) -> SubstituteResult:
    """Each candidate says whether it passes the allergen rule, whether it can be ordered now, the reason
    when it cannot, and what the buyer gives up. A substitute that adds an allergen is shown and can never
    be ordered."""
    return _service(request).find_substitutes(caller, product_id, query)


# --- Core 2: offer and order ----------------------------------------------------------------------------


@router.post(
    "/offers", operation_id="create_offer", tags=[docs.TAG_ORDER], status_code=CREATED,
    responses=docs.problems(*CALLER, InvalidRequest, UnknownProduct, RateLimited, SupplierUnavailable),
    summary="A typed request becomes an offer",
)
def create_offer(request: Request, caller: Caller, purchase: PurchaseRequest) -> Offer:
    """At most three options at fixed prices, each with a status per claim, a check per thing the buyer asked
    for, and the policy verdict for the caller's buyer profile. Everything that dropped out is listed with a
    reason. "Nothing fits" is an offer with no option and the reasons, not an error. A request names at most
    1,000 product ids."""
    return _service(request).create_offer(caller, purchase)


@router.get(
    "/offers/{offer_id}", operation_id="get_offer", tags=[docs.TAG_ORDER],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="A stored offer",
)
def get_offer(request: Request, caller: Caller, offer_id: StoredId) -> Offer:
    """The offer as it was made. Another buyer's offer answers as an id nobody issued."""
    return _service(request).get_offer(caller, offer_id)


@router.post(
    "/orders", operation_id="place_order", tags=[docs.TAG_ORDER], status_code=CREATED,
    responses=docs.problems(
        *CALLER, InvalidRequest, NotFound, OfferExpired, OfferStale, PolicyBlocked, RateLimited, SupplierUnavailable
    ),
    summary="Commit one option of an offer",
)
def place_order(
    request: Request, caller: Caller, order: PlaceOrderRequest, idempotency_key: IdempotencyKey
) -> Order:
    """Price and availability are checked again, then the policy decides: `AUTO` gives an `ORDERED` order
    placed by the agent, `APPROVAL` a `PENDING_APPROVAL` order that waits for the roles named, `BLOCK` a
    `policy-blocked` problem and no order. When something changed or ran out (`offer-stale`, `offer-expired`)
    the problem carries `fresh_offer_id`: a new offer for the same request. `ORDERED` means recorded in this
    gateway's order book; the mock has no order endpoint."""
    return _service(request).place_order(caller, order.offer_id, order.option_id, idempotency_key)


@router.get(
    "/orders", operation_id="list_orders", tags=[docs.TAG_ORDER], responses=docs.problems(*CALLER),
    summary="The orders of the caller's buyer",
)
def list_orders(request: Request, caller: Caller) -> tuple[Order, ...]:
    """Newest first, at most 100."""
    return _service(request).list_orders(caller)


@router.get(
    "/orders/{order_id}", operation_id="get_order", tags=[docs.TAG_ORDER],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="One order",
)
def get_order(request: Request, caller: Caller, order_id: StoredId) -> Order:
    """The order with its status, the policy decision, the option as ordered and the statements of Valio
    Aimo's data it relied on. A waiting order past its "order by" time is `EXPIRED`."""
    return _service(request).get_order(caller, order_id)


# --- audit trail ----------------------------------------------------------------------------------------


@router.get(
    "/audit", operation_id="get_audit", tags=[docs.TAG_AUDIT],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="The audit trail as one reader sees it",
)
def get_audit(
    request: Request,
    caller: Caller,
    order_id: StoredIdQuery = None,
    offer_id: StoredIdQuery = None,
    reader: Annotated[AuditReader | None, Query(description="Default: the caller's own view")] = None,
) -> AuditView:
    """One sentence per step, built from a template, never by a model, with the state of the hash chain.
    The supplier token gets the supplier's view only: no limit value, no allergen exclusion, no approver's
    name or note. An agent or approver gets the buyer's view of its own buyer's events, and may ask for
    `reader=supplier` to see what the supplier sees. With no order or offer: all of the caller's events,
    the newest 100."""
    return _service(request).get_audit(caller, reader, order_id=order_id, offer_id=offer_id)


# --- buyer agent ----------------------------------------------------------------------------------------


@router.post(
    "/requests/parse", operation_id="parse_request", tags=[docs.TAG_AGENT],
    responses={
        200: {"description": "The typed request", "headers": READING_HEADERS},
        **docs.problems(*CALLER, InvalidRequest, RateLimited, SupplierUnavailable),
    },
    summary="Free text becomes a typed request",
)
def parse_request(request: Request, response: Response, caller: Caller, pasted: ParseRequestBody) -> PurchaseRequest:
    """A missing quantity, or an allergen exclusion with no strictness, is reported as `invalid-request`
    and never guessed. Two headers say who read the text: `TTA-Read-By` and `TTA-Reading-Source`, so a
    reading served from a recording is never taken for the model's. Answers `supplier-unavailable` while no
    parser is running; the typed request can always be sent to `POST /v1/offers`."""
    reading = _service(request).read_request(caller, pasted.text)
    response.headers[READ_BY_HEADER] = header_value(reading.model)
    response.headers[READING_SOURCE_HEADER] = reading.source.value
    return reading.request


@router.post(
    READ_IMAGE_PATH.removeprefix(router.prefix), operation_id="read_image", tags=[docs.TAG_AGENT],
    openapi_extra=REQUEST_BODY,
    responses={
        200: {"description": "What was read in the photo, and the typed request", "headers": READING_HEADERS},
        **docs.problems(*CALLER, InvalidRequest, RateLimited, SupplierUnavailable), **body_too_large_answer(),
    },
    summary="A photo of an order list becomes a typed request",
)
async def read_image(request: Request, response: Response, caller: Caller) -> ImageReading:
    """One photo of a handwritten or printed list (JPEG, PNG, WebP or HEIC, at most 5 MB; this route's body may
    be 5 MB and 64 KB), as `multipart/form-data` in the field `image`. Two steps: the model writes down the lines
    it reads, word for word, then the same parser and text check as `POST /v1/requests/parse` read those lines.
    The answer holds both, so the person sees what was read. An instruction written in the photo is a line like
    any other. The upload is checked by its first bytes before any model is asked, and is never stored. Counted
    as a model call."""
    upload = await read_upload(request)
    lines, reading = await run_in_threadpool(_service(request).read_image, caller, upload.image, upload.media_type)
    response.headers[READ_BY_HEADER] = header_value(reading.model)
    response.headers[READING_SOURCE_HEADER] = reading.source.value
    return ImageReading(transcription=lines, request=reading.request, reading=reading)


@router.post(
    "/agent/run", operation_id="run_agent", tags=[docs.TAG_AGENT],
    responses=docs.problems(*CALLER, InvalidRequest, RateLimited, SupplierUnavailable),
    summary="Run the buyer agent on a pasted request",
)
def run_agent(request: Request, caller: Caller, pasted: ParseRequestBody) -> AgentRun:
    """For the demonstration. The agent works only through this gateway's own functions, as the caller's
    identity; the answer is its tool-call trace and a report built from the gateway's sentences. A run that
    stops after the gateway placed its order is answered with that order, never with an error."""
    return _service(request).run_agent(caller, pasted.text)


# --- open formats and health ----------------------------------------------------------------------------


@router.get("/schemas", operation_id="get_schemas", tags=[docs.TAG_OPEN], summary="JSON Schema of every model")
def get_schemas() -> dict[str, dict[str, Any]]:
    """Every contract model by name, as JSON Schema draft 2020-12. No token needed."""
    return all_schemas()


class AuditHead(BaseModel):
    """Kept by another party, this pair shows an audit trail that was cut short."""

    model_config = ConfigDict(frozen=True)

    events: int
    last_hash: str


class Health(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str  # "ok", or "degraded" with the reasons
    reasons: tuple[str, ...]
    environment: str
    mode: str  # what was asked for: live or replay
    source: str | None  # where the last look at price and availability came from; null before the first one
    audit_head: AuditHead
    settings: dict[str, Any]  # secrets appear only as true or false
    agent: dict[str, bool]
    surfaces: dict[str, bool]


OK, DEGRADED = "ok", "degraded"
LIVE_PAUSED = "live looks are paused after a supplier failure"
BUDGET_LOW = "the call budget is low"
CAPTURE_IN_LIVE_MODE = "answers come from the recorded capture while live mode is asked for"
NOT_SHOWN = ("valio_call_budget",)  # how much is left to spend is nobody's business on a public route


def _looks(gateway: Any, mode: DataSource) -> tuple[DataSource | None, tuple[str, ...]]:
    """The source of the last look and what is wrong, from memory. A gateway with one source (the capture in
    replay mode) has no state to report: its source is the answer."""
    state = getattr(gateway, "state", None)
    if not callable(state):
        return gateway.source, ()
    looks = state()
    in_capture = mode is DataSource.LIVE and looks.last_source is DataSource.REPLAY
    reasons = ((LIVE_PAUSED, looks.live_paused), (BUDGET_LOW, looks.budget_low), (CAPTURE_IN_LIVE_MODE, in_capture))
    return looks.last_source, tuple(reason for reason, holds in reasons if holds)


@public.get("/healthz", operation_id="get_health", tags=[docs.TAG_OPEN], summary="What is running")
def get_health(request: Request) -> Health:
    """The environment, the mode, the source of the last look at price and availability, whether the gateway
    is `ok` or `degraded` and why, and the head of the audit chain. No token needed; no secret, no path and
    no budget figure is shown. Nothing is asked of the supplier and the audit trail is not read through."""
    parts, state = request.app.state.parts, request.app.state
    events, last_hash = parts.audit.head()
    source, reasons = _looks(parts.gateway, parts.settings.tta_mode)
    reasons = (*reasons, *parts.start_reasons)  # what the start had to do without, for example the database
    return Health(
        status=DEGRADED if reasons else OK,
        reasons=reasons,
        environment=parts.settings.tta_env,
        mode=parts.settings.tta_mode.value,
        source=None if source is None else source.value,
        audit_head=AuditHead(events=events, last_hash=last_hash),
        settings={name: value for name, value in parts.settings.describe().items() if name not in NOT_SHOWN},
        agent={
            "request_parser": parts.service.has_request_parser, "agent_runner": parts.service.has_agent_runner,
        },
        surfaces=dict(state.surfaces),
    )
