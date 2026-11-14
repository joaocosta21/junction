"""An OpenAI-compatible chat-completions endpoint behind the `AgentModel` interface (task AG).

Scores on the 30% "working end-to-end demo" (a real model reads the sentence and makes the calls) and the 15%
"open, documented standards": the request and the answer are the chat-completions shapes any OpenAI-compatible
server takes, so the model behind the buyer's agent is a setting, not code. Written for the open-weights model of
`deploy/agent_model.py`, served by vLLM on Modal, from vLLM's documentation as read on 14 Nov 2026
("OpenAI-compatible server", "Tool calling", "Structured outputs"):
- one `POST {base_url}/chat/completions` per call, with plain `httpx`; the key goes in `Authorization: Bearer`
  and nowhere else;
- a structured answer (`extract`): `response_format` of type `json_schema` with the schema as written, and the
  same schema in the instruction, as the page advises. A server that refuses the schema (400) is asked once more
  without `response_format`, and from then on without it: the parser validates every answer whatever enforced it;
- the corrective turn: the answer that failed the checks goes back as the assistant's turn, followed by what
  failed, each as a field path and a fixed reason of ours;
- tool calling (`next_turn`): `tools` of type `function`, `tool_choice` `auto`; the model's turn goes back as an
  `assistant` message with its `tool_calls`, each result as a `tool` message with the `tool_call_id`;
- one retry, counted here: a time-out, a connection failure, 408, 429 or a 5xx is tried twice, then raised as
  `ModelUnreachable`; 401 and 403 raise it at once. A model on Modal that has scaled to zero answers 503 while
  its container starts, so the first request after an idle time ends here and the fixed rules read it;
- any other refusal, an answer cut short or one with nothing to read is `ModelUnusable`: the fallback lets the
  fixed rules read then too, and says the model gave no usable answer.

No error and no log line of this module carries the address, the key, the request or the server's text: a failure
is named by its HTTP status or by the exception's class name only.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from tta.agent.model import AnswerSource, ExtractCall, FunctionCall, ModelTurn, ModelUnreachable, TurnCall
from tta.agent.outage import Outage
from tta.agent.status import ModelStatus
from tta.config import Settings
from tta.contracts.agent import ReadingSource
from tta.contracts.common import JsonDict
from tta.contracts.errors import SupplierUnavailable

CHAT_COMPLETIONS_PATH = "/chat/completions"
# One sentence waits for two attempts at most. The first structured answer after a start compiles the schema's
# grammar, which vLLM's page puts at "several seconds"; a model already loaded answers a sentence well inside this.
REQUEST_TIMEOUT_SECONDS = 45.0
CONNECT_TIMEOUT_SECONDS = 10.0
MAX_RETRIES = 1
RETRY_WAIT_SECONDS = 0.5
OUTAGE_MEMORY_SECONDS = 45.0  # shorter than Gemini's: a container on Modal that was starting is soon there
RETRYABLE_STATUSES = frozenset({408, 429})
SERVER_ERRORS = range(500, 600)
NOT_AVAILABLE_TO_US = frozenset({401, 403})
BAD_REQUEST = 400
TEMPERATURE = 0  # the same sentence is read the same way twice
MAX_ANSWER_TOKENS = 1024  # a request of twenty lines fits; a longer answer is cut and refused
MAX_TURN_TOKENS = 512
MAX_SENT_BACK_CHARACTERS = 4000  # how much of an answer that failed is sent back in the corrective turn
SCHEMA_NAME = "purchase_request"
FINISHED = frozenset({"stop", "tool_calls"})
MODAL_HOST_SUFFIX = ".modal.run"  # the addresses Modal gives a deployed app
ON_MODAL = "Modal"
LOCAL_CALL_ID = "call-{turn}-{number}"  # for a call the model gave no id
NOT_JSON_ARGUMENTS = "arguments"  # the one argument of a call whose arguments were not a JSON object
NOT_A_JSON_OBJECT = "<not a JSON object>"

ASSISTANT_MESSAGE = "assistant_message"  # the model's turn as a history step
USER_INPUT, FUNCTION_RESULT = "user_input", "function_result"  # the runner's steps (`tta.agent.runner`)

ANSWER_AS_JSON = (
    "Answer with one JSON object and nothing else: no explanation, no code fence. It must be valid for this "
    "JSON Schema:\n{schema}"
)
CORRECTION = (
    "That answer did not pass the checks against the buyer's own words. What failed, by field:\n{faults}\n"
    "Read the buyer's text again and answer with the corrected JSON object only. Report only what the text says: "
    "take every number, date, exclusion and product word from the text itself, and add nothing it does not say."
)
USE_THE_TYPED_REQUEST = "Send the typed request to POST /v1/offers instead."
NOT_CONFIGURED = (
    "TTA_AGENT_PROVIDER is openai_compatible but TTA_AGENT_BASE_URL or TTA_AGENT_MODEL is not set, so no model "
    "can be asked."
)
UNREACHABLE = "The language model did not answer after {attempts} attempts ({reason}). " + USE_THE_TYPED_REQUEST
NOT_AVAILABLE = (
    "The language model is not available to this gateway ({reason}: the key or its permissions). "
    + USE_THE_TYPED_REQUEST
)
REFUSED = "The language model refused the call ({reason}). " + USE_THE_TYPED_REQUEST
NOT_FINISHED = "The language model did not finish its answer (finish reason {reason}). " + USE_THE_TYPED_REQUEST
NO_TEXT = "The language model returned no text to read. " + USE_THE_TYPED_REQUEST
REMEMBERED = (
    "The language model did not answer a moment ago, so it is not asked again for {seconds:.0f} seconds. "
    + USE_THE_TYPED_REQUEST
)
NO_RESPONSE = "no response: a time-out or a connection failure"
NO_USABLE_RESPONSE = "no usable response: {name}"
HTTP_STATUS = "HTTP status {status}"
NOT_GIVEN, NOT_RECOGNISED = "not given", "not recognised"
KNOWN_FINISH_REASONS = frozenset({"stop", "tool_calls", "length", "content_filter", "function_call"})

logger = logging.getLogger(__name__)


class ModelUnusable(SupplierUnavailable):
    """The model was reached and gave nothing that can be used: it refused the call, its answer was cut short, or
    it held nothing to read. Answered as `supplier-unavailable`; the fixed rules may stand in for it."""

    def __init__(self, detail: str, *, http_status: int | None = None) -> None:
        super().__init__(detail)
        self.http_status = http_status  # kept off the problem document: it is the model server's, not ours


@dataclass(frozen=True)
class _Failure:
    """Why one attempt got no answer, in words that never repeat the server's text."""

    status: int | None = None
    error_class: str | None = None

    @property
    def reason(self) -> str:
        if self.status is not None:
            return HTTP_STATUS.format(status=self.status)
        return NO_RESPONSE if self.error_class is None else NO_USABLE_RESPONSE.format(name=self.error_class)

    @property
    def may_pass(self) -> bool:
        return self.status is None or self.status in RETRYABLE_STATUSES or self.status in SERVER_ERRORS


def host_of(base_url: str) -> str | None:
    """"Modal" for an address Modal gave; `None` for any other, which a reading's sentence then does not name."""
    hostname = urlsplit(base_url).hostname or ""
    return ON_MODAL if hostname.endswith(MODAL_HOST_SUFFIX) else None


def http_client(settings: Settings, *, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """The HTTP client of the endpoint the settings name. `transport` replaces the network (a test's stand-in
    server). Raises `SupplierUnavailable` when the address or the model name is not set. Building it sends
    nothing. The key is unwrapped here, into the client's own header, and kept nowhere else."""
    if not settings.has_agent_endpoint or settings.tta_agent_base_url is None:
        raise SupplierUnavailable(NOT_CONFIGURED)
    headers = {"Content-Type": "application/json"}
    if settings.has_agent_key and settings.tta_agent_api_key is not None:
        headers["Authorization"] = f"Bearer {settings.tta_agent_api_key.get_secret_value().strip()}"
    return httpx.Client(
        base_url=settings.tta_agent_base_url, headers=headers, transport=transport,
        timeout=httpx.Timeout(REQUEST_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
    )


def _tool(declaration: JsonDict) -> JsonDict:
    """A function of the gateway as chat completions declares it. One with no parameters takes an empty object."""
    return {"type": "function", "function": {
        "name": str(declaration["name"]), "description": str(declaration["description"]),
        "parameters": declaration.get("parameters") or {"type": "object", "properties": {}},
    }}


def _texts(items: Any) -> str:
    return "".join(str(item["text"]) for item in items or ()
                   if isinstance(item, dict) and isinstance(item.get("text"), str))


def to_messages(system: str, history: Sequence[JsonDict]) -> list[JsonDict]:
    """The `messages` of a tool-calling request. Raises `ValueError` for a step this module does not know."""
    messages: list[JsonDict] = [{"role": "system", "content": system}]
    for step in history:
        kind = step.get("type")
        if kind == USER_INPUT:
            messages.append({"role": "user", "content": _texts(step.get("content"))})
        elif kind == ASSISTANT_MESSAGE:
            messages.append(dict(step["message"]))
        elif kind == FUNCTION_RESULT:
            messages.append({"role": "tool", "tool_call_id": str(step.get("call_id")),
                             "content": _texts(step.get("result"))})
        else:
            raise ValueError(f"A history step of type {str(kind)[:40]!r} cannot be sent as a chat message.")
    return messages


def _arguments(raw: Any) -> JsonDict:
    """The arguments of a call as an object. Anything else becomes one argument no function takes, so the runner
    refuses the call and the model is told: nothing is guessed from a broken call."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            return {NOT_JSON_ARGUMENTS: NOT_A_JSON_OBJECT}
    return dict(raw) if isinstance(raw, dict) else {NOT_JSON_ARGUMENTS: NOT_A_JSON_OBJECT}


def _calls_of(message: Mapping[str, Any], turn: int) -> tuple[FunctionCall, ...]:
    calls = []
    asked = [call for call in message.get("tool_calls") or () if isinstance(call, dict)]
    for number, call in enumerate(asked, start=1):
        function = call.get("function") if isinstance(call.get("function"), dict) else {}
        call_id = call.get("id") if isinstance(call.get("id"), str) and call.get("id") else None
        calls.append(FunctionCall(
            id=call_id or LOCAL_CALL_ID.format(turn=turn, number=number), name=str(function.get("name") or ""),
            arguments=_arguments(function.get("arguments")),
        ))
    return tuple(calls)


def _assistant_step(text: str | None, calls: Sequence[FunctionCall]) -> JsonDict:
    """The model's turn as it goes back on the next request: rebuilt from what was read, never the raw answer."""
    message: JsonDict = {"role": "assistant", "content": text}
    if calls:
        message["tool_calls"] = [
            {"id": call.id, "type": "function",
             "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
            for call in calls
        ]
    return {"type": ASSISTANT_MESSAGE, "message": message}


def _json_text(text: str) -> str:
    """The answer without a code fence around it, when the model wrote one."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```")
    return stripped.strip()


class OpenAICompatibleModel:
    """Implements `AgentModel` over `POST /chat/completions`. It cannot be shown a photo."""

    def __init__(
        self,
        client: httpx.Client,
        model: str,
        *,
        host: str | None = None,
        max_retries: int = MAX_RETRIES,
        sleep: Callable[[float], None] = time.sleep,
        outage: Outage | None = None,
        status: ModelStatus | None = None,
    ) -> None:
        """`host`: where the model is served, as a reading's sentence says it ("Modal"). `outage`: where a failure
        for unreachability is remembered. `status`: where the outcome of the last call is noted for `/healthz`."""
        self._client = client
        self._model = model
        self._host = host
        self._max_retries = max_retries
        self._sleep = sleep
        self._outage = outage
        self._status = status
        self._schema_enforced = True  # until the server refuses a schema

    @classmethod
    def from_settings(
        cls, settings: Settings, *, transport: httpx.BaseTransport | None = None, outage: Outage | None = None,
        status: ModelStatus | None = None, sleep: Callable[[float], None] = time.sleep,
    ) -> OpenAICompatibleModel:
        client = http_client(settings, transport=transport)
        return cls(client, str(settings.tta_agent_model), host=host_of(str(settings.tta_agent_base_url)),
                   outage=outage, status=status, sleep=sleep)

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def recorded(self) -> bool:
        return False

    def label_for(self, request_text: str) -> str:
        return self._model

    def answer_source(self, request_text: str) -> AnswerSource:
        return AnswerSource(ReadingSource.MODEL, self._model, host=self._host, checked=True)

    def extract(self, call: ExtractCall) -> str:
        """The JSON text of a structured answer. With `previous_answer`, the corrective turn."""
        system = f"{call.system}\n\n{ANSWER_AS_JSON.format(schema=json.dumps(call.schema))}"
        messages: list[JsonDict] = [{"role": "system", "content": system}, {"role": "user", "content": call.text}]
        if call.previous_answer is not None:
            faults = "\n".join(f"- {fault}" for fault in call.faults)
            messages += [
                {"role": "assistant", "content": call.previous_answer[:MAX_SENT_BACK_CHARACTERS]},
                {"role": "user", "content": CORRECTION.format(faults=faults)},
            ]
        payload: JsonDict = {"messages": messages, "max_tokens": MAX_ANSWER_TOKENS}
        text = self._message(payload, schema=call.schema).get("content")
        if not isinstance(text, str) or not text.strip():
            raise ModelUnusable(NO_TEXT)
        return _json_text(text)

    def next_turn(self, call: TurnCall) -> ModelTurn:
        payload: JsonDict = {
            "messages": to_messages(call.system, call.history), "tools": [_tool(tool) for tool in call.tools],
            "tool_choice": "auto", "max_tokens": MAX_TURN_TOKENS,
        }
        message = self._message(payload)
        calls = _calls_of(message, call.turn)
        content = message.get("content")
        text = content if isinstance(content, str) and content.strip() else None
        return ModelTurn(steps=(_assistant_step(text, calls),), calls=calls, text=text)

    def _message(self, payload: JsonDict, *, schema: JsonDict | None = None) -> Mapping[str, Any]:
        """The message of one finished answer. With a schema, the answer is held to it by the server while the
        server takes it; a server that refuses the schema is asked without it."""
        if schema is not None and self._schema_enforced:
            held = {**payload, "response_format": {
                "type": "json_schema", "json_schema": {"name": SCHEMA_NAME, "schema": schema},
            }}
            try:
                return self._answer(held)
            except ModelUnusable as refused:
                if refused.http_status != BAD_REQUEST:
                    raise
                logger.warning("The model's server refused the JSON Schema (HTTP status 400): asked without it.")
                self._schema_enforced = False
        return self._answer(payload)

    def _answer(self, payload: JsonDict) -> Mapping[str, Any]:
        """Raises `ModelUnreachable` after the retries, or at once while a recent failure is remembered;
        `ModelUnusable` at once for a refusal or an answer another try cannot change."""
        if self._outage is not None and self._outage.is_open():
            raise ModelUnreachable(REMEMBERED.format(seconds=self._outage.seconds))
        attempts = self._max_retries + 1
        failure = _Failure()
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self._sleep(RETRY_WAIT_SECONDS * 2 ** (attempt - 2))
            body, failure = self._send(payload)
            if failure is None:
                self._note(reachable=True)
                return self._finished(body)
            # Logged by its HTTP status or class name only: never the address, the key or the server's text.
            logger.warning("Model call failed (attempt %d of %d): %s", attempt, attempts, failure.reason)
            if failure.status in NOT_AVAILABLE_TO_US:
                self._unreachable()
                raise ModelUnreachable(NOT_AVAILABLE.format(reason=failure.reason))
            if not failure.may_pass:
                self._note(reachable=True)  # it answered: the call is what it refused
                raise ModelUnusable(REFUSED.format(reason=failure.reason), http_status=failure.status)
        self._unreachable()
        raise ModelUnreachable(UNREACHABLE.format(attempts=attempts, reason=failure.reason))

    def _note(self, *, reachable: bool) -> None:
        if self._status is not None:
            self._status.note(reachable=reachable)

    def _unreachable(self) -> None:
        self._note(reachable=False)
        if self._outage is not None:
            self._outage.note()

    def _send(self, payload: JsonDict) -> tuple[Any, _Failure | None]:
        """(the decoded body, None), or (None, why). No exception is chained or re-raised, so the text of none
        reaches a log or a caller: httpx's can hold the address."""
        request = {"model": self._model, "temperature": TEMPERATURE, **payload}
        try:
            response = self._client.post(CHAT_COMPLETIONS_PATH, json=request)
        except httpx.TransportError:
            return None, _Failure()
        except Exception as error:  # see above: named by its class, never by its text
            return None, _Failure(error_class=type(error).__name__)
        if response.status_code != httpx.codes.OK:
            return None, _Failure(status=response.status_code)
        try:
            return response.json(), None
        except ValueError:
            return None, _Failure(error_class="JSONDecodeError")

    def _finished(self, body: Any) -> Mapping[str, Any]:
        choices = body.get("choices") if isinstance(body, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = choice.get("message")
        reason = choice.get("finish_reason")
        if not isinstance(message, dict) or reason not in FINISHED:
            named = NOT_GIVEN if reason is None else reason if reason in KNOWN_FINISH_REASONS else NOT_RECOGNISED
            logger.warning("The model's answer did not finish (finish reason %s)", named)
            raise ModelUnusable(NOT_FINISHED.format(reason=named))
        return message
