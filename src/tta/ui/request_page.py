"""The first page: paste a request, choose who is asking, run; then the offer and what happened to it.

Scores on the 30% "working end-to-end demo" (the visible half of the flow) and the 20% "solving the problem":
the first screen shows what is confirmed, what is not, and what was excluded and why (SPEC section 12).
Everything is read from and written to the browser session's own order book (task FIX-10, finding 1).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Annotated

from fastapi import FastAPI, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.api.service import Gateway
from tta.contracts.common import ExclusionReason, Identity, OrderStatus
from tta.contracts.errors import NotFound, TtaError
from tta.contracts.offer import Exclusion, Offer, OfferOption
from tta.contracts.order import Order
from tta.contracts.policy import Authority
from tta.contracts.request import MAX_TEXT_LENGTH
from tta.ui import security, view
from tta.ui.examples import EXAMPLES, Example, example_by_key, example_for_text
from tta.ui.outcome import Outcome, outcome_of_run
from tta.ui.run import (
    Problem,
    RunRecord,
    Substitutes,
    broken_run,
    look_up_substitutes,
    order_key,
    run_request,
)
from tta.ui.site import CONFLICT, NOT_FOUND, RECORD_ID, UNPROCESSABLE, Site, page_error

TEMPLATE = "index.html"
SEE_OTHER = 303
RESULT_ANCHOR = "glance"  # the id of the summary strip at the top of a result
SUBSTITUTES_ANCHOR = "substitutes"
EXCLUSIONS_SHOWN_FIRST = 5  # the task: "collapsed after the first five"
OTHER_CANDIDATES_SHOWN_FIRST = 3

NO_SUCH_OFFER = ("No such offer", "No offer has this id in your order book. Run a request to get one.")
NOT_A_DEMO_AGENT = ("Choose who is asking", "The request must come from one of the demo agents on the first page.")
NO_TEXT = ("Nothing to run", "Write a request in the box, or pick one of the examples.")
TEXT_TOO_LONG = ("The request is too long", f"A request is at most {MAX_TEXT_LENGTH:,} characters.")
NO_SUCH_EXAMPLE = ("No such example", "Pick one of the examples on the first page.")
ALREADY_RUNNING = ("This request is already running", "The form was sent twice. Open the first page again in a moment.")
USE_AN_EXAMPLE = "The examples below carry their typed request, so one of the examples runs without a model."


@dataclass(frozen=True)
class AgentCard:
    """A demo agent in the "who is asking" selector, with what its buyer lets it decide alone."""

    identity: Identity
    authority: Authority


@dataclass(frozen=True)
class Result:
    """Everything the result of one request shows, read from the gateway as the agent that asked."""

    offer: Offer
    asker: Identity
    record: RunRecord | None  # how the request was read; gone after a restart or "Start again"
    order: Order | None
    outcome: Outcome
    confirmed: tuple[OfferOption, ...]  # options in which Valio's data confirms every claim an order needs
    unconfirmed: tuple[OfferOption, ...]  # the other options
    excluded: tuple[Exclusion, ...]  # ordered so that the first rows shown cover every reason
    reason_counts: tuple[tuple[ExclusionReason, int], ...]
    substitutes: Substitutes | None  # looked up when the request ran, or with the button
    can_look_up: bool  # the request names products whose substitutes are not shown yet
    decider: Identity | None  # a demo approver who holds a role the waiting order needs


def _read_offer(site: Site, service: Gateway, request: Request, offer_id: str) -> tuple[Identity, Offer]:
    """The offer and the demo agent of the buyer it belongs to. Another buyer's agent gets `not-found`."""
    if not RECORD_ID.fullmatch(offer_id):
        raise page_error(NOT_FOUND, *NO_SUCH_OFFER)
    for agent in site.agents_chosen_first(request):
        try:
            return agent, service.get_offer(agent, offer_id)
        except NotFound:
            continue
    raise page_error(NOT_FOUND, *NO_SUCH_OFFER)


def _decider(site: Site, order: Order | None) -> Identity | None:
    if order is None or order.status is not OrderStatus.PENDING_APPROVAL:
        return None
    return next(iter(site.holders(order.profile_id, order.decision.required_roles)), None)


def _is_confirmed(option: OfferOption, offer: Offer) -> bool:
    """Whether every line is confirmed for an order, as the contract defines it (SPEC section 4): price,
    quantity and allergens always, the delivery date when the request gave one."""
    dated = offer.request.needed_by is not None
    return all(line.confirmed_for_order(dated=dated) for line in option.lines)


def _names_products(offer: Offer) -> bool:
    return any(line.product_ids for line in offer.request.lines)


def _result(site: Site, request: Request, offer_id: str) -> Result:
    """The result of an offer of the visitor's book. Nothing is looked up here: a view reads (finding 8)."""
    book = site.book(request)
    asker, offer = _read_offer(site, book.service, request, offer_id)
    runs = site.runs(book)
    record, substitutes = runs.by_offer(offer.offer_id), runs.substitutes_of(offer.offer_id)
    order = book.service.order_for_offer(asker, offer.offer_id)  # through the store, never a cut list
    return Result(
        offer=offer, asker=asker, record=record, order=order, outcome=outcome_of_run(offer, order, record),
        confirmed=tuple(option for option in offer.options if _is_confirmed(option, offer)),
        unconfirmed=tuple(option for option in offer.options if not _is_confirmed(option, offer)),
        excluded=view.spread_by_reason(offer.excluded), reason_counts=view.reason_counts(offer.excluded),
        substitutes=substitutes,
        can_look_up=_names_products(offer) and (substitutes is None or substitutes.problem is not None),
        decider=_decider(site, order),
    )


def _page(
    site: Site, request: Request, *, result: Result | None = None, record: RunRecord | None = None,
    problem: Problem | None = None, text: str | None = None, asker: Identity | None = None, status: int = 200,
) -> HTMLResponse:
    """The first page: the form, and below it a result, a run that reached no offer, or a refusal."""
    if result is not None:
        asker = result.asker
        text = result.record.text if result.record is not None else result.offer.request.lines[0].text
    service = site.book(request).service
    cards = tuple(AgentCard(agent, service.get_authority(agent)) for agent in site.agents)
    return site.render(
        request, TEMPLATE, status=status, agents=cards, examples=EXAMPLES, asker=asker or site.chosen_agent(request),
        text=text or "", run_key=security.new_token(), result=result, record=record, problem=problem,
        use_an_example=USE_AN_EXAMPLE, exclusions_shown=EXCLUSIONS_SHOWN_FIRST,
        candidates_shown=OTHER_CANDIDATES_SHOWN_FIRST, max_text_length=MAX_TEXT_LENGTH,
    )


def _what_was_asked(site: Site, who: str, text: str, example_key: str) -> tuple[Identity, str, Example | None]:
    """Who asks, what, and which example it is. An example button brings its own agent and sentence."""
    if example_key:
        example = example_by_key(example_key)
        asker = site.agent(example.agent_id) if example is not None else None
        if example is None or asker is None:
            raise page_error(UNPROCESSABLE, *NO_SUCH_EXAMPLE)
        return asker, example.text, example
    asker = site.agent(who)
    if asker is None:
        raise page_error(UNPROCESSABLE, *NOT_A_DEMO_AGENT)
    pasted = text.strip()
    if not pasted:
        raise page_error(UNPROCESSABLE, *NO_TEXT)
    if len(pasted) > MAX_TEXT_LENGTH:
        raise page_error(UNPROCESSABLE, *TEXT_TOO_LONG)
    return asker, pasted, example_for_text(pasted)


def _where(offer_id: str, anchor: str = RESULT_ANCHOR) -> str:
    """The address of a result. The fragment opens it at the summary, so the first screen shows what is
    confirmed, what is not, what was excluded and the outcome; the form is one scroll up."""
    return f"/?offer={offer_id}#{anchor}"


def _after(site: Site, request: Request, record: RunRecord, asker: Identity) -> Response:
    """To the result of the run: a page of its own address, so a reload shows it again and orders nothing."""
    if record.offer_id is not None:
        return RedirectResponse(_where(record.offer_id), status_code=SEE_OTHER)
    return _page(site, request, record=record, text=record.text, asker=asker)


def _with_substitutes(service: Gateway, asker: Identity, record: RunRecord) -> RunRecord:
    """The run with the substitutes of the products its request names, looked up once, now (finding 8)."""
    if record.offer_id is None:
        return record
    return replace(record, substitutes=look_up_substitutes(service, asker, record.offer_id))


def _run_once(
    site: Site, request: Request, key: str, asker: Identity, text: str, example: Example | None
) -> Response:
    """Run the request unless this form already did; a form sent again shows its first result (finding 4).

    A refusal of the gateway is shown on the first page, with the text still in the box, and frees the form
    for another try: the gateway answers a run that placed an order with the run, never with a refusal, so
    nothing was ordered. Any other fault keeps the form taken: whether or not it came after an order, the form
    is never run a second time.
    """
    book = site.own_book(request)
    runs = site.runs(book)
    if not runs.reserve(key):
        earlier = runs.by_key(key)
        if earlier is None:
            raise page_error(CONFLICT, *ALREADY_RUNNING)
        return _after(site, request, earlier, asker)
    try:
        record = run_request(book.service, asker, text, example, order_key=order_key(key))
    except TtaError as error:
        runs.release(key)
        return _page(site, request, problem=Problem.of(error), text=text, asker=asker, status=error.status_code)
    except Exception:
        runs.finish(key, broken_run(text, asker.id))
        raise
    record = _with_substitutes(book.service, asker, record)
    runs.finish(key, record)
    return _after(site, request, record, asker)


def _look_up(site: Site, request: Request, offer_id: str) -> Response:
    """The "Look up substitutes" button of a result whose run is not in memory, or whose lookup was refused."""
    book = site.own_book(request)
    asker, offer = _read_offer(site, book.service, request, offer_id)
    found = look_up_substitutes(book.service, asker, offer.offer_id)
    if found is not None:
        site.runs(book).remember_substitutes(offer.offer_id, found)
    return RedirectResponse(_where(offer.offer_id, SUBSTITUTES_ANCHOR), status_code=SEE_OTHER)


def add_routes(app: FastAPI, site: Site) -> None:
    @app.get("/", response_class=HTMLResponse)
    def first_page(request: Request, offer: str | None = None) -> HTMLResponse:
        return _page(site, request, result=None if offer is None else _result(site, request, offer))

    @app.post("/run", response_class=HTMLResponse)
    def run(
        request: Request,
        csrf: Annotated[str, Form()] = "",
        run_key: Annotated[str, Form()] = "",
        text: Annotated[str, Form()] = "",
        who: Annotated[str, Form()] = "",
        example: Annotated[str, Form()] = "",
    ) -> Response:
        site.check_form(request, csrf)
        asker, pasted, found = _what_was_asked(site, who, text, example)
        key = run_key if RECORD_ID.fullmatch(run_key) else security.new_token()
        response = _run_once(site, request, key, asker, pasted, found)
        security.set_session_cookie(response, request, security.AGENT_COOKIE, asker.id)
        return response

    @app.post("/substitutes", response_class=HTMLResponse)
    def substitutes(
        request: Request, csrf: Annotated[str, Form()] = "", offer: Annotated[str, Form()] = ""
    ) -> Response:
        site.check_form(request, csrf)
        return _look_up(site, request, offer)
