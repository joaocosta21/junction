"""The buyer agent: a function-calling loop over the gateway's own functions (SPEC section 11; task T10).

Scores on the 30% "one continuous flow" (the demonstration starts from a pasted sentence) and on the 20%
"autonomy and controls". The loop reads the request with the parser, then lets the model call
`get_authority`, `create_offer`, `place_order` and `get_order` until it stops or `MAX_AGENT_STEPS` calls
were made. The gateway, not the model, decides whether an order goes through; the report is put together
from the gateway's own sentences, never from the model's words.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Sequence
from enum import Enum

from tta.agent.model import AgentModel, FunctionCall, TurnCall
from tta.agent.prompts import RUN_INPUT_LEAD, RUNNER_INSTRUCTION
from tta.agent.summaries import offer_sentence
from tta.agent.tools import TOOL_DECLARATIONS, GatewayTools, RunState, ToolOutcome
from tta.contracts.agent import MAX_AGENT_STEPS, AgentRun, AgentStep
from tta.contracts.common import Identity, JsonDict
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import GatewayService, RequestParser
from tta.contracts.request import PurchaseRequest

MAX_TOOL_NAME_CHARACTERS = 64  # a function name the model made up is cut to this in the trace

NO_ORDER_PLACED = "No order was placed."
STOPPED_AT_CAP = "The agent stopped after {steps} steps, the most one run may take."
MODEL_STOPPED = (
    "The language model stopped answering after {steps} steps, so the run ended there; "
    "what the gateway did up to then stands."
)

logger = logging.getLogger(__name__)


class _Ended(Enum):
    """Why a run ended."""

    MODEL_DONE = "the model called no further function"
    CAP = "the step cap was reached"
    MODEL_STOPPED = "the model could not be reached after at least one step"


def _user_input(request: PurchaseRequest) -> JsonDict:
    """The first step of the conversation: the typed request, as data."""
    text = RUN_INPUT_LEAD + json.dumps(request.model_dump(mode="json"))
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


def _function_result(call: FunctionCall, outcome: ToolOutcome) -> JsonDict:
    step: JsonDict = {
        "type": "function_result", "name": call.name, "call_id": call.id,
        "result": [{"type": "text", "text": json.dumps(outcome.result)}],
    }
    return step if outcome.ok else {**step, "is_error": True}


def _step(index: int, call: FunctionCall, outcome: ToolOutcome) -> AgentStep:
    return AgentStep(
        index=index, tool=call.name[:MAX_TOOL_NAME_CHARACTERS], arguments=outcome.arguments, ok=outcome.ok,
        result=outcome.result, sentence=outcome.sentence,
    )


def _report(state: RunState, steps: Sequence[AgentStep], ended: _Ended) -> str:
    """What happened and why, in the gateway's sentences: the option, the policy's verdict, the order."""
    if state.order is not None:
        order = state.order
        parts = [order.option.summary, order.decision.sentence, order.status_sentence]
    else:
        last_refusal = next((step.sentence for step in reversed(steps) if not step.ok), None)
        parts = [offer_sentence(state.offer) if state.offer else None, last_refusal, NO_ORDER_PLACED]
    if ended is _Ended.CAP:
        parts.append(STOPPED_AT_CAP.format(steps=MAX_AGENT_STEPS))
    if ended is _Ended.MODEL_STOPPED:
        parts.append(MODEL_STOPPED.format(steps=len(steps)))
    return " ".join(part for part in parts if part)


class ModelAgentRunner:
    """Implements the `AgentRunner` port over any `AgentModel`: the Gemini model or the recorded one."""

    def __init__(self, *, model: AgentModel, parser: RequestParser) -> None:
        self._model = model
        self._parser = parser

    @property
    def model_id(self) -> str:
        return self._model.model_id

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        """Raises `InvalidRequest` when the text cannot be read into a request, and `SupplierUnavailable`
        when the model cannot be reached: both before any gateway call. Once a call was made the run is
        always returned, so an order that was placed is never lost behind an error."""
        # Its own parser, not `tools.parse_request`: the gateway already recorded this text as received.
        request = self._parser.parse_request(text, identity)
        toolbox = GatewayTools(tools, identity)
        state = RunState(request=request, run_id=uuid.uuid4().hex)
        history: list[JsonDict] = [_user_input(request)]
        steps: list[AgentStep] = []
        turn_number = 0
        while len(steps) < MAX_AGENT_STEPS:
            turn_number += 1
            call_for_turn = TurnCall(
                system=RUNNER_INSTRUCTION, request_text=text, history=tuple(history), tools=TOOL_DECLARATIONS,
                turn=turn_number,
            )
            try:
                turn = self._model.next_turn(call_for_turn)
            except SupplierUnavailable as unreachable:
                if not steps:
                    raise  # nothing was done: the caller gets the error itself
                logger.warning("The model stopped answering after %d steps: %s", len(steps), unreachable.detail)
                return self._run(text, state, steps, _Ended.MODEL_STOPPED)
            if not turn.calls:
                return self._run(text, state, steps, _Ended.MODEL_DONE)
            history.extend(turn.steps)
            for call in turn.calls[: MAX_AGENT_STEPS - len(steps)]:  # calls beyond the cap are not made
                outcome = toolbox.call(call.name, call.arguments, state)
                state = outcome.state
                steps.append(_step(len(steps) + 1, call, outcome))
                history.append(_function_result(call, outcome))
        return self._run(text, state, steps, _Ended.CAP)

    def _run(self, text: str, state: RunState, steps: Sequence[AgentStep], ended: _Ended) -> AgentRun:
        offer_id = state.order.offer_id if state.order else state.offer.offer_id if state.offer else None
        return AgentRun(
            text=text, model=self._model.label_for(text), recorded=self._model.recorded, steps=tuple(steps),
            offer_id=offer_id, order_id=state.order.order_id if state.order else None,
            order_status=state.order.status if state.order else None,
            report=_report(state, steps, ended), stopped_at_cap=ended is _Ended.CAP,
        )
