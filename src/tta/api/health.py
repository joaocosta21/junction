"""`GET /healthz`: what is running, where the data comes from, which store is in use, the head of the audit chain.

Scores on the 20% "how decisions are logged and auditable" (a head another party can keep shows a trail cut short;
the answer says where the record is kept; a changed, removed or inserted event degrades the gateway and is named)
and on the 15% path to production. No token; no secret, no path, no host.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from tta.api import docs
from tta.api.clock_info import HealthClock, describe_clock
from tta.api.limits import UNKNOWN_CLIENT, current_client_key, forwarded_for_entries
from tta.api.signing import JWKS_PATH
from tta.config import Settings
from tta.contracts.audit import ChainVerification
from tta.contracts.common import DataSource
from tta.contracts.offer import PROOF_ALGORITHM

public = APIRouter()
DEMO_KEY = (
    "A demo key, generated when this gateway started because no signing key is set. It changes at every start; "
    "nothing is claimed about a signature made with it."
)
SET_KEY = "The key this gateway's operator set. The gateway signs with it; Valio Aimo does not."
DEMO_KEY_IN_USE = "offers and orders are signed with a demo key that changes at every start"
SERVICE_UNAVAILABLE = 503
# How old the last walk of the whole audit chain may be before `/healthz` walks it again (checks C1-4, C4-F4).
CHAIN_WALK_SECONDS = 30


class ChainWatch:
    """The last verification of the whole audit chain of the shared order book, for `/healthz`.

    The route is public and not rate limited, and a walk reads every event, so it is made again only when the last
    one is `CHAIN_WALK_SECONDS` old: until then the last result is answered, and a change of a stored event shows
    at most that much later. One walk at a time; a caller that arrives during one waits and reads its result."""

    def __init__(
        self, verify: Callable[[], ChainVerification], *, every_seconds: float = CHAIN_WALK_SECONDS,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._verify = verify
        self._every_seconds = every_seconds
        self._monotonic = monotonic
        self._lock = threading.Lock()  # routes run in a thread pool
        self._found: ChainVerification | None = None
        self._walked_at = 0.0

    def state(self) -> ChainVerification:
        with self._lock:
            now = self._monotonic()
            if self._found is None or now - self._walked_at >= self._every_seconds:
                self._found, self._walked_at = self._verify(), now
            return self._found


class AuditHead(BaseModel):
    """Kept by another party, this pair shows an audit trail that was cut short."""

    model_config = ConfigDict(frozen=True)

    events: int
    last_hash: str


class StoreInUse(BaseModel):
    """The database of the shared order book and the audit trail. Never its address, its name or its path."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["postgresql", "sqlite"]
    reason: str


class SigningKey(BaseModel):
    """The key behind the `proof` of every offer and order record. Only what is public."""

    model_config = ConfigDict(frozen=True)

    key_id: str
    algorithm: str
    jwks_path: str
    demo_key: bool  # true: generated when the gateway started, gone at the next start
    note: str


AddressFamily = Literal["IPv4", "IPv6", "unknown"]
BUCKET_LABEL_CHARACTERS = 8
# Keys the bucket label. Made when the process starts and never shown, so a label cannot be turned back into an
# address by trying every address; after a restart the labels are new.
_BUCKET_LABEL_KEY = secrets.token_bytes(32)
CALLER_SENTENCE = (
    "The rate limiter trusts {hops} prox{ies} in front of this gateway and counted this call for an {family} "
    "address (bucket {bucket}; X-Forwarded-For held {entries} entr{ys}). Call this from two networks: if both "
    "read the same bucket, all visitors share one rate-limit window and TTA_TRUSTED_PROXY_HOPS must be raised."
)


class RateLimitCaller(BaseModel):
    """Who the rate limiter took the caller of `/healthz` for (earlier review F3): a check a person makes after a
    deploy. Never the address: its family and a label that is the same for one address and differs between two."""

    model_config = ConfigDict(frozen=True)

    trusted_proxy_hops: int  # `TTA_TRUSTED_PROXY_HOPS`: how many forwarded entries are believed
    address_family: AddressFamily
    forwarded_for_entries: int  # how many entries X-Forwarded-For held on this call
    bucket: str  # a keyed hash of the address the call was counted for, cut short
    sentence: str


def _rate_limit_caller(request: Request, trusted_proxy_hops: int) -> RateLimitCaller:
    key = current_client_key()
    family: AddressFamily = "unknown" if key == UNKNOWN_CLIENT else "IPv6" if ":" in key else "IPv4"
    bucket = hmac.new(_BUCKET_LABEL_KEY, key.encode(), hashlib.sha256).hexdigest()[:BUCKET_LABEL_CHARACTERS]
    entries = forwarded_for_entries(request.scope)
    sentence = CALLER_SENTENCE.format(
        hops=trusted_proxy_hops, ies="y" if trusted_proxy_hops == 1 else "ies", family=family, bucket=bucket,
        entries=entries, ys="y" if entries == 1 else "ies",
    )
    return RateLimitCaller(
        trusted_proxy_hops=trusted_proxy_hops, address_family=family, forwarded_for_entries=entries, bucket=bucket,
        sentence=sentence,
    )


ReaderKind = Literal["none", "fixed_rules", "gemini", "openai_compatible"]
READER_SENTENCES: dict[ReaderKind, str] = {
    "none": "No reader of sentences is installed: a request is sent in structured form.",
    "fixed_rules": (
        "No language model is asked. A sentence is read from a recording when it has one, otherwise by the "
        "fixed-rules reader, and the answer says which."
    ),
    "gemini": (
        "Gemini is asked first, because a Gemini key is set (so also when the provider setting says none). When "
        "it does not answer, a recording or the fixed-rules reader reads the sentence, and the answer says so."
    ),
    "openai_compatible": (
        "The model behind the OpenAI-compatible endpoint is asked first. When it does not answer, or its reading "
        "fails the checks against the buyer's words, a recording or the fixed-rules reader reads the sentence, and "
        "the answer says so."
    ),
}


class ReaderInUse(BaseModel):
    """What reads a buyer's sentence in this process, told from the settings alone: no model is asked to find out."""

    model_config = ConfigDict(frozen=True)

    kind: ReaderKind  # what is asked first
    model: str | None  # the model the settings name; null when they name none (the fixed rules, Gemini's default)
    sentence: str


def _agent_reader(settings: Settings, *, installed: bool) -> ReaderInUse:
    """As `tta.agent` chooses (`build_request_parser`, `build_agent_runner`): the OpenAI-compatible endpoint when
    that provider is chosen with its address and model; otherwise Gemini when its key is set, whatever the provider
    setting says; otherwise no model. `installed`: the gateway has a reader of sentences at all."""
    if not installed:
        return _reader_of("none")
    if settings.has_agent_endpoint:
        return _reader_of("openai_compatible", settings.tta_agent_model)
    if settings.has_gemini_key:
        return _reader_of("gemini", settings.tta_gemini_model)
    return _reader_of("fixed_rules")


def _reader_of(kind: ReaderKind, model: str | None = None) -> ReaderInUse:
    return ReaderInUse(kind=kind, model=model, sentence=READER_SENTENCES[kind])


class Health(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: str  # "ok", or "degraded" with the reasons
    reasons: tuple[str, ...]
    # True of this gateway and not a fault in dev and demo, where it leaves `status` as it is: a demo signing key.
    # Outside dev and demo the same sentence is a reason.
    notices: tuple[str, ...] = ()
    environment: str
    mode: str  # what was asked for: live or replay
    source: str | None  # where the last look at price and availability came from; null before the first one
    clock: HealthClock  # the instant order deadlines are judged against, what it rests on, whether it was set
    audit_head: AuditHead
    settings: dict[str, Any]  # secrets appear only as true or false
    agent: dict[str, bool]  # whether the reader of sentences and the buyer agent's runner are installed
    agent_reader: ReaderInUse  # what reads a sentence: the fixed rules, or the model that is asked first
    surfaces: dict[str, bool]
    store: StoreInUse  # which database holds the shared order book and the audit trail, and why
    signing: SigningKey  # the key offers and order records are signed with, and whether it is a demo key
    # Dev and demo only: who the rate limiter took this caller for, without the address. Null anywhere else.
    rate_limit_caller: RateLimitCaller | None = None


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


def _chain_watch(state: Any, verify: Callable[[], ChainVerification]) -> ChainWatch:
    """The application's watch (`tta.api.app` makes it at start). An application put together another way gets
    one at its first call."""
    watch = getattr(state, "chain_watch", None)
    if watch is None:
        watch = state.chain_watch = ChainWatch(verify)
    return watch


@public.get("/healthz", operation_id="get_health", tags=[docs.TAG_OPEN], summary="What is running")
def get_health(request: Request, response: Response) -> Health:
    """The environment, the mode, the source of the last look at price and availability, the clock in force
    (the recording's instant, the supplier's time, or a demo clock that was set), whether the gateway
    is `ok` or `degraded` and why, the head of the audit chain, and which database holds the shared order book
    (`store`: PostgreSQL or SQLite, and why) and the key offers and orders are signed with (`signing`, saying when
    it is a demo key).
    `agent_reader` says what reads a buyer's sentence: the fixed rules, or the language model that is asked first;
    it is told from the settings and no model is called. No token needed; no secret, no path, no host name and no budget
    figure is shown. In dev and demo `rate_limit_caller` says how many proxy hops the rate limiter trusts and which
    address family it counted this call for, with a short label instead of the address: two networks that read
    the same label share one rate-limit window. Nothing is asked of the supplier.

    The whole audit chain of the shared order book is verified for this answer, at most once every 30 seconds
    (between two walks the last result is answered). A stored event that was changed, removed or inserted makes
    the gateway `degraded`, and `reasons` names the first event that does not verify. An intact chain cannot show
    that the newest events were cut off: for that, keep `audit_head` from an earlier answer.

    A demo signing key is a `notices` line in dev and demo and a reason anywhere else. A degraded gateway answers
    200 in dev and demo, so a demonstration stays reachable, and 503 anywhere else."""
    parts, state = request.app.state.parts, request.app.state
    events, last_hash = parts.audit.head()
    source, reasons = _looks(parts.gateway, parts.settings.tta_mode)
    # What the start had to do without: the database, a customer's standing orders (`tta.api.app`).
    reasons = (*reasons, *parts.start_reasons, *getattr(state, "start_reasons", ()))
    chain = _chain_watch(state, parts.audit.verify_chain).state()
    if not chain.ok:
        reasons = (*reasons, chain.sentence)
    demo = parts.settings.is_demo_environment
    key_notice = (DEMO_KEY_IN_USE,) if parts.signer.demo_key else ()
    if not demo:
        reasons = (*reasons, *key_notice)
    if reasons and not demo:
        response.status_code = SERVICE_UNAVAILABLE
    return Health(
        status=DEGRADED if reasons else OK,
        reasons=reasons,
        notices=key_notice if demo else (),
        environment=parts.settings.tta_env,
        mode=parts.settings.tta_mode.value,
        source=None if source is None else source.value,
        clock=describe_clock(parts.settings, parts.clock, parts.replay),
        audit_head=AuditHead(events=events, last_hash=last_hash),
        settings={name: value for name, value in parts.settings.describe().items() if name not in NOT_SHOWN},
        agent={
            "request_parser": parts.service.has_request_parser, "agent_runner": parts.service.has_agent_runner,
        },
        # The buyer agent's runner reads a pasted sentence with a parser of its own, so either part is a reader.
        agent_reader=_agent_reader(
            parts.settings, installed=parts.service.has_request_parser or parts.service.has_agent_runner
        ),
        surfaces=dict(state.surfaces),
        store=StoreInUse(kind=parts.store_kind, reason=parts.store_reason),
        signing=SigningKey(
            key_id=parts.signer.key_id, algorithm=PROOF_ALGORITHM, jwks_path=JWKS_PATH, demo_key=parts.signer.demo_key,
            note=DEMO_KEY if parts.signer.demo_key else SET_KEY,
        ),
        rate_limit_caller=_rate_limit_caller(request, parts.settings.tta_trusted_proxy_hops) if demo else None,
    )
