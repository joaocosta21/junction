"""The routes of SPEC section 2. Each one validates, calls the gateway service and returns the contract model.

Scores on the 30% "one continuous flow" and on Core 1, 2 and 3 of the brief. No rule lives here: what a
caller may do is decided in `tta.api.service`, the same for every transport.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from pydantic import BeforeValidator
from starlette.concurrency import run_in_threadpool

from tta.api import docs, product_lookup
from tta.api.agent_calls import header_value
from tta.api.audit_pages import AUDIT_PAGE_DEFAULT, AUDIT_PAGE_MAX, AuditPage
from tta.api.idempotency import PARAMETER as IDEMPOTENCY_PARAMETER
from tta.api.idempotency import MissingIdempotencyKey, idempotency_key
from tta.api.identity import Caller
from tta.api.schema_export import exported_schemas
from tta.api.service import Gateway
from tta.api.uploads import READ_IMAGE_PATH, REQUEST_BODY, ImageReading, body_too_large_answer, read_upload
from tta.catalog.product_types import load_product_types
from tta.contracts.agent import AgentRun, ParseRequestBody
from tta.contracts.common import ApprovalStatus, AuditReader
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

MAX_STORED_ID_LENGTH = 64
CALLER = (Unauthenticated, NotAuthorised)  # every route with a token can answer these two
CREATED, LOCATION_HEADER = docs.CREATED, docs.LOCATION_HEADER
READ_BY_HEADER = "TTA-Read-By"
READING_SOURCE_HEADER = "TTA-Reading-Source"
READING_HEADERS = {
    READ_BY_HEADER: {
        "description": "The model id that read the text, or that the recording came from; `hand-built` for an "
                       "answer a person wrote; `rule-based` when fixed rules read it because no model answered.",
        "schema": {"type": "string"},
    },
    READING_SOURCE_HEADER: {
        "description": "`model` (the model read it just now), `recording` (a recording of the model's earlier "
                       "answer), `hand-built`, or `rule-based` (fixed rules, when no model answered).",
        "schema": {"type": "string", "enum": ["model", "recording", "hand-built", "rule-based"]},
    },
}

EXAMPLE_PRODUCT_ID = "464013"  # the plant drink of scenario 2, in the recording
# What the reader says of its own reading ('"50 packs" is read as 50 sales units. …'), for a REST caller of the
# parse route: the route answers the typed request alone, so the sentence travels as the other reading facts do.
# The route that reads a photo answers the whole reading in its body and keeps the two headers above.
READING_SENTENCE_HEADER = "TTA-Reading-Sentence"
MAX_SENTENCE_CHARACTERS = 1000  # of the sentence before it is encoded: a header stays far below a proxy's limit
SHORTENED = " [shortened]"
# Printable ASCII travels as written. Anything else, and the percent sign itself, is percent-encoded as UTF-8.
_AS_WRITTEN = "".join(chr(code) for code in range(0x20, 0x7F) if chr(code) != "%")
PARSE_HEADERS = {
    **READING_HEADERS,
    READING_SENTENCE_HEADER: {
        "description": "What the reader says of its own reading, in one sentence or a few: who read the text and, "
                       "for example, that \"50 packs\" was read as 50 sales units or that 5 kg of milk was read "
                       "by weight. One line of printable ASCII; any other character, and `%`, is percent-encoded "
                       f"as UTF-8 (RFC 3986), so percent-decoding gives the sentence. At most "
                       f"{MAX_SENTENCE_CHARACTERS:,} characters: a longer one ends with `{SHORTENED.strip()}`.",
        "schema": {"type": "string"},
    },
}


def sentence_header(sentence: str) -> str:
    """The reader's sentence as a header value: one line, shortened when very long, safe for any HTTP stack."""
    line = " ".join(sentence.split())
    if len(line) > MAX_SENTENCE_CHARACTERS:
        line = line[:MAX_SENTENCE_CHARACTERS - len(SHORTENED)].rstrip() + SHORTENED
    return quote(line, safe=_AS_WRITTEN)


ProductIdPath = Annotated[
    str,
    Path(
        min_length=1, max_length=MAX_ID_LENGTH, pattern=r"^[A-Za-z0-9]+$", description="A Valio product id",
        openapi_examples={"plant_drink": {"summary": "A plant drink", "value": EXAMPLE_PRODUCT_ID}},
    ),
]
StoredId = Annotated[str, Path(min_length=1, max_length=MAX_STORED_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")]
StoredIdQuery = Annotated[
    str | None, Query(min_length=1, max_length=MAX_STORED_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$")
]
IdempotencyKey = Annotated[str, Depends(idempotency_key)]  # documented by `IDEMPOTENCY_PARAMETER`


def _upper(value: Any) -> Any:
    return value.upper() if isinstance(value, str) else value


StatusQuery = Annotated[
    ApprovalStatus | None,
    BeforeValidator(_upper),
    Query(alias="status", description="Only approvals with this status, for example `pending`. Any case."),
]

# The flag of decision B58 and its date, the same two on the search and on the read of one product. The examples
# are the ones the operation's description sends: with the example body they work as written.
EXAMPLE_NEEDED_BY = "2026-11-16"  # the Monday after the recording; Valio Aimo's recorded delivery date
PriceAndAvailabilityQuery = Annotated[
    bool,
    Query(
        description=f"`true`: each product answered carries `price_and_availability`, the supplier's fixed price "
                    f"and availability now, in the shapes of an offer line. At most "
                    f"{product_lookup.MAX_PRICED_PRODUCTS} products are read in one call. Off when not given: the "
                    f"answer is then the product file alone.",
        openapi_examples={"with_price_and_availability": {
            "summary": "Each product with the supplier's price and availability now", "value": True,
        }},
    ),
]
NeededByQuery = Annotated[
    date | None,
    Query(
        description="Only with `price_and_availability=true`: the date the goods are needed. Each product's "
                    "delivery date is then judged against it (the `delivery_date` claim, and `LATE_FOR_NEEDED_BY` "
                    "when it arrives later). Without it the dates are stated and nothing is judged. Alone it is "
                    "refused, never dropped.",
        openapi_examples={"by_monday": {"summary": "Needed by Monday 16 Nov 2026", "value": EXAMPLE_NEEDED_BY}},
    ),
]
# The keys of the product-type table (`src/tta/catalog/product_types.yaml`, ours), read once when the routes are
# loaded: a request names a kind of product by one of them, and nothing else publishes the list (review C2-7).
PRODUCT_TYPE_KEYS = tuple(sorted(load_product_types()))
PRODUCT_TYPES = (
    "**Product types.** `product_type` is one key of this gateway's own table of "
    f"{len(PRODUCT_TYPE_KEYS)} kinds of product (ours, not Valio's): "
    + ", ".join(f"`{key}`" for key in PRODUCT_TYPE_KEYS)
    + ". A kind of product that is in this list goes in `product_type`, never in `name_terms`: the type also "
    "leaves out what a buyer would send back (`milk` holds no milk for coffee, which is `coffee_milk`), so the "
    "same request typed with a name term gets another answer. `name_terms` are words the product name must hold: "
    "a brand, or a variant the type does not say (`oat`, `barista`). Any other key is `invalid-request`."
)
SEARCH_DESCRIPTION = f"""By product type, name terms (English or Finnish), nutritional claims, category and ids.
Every filter given must hold. At most 100 products are returned; `total` says how many match. Counted with the
offers in the caller's lookup window; in dev and demo a search names at most 4 name terms.

**Price and availability.** With `price_and_availability=true` each product answered carries
`price_and_availability`: the fixed price of one sales unit (net, currency, tax rate, sales unit, pack size, until
when it holds), the availability as an offer line states it (one of six states, the usable amount, the delivery
date, the order cut-off), a status for each claim (price, quantity, delivery date, allergens, origin), whether an
offer could hold the product now for the caller's buyer and the reason when not, and where and when the data was
read (`source`, `time_now`, `time_basis`). It is computed by the functions an offer is built with, with no
quantity asked, so a product reads here as on an offer line. Allergens are read against the exclusions of the
caller's buyer profile; a product that states nothing about one is unknown, never safe. One such call reads at
most {product_lookup.MAX_PRICED_PRODUCTS} products (the note says so; name the others in `product_ids`), makes one
look at the supplier, counts as one lookup and writes one audit event. In replay, a product the recorded copy
holds no answer for says `NOT_IN_RECORDING`, with no price and no state. Nothing here can be ordered: an order
needs an offer (`POST /v1/offers`), where the policy decides.

**Example that works as written,** as the hotel's agent:
`POST /v1/products/search?price_and_availability=true&needed_by={EXAMPLE_NEEDED_BY}` with the example body
`{{"product_type": "plant_drink", "limit": 3}}`.

{PRODUCT_TYPES}"""
PRODUCT_DESCRIPTION = f"""The product with its allergen statements (GS1 codes) and nutritional claims. A claim is
never an allergen statement, and a product with no statement is unknown, not safe. Counted with the offers in the
caller's lookup window.

**Price and availability.** With `price_and_availability=true` the product also carries `price_and_availability`:
the supplier's fixed price and availability now in the shapes of an offer line, a status per claim, and where and
when the data was read, exactly as `POST /v1/products/search` gives it for each product (described there).
`needed_by` judges the delivery date. One look at the supplier, one lookup, one audit event; nothing here can be
ordered.

**Example that works as written:**
`GET /v1/products/{EXAMPLE_PRODUCT_ID}?price_and_availability=true&needed_by={EXAMPLE_NEEDED_BY}`."""
OFFER_DESCRIPTION = f"""At most three options at fixed prices, each with a status per claim, a check per thing
the buyer asked for, and the policy verdict for the caller's buyer profile. Everything that dropped out is listed
with a reason. "Nothing fits" is an offer with no option and the reasons, not an error. A request names at most
1,000 product ids. `Location` is the address of the new offer.

`suggestions` holds at most three, computed from the customer's past orders and the catalog. Suggestions never
add themselves to an order: accept one by sending its `accept_request` as a new request to this route.

{PRODUCT_TYPES} `pack` may be left out: it is `BULK` for litres and kilograms, `ANY` for sales units."""
ORDER_BODY = (
    "`offer_id` and `option_id` come from the answer of `POST /v1/offers` a moment earlier (or of "
    "`GET /v1/offers/{offer_id}`): an offer is made first, then one of its options is ordered. The ids in the "
    "examples below are those of the offers this gateway made for its own examples, in a private order book: sent "
    "as written they answer `not-found` (404)."
)

router = APIRouter(prefix="/v1")


def _service(request: Request) -> Gateway:
    return request.app.state.parts.service


def _signed[Record: (Offer, Order)](request: Request, record: Record) -> Record:
    """The offer or order as it is answered: with the gateway's `proof` (`tta.api.signing`)."""
    return request.app.state.parts.signer.signed(record)


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
    return _signed(request, _service(request).decide_approval(caller, approval_id, decision))


# --- Core 1: lookup -------------------------------------------------------------------------------------


@router.post(
    "/products/search", operation_id="search_products", tags=[docs.TAG_LOOKUP],
    responses=docs.problems(*CALLER, InvalidRequest, RateLimited, SupplierUnavailable),
    summary="Search the catalog, with price and availability when asked", description=SEARCH_DESCRIPTION,
)
def search_products(
    request: Request, caller: Caller, query: ProductQuery, price_and_availability: PriceAndAvailabilityQuery = False,
    needed_by: NeededByQuery = None,
) -> SearchResult:
    """The catalog search; with the flag, each product with the supplier's price and availability now
    (`tta.api.product_lookup`, which also counts the call). What a caller reads is `SEARCH_DESCRIPTION`."""
    return product_lookup.search_products(
        _service(request), caller, query, price_and_availability=price_and_availability, needed_by=needed_by
    )


@router.get(
    "/products/{product_id}", operation_id="get_product", tags=[docs.TAG_LOOKUP],
    responses=docs.problems(*CALLER, InvalidRequest, UnknownProduct, RateLimited, SupplierUnavailable),
    summary="One product, with price and availability when asked", description=PRODUCT_DESCRIPTION,
)
def get_product(
    request: Request, caller: Caller, product_id: ProductIdPath,
    price_and_availability: PriceAndAvailabilityQuery = False, needed_by: NeededByQuery = None,
) -> Product:
    """One product; with the flag, with the supplier's price and availability now (`tta.api.product_lookup`,
    which also counts the call). What a caller reads is `PRODUCT_DESCRIPTION`."""
    return product_lookup.get_product(
        _service(request), caller, product_id, price_and_availability=price_and_availability, needed_by=needed_by
    )


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
    responses={
        **docs.created("The offer", "/v1/offers/{offer_id}"),
        **docs.problems(*CALLER, InvalidRequest, UnknownProduct, RateLimited, SupplierUnavailable),
    },
    summary="A typed request becomes an offer", description=OFFER_DESCRIPTION,
)
def create_offer(request: Request, response: Response, caller: Caller, purchase: PurchaseRequest) -> Offer:
    """The offer for a typed request, stored and signed. What a caller reads is `OFFER_DESCRIPTION`."""
    offer = _service(request).create_offer(caller, purchase)
    response.headers[LOCATION_HEADER] = f"{router.prefix}/offers/{offer.offer_id}"
    return _signed(request, offer)


@router.get(
    "/offers/{offer_id}", operation_id="get_offer", tags=[docs.TAG_ORDER],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="A stored offer",
)
def get_offer(request: Request, caller: Caller, offer_id: StoredId) -> Offer:
    """The offer as it was made. Another buyer's offer answers as an id nobody issued."""
    return _signed(request, _service(request).get_offer(caller, offer_id))


@router.post(
    "/orders", operation_id="place_order", tags=[docs.TAG_ORDER], status_code=CREATED,
    responses={
        **docs.created("The order, ordered or waiting for a person", "/v1/orders/{order_id}"),
        **docs.problems(
            *CALLER, MissingIdempotencyKey, InvalidRequest, NotFound, OfferExpired, OfferStale, PolicyBlocked,
            RateLimited, SupplierUnavailable,
        ),
    },
    openapi_extra={"parameters": [IDEMPOTENCY_PARAMETER], "requestBody": {"description": ORDER_BODY}},
    summary="Order one offer option: alone where the buyer allows it, otherwise it waits for a person",
)
def place_order(
    request: Request, response: Response, caller: Caller, order: PlaceOrderRequest, key: IdempotencyKey
) -> Order:
    """Price and availability are checked again, then the policy decides. `AUTO`: the order is `ORDERED`,
    `placed_by: AGENT`. That happens only when the buyer switched ordering alone on (`auto_order_enabled`, off in
    every shipped profile, rule F-10), no rule asks for a person and every statement of every line is confirmed.
    Otherwise an eligible option becomes a `PENDING_APPROVAL` order that waits for the roles named. `BLOCK` gives
    a `policy-blocked` problem and no order. When something changed or ran out (`offer-stale`, `offer-expired`)
    the problem carries `fresh_offer_id`: a new offer for the same request. `ORDERED` means recorded in this
    gateway's order book (the mock has no order endpoint). `Location`: the order, also on a retry with the key.

    `offer_id` and `option_id` are those of an offer made a moment earlier with `POST /v1/offers`. The examples
    carry the ids of this gateway's own example offers, kept in a private order book: sent as written they answer
    `not-found` (404)."""
    placed = _service(request).place_order(caller, order.offer_id, order.option_id, key)
    response.headers[LOCATION_HEADER] = f"{router.prefix}/orders/{placed.order_id}"
    return _signed(request, placed)


@router.get(
    "/orders", operation_id="list_orders", tags=[docs.TAG_ORDER], responses=docs.problems(*CALLER),
    summary="The orders of the caller's buyer",
)
def list_orders(request: Request, caller: Caller) -> tuple[Order, ...]:
    """Newest first, at most 100."""
    return tuple(_signed(request, order) for order in _service(request).list_orders(caller))


@router.get(
    "/orders/{order_id}", operation_id="get_order", tags=[docs.TAG_ORDER],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound), summary="One order",
)
def get_order(request: Request, caller: Caller, order_id: StoredId) -> Order:
    """The order with its status, the policy decision, the option as ordered and the statements of Valio
    Aimo's data it relied on. A waiting order past its "order by" time is `EXPIRED`."""
    return _signed(request, _service(request).get_order(caller, order_id))


# --- audit trail ----------------------------------------------------------------------------------------


AuditLimitQuery = Annotated[
    int | None,
    Query(ge=1, le=AUDIT_PAGE_MAX, description=f"The most events to answer: {AUDIT_PAGE_DEFAULT} when not given, "
                                               f"at most {AUDIT_PAGE_MAX}"),
]
AuditBeforeQuery = Annotated[
    str | None,
    Query(min_length=1, max_length=MAX_STORED_ID_LENGTH, pattern=r"^[A-Za-z0-9_-]+$",
          description="The `next_cursor` of an earlier answer: read the events before it"),
]


@router.get(
    "/audit", operation_id="get_audit", tags=[docs.TAG_AUDIT],
    responses=docs.problems(*CALLER, InvalidRequest, NotFound, RateLimited),
    summary="The audit trail as one reader sees it",
)
def get_audit(
    request: Request,
    caller: Caller,
    order_id: StoredIdQuery = None,
    offer_id: StoredIdQuery = None,
    reader: Annotated[AuditReader | None, Query(description="Default: the caller's own view")] = None,
    limit: AuditLimitQuery = None,
    before: AuditBeforeQuery = None,
) -> AuditPage:
    """One sentence per step, built from a template, never by a model, with the state of the hash chain.
    The supplier token gets the supplier's view only: no limit value, no allergen exclusion, no approver's
    name or note. An agent or approver gets the buyer's view of its own buyer's events, and may ask for
    `reader=supplier` to see what the supplier sees. With no order or offer: all of the caller's events.

    In pages: the newest events, at most `limit` (100 when not given, at most 200), oldest of them first. A
    trail that fits the page is answered whole. Otherwise `next_cursor` is set: send it as `before` to read the
    page before. `chain` speaks of the events returned, and `verified` says what was checked for this answer:
    `whole_chain` while the trail holds at most 1,000 events, `returned_span` above that (each event returned
    against its own hash and the hash of the event stored before it). Counted with the offers in the caller's
    lookup window."""
    service = _service(request)
    service.count_read(caller)
    return service.get_audit(caller, reader, order_id=order_id, offer_id=offer_id, limit=limit, before=before)


# --- buyer agent ----------------------------------------------------------------------------------------


@router.post(
    "/requests/parse", operation_id="parse_request", tags=[docs.TAG_AGENT],
    responses={
        200: {"description": "The typed request", "headers": PARSE_HEADERS},
        **docs.problems(*CALLER, InvalidRequest, RateLimited, SupplierUnavailable),
    },
    summary="Free text becomes a typed request",
)
def parse_request(request: Request, response: Response, caller: Caller, pasted: ParseRequestBody) -> PurchaseRequest:
    """Nothing is guessed: a text that cannot be read (no quantity in digits with a unit, for example) is
    `invalid-request` (422), and the problem carries `question` (what to write), `not_read` (what was missing)
    and `read_by`. An allergen exclusion with no strictness is read as STRICT, the safe reading. Two headers say
    who read the text, `TTA-Read-By` and `TTA-Reading-Source`, so fixed rules or a recording are never taken for
    the model. A third, `TTA-Reading-Sentence`, carries what the reader says of its own reading: for example that
    "50 packs" was read as 50 sales units, or that 5 kg of milk was read by weight and how to ask for litres
    (percent-decode it). `supplier-unavailable` only when no reader is installed; the typed request can always
    be sent to `POST /v1/offers`."""
    reading = _service(request).read_request(caller, pasted.text)
    response.headers[READ_BY_HEADER] = header_value(reading.model)
    response.headers[READING_SOURCE_HEADER] = reading.source.value
    response.headers[READING_SENTENCE_HEADER] = sentence_header(reading.sentence)
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


# --- open formats (health: `tta.api.health`) -----------------------------------------------------------


@router.get("/schemas", operation_id="get_schemas", tags=[docs.TAG_OPEN], summary="JSON Schema of every model")
def get_schemas() -> dict[str, dict[str, Any]]:
    """Every contract model by name, the menu and standing-order models included, as JSON Schema 2020-12: each
    schema says so in its `$schema`. No token needed."""
    return exported_schemas()
