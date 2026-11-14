"""The Gemini model behind the `AgentModel` interface (SPEC section 11; task T10).

Written from the Gemini API documentation as read on 14 Nov 2026 (https://aistudio.google.com/docs, the pages
marked "(generateContent)": "Structured outputs", "Function calling", "Thought signatures", "Thinking"; the
v1 reference of `generateContent`; "API versions"; "API troubleshooting") and from the installed
`google-genai` 3.3.0:
- `generateContent` (`client.models.generate_content`), not the Interactions API: on 14 Nov 2026 the
  Interactions endpoint answered 503 to every request with the team's key, while `generateContent` with the
  same key and SDK answered (orchestrator's probe, 07:50). The documentation calls `generateContent` legacy
  and "fully supported". The SDK calls the stable `v1`, which has function calling, structured output,
  thinking and system instructions; it is pinned here so an environment variable cannot change it.
- Structured output: `response_mime_type` `application/json` with `response_json_schema`, the JSON Schema
  sent as written.
- A photo (task T18; "Image understanding (generateContent)"): the image as inline data
  (`types.Part.from_bytes`), then the words that ask for the transcription, as the page advises ("place the text
  prompt after the image part"); the answer held to a JSON Schema as above. A request with inline image data is
  at most 20 MB in all; a photo is at most 5 MB here (`tta.agent.images`). The media resolution is left at its
  default, which the "Media resolution (generateContent)" page gives as 1,120 tokens an image for Gemini 3, the
  same as `MEDIA_RESOLUTION_HIGH`.
- Function calling: the declarations in one `Tool`, automatic function calling off, so one request is one
  model call and every function is made by the runner. The whole history is sent on every turn, with the
  model's own `Content` unchanged: its thought signatures must come back where they were received
  (`tta.agent.contents`).
- The SDK does not retry (one attempt); this module retries by its own count, so the number of calls is
  always known: one retry, so one sentence waits for two attempts at most (task FIX-9).
- Every exception of the SDK or of the HTTP client becomes this module's own error, named by its HTTP status
  or by the exception's class name only. After a failure for unreachability the model refuses at once for a
  while (`tta.agent.outage`).

The key is read from the settings, handed to the SDK and kept nowhere else. No error and no log line of this
module carries the SDK's error text, which could repeat what the service was sent.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from google import genai
from google.genai import errors, types

from tta.agent.contents import function_tool, model_step, to_contents
from tta.agent.model import (
    AnswerSource,
    ExtractCall,
    FunctionCall,
    ModelTurn,
    ModelUnreachable,
    TranscribeCall,
    TurnCall,
)
from tta.agent.outage import Outage
from tta.config import Settings
from tta.contracts.agent import ReadingSource
from tta.contracts.errors import SupplierUnavailable

# Chosen from the documentation's model list: the newest Flash model marked stable, with structured
# outputs and function calling both supported, and one the team's key lists (task T10).
# 14 Nov 2026: gemini-3.8-flash answered 504 to every request of the live check (30 s and 120 s deadlines) while
# gemini-3.6-flash, also documented as stable with function calling and structured output, answered. Override
# with TTA_GEMINI_MODEL.
DEFAULT_MODEL = "gemini-3.6-flash"
API_VERSION = "v1"  # the stable version ("API versions"); the SDK's default, pinned
# "low" is the lowest level this model supports; the documentation recommends it for latency-sensitive
# work. Reading one sentence and choosing among four functions needs no more.
THINKING_LEVEL = "low"
REQUEST_TIMEOUT_SECONDS = 30.0
MILLISECONDS_PER_SECOND = 1000
MAX_RETRIES = 1  # one sentence waits for two attempts at most (task FIX-9)
RETRY_WAIT_SECONDS = 0.5  # doubled before each further retry
SDK_ATTEMPTS = 1  # the SDK does not retry: this module does, and counts
# The documentation's troubleshooting page: retry 408, 429 and 5xx; never 400, 402 or 403.
RETRYABLE_STATUSES = frozenset({408, 429})
SERVER_ERRORS = range(500, 600)
# A key, billing or permission refusal (unauthenticated, payment required, forbidden): another try cannot change
# it, but the model is then out of reach for this gateway, so a recording or the fixed rules may stand in. Seen
# as a risk on 14 Nov 2026, when the key's balance was zero. 400 and 404 stay refusals: they point at our call.
NOT_AVAILABLE_TO_US = frozenset({401, 402, 403})
FINISHED = types.FinishReason.STOP  # "natural stop point of the model"; an empty reason means it has not stopped
JSON_MIME_TYPE = "application/json"
LOCAL_CALL_ID = "gemini-{turn}-{number}"  # for a call the model gave no id

NO_KEY = "No GEMINI_API_KEY is set, so the Gemini model cannot be called."
USE_THE_TYPED_REQUEST = "Send the typed request to POST /v1/offers instead."
UNREACHABLE = "The language model did not answer after {attempts} attempts ({reason}). " + USE_THE_TYPED_REQUEST
REFUSED = "The language model refused the call ({reason}). " + USE_THE_TYPED_REQUEST
NOT_AVAILABLE = (
    "The language model is not available to this gateway ({reason}: the key, its billing or its permissions). "
    + USE_THE_TYPED_REQUEST
)
NOT_FINISHED = "The language model did not finish its answer (finish reason {reason}). " + USE_THE_TYPED_REQUEST
NO_TEXT = "The language model returned no text to read. " + USE_THE_TYPED_REQUEST
REMEMBERED = (
    "The language model did not answer a moment ago, so it is not asked again for {seconds:.0f} seconds. "
    + USE_THE_TYPED_REQUEST
)
NO_RESPONSE = "no response: a time-out or a connection failure"
NO_USABLE_RESPONSE = "no usable response: {name}"
HTTP_STATUS = "HTTP status {status}"
NO_CANDIDATE = "none: no candidate was returned"
NOT_GIVEN = "not given"
NOT_RECOGNISED = "not recognised"

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_MODEL", "GeminiModel", "ModelUnreachable", "chosen_model", "sdk_transport"]


class ContentTransport(Protocol):
    """Sends one `generateContent` request. `GeminiModel` talks to nothing else."""

    def create(self, **request: Any) -> Any: ...


class _SdkTransport:
    """The SDK client. It is kept here for as long as the transport lives: a client that is no longer
    referenced closes its connection pool, and a later call then fails."""

    def __init__(self, client: genai.Client) -> None:
        self._client = client

    def create(self, **request: Any) -> Any:
        return self._client.models.generate_content(**request)


def chosen_model(settings: Settings) -> str:
    """The model id: `TTA_GEMINI_MODEL` when set, otherwise the default."""
    return settings.tta_gemini_model or DEFAULT_MODEL


def sdk_transport(
    settings: Settings,
    *,
    client_args: Mapping[str, Any] | None = None,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
) -> ContentTransport:
    """The real transport. `client_args` are passed to the SDK's HTTP client (a test passes a mock transport).
    The SDK also sends the time-out to the service as its deadline (`X-Server-Timeout`): past it, a 504.

    Raises `SupplierUnavailable` when no key is set. Building it sends nothing.
    """
    if settings.gemini_api_key is None or not settings.has_gemini_key:
        raise SupplierUnavailable(NO_KEY)
    options = types.HttpOptions(
        api_version=API_VERSION,
        timeout=int(timeout_seconds * MILLISECONDS_PER_SECOND),
        retry_options=types.HttpRetryOptions(attempts=SDK_ATTEMPTS),
        client_args=dict(client_args) if client_args else None,
    )
    return _SdkTransport(genai.Client(api_key=settings.gemini_api_key.get_secret_value(), http_options=options))


@dataclass(frozen=True)
class _Failure:
    """Why one attempt got no answer, in words that never repeat the SDK's text."""

    status: int | None = None
    error_class: str | None = None

    @property
    def reason(self) -> str:
        if self.status is not None:
            return HTTP_STATUS.format(status=self.status)
        return NO_RESPONSE if self.error_class is None else NO_USABLE_RESPONSE.format(name=self.error_class)

    @property
    def may_pass(self) -> bool:
        """No answer or no usable one, a time-out (408), too many requests (429) or a server error."""
        return self.status is None or self.status in RETRYABLE_STATUSES or self.status in SERVER_ERRORS


def _config(system: str, **more: Any) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system,
        thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **more,
    )


def _finish_reason(candidate: Any) -> str:
    """The finish reason as the error may repeat it: a name the API reference lists, or a fixed word."""
    reason = getattr(candidate, "finish_reason", None)
    if reason is None:
        return NOT_GIVEN
    name = getattr(reason, "name", None)
    return name if name in types.FinishReason.__members__ else NOT_RECOGNISED


def _text_of(content: types.Content) -> str | None:
    """The model's words, without its thoughts."""
    text = "".join(part.text for part in content.parts or () if part.text and not part.thought)
    return text if text.strip() else None


def _calls_of(content: types.Content, turn: int) -> tuple[FunctionCall, ...]:
    calls = [part.function_call for part in content.parts or () if part.function_call is not None]
    return tuple(
        FunctionCall(
            id=call.id or LOCAL_CALL_ID.format(turn=turn, number=number), name=call.name or "",
            arguments=dict(call.args or {}),
        )
        for number, call in enumerate(calls, start=1)
    )


class GeminiModel:
    """Implements `AgentModel` and `ImageModel` over `generateContent`."""

    def __init__(
        self,
        transport: ContentTransport,
        model_id: str,
        *,
        max_retries: int = MAX_RETRIES,
        sleep: Callable[[float], None] = time.sleep,
        outage: Outage | None = None,
    ) -> None:
        """`outage`: where a failure for unreachability is remembered; `None` asks the model every time."""
        self._transport = transport
        self._model_id = model_id
        self._max_retries = max_retries
        self._sleep = sleep
        self._outage = outage

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def recorded(self) -> bool:
        return False

    def label_for(self, request_text: str) -> str:
        return self._model_id

    def answer_source(self, request_text: str) -> AnswerSource:
        return AnswerSource(ReadingSource.MODEL, self._model_id)

    def extract(self, call: ExtractCall) -> str:
        config = _config(call.system, response_mime_type=JSON_MIME_TYPE, response_json_schema=call.schema)
        text = _text_of(self._answer(contents=call.text, config=config))
        if text is None:
            raise SupplierUnavailable(NO_TEXT)
        return text

    def transcribe(self, call: TranscribeCall) -> str:
        """The JSON text of the lines the photo holds. The image goes as inline data; nothing of it is logged."""
        config = _config(call.system, response_mime_type=JSON_MIME_TYPE, response_json_schema=call.schema)
        contents = [types.Part.from_bytes(data=call.image, mime_type=call.media_type), call.request]
        text = _text_of(self._answer(contents=contents, config=config))
        if text is None:
            raise SupplierUnavailable(NO_TEXT)
        return text

    def transcription_source(self, digest: str) -> AnswerSource:
        return AnswerSource(ReadingSource.MODEL, self._model_id)

    def next_turn(self, call: TurnCall) -> ModelTurn:
        config = _config(call.system, tools=[function_tool(call.tools)])
        content = self._answer(contents=to_contents(call.history), config=config)
        return ModelTurn(steps=(model_step(content),), calls=_calls_of(content, call.turn), text=_text_of(content))

    def _answer(self, **request: Any) -> types.Content:
        """The content of one finished answer. Raises `ModelUnreachable` after the retries, or at once while a
        recent failure is remembered; `SupplierUnavailable` at once for a refusal or an answer that another try
        cannot change."""
        if self._outage is not None and self._outage.is_open():
            raise ModelUnreachable(REMEMBERED.format(seconds=self._outage.seconds))
        attempts = self._max_retries + 1
        failure = _Failure()
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                self._sleep(RETRY_WAIT_SECONDS * 2 ** (attempt - 2))
            response, failure = self._send(request)
            if failure is None:
                return self._finished(response)
            # Logged by its HTTP status or class name only: the SDK's message can repeat what it was sent.
            logger.warning("Gemini call failed (attempt %d of %d): %s", attempt, attempts, failure.reason)
            if failure.status in NOT_AVAILABLE_TO_US:
                if self._outage is not None:
                    self._outage.note()
                raise ModelUnreachable(NOT_AVAILABLE.format(reason=failure.reason))
            if not failure.may_pass:
                raise SupplierUnavailable(REFUSED.format(reason=failure.reason))
        if self._outage is not None:
            self._outage.note()
        raise ModelUnreachable(UNREACHABLE.format(attempts=attempts, reason=failure.reason))

    def _send(self, request: Mapping[str, Any]) -> tuple[Any, _Failure | None]:
        """(the response, None), or (None, why) when the SDK or the HTTP client raised.

        Every exception becomes a `_Failure`: an `APIError` by its HTTP status; no answer at all (the HTTP
        client's `TransportError`) or an answer that could not be read (a decoding error, the SDK's
        `UnknownApiResponseError`, anything else it raises) by the exception's class name. The exception is
        not chained and not re-raised, so its text reaches no log and no caller.
        """
        try:
            response = self._transport.create(model=self._model_id, **request)
        except errors.APIError as error:
            return None, _Failure(status=error.code if isinstance(error.code, int) else None)
        except httpx.TransportError:
            return None, _Failure()
        except Exception as error:  # see above: named by its class, never by its text
            return None, _Failure(error_class=type(error).__name__)
        return response, None

    def _finished(self, response: Any) -> types.Content:
        candidates = getattr(response, "candidates", None) or ()
        candidate = candidates[0] if candidates else None
        reason = NO_CANDIDATE if candidate is None else _finish_reason(candidate)
        content = getattr(candidate, "content", None)
        if candidate is None or candidate.finish_reason != FINISHED or content is None:
            logger.warning("Gemini answer did not finish (finish reason %s)", reason)
            raise SupplierUnavailable(NOT_FINISHED.format(reason=reason))
        return content
