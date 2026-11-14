"""What the gateway service needs around the buyer agent: who read a request, and what a run did (task FIX-10).

Scores on the 20% "solving the problem" and the 20% "decisions logged and auditable": a reading served from
a recording is never passed off as the model's (finding 5), and a run that breaks after the gateway placed
its order is answered with that order, never with an error that hides it (finding 4).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace

from tta.contracts.agent import AgentRun, Reading, ReadingSource
from tta.contracts.common import Identity
from tta.contracts.order import Order
from tta.contracts.ports import AgentRunner, RequestParser

UNNAMED_MODEL = "unnamed-model"  # a parser of the old port that does not say which model it asks
READ_BY_MODEL = "Read by {model}."
RUN_STOPPED = "The buyer agent stopped on an error ({error}) after the gateway placed order {order_id}. {status}"
# A header carries a model id only in this form; anything else, a line break above all, is not repeated.
HEADER_VALUE = re.compile(r"^[A-Za-z0-9._:/+-]{1,100}$")
UNKNOWN_READER = "unknown"

logger = logging.getLogger(__name__)


# --- who read a request (finding 5) ----------------------------------------------------------------------


def read_with(parser: RequestParser, identity: Identity, text: str) -> Reading:
    """The parser's own reading when it has `read` (task FIX-9). A parser of the old port answers with a
    typed request only: it is named as the model that read it, by its `model_id`."""
    read = getattr(parser, "read", None)
    if callable(read):
        reading = read(text, identity)
        if isinstance(reading, Reading):
            return reading
        raise TypeError(f"{type(parser).__name__}.read must return a Reading.")
    model = str(getattr(parser, "model_id", UNNAMED_MODEL))
    request = parser.parse_request(text, identity)
    return Reading(request=request, source=ReadingSource.MODEL, model=model, sentence=READ_BY_MODEL.format(model=model))


def header_value(model: str) -> str:
    """The model id as a header value, or `unknown` when it is not a plain id."""
    return model if HEADER_VALUE.fullmatch(model) else UNKNOWN_READER


# --- what a run did (finding 4) --------------------------------------------------------------------------


@dataclass(frozen=True)
class RunTrace:
    """The offers and orders the gateway made while one run of the buyer agent was in progress, in order."""

    offer_ids: tuple[str, ...] = ()
    order_ids: tuple[str, ...] = ()


# The trace of the run in progress, or `None` outside a run. A runner that calls its tools on another thread
# is not traced; its own run says what it made.
_trace: ContextVar[RunTrace | None] = ContextVar("tta_run_trace", default=None)


@contextmanager
def traced() -> Iterator[Callable[[], RunTrace]]:
    """Trace what the gateway makes inside the block; the function handed out reads the trace so far."""
    token = _trace.set(RunTrace())
    try:
        yield lambda: _trace.get() or RunTrace()
    finally:
        _trace.reset(token)


def note_offer(offer_id: str) -> None:
    trace = _trace.get()
    if trace is not None:
        _trace.set(replace(trace, offer_ids=(*trace.offer_ids, offer_id)))


def note_order(order_id: str) -> None:
    trace = _trace.get()
    if trace is not None:
        _trace.set(replace(trace, order_ids=(*trace.order_ids, order_id)))


def run_that_stopped(text: str, runner: AgentRunner, order: Order, error: Exception) -> AgentRun:
    """The run as the gateway knows it when the runner broke after an order: the order, and a report that
    opens with what stopped it. Only the error's class is named: its text may hold anything an SDK said."""
    logger.error(
        "The buyer agent stopped on %s after order %s was placed; the run is answered with the order.",
        type(error).__name__, order.order_id, exc_info=error,
    )
    return AgentRun(
        text=text, model=str(getattr(runner, "model_id", UNNAMED_MODEL)),
        recorded=bool(getattr(runner, "recorded", False)), offer_id=order.offer_id, order_id=order.order_id,
        order_status=order.status,
        report=RUN_STOPPED.format(error=type(error).__name__, order_id=order.order_id, status=order.status_sentence),
    )
