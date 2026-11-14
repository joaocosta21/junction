"""Running a pasted request from the first page (SPEC sections 11 and 12).

Scores on the 30% "one continuous request -> lookup -> order/approval flow". The page decides nothing: it
calls the same service functions as the REST routes and the MCP tools, as the demo agent chosen on the page,
in the order book of the visitor's own browser session (`tta.api.sandbox`).

Who reads the request, once per form submission (task FIX-10, finding 7):
1. the buyer agent, when one is running: it reads the text, asks for the offer and places the order itself,
   and the page shows its steps. When it cannot, the parser is not asked to read the same text again;
2. else the request parser, then the page asks for the offer and orders the top option;
3. for one of the examples only, the example's own typed request, when neither could do it. The page
   says which of the three happened, and says "no model was asked" only when none was. An example needs no
   model, so the ceiling on model calls does not stop it; the limits on offers and orders apply to it.

A photo of an order list (task T18) is read by the request parser in two steps, the lines it reads and then the
reading of those lines; the page then asks for the offer and orders the top option, as in 2. The buyer agent is
not asked, so the lines are read once.

The order the page places carries one idempotency key per form submission, derived from the form's run key
(finding 4): a form sent again can never place a second order, even when the page has forgotten the run.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import weakref
from collections import OrderedDict
from dataclasses import dataclass, replace
from enum import StrEnum

from tta.api.sandbox import Sandbox
from tta.api.service import Gateway
from tta.contracts.agent import AgentRun, Reading
from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, RateLimited, SupplierUnavailable, TtaError
from tta.contracts.offer import SubstituteQuery, SubstituteResult
from tta.contracts.request import PurchaseRequest
from tta.ui.examples import Example

RUNS_PER_VISITOR = 50  # the runs of one browser's book whose reading, steps and substitutes are kept, newest last
KEY_PREFIX = "page-"  # idempotency keys of orders placed from the page
KEY_BYTES = 12
ORDER_KEY_HEX_DIGITS = 32  # of the SHA-256 of the form's run key: the key never shows the run key itself
MAX_SUBSTITUTE_LOOKUPS = 3  # product ids named in a request whose substitutes are listed on the result
# A model that cannot be reached, that could not read the sentence, or whose calls are rate limited. Only
# these let an example go on with its typed request; every other error is the caller's to see.
MODEL_COULD_NOT = (SupplierUnavailable, InvalidRequest, RateLimited)

AGENT_COULD_NOT_RUN = "The buyer agent could not run: {detail}"
AGENT_STOPPED = "The buyer agent stopped without an offer: {report}"
PARSER_COULD_NOT_READ = "The request parser could not read it: {detail}"
READ_FROM_EXAMPLE = "Read from the typed request of this example, not from a model's reading."
READ_FROM_EXAMPLE_NO_MODEL = "Read from the typed request of this example. No model was asked."
RUN_BROKE = (
    "The first send of this form stopped on an unexpected fault, so it is not run again: a second run could "
    "order twice. Reload the first page to send a new request."
)


class ReadBy(StrEnum):
    AGENT = "agent"
    PARSER = "parser"
    EXAMPLE = "example"
    PHOTO = "photo"  # transcribed, then read by the request parser (task T18)


@dataclass(frozen=True)
class Problem:
    """A refusal of the gateway, as the page shows it: the error's title, its sentence and its status."""

    title: str
    detail: str
    status: int

    @classmethod
    def of(cls, error: TtaError) -> Problem:
        return cls(title=error.title, detail=error.detail, status=error.status_code)


@dataclass(frozen=True)
class Substitutes:
    """The ranked substitutes of the products a request names, looked up once (task FIX-10, finding 8). A
    refusal of the gateway (a rate limit, for example) is kept in their place."""

    found: tuple[SubstituteResult, ...] = ()
    problem: Problem | None = None


@dataclass(frozen=True)
class RunRecord:
    """What happened to one pasted request. The offer and the order themselves are read from the gateway."""

    text: str
    agent_id: str
    read_by: ReadBy | None  # None: the run stopped before anything read the text
    notes: tuple[str, ...] = ()  # what was tried first, and why it was not used
    agent_run: AgentRun | None = None
    reading: Reading | None = None  # the parser's reading, with who read it
    offer_id: str | None = None
    order_id: str | None = None
    not_ordered: Problem | None = None  # the offer exists, and the gateway refused the order
    substitutes: Substitutes | None = None  # None: the request names no product by id
    transcription: tuple[str, ...] = ()  # the lines read in a photo, word for word (task T18)


def new_key() -> str:
    """An idempotency key in the form the order book accepts (1 to 100 characters of `[A-Za-z0-9._:-]`)."""
    return KEY_PREFIX + secrets.token_hex(KEY_BYTES)


def order_key(run_key: str) -> str:
    """The idempotency key of the order a form submission places: the same for every send of the form."""
    return KEY_PREFIX + hashlib.sha256(run_key.encode()).hexdigest()[:ORDER_KEY_HEX_DIGITS]


def _by_the_agent(
    service: Gateway, identity: Identity, text: str, example: Example | None
) -> tuple[RunRecord | None, tuple[str, ...]]:
    """The agent's run when it reached an offer, or what to tell the reader about why the page went on.

    For free text the agent's answer is the answer: a refusal is raised, and a run without an offer is shown
    as it is. Only an example goes on, with its typed request.
    """
    try:
        run = service.run_agent(identity, text)
    except MODEL_COULD_NOT as error:
        if example is None:
            raise
        return None, (AGENT_COULD_NOT_RUN.format(detail=error.detail),)
    record = RunRecord(
        text=text, agent_id=identity.id, read_by=ReadBy.AGENT, agent_run=run, offer_id=run.offer_id,
        order_id=run.order_id,
    )
    if run.offer_id is None and example is not None:
        return None, (AGENT_STOPPED.format(report=run.report),)
    return record, ()


def _typed_request(
    service: Gateway, identity: Identity, text: str, example: Example | None
) -> tuple[PurchaseRequest, ReadBy, Reading | None, tuple[str, ...]]:
    """The typed request for this text when no buyer agent runs: the parser's reading, or the example's."""
    try:
        reading = service.read_request(identity, text)
    except MODEL_COULD_NOT as error:
        if example is None:
            raise
        if not service.has_request_parser:
            return example.request, ReadBy.EXAMPLE, None, (READ_FROM_EXAMPLE_NO_MODEL,)
        notes = (PARSER_COULD_NOT_READ.format(detail=error.detail), READ_FROM_EXAMPLE)
        return example.request, ReadBy.EXAMPLE, None, notes
    return reading.request, ReadBy.PARSER, reading, ()


def run_request(
    service: Gateway, identity: Identity, text: str, example: Example | None, order_key: str | None = None
) -> RunRecord:
    """Request -> offer -> order of the top option, as `identity`, ordering with `order_key` (one per form
    submission; a new key when none is given). Raises the gateway's typed error when no offer could be built;
    an order the gateway refuses is kept in the record, next to the offer."""
    notes: tuple[str, ...] = ()
    if service.has_agent_runner:
        by_agent, notes = _by_the_agent(service, identity, text, example)
        if by_agent is not None:
            return by_agent
    if notes and example is not None:  # the agent was asked: no second reading of the same text
        request, read_by, reading, more = example.request, ReadBy.EXAMPLE, None, (READ_FROM_EXAMPLE,)
    else:
        request, read_by, reading, more = _typed_request(service, identity, text, example)
    record = RunRecord(text=text, agent_id=identity.id, read_by=read_by, notes=(*notes, *more), reading=reading)
    return _offer_and_order(service, identity, request, record, order_key)


def run_photo(
    service: Gateway, identity: Identity, image: bytes, media_type: str, order_key: str | None = None
) -> RunRecord:
    """Photo -> the lines read in it -> the typed request read from them -> offer -> order of the top option,
    as `identity` (task T18). Raises the gateway's typed error when the photo cannot be read or no offer could
    be built; an order the gateway refuses is kept in the record, next to the offer."""
    lines, reading = service.read_image(identity, image, media_type)
    record = RunRecord(
        text=reading.request.lines[0].text, agent_id=identity.id, read_by=ReadBy.PHOTO, reading=reading,
        transcription=tuple(lines),
    )
    return _offer_and_order(service, identity, reading.request, record, order_key)


def _offer_and_order(
    service: Gateway, identity: Identity, request: PurchaseRequest, record: RunRecord, order_key: str | None
) -> RunRecord:
    """The offer for the request, and the order of its top option when it has one."""
    offer = service.create_offer(identity, request)
    record = replace(record, offer_id=offer.offer_id)
    if not offer.options:
        return record
    try:
        order = service.place_order(identity, offer.offer_id, offer.options[0].option_id, order_key or new_key())
    except TtaError as error:
        return replace(record, not_ordered=Problem.of(error))
    return replace(record, order_id=order.order_id)


def look_up_substitutes(service: Gateway, identity: Identity, offer_id: str) -> Substitutes | None:
    """The ranked substitutes of each product the offer's request names by id (scenario 3), at most three;
    `None` when it names none. A refusal of the gateway is kept in their place: it never hides the offer."""
    try:
        offer = service.get_offer(identity, offer_id)
    except TtaError as error:
        return Substitutes(problem=Problem.of(error))
    named = [(product_id, line) for line in offer.request.lines for product_id in line.product_ids]
    if not named:
        return None
    found: list[SubstituteResult] = []
    for product_id, line in named[:MAX_SUBSTITUTE_LOOKUPS]:
        query = SubstituteQuery(quantity=line.quantity, unit=line.unit, needed_by=offer.request.needed_by)
        try:
            found.append(service.find_substitutes(identity, product_id, query))
        except TtaError as error:
            return Substitutes(found=tuple(found), problem=Problem.of(error))
    return Substitutes(found=tuple(found))


def broken_run(text: str, agent_id: str) -> RunRecord:
    """What a form whose run broke on an unexpected fault answers when it is sent again: never a second run."""
    return RunRecord(text=text, agent_id=agent_id, read_by=None, notes=(RUN_BROKE,))


class RunLog:
    """The last runs of one browser's order book, by form key and by offer id, and the substitutes looked up
    for an offer without a run. In memory: after a restart a result page still shows the offer and the order
    from the gateway, and says that how the request was read is no longer known.

    A form carries a key, and a key runs once: a double click or a re-sent form does not order twice.
    """

    def __init__(self, capacity: int | None = None) -> None:
        self._capacity = RUNS_PER_VISITOR if capacity is None else capacity
        self._lock = threading.Lock()
        self._by_key: OrderedDict[str, RunRecord | None] = OrderedDict()  # None: reserved, still running
        self._key_of_offer: dict[str, str] = {}
        self._looked_up: OrderedDict[str, Substitutes] = OrderedDict()  # for offers that have no run here

    def reserve(self, key: str) -> bool:
        """True when this key has not run yet: the caller runs it and then calls `finish` or `release`."""
        with self._lock:
            if key in self._by_key:
                return False
            self._by_key[key] = None
            self._forget_the_oldest()
            return True

    def finish(self, key: str, record: RunRecord) -> None:
        with self._lock:
            self._by_key[key] = record
            if record.offer_id is not None:
                self._key_of_offer[record.offer_id] = key

    def release(self, key: str) -> None:
        """The run was refused before anything was offered or ordered: the same form may be sent again."""
        with self._lock:
            if self._by_key.get(key) is None:
                self._by_key.pop(key, None)

    def by_key(self, key: str) -> RunRecord | None:
        with self._lock:
            return self._by_key.get(key)

    def by_offer(self, offer_id: str) -> RunRecord | None:
        with self._lock:
            key = self._key_of_offer.get(offer_id)
            return None if key is None else self._by_key.get(key)

    def substitutes_of(self, offer_id: str) -> Substitutes | None:
        """The substitutes of the offer: looked up by its run, or later by the "Look up substitutes" button."""
        with self._lock:
            looked_up = self._looked_up.get(offer_id)
        if looked_up is not None:
            return looked_up
        record = self.by_offer(offer_id)
        return None if record is None else record.substitutes

    def remember_substitutes(self, offer_id: str, substitutes: Substitutes) -> None:
        with self._lock:
            self._looked_up[offer_id] = substitutes
            while len(self._looked_up) > self._capacity:
                self._looked_up.popitem(last=False)

    def _forget_the_oldest(self) -> None:
        while len(self._by_key) > self._capacity:
            _, record = self._by_key.popitem(last=False)
            if record is not None and record.offer_id is not None:
                self._key_of_offer.pop(record.offer_id, None)


class RunLogs:
    """One run log per order book. A book that is dropped (idle, above the cap, "Start again") takes its log
    with it: nothing here keeps a book alive."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._logs: weakref.WeakKeyDictionary[Sandbox, RunLog] = weakref.WeakKeyDictionary()

    def of(self, book: Sandbox) -> RunLog:
        with self._lock:
            log = self._logs.get(book)
            if log is None:
                log = self._logs[book] = RunLog()
            return log
