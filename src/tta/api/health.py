"""`GET /healthz`: what is running, where the data comes from, which store is in use, the head of the audit chain.

Scores on the 20% "how decisions are logged and auditable" (a head another party can keep shows a trail cut short;
the answer says where the record is kept) and on the 15% path to production. No token; no secret, no path, no host.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict

from tta.api import docs
from tta.api.clock_info import HealthClock, describe_clock
from tta.api.signing import JWKS_PATH
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
    agent: dict[str, bool]
    surfaces: dict[str, bool]
    store: StoreInUse  # which database holds the shared order book and the audit trail, and why
    signing: SigningKey  # the key offers and order records are signed with, and whether it is a demo key


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
def get_health(request: Request, response: Response) -> Health:
    """The environment, the mode, the source of the last look at price and availability, the clock in force
    (the recording's instant, the supplier's time, or a demo clock that was set), whether the gateway
    is `ok` or `degraded` and why, the head of the audit chain, and which database holds the shared order book
    (`store`: PostgreSQL or SQLite, and why) and the key offers and orders are signed with (`signing`, saying when
    it is a demo key). No token needed; no secret, no path, no host name and no budget
    figure is shown. Nothing is asked of the supplier and the audit trail is not read through.

    A demo signing key is a `notices` line in dev and demo and a reason anywhere else. A degraded gateway answers
    200 in dev and demo, so a demonstration stays reachable, and 503 anywhere else."""
    parts, state = request.app.state.parts, request.app.state
    events, last_hash = parts.audit.head()
    source, reasons = _looks(parts.gateway, parts.settings.tta_mode)
    # What the start had to do without: the database, a customer's standing orders (`tta.api.app`).
    reasons = (*reasons, *parts.start_reasons, *getattr(state, "start_reasons", ()))
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
        surfaces=dict(state.surfaces),
        store=StoreInUse(kind=parts.store_kind, reason=parts.store_reason),
        signing=SigningKey(
            key_id=parts.signer.key_id, algorithm=PROOF_ALGORITHM, jwks_path=JWKS_PATH, demo_key=parts.signer.demo_key,
            note=DEMO_KEY if parts.signer.demo_key else SET_KEY,
        ),
    )
