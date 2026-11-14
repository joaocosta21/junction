"""The buyer agent: a function-calling loop over the gateway's own functions (SPEC section 11; task T10).

Scores on the 30% "one continuous flow" (the demonstration starts from a pasted sentence) and on the 20%
"autonomy and controls". The loop reads the request with the parser, then lets the model call
`get_authority`, `create_offer`, `place_order` and `get_order` until it stops or `MAX_AGENT_STEPS` calls
were made. The gateway, not the model, decides whether an order goes through; the report is put together
from the gateway's own sentences, never from the model's words.

Once the run has called the gateway, any exception ends it and the run is returned with every step done so
far and the order, if one was placed: a failure never hides an order (task FIX-9). Its report opens with what
stopped it. Before the first gateway call, an exception is the caller's: nothing was done.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, replace

from tta.agent.model import AgentModel, FunctionCall, TurnCall
from tta.agent.prompts import RUN_INPUT_LEAD, RUNNER_INSTRUCTION
from tta.agent.summaries import offer_sentence
from tta.agent.tools import PLACE_ORDER, TOOL_DECLARATIONS, GatewayTools, RunState, ToolOutcome
from tta.contracts.agent import MAX_AGENT_STEPS, AgentRun, AgentStep
from tta.contracts.common import Identity, JsonDict
from tta.contracts.errors import TtaError
from tta.contracts.ports import GatewayService, RequestParser
from tta.contracts.request import PurchaseRequest

MAX_TOOL_NAME_CHARACTERS = 64  # a function name the model made up is cut to this in the trace
ORDER_FOR_OFFER = "order_for_offer"  # `GatewayService.order_for_offer`, where the gateway has it (task FIX-10)

NO_ORDER_PLACED = "No order was placed."
STOPPED_AT_CAP = "The agent stopped after {steps}, the most one run may take."
MODEL_STOPPED = (
    "The language model stopped answering after {steps}, so the run ended there; "
    "what the gateway did up to then stands."
)
MODEL_FAILED = (
    "The run ended after {steps}: the language model's answer could not be used ({error}); "
    "what the gateway did up to then stands."
)
GATEWAY_FAILED = (
    "The run ended at step {step} ({tool}): the gateway failed ({error}); what the gateway did up to then stands."
)
MODEL_DONE_WITHOUT = "The agent stopped after {steps} without {what}."  # a model or the fixed rules
WITHOUT_OFFER, WITHOUT_ORDER = "an offer", "an order"

logger = logging.getLogger(__name__)


def _steps(count: int) -> str:
    return f"{count} step" if count == 1 else f"{count} steps"


@dataclass(frozen=True)
class _Progress:
    """What the run has done so far."""

    state: RunState
    steps: tuple[AgentStep, ...] = ()
    gateway_refusals: tuple[str, ...] = ()  # the gateway's own sentences for the calls it refused
    called: bool = False  # a call reached the gateway, or was on its way when it failed

    def after(self, call: FunctionCall, outcome: ToolOutcome) -> _Progress:
        step = AgentStep(
            index=len(self.steps) + 1, tool=call.name[:MAX_TOOL_NAME_CHARACTERS], arguments=outcome.arguments,
            ok=outcome.ok, result=outcome.result, sentence=outcome.sentence,
        )
        refusals = self.gateway_refusals
        if outcome.by_gateway and outcome.sentence:
            refusals = (*refusals, outcome.sentence)
        return replace(self, state=outcome.state, steps=(*self.steps, step), gateway_refusals=refusals)

    def refusal(self) -> str | None:
        """The gateway's last refusal; with none, the runner's last one."""
        if self.gateway_refusals:
            return self.gateway_refusals[-1]
        return next((step.sentence for step in reversed(self.steps) if not step.ok), None)


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


def _report(progress: _Progress, *, opening: str | None = None, at_cap: bool = False) -> str:
    """What happened and why, in the gateway's sentences: the option, the policy's verdict, the order. A run
    that did not end by itself opens with what stopped it."""
    state = progress.state
    if state.order is not None:
        order = state.order
        parts = [order.option.summary, order.decision.sentence, order.status_sentence]
    else:
        parts = [offer_sentence(state.offer) if state.offer else None, progress.refusal(), NO_ORDER_PLACED]
    if at_cap:
        parts.append(STOPPED_AT_CAP.format(steps=_steps(MAX_AGENT_STEPS)))
    return " ".join(part for part in (opening, *parts) if part)


def _model_failed(error: Exception, steps: int) -> str:
    """What stopped the run, never the exception's own text: the SDK's can repeat what the service was sent."""
    if isinstance(error, TtaError):
        return MODEL_STOPPED.format(steps=_steps(steps))
    return MODEL_FAILED.format(steps=_steps(steps), error=type(error).__name__)


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
        progress = _Progress(state=RunState(request=request, run_id=uuid.uuid4().hex))
        history: list[JsonDict] = [_user_input(request)]
        turn_number = 0
        while len(progress.steps) < MAX_AGENT_STEPS:
            turn_number += 1
            call_for_turn = TurnCall(
                system=RUNNER_INSTRUCTION, request_text=text, history=tuple(history), tools=TOOL_DECLARATIONS,
                turn=turn_number, profile_id=identity.profile_id,
            )
            try:
                turn = self._model.next_turn(call_for_turn)
            except Exception as error:  # once the gateway was called, nothing may hide what it did
                if not progress.called:
                    raise  # nothing was done: the caller gets the error itself
                logger.warning("The model failed after %d steps (%s)", len(progress.steps), type(error).__name__)
                return self._run(text, progress, opening=_model_failed(error, len(progress.steps)))
            if not turn.calls:
                return self._run(text, progress, opening=self._model_done(progress))
            history.extend(turn.steps)
            for call in turn.calls[: MAX_AGENT_STEPS - len(progress.steps)]:  # calls beyond the cap are not made
                progress = replace(progress, called=True)
                try:
                    outcome = toolbox.call(call.name, call.arguments, progress.state)
                except Exception as error:  # a fault below the gateway's typed errors: the run still stands
                    return self._gateway_failed(text, progress, call, error, (tools, identity))
                progress = progress.after(call, outcome)
                history.append(_function_result(call, outcome))
        return self._run(text, progress, at_cap=True)

    @staticmethod
    def _model_done(progress: _Progress) -> str | None:
        """The model ended with no function call: said when it ended without an order."""
        if progress.state.order is not None:
            return None
        what = WITHOUT_OFFER if progress.state.offer is None else WITHOUT_ORDER
        return MODEL_DONE_WITHOUT.format(steps=_steps(len(progress.steps)), what=what)

    def _gateway_failed(
        self, text: str, progress: _Progress, call: FunctionCall, error: Exception,
        caller: tuple[GatewayService, Identity],
    ) -> AgentRun:
        step = len(progress.steps) + 1
        logger.warning("The gateway failed at step %d (%s): %s", step, call.name[:MAX_TOOL_NAME_CHARACTERS],
                       type(error).__name__)
        recovered = replace(progress, state=_order_placed_anyway(progress.state, call, *caller))
        opening = GATEWAY_FAILED.format(step=step, tool=call.name[:MAX_TOOL_NAME_CHARACTERS],
                                        error=type(error).__name__)
        return self._run(text, recovered, opening=opening)

    def _run(self, text: str, progress: _Progress, *, opening: str | None = None, at_cap: bool = False) -> AgentRun:
        state = progress.state
        offer_id = state.order.offer_id if state.order else state.offer.offer_id if state.offer else None
        return AgentRun(
            text=text, model=self._model.label_for(text), recorded=self._model.recorded, steps=progress.steps,
            offer_id=offer_id, order_id=state.order.order_id if state.order else None,
            order_status=state.order.status if state.order else None,
            report=_report(progress, opening=opening, at_cap=at_cap), stopped_at_cap=at_cap,
        )


def _order_placed_anyway(state: RunState, call: FunctionCall, tools: GatewayService, identity: Identity) -> RunState:
    """After `place_order` failed with an untyped error, the order it may still have placed, read back through
    `order_for_offer` where the gateway has it. Anything else: the state as it was."""
    find = getattr(tools, ORDER_FOR_OFFER, None)
    if call.name != PLACE_ORDER or state.offer is None or state.order is not None or find is None:
        return state
    try:
        order = find(identity, state.offer.offer_id)
    except Exception as error:  # the run is already ending on an error: this one is logged, not raised
        logger.warning("The order of offer %s could not be read back (%s)", state.offer.offer_id,
                       type(error).__name__)
        return state
    return state if order is None else replace(state, order=order)
