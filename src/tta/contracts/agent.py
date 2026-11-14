"""What the buyer agent returns: its tool-call trace and a report (SPEC section 11)."""

from __future__ import annotations

from pydantic import Field

from tta.contracts.common import Contract, JsonDict, OrderStatus
from tta.contracts.request import MAX_TEXT_LENGTH

MAX_AGENT_STEPS = 8


class ParseRequestBody(Contract):
    """Body of POST /v1/requests/parse and POST /v1/agent/run."""

    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)


class AgentStep(Contract):
    """One tool call of the agent and what the gateway answered."""

    index: int = Field(ge=1)
    tool: str
    arguments: JsonDict = Field(default_factory=dict)
    ok: bool
    result: JsonDict = Field(default_factory=dict)  # a summary of the gateway's answer, never a secret
    sentence: str | None = None  # the gateway's own sentence for this step, when it has one


class AgentRun(Contract):
    text: str
    model: str  # the model id, or "recorded" when served from recorded outputs
    recorded: bool
    steps: tuple[AgentStep, ...] = ()
    offer_id: str | None = None
    order_id: str | None = None
    order_status: OrderStatus | None = None
    report: str  # plain language, built from the gateway's sentences
    stopped_at_cap: bool = False
