"""The first page: paste a request, choose who is asking, run; then the offer and what happened to it.

Scores on the 30% "working end-to-end demo" (the visible half of the flow) and the 20% "solving the problem":
the first screen shows what is confirmed, what is not, and what was excluded and why (SPEC section 12).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import FastAPI, Form
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from tta.contracts.common import ExclusionReason, Identity, OrderStatus
from tta.contracts.errors import NotFound, TtaError
from tta.contracts.offer import Exclusion, Offer, OfferOption, SubstituteQuery, SubstituteResult
from tta.contracts.order import Order
from tta.contracts.policy import Authority
from tta.contracts.request import MAX_TEXT_LENGTH
from tta.ui import security, view
from tta.ui.examples import EXAMPLES, Example, example_by_key, example_for_text
from tta.ui.outcome import Outcome, outcome_of_run
from tta.ui.run import Problem, RunRecord, run_request
from tta.ui.site import CONFLICT, NOT_FOUND, RECORD_ID, UNPROCESSABLE, Site, page_error

TEMPLATE = "index.html"
SEE_OTHER = 303
RESULT_ANCHOR = "glance"  # the id of the summary strip at the top of a result
EXCLUSIONS_SHOWN_FIRST = 5  # the task: "collapsed after the first five"
OTHER_CANDIDATES_SHOWN_FIRST = 3
MAX_SUBSTITUTE_LOOKUPS = 3  # product ids named in a request whose substitutes are listed on the result

NO_SUCH_OFFER = ("No such offer", "No offer has this id. Run a request to get one.")
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
    record: RunRecord | None  # how the request was read; gone after a restart
    order: Order | None
    outcome: Outcome
    confirmed: tuple[OfferOption, ...]  # options in which Valio's data confirms every claim an order needs
    unconfirmed: tuple[OfferOption, ...]  # the other options
    excluded: tuple[Exclusion, ...]  # ordered so that the first rows shown cover every reason
    reason_counts: tuple[tuple[ExclusionReason, int], ...]
    substitutes: tuple[SubstituteResult, ...]
    substitutes_problem: Problem | None
    decider: Identity | None  # a demo approver who holds a role the waiting order needs


def _read_offer(site: Site, request: Request, offer_id: str) -> tuple[Identity, Offer]:
    """The offer and the demo agent of the buyer it belongs to. Another buyer's agent gets `not-found`."""
    if not RECORD_ID.fullmatch(offer_id):
        raise page_error(NOT_FOUND, *NO_SUCH_OFFER)
    for agent in site.agents_chosen_first(request):
        try:
            return agent, site.service.get_offer(agent, offer_id)
        except NotFound:
            continue
    raise page_error(NOT_FOUND, *NO_SUCH_OFFER)


def _order_of(site: Site, asker: Identity, offer: Offer, record: RunRecord | None) -> Order | None:
    """The order placed on this offer, if any: the one of the run, else the newest in the buyer's orders."""
    if record is not None and record.order_id is not None:
        return site.service.get_order(asker, record.order_id)
    return next((order for order in site.service.list_orders(asker) if order.offer_id == offer.offer_id), None)


def _substitutes(site: Site, asker: Identity, offer: Offer) -> tuple[tuple[SubstituteResult, ...], Problem | None]:
    """The ranked substitutes of each product the request names by id (scenario 3). A refusal of the gateway
    (a rate limit, for example) is shown in their place; it never hides the offer."""
    named = [
        (product_id, line) for line in offer.request.lines for product_id in line.product_ids
    ][:MAX_SUBSTITUTE_LOOKUPS]
    found: list[SubstituteResult] = []
    for product_id, line in named:
        query = SubstituteQuery(quantity=line.quantity, unit=line.unit, needed_by=offer.request.needed_by)
        try:
            found.append(site.service.find_substitutes(asker, product_id, query))
        except TtaError as error:
            return tuple(found), Problem.of(error)
    return tuple(found), None


def _decider(site: Site, order: Order | None) -> Identity | None:
    if order is None or order.status is not OrderStatus.PENDING_APPROVAL:
        return None
    return next(iter(site.holders(order.profile_id, order.decision.required_roles)), None)


def _is_confirmed(option: OfferOption, offer: Offer) -> bool:
    """Whether every line is confirmed for an order, as the contract defines it (SPEC section 4): price,
    quantity and allergens always, the delivery date when the request gave one."""
    dated = offer.request.needed_by is not None
    return all(line.confirmed_for_order(dated=dated) for line in option.lines)


def _result(site: Site, request: Request, offer_id: str) -> Result:
    asker, offer = _read_offer(site, request, offer_id)
    record = site.runs.by_offer(offer.offer_id)
    order = _order_of(site, asker, offer, record)
    substitutes, substitutes_problem = _substitutes(site, asker, offer)
    return Result(
        offer=offer, asker=asker, record=record, order=order, outcome=outcome_of_run(offer, order, record),
        confirmed=tuple(option for option in offer.options if _is_confirmed(option, offer)),
        unconfirmed=tuple(option for option in offer.options if not _is_confirmed(option, offer)),
        excluded=view.spread_by_reason(offer.excluded), reason_counts=view.reason_counts(offer.excluded),
        substitutes=substitutes, substitutes_problem=substitutes_problem, decider=_decider(site, order),
    )


def _page(
    site: Site, request: Request, *, result: Result | None = None, record: RunRecord | None = None,
    problem: Problem | None = None, text: str | None = None, asker: Identity | None = None, status: int = 200,
) -> HTMLResponse:
    """The first page: the form, and below it a result, a run that reached no offer, or a refusal."""
    if result is not None:
        asker = result.asker
        text = result.record.text if result.record is not None else result.offer.request.lines[0].text
    cards = tuple(AgentCard(agent, site.service.get_authority(agent)) for agent in site.agents)
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


def _where(record: RunRecord) -> str:
    """The address of a result. The fragment opens it at the summary, so the first screen shows what is
    confirmed, what is not, what was excluded and the outcome; the form is one scroll up."""
    return f"/?offer={record.offer_id}#{RESULT_ANCHOR}"


def _after(site: Site, request: Request, record: RunRecord, asker: Identity) -> Response:
    """To the result of the run: a page of its own address, so a reload shows it again and orders nothing."""
    if record.offer_id is not None:
        return RedirectResponse(_where(record), status_code=SEE_OTHER)
    return _page(site, request, record=record, text=record.text, asker=asker)


def _run_once(site: Site, request: Request, key: str, asker: Identity, text: str, example: Example | None) -> Response:
    """Run the request unless this form already did. A refusal of the gateway is shown on the first page,
    with the text still in the box, and frees the form for another try."""
    if not site.runs.reserve(key):
        earlier = site.runs.by_key(key)
        if earlier is None:
            raise page_error(CONFLICT, *ALREADY_RUNNING)
        return _after(site, request, earlier, asker)
    try:
        record = run_request(site.service, asker, text, example)
    except TtaError as error:
        site.runs.release(key)
        return _page(site, request, problem=Problem.of(error), text=text, asker=asker, status=error.status_code)
    except BaseException:
        site.runs.release(key)
        raise
    site.runs.finish(key, record)
    return _after(site, request, record, asker)


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
