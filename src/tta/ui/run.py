"""Running a pasted request from the first page (SPEC sections 11 and 12).

Scores on the 30% "one continuous request -> lookup -> order/approval flow". The page decides nothing: it
calls the same service functions as the REST routes and the MCP tools, as the demo agent chosen on the page.

Who reads the request, in this order:
1. the buyer agent, when one is running: it reads the text, asks for the offer and places the order itself,
   and the page shows its steps;
2. the request parser, then the page asks for the offer and orders the top option;
3. for one of the three examples only, the example's own typed request, when neither could do it. The page
   says which of the three happened. An example needs no model, so the ceiling on model calls does not stop
   it; the limits on offers and orders apply to it like to any other request.
"""

from __future__ import annotations

import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from enum import StrEnum

from tta.api.service import Gateway
from tta.contracts.agent import AgentRun
from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, RateLimited, SupplierUnavailable, TtaError
from tta.contracts.request import PurchaseRequest
from tta.ui.examples import Example

RUN_LOG_CAPACITY = 200  # the runs whose "how it was read" and agent steps are kept, newest last
KEY_PREFIX = "page-"  # idempotency keys of orders placed from the page
KEY_BYTES = 12
# A model that cannot be reached, that could not read the sentence, or whose calls are rate limited. Only
# these let an example go on with its typed request; every other error is the caller's to see.
MODEL_COULD_NOT = (SupplierUnavailable, InvalidRequest, RateLimited)

AGENT_COULD_NOT_RUN = "The buyer agent could not run: {detail}"
AGENT_STOPPED = "The buyer agent stopped without an offer: {report}"
PARSER_COULD_NOT_READ = "The request parser could not read it: {detail}"
READ_FROM_EXAMPLE = "Read from the typed request of this example. No model was asked."


class ReadBy(StrEnum):
    AGENT = "agent"
    PARSER = "parser"
    EXAMPLE = "example"


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
class RunRecord:
    """What happened to one pasted request. The offer and the order themselves are read from the gateway."""

    text: str
    agent_id: str
    read_by: ReadBy
    notes: tuple[str, ...] = ()  # what was tried first, and why it was not used
    agent_run: AgentRun | None = None
    offer_id: str | None = None
    order_id: str | None = None
    not_ordered: Problem | None = None  # the offer exists, and the gateway refused the order


def new_key() -> str:
    """An idempotency key in the form the order book accepts (1 to 100 characters of `[A-Za-z0-9._:-]`)."""
    return KEY_PREFIX + secrets.token_hex(KEY_BYTES)


def _by_the_agent(
    service: Gateway, identity: Identity, text: str, example: Example | None
) -> tuple[RunRecord | None, tuple[str, ...]]:
    """The agent's run when it reached an offer, or what to tell the reader about why the page went on.

    For free text an agent that refuses the sentence, or stops without an offer, is the answer: nothing else
    is tried, except the parser when the model behind the agent cannot be reached.
    """
    if not service.has_agent_runner:
        return None, ()
    try:
        run = service.run_agent(identity, text)
    except MODEL_COULD_NOT as error:
        if example is None and not isinstance(error, SupplierUnavailable):
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
    service: Gateway, identity: Identity, text: str, example: Example | None, agent_was_asked: bool
) -> tuple[PurchaseRequest, ReadBy, tuple[str, ...]]:
    """The typed request for this text: from the parser, or from the example the text is.

    When the agent was already asked about an example, the parser is not asked again: the gateway has
    recorded the request as received once.
    """
    if example is not None and agent_was_asked:
        return example.request, ReadBy.EXAMPLE, (READ_FROM_EXAMPLE,)
    try:
        return service.parse_request(identity, text), ReadBy.PARSER, ()
    except MODEL_COULD_NOT as error:
        if example is None:
            raise
        notes = () if not service.has_request_parser else (PARSER_COULD_NOT_READ.format(detail=error.detail),)
        return example.request, ReadBy.EXAMPLE, (*notes, READ_FROM_EXAMPLE)


def run_request(service: Gateway, identity: Identity, text: str, example: Example | None) -> RunRecord:
    """Request -> offer -> order of the top option, as `identity`. Raises the gateway's typed error when no
    offer could be built; an order the gateway refuses is kept in the record, next to the offer."""
    by_agent, agent_notes = _by_the_agent(service, identity, text, example)
    if by_agent is not None:
        return by_agent
    request, read_by, notes = _typed_request(service, identity, text, example, agent_was_asked=bool(agent_notes))
    offer = service.create_offer(identity, request)
    record = RunRecord(
        text=text, agent_id=identity.id, read_by=read_by, notes=(*agent_notes, *notes), offer_id=offer.offer_id
    )
    if not offer.options:
        return record
    try:
        order = service.place_order(identity, offer.offer_id, offer.options[0].option_id, new_key())
    except TtaError as error:
        return replace(record, not_ordered=Problem.of(error))
    return replace(record, order_id=order.order_id)


class RunLog:
    """The last runs of this process, by form key and by offer id. In memory: after a restart a result page
    still shows the offer and the order from the gateway, without how the request was read.

    A form carries a key, and a key runs once: a double click or a re-sent form does not order twice.
    """

    def __init__(self, capacity: int = RUN_LOG_CAPACITY) -> None:
        self._capacity = capacity
        self._lock = threading.Lock()
        self._by_key: OrderedDict[str, RunRecord | None] = OrderedDict()  # None: reserved, still running
        self._key_of_offer: dict[str, str] = {}

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
        """The run failed before anything was offered: the same form may be sent again."""
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

    def _forget_the_oldest(self) -> None:
        while len(self._by_key) > self._capacity:
            _, record = self._by_key.popitem(last=False)
            if record is not None and record.offer_id is not None:
                self._key_of_offer.pop(record.offer_id, None)
