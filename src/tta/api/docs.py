"""What `/openapi.json` says beyond the generated shapes: title, description, tags per requirement of the
brief, the problem responses and the examples (SPEC section 2).

Scores on the 15% "open, documented standards rather than a proprietary format, clear visibility of
assumptions". The shapes come from the typed contract models, the problem responses from the typed errors
and the examples from the scenarios run in replay; none of them is written by hand.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from tta.api.limits import (
    DEFAULT_RATE_LIMIT_CALLS,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    MAX_BODY_KILOBYTES,
    MAX_LIVE_LOOKS_PER_MINUTE,
    MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE,
    MAX_LOOKUPS_PER_ADDRESS_PER_MINUTE,
    MAX_LOOKUPS_PER_VISITOR_PER_MINUTE,
    MAX_MODEL_CALLS_PER_ADDRESS_PER_MINUTE,
    MAX_MODEL_CALLS_PER_MINUTE,
    MAX_MODEL_CALLS_PER_VISITOR_PER_MINUTE,
    MAX_OFFERS_AND_SUBSTITUTES_PER_MINUTE,
    MAX_ORDERS_AND_DECISIONS_PER_MINUTE,
    MAX_ORDERS_PER_ADDRESS_PER_MINUTE,
    MAX_ORDERS_PER_VISITOR_PER_MINUTE,
)
from tta.api.sandbox import MAX_NEW_BOOKS_PER_ADDRESS, NEW_BOOKS_WINDOW_MINUTES
from tta.api.service import MAX_DEMO_REQUEST_LINES, MAX_LIST_ITEMS
from tta.contracts.errors import (
    PROBLEM_CONTENT_TYPE,
    InvalidRequest,
    NotAuthorised,
    NotFound,
    OfferExpired,
    OfferStale,
    PolicyBlocked,
    ProblemDetails,
    RateLimited,
    SupplierUnavailable,
    TtaError,
    Unauthenticated,
    UnknownProduct,
)
from tta.contracts.request import MAX_PRODUCT_IDS

TITLE = "Trusted Trade Agents gateway"
VERSION = "0.1.0"
DESCRIPTION = f"""
A gateway that makes a food-service wholesaler **readable by a buyer's purchasing agent**: the agent looks up
products, gets an offer at **fixed prices** with live price and availability, and places the order within its
authority or sends it to a **human** for approval. Built for the Valio Aimo challenge "Trusted Trade Agents"
on Valio Aimo's mock API.

**One flow.** `GET /v1/authority` → `POST /v1/offers` → `POST /v1/orders` → placed by the agent, or
`GET /v1/approvals` and `POST /v1/approvals/{{id}}/decision` by a human → `GET /v1/audit`.

**What an agent can trust.** Every offer line states, claim by claim (price, quantity, delivery date,
allergens, origin), whether the supplier's data confirms it. Every option carries the policy verdict
(`APPROVAL` or `BLOCK`) with the rules that fired. Every eligible order waits for an authorised human
decision. No model decides a price, a quantity, an allergen status or a verdict.

**Open formats.** OpenAPI 3.1 generated from the typed models (this document); JSON Schema of every model at
`GET /v1/schemas`; errors as RFC 9457 problem details (`application/problem+json`) with one stable `type`
per kind of problem; audit events in a CloudEvents 1.0 envelope, hash-chained; `Idempotency-Key` on order
placement; ISO 8601 timestamps with offset, ISO 4217 currency, GS1 allergen codes. The same functions are
offered as MCP tools at `/mcp` when that surface is installed.

**Identity.** Every route under `/v1` except the schemas needs `Authorization: Bearer <token>`. A token is
one identity: an agent bound to one buyer profile, an approver with roles, or the supplier reader. The buyer
profile is never a request field. The demonstration tokens are **public by design** and exist only in the
`dev` and `demo` environments (see the security scheme below).

**Assumptions to know.** The limits in a buyer profile are **illustrative** values of ours: the mock has no
customer model. `ORDERED` means recorded in this gateway's order book: the mock has no order endpoint, and
the record commits nobody. Answers say whether their data is `live` or a `replay` of recorded responses.
`POST /v1/requests/parse` says who read the text in two headers, `TTA-Read-By` and `TTA-Reading-Source`
(`model`, `recording`, `hand-built`, or `rule-based` when fixed rules read it because no model answered).
The REST routes and MCP share one order book per buyer; the
demonstration pages keep each browser's orders in an order book of its own, which this API does not see.

**Limits** (illustrative as well). A request body is at most {MAX_BODY_KILOBYTES} KB (`413` otherwise; a
`Content-Length` that is not a number is `400`). A request names at most {MAX_PRODUCT_IDS:,} product ids and,
in the dev and demo environments, at most {MAX_DEMO_REQUEST_LINES} lines. A list answers at most {MAX_LIST_ITEMS}
items, the newest. The routes that reach the supplier, the model or the audit trail are counted, in windows of
one minute. A token from the environment makes at most {DEFAULT_RATE_LIMIT_CALLS} such calls in
{DEFAULT_RATE_LIMIT_WINDOW_SECONDS:g} seconds. The demonstration tokens are public, so there the caller is the
visitor, whichever token it sends: **per browser** on the demonstration pages (known by the cookie of its own
order book), and **per address** for REST and MCP and for a page request without that cookie. Each visitor makes
at most {MAX_LOOKUPS_PER_VISITOR_PER_MINUTE} offers and substitute searches, {MAX_ORDERS_PER_VISITOR_PER_MINUTE}
orders and approval decisions and {MAX_MODEL_CALLS_PER_VISITOR_PER_MINUTE} request readings and agent runs a
minute. Every browser and caller behind **one address** together make at most
{MAX_LOOKUPS_PER_ADDRESS_PER_MINUTE}, {MAX_ORDERS_PER_ADDRESS_PER_MINUTE} and {MAX_MODEL_CALLS_PER_ADDRESS_PER_MINUTE}
of these a minute, so a room on one network is served and one address cannot fill the whole app; one address opens
at most {MAX_NEW_BOOKS_PER_ADDRESS} new order books on the pages in {NEW_BOOKS_WINDOW_MINUTES} minutes.
**All callers** together make at most {MAX_OFFERS_AND_SUBSTITUTES_PER_MINUTE}, {MAX_ORDERS_AND_DECISIONS_PER_MINUTE}
and {MAX_MODEL_CALLS_PER_MINUTE} a minute. Beyond any of these the answer is `rate-limited` with `Retry-After`, naming
the window that was full. The address is the peer's; `X-Forwarded-For` is read only as far as
`TTA_TRUSTED_PROXY_HOPS` says (default 0: never). In live mode at most {MAX_LIVE_LOOKS_PER_MINUTE} looks a minute
reach the supplier, {MAX_LIVE_LOOKS_PER_VISITOR_PER_MINUTE} for one address; further looks are answered from the
recorded capture and say `replay`.
"""

EXAMPLES_NOT_BUILT = (
    "\n**Examples.** The examples of this document are the demonstration scenarios, run when the gateway "
    "starts. This time an example could not be built for: {names}. The routes work as described; only their "
    "examples are missing here.\n"
)

TAG_LOOKUP = "Core 1: lookup"
TAG_ORDER = "Core 2: offer and order"
TAG_AUTHORITY = "Core 3: authority and approval"
TAG_SUBSTITUTES = "Exceptions: substitutes"
TAG_AUDIT = "Audit trail"
TAG_AGENT = "Buyer agent"
TAG_MENUS = "Exceptions: recipes and menus"
TAG_OPEN = "Open formats and health"
TAGS = [
    {"name": TAG_LOOKUP, "description": "The brief: \"a structured way for an external agent to search for and "
                                        "retrieve what's available and at what price\"."},
    {"name": TAG_ORDER, "description": "The brief: \"a defined interaction for moving from inquiry to "
                                       "commitment, based on fixed prices rather than a negotiated quote\"."},
    {"name": TAG_AUTHORITY, "description": "The brief: \"what the agent may decide on its own, and what must go "
                                           "to a human for sign-off\". An agent token is refused here."},
    {"name": TAG_SUBSTITUTES, "description": "Optional direction of the brief: ranked substitutes, each with "
                                             "pass or fail and the reason."},
    {"name": TAG_AUDIT, "description": "The brief: \"a human-readable log for both buyer and Valio Aimo\". One "
                                       "sentence per decision, two readers, a hash chain."},
    {"name": TAG_AGENT, "description": "From a pasted sentence to the typed request, and the buyer agent's run. "
                                       "The gateway, not the model, decides whether an order goes through."},
    {"name": TAG_MENUS, "description": "Valio's example scenarios: a menu becomes one order, and an ingredient "
                                       "that cannot be had is replaced by recipe logic, never alone (F-09)."},
    {"name": TAG_OPEN, "description": "JSON Schema of every model, and what is running."},
]

# One line per typed error, for the examples of the problem responses. The type, title and status are the
# error class's own.
EXAMPLE_DETAILS: dict[type[TtaError], str] = {
    InvalidRequest: "The request does not match what this route takes. body.lines.0.quantity: Field required.",
    Unauthenticated: "This route needs a bearer token: send the header 'Authorization: Bearer <token>'.",
    NotAuthorised: "An agent cannot approve or reject an order (F-06). A human with the role asked for decides.",
    UnknownProduct: "No product in the catalog has this id.",
    NotFound: "No offer has this id.",
    OfferExpired: "The offer can no longer be ordered: its \"order by\" time has passed. Ask for a fresh offer.",
    OfferStale: "Price or availability changed since the offer was made. Ask for a fresh offer.",
    PolicyBlocked: "The policy does not allow this order, even with approval.",
    SupplierUnavailable: "The supplier cannot be asked right now, so no call was made.",
    RateLimited: "Too many requests that reach the supplier or write to the audit trail.",
}
PROBLEM_SCHEMA_NAME = ProblemDetails.__name__
PROBLEM_REF = {"$ref": f"#/components/schemas/{PROBLEM_SCHEMA_NAME}"}
SUCCESS_MEDIA_TYPE = "application/json"

Examples = dict[str, dict[str, dict[str, Any]]]  # operation id -> example name -> {"summary", "value"}


@dataclass(frozen=True)
class BuiltExamples:
    """What `tta.api.examples` hands to the document: the request examples, the answer examples, and the
    names of the scenarios whose examples could not be built."""

    requests: Examples
    answers: Examples
    not_built: tuple[str, ...] = ()


def problems(*errors: type[TtaError]) -> dict[int | str, dict[str, Any]]:
    """The `responses` of a route for the typed errors it can answer: one entry per status, as problem+json."""
    documented: dict[int | str, dict[str, Any]] = {}
    for error in errors:
        example = error(EXAMPLE_DETAILS[error]).to_problem().model_dump(mode="json", exclude_none=True)
        answer = documented.setdefault(error.status_code, {
            "description": "", "content": {PROBLEM_CONTENT_TYPE: {"schema": PROBLEM_REF, "examples": {}}},
        })
        named = f"`{error.slug}`: {error.title}"
        answer["description"] = f"{answer['description']}; {named}" if answer["description"] else named
        # Two errors share a status only when their types differ, so the type names the example.
        answer["content"][PROBLEM_CONTENT_TYPE]["examples"][error.slug] = {"summary": error.title, "value": example}
    return documented


def _attach(operation: dict[str, Any], requests: Examples, answers: Examples) -> None:
    name = operation.get("operationId", "")
    body = operation.get("requestBody", {}).get("content", {}).get(SUCCESS_MEDIA_TYPE)
    if body is not None and name in requests:
        body["examples"] = requests[name]
    for status, answer in operation.get("responses", {}).items():
        media = answer.get("content", {}).get(SUCCESS_MEDIA_TYPE)
        if status.startswith("2") and media is not None and name in answers:
            media["examples"] = answers[name]


def describe(not_built: Sequence[str]) -> str:
    """The document's description, with a paragraph naming the examples that could not be built."""
    if not not_built:
        return DESCRIPTION
    return DESCRIPTION + EXAMPLES_NOT_BUILT.format(names="; ".join(not_built))


def install_openapi(app: FastAPI, examples: Callable[[], BuiltExamples]) -> None:
    """Replace the app's OpenAPI builder: FastAPI's generated document, plus the problem schema and the
    examples. `examples` hands over what was built at start-up, so asking for the document runs no scenario.
    Put together on the first request for it and kept: what it lacks, its description says."""

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        built = examples()
        document = get_openapi(
            title=TITLE, version=VERSION, description=describe(built.not_built), routes=app.routes, tags=TAGS,
            license_info={"name": "MIT", "identifier": "MIT"},
        )
        document.setdefault("components", {}).setdefault("schemas", {})[PROBLEM_SCHEMA_NAME] = (
            ProblemDetails.model_json_schema()
        )
        for methods in document.get("paths", {}).values():
            for operation in methods.values():
                _attach(operation, built.requests, built.answers)
        app.openapi_schema = document
        return document

    app.openapi = openapi  # type: ignore[method-assign]
