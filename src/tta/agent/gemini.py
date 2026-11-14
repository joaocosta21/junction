"""The Gemini model behind the `AgentModel` interface (SPEC section 11; task T10).

Written from the Gemini API documentation as read on 14 Nov 2026 (https://ai.google.dev/gemini-api/docs,
which redirects to https://aistudio.google.com/docs: "Interactions API", "Structured outputs", "Function
calling", "Thinking", "Models", "Troubleshooting") and from the installed `google-genai` 3.3.0:
- The Interactions API (`client.interactions.create`) is the interface the documentation recommends for new
  projects; `generateContent` is described there as legacy.
- Structured output: `response_format` of type `text` with `mime_type` `application/json` and a `schema`.
- Function calling: `tools` of type `function`; the model's `function_call` steps carry `id`, `name` and
  `arguments`; the result goes back as a `function_result` step.
- `store=False`: the conversation is not kept by the provider. The whole history is sent on every turn,
  with the model's own steps unchanged (a `thought` step carries the signature the next turn needs).
- One request is one model call here: the SDK's own retries and its automatic continuation are switched
  off, and this module retries by its own count, so the number of calls is always known.

The key is read from the settings, handed to the SDK and kept nowhere else. No error and no log line of this
module carries the SDK's error text, which could repeat what the service was sent.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from google import genai
from google.genai import types

from tta.agent.model import ExtractCall, FunctionCall, ModelTurn, TurnCall
from tta.config import Settings
from tta.contracts.common import JsonDict
from tta.contracts.errors import SupplierUnavailable

# Chosen from the documentation's model list: the newest Flash model marked stable, with structured
# outputs and function calling both supported, and one the team's key lists (task T10).
DEFAULT_MODEL = "gemini-3.8-flash"
# "low" is the lowest level this model supports; the documentation recommends it for latency-sensitive
# work and says it is still capable on agentic tasks. Reading one sentence and choosing among four
# functions needs no more.
THINKING_LEVEL = "low"
REQUEST_TIMEOUT_SECONDS = 30.0
MILLISECONDS_PER_SECOND = 1000
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = 0.5  # doubled before each further retry
SDK_ATTEMPTS = 1  # the SDK does not retry: this module does, and counts
# The documentation's troubleshooting page: retry 408, 429 and 5xx; never 400, 402 or 403.
RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
ANSWERED_STATUSES = frozenset({"completed", "requires_action"})  # the second: the model asks for a function
# The other statuses of an interaction (API reference, "Interaction.status"). Only these are repeated in an error.
UNANSWERED_STATUSES = frozenset(
    {"in_progress", "failed", "cancelled", "incomplete", "budget_exceeded", "queued", "requires_continuation"}
)
STATUS_NOT_RECOGNISED = "not recognised"
JSON_MIME_TYPE = "application/json"

NO_KEY = "No GEMINI_API_KEY is set, so the Gemini model cannot be called."
USE_THE_TYPED_REQUEST = "Send the typed request to POST /v1/offers instead."
UNREACHABLE = "The language model did not answer after {attempts} attempts ({reason}). " + USE_THE_TYPED_REQUEST
REFUSED = "The language model refused the call ({reason}). " + USE_THE_TYPED_REQUEST
NOT_FINISHED = "The language model did not finish its answer (status {status}). " + USE_THE_TYPED_REQUEST
NO_TEXT = "The language model returned no text to read. " + USE_THE_TYPED_REQUEST
NO_RESPONSE = "no response: a time-out or a connection failure"
HTTP_STATUS = "HTTP status {status}"

logger = logging.getLogger(__name__)


class InteractionsTransport(Protocol):
    """Sends one request to the Interactions API. `GeminiModel` talks to nothing else."""

    def create(self, **request: Any) -> Any: ...


class _SdkTransport:
    """The SDK client. It is kept here for as long as the transport lives: a client that is no longer
    referenced closes its connection pool, and a later call then fails."""

    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def create(self, **request: Any) -> Any:
        return self._client.interactions.create(
            **request, store=False, automatic_continuation=False, timeout=REQUEST_TIMEOUT_SECONDS
        )


def chosen_model(settings: Settings) -> str:
    """The model id: `TTA_GEMINI_MODEL` when set, otherwise the default."""
    return settings.tta_gemini_model or DEFAULT_MODEL


def sdk_transport(settings: Settings, *, client_args: Mapping[str, Any] | None = None) -> InteractionsTransport:
    """The real transport. `client_args` are passed to the SDK's HTTP client (a test passes a mock transport).

    Raises `SupplierUnavailable` when no key is set. Building it sends nothing.
    """
    if settings.gemini_api_key is None or not settings.has_gemini_key:
        raise SupplierUnavailable(NO_KEY)
    options = types.HttpOptions(
        timeout=int(REQUEST_TIMEOUT_SECONDS * MILLISECONDS_PER_SECOND),
        retry_options=types.HttpRetryOptions(attempts=SDK_ATTEMPTS),
        client_args=dict(client_args) if client_args else None,
    )
    return _SdkTransport(genai.Client(api_key=settings.gemini_api_key.get_secret_value(), http_options=options))


def _status_of(error: Exception) -> int | None:
    """The HTTP status of an SDK error; `None` for a time-out or a connection failure."""
    status = getattr(error, "status_code", None)
    return status if isinstance(status, int) else None


def _reason(status: int | None) -> str:
    return NO_RESPONSE if status is None else HTTP_STATUS.format(status=status)


def _text_of(interaction: Any) -> str | None:
    text = getattr(interaction, "output_text", None)
    return text if isinstance(text, str) and text.strip() else None


class GeminiModel:
    """Implements `AgentModel` over the Interactions API."""

    def __init__(
        self,
        transport: InteractionsTransport,
        model_id: str,
        *,
        max_retries: int = MAX_RETRIES,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transport = transport
        self._model_id = model_id
        self._max_retries = max_retries
        self._sleep = sleep

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def recorded(self) -> bool:
        return False

    def label_for(self, request_text: str) -> str:
        return self._model_id

    def extract(self, call: ExtractCall) -> str:
        interaction = self._create(
            input=call.text,
            system_instruction=call.system,
            response_format={"type": "text", "mime_type": JSON_MIME_TYPE, "schema": call.schema},
        )
        text = _text_of(interaction)
        if text is None:
            raise SupplierUnavailable(NO_TEXT)
        return text

    def next_turn(self, call: TurnCall) -> ModelTurn:
        interaction = self._create(
            input=list(call.history), system_instruction=call.system, tools=list(call.tools)
        )
        steps = tuple(getattr(interaction, "steps", None) or ())
        calls = tuple(
            FunctionCall(id=step.id, name=step.name, arguments=dict(step.arguments or {}))
            for step in steps
            if step.type == "function_call"
        )
        # As the documentation's stateless example does: every step goes back as it was received.
        as_received: tuple[JsonDict, ...] = tuple(step.model_dump() for step in steps)
        return ModelTurn(steps=as_received, calls=calls, text=_text_of(interaction))

    def _create(self, **request: Any) -> Any:
        """One answered interaction. Raises `SupplierUnavailable` after the retries, or at once for a
        refusal that another try cannot change."""
        attempts = self._max_retries + 1
        status: int | None = None
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self._sleep(RETRY_WAIT_SECONDS * 2 ** (attempt - 2))
            answer, status, answered = self._send(request)
            if answered:
                return self._finished(answer)
            # Logged by its HTTP status only: the SDK's message can repeat what the service was sent.
            logger.warning("Gemini call failed (attempt %d of %d): %s", attempt, attempts, _reason(status))
            if status is not None and status not in RETRYABLE_STATUSES:
                raise SupplierUnavailable(REFUSED.format(reason=_reason(status)))
        raise SupplierUnavailable(UNREACHABLE.format(attempts=attempts, reason=_reason(status)))

    def _send(self, request: Mapping[str, Any]) -> tuple[Any, int | None, bool]:
        """(the interaction, None, True), or (None, the HTTP status if any, False) when the SDK raised.

        The SDK's error is not chained to ours and not re-raised, so its text reaches no log and no caller.
        Every error the SDK raises for a call carries `status_code`; anything else is a fault of ours and
        is not caught.
        """
        try:
            answer = self._transport.create(
                model=self._model_id, generation_config={"thinking_level": THINKING_LEVEL}, **request
            )
        except Exception as error:
            if not hasattr(error, "status_code"):
                raise
            return None, _status_of(error), False
        return answer, None, True

    def _finished(self, interaction: Any) -> Any:
        status = str(getattr(interaction, "status", ""))
        if status in ANSWERED_STATUSES:
            return interaction
        shown = status if status in UNANSWERED_STATUSES else STATUS_NOT_RECOGNISED
        logger.warning("Gemini interaction ended with status %s", shown)
        raise SupplierUnavailable(NOT_FINISHED.format(status=shown))
