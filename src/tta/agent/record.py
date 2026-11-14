"""The live check of task T10: ask the real model once and save its answers as the recorded fixtures.

Run it with `.venv/bin/python -m tta.agent.record`. It needs `GEMINI_API_KEY` (read through `tta.config`,
never printed). It reads the two scenario sentences, the sentence with no quantity and the two Finnish sentences,
runs scenario 2 once, and transcribes and reads the demo photo (`--only photo`, task T18), against a gateway in
replay with a database of its own in a temporary folder: nothing reaches the real order book or the live
supplier API. A photo is recorded as two files: `transcribe-photo.json` (the lines read, named by the photo's
SHA-256) and `parse-photo.json` (the reading of those lines). Replacing the photo means recording it again.
Every request to the model is counted and the run stops at `--max-calls`. A recording that holds a secret is
not written.

Only answers that validated are written (task FIX-9): an `invalid-request` for a fact the text does not give
is a valid answer and is written; one for an answer that did not validate twice is not. A run that ended
because the model stopped answering is never written. Each recording names the buyer profile it was made for.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from tta.agent import profile_strictness
from tta.agent.days import helsinki_date
from tta.agent.gemini import REQUEST_TIMEOUT_SECONDS, ContentTransport, GeminiModel, chosen_model, sdk_transport
from tta.agent.images import checked_image
from tta.agent.model import AgentModel, AnswerSource, ExtractCall, ModelTurn, TranscribeCall, TurnCall
from tta.agent.parser import ModelRequestParser
from tta.agent.recorded import (
    AGENT_FIXTURES_FOLDER,
    LINE_BREAK,
    LIVE_SOURCE,
    RecordedCall,
    RecordedTurn,
    Recording,
    text_key,
)
from tta.agent.runner import ModelAgentRunner
from tta.config import Settings, get_settings
from tta.contracts.common import Identity, IdentityKind
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.ports import AgentRunner, GatewayService, RequestParser

MAX_LIVE_CALLS = 20  # the most requests one live check may send to the model (task T10)
LIVE_CHECK_RETRIES = 1  # two attempts at most for a call that fails (AIMO/build/AGENT-RULES.md, rule 10)
EXIT_OK, EXIT_FAILED, EXIT_NO_KEY = 0, 1, 2
Kind = Literal["parse", "run"]
TaskKind = Literal["parse", "run", "photo"]
PHOTO_KINDS = ("transcribe", "parse")  # the two recordings of a photo, in the order they are made

logger = logging.getLogger(__name__)


class CallBudgetSpent(RuntimeError):
    """The live check reached the number of model requests it may send."""


class SecretInRecording(RuntimeError):
    """A recording holds a secret and was not written."""


@dataclass(frozen=True)
class Task:
    """One sentence of the live check. A run is recorded together with its reading of the sentence; a photo is
    named by its path under `fixtures/agent/` and recorded with the reading of the lines read in it."""

    name: str
    kind: TaskKind
    profile_id: str
    text: str


PLAN: tuple[Task, ...] = (
    Task("scenario-1", "parse", "hotel-kitchen", "1,000 litres of lactose-free milk by Monday"),
    Task("scenario-2", "run", "allergy-ward",
         "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"),
    Task("no-quantity", "parse", "hotel-kitchen", "Some milk for Monday"),
    Task("finnish-1", "parse", "hotel-kitchen", "1000 litraa laktoositonta maitoa maanantaiksi"),
    Task("finnish-2", "parse", "allergy-ward",
         "200 litraa maidotonta ja gluteenitonta kasvijuomaa maanantaiksi, vain vahvistetut tiedot"),
    Task("photo", "photo", "hotel-kitchen", "photos/order-list.png"),
)


class CallBudget:
    """A transport that counts every request sent to the model and refuses the one beyond the budget."""

    def __init__(self, transport: ContentTransport, max_calls: int) -> None:
        self._transport = transport
        self._max_calls = max_calls
        self._calls = 0

    @property
    def calls(self) -> int:
        return self._calls

    def create(self, **request: Any) -> Any:
        if self._calls >= self._max_calls:
            raise CallBudgetSpent(f"The live check may send {self._max_calls} requests to the model and has sent them.")
        self._calls += 1
        return self._transport.create(**request)


class RecordingModel:
    """Passes every call on to a model and keeps its answers, by sentence. Implements `AgentModel`."""

    def __init__(self, inner: AgentModel) -> None:
        self._inner = inner
        self._answers: dict[str, str] = {}
        self._transcriptions: dict[str, str] = {}  # by the SHA-256 of the photo
        self._turns: dict[str, list[ModelTurn]] = {}
        self._stopped: set[str] = set()  # sentences whose run the model stopped answering

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    @property
    def recorded(self) -> bool:
        return self._inner.recorded

    def label_for(self, request_text: str) -> str:
        return self._inner.label_for(request_text)

    def answer_source(self, request_text: str) -> AnswerSource:
        return self._inner.answer_source(request_text)

    def extract(self, call: ExtractCall) -> str:
        answer = self._inner.extract(call)
        self._answers[text_key(call.text)] = answer  # after a second answer, the one that was used
        return answer

    def transcribe(self, call: TranscribeCall) -> str:
        answer = self._inner.transcribe(call)  # type: ignore[attr-defined]  # a model that cannot is refused
        self._transcriptions[call.digest] = answer
        return answer

    def transcription_source(self, digest: str) -> AnswerSource:
        return self._inner.transcription_source(digest)  # type: ignore[attr-defined]

    def next_turn(self, call: TurnCall) -> ModelTurn:
        key = text_key(call.request_text)
        try:
            turn = self._inner.next_turn(call)
        except Exception:
            self._stopped.add(key)
            raise
        self._turns.setdefault(key, []).append(turn)
        return turn

    def stopped(self, text: str) -> bool:
        """True when the model stopped answering during the run of this sentence."""
        return text_key(text) in self._stopped

    def recording(
        self, kind: Kind, text: str, *, profile_id: str, today: date, recorded_at: datetime, note: str | None = None
    ) -> Recording:
        """What the model answered for this sentence. Raises `KeyError` when it was never asked."""
        common = {"kind": kind, "text": text, "profile_id": profile_id, "model": self.model_id,
                  "source": LIVE_SOURCE, "recorded_at": recorded_at, "today": today, "note": note}
        if kind == "parse":
            return Recording(**common, proposal=_as_object(self._answers[text_key(text)]))
        turns = tuple(
            RecordedTurn(
                calls=tuple(RecordedCall(name=call.name, arguments=call.arguments) for call in turn.calls),
                text=turn.text,
            )
            for turn in self._turns[text_key(text)]
        )
        return Recording(**common, turns=turns)


    def photo_recording(
        self, digest: str, *, profile_id: str, today: date, recorded_at: datetime
    ) -> Recording:
        """The lines the model read in the photo with this SHA-256. Raises `KeyError` when it was never shown it."""
        lines = _as_object(self._transcriptions[digest]).get("lines")
        if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
            raise KeyError(digest)  # an answer that did not validate is never written
        return Recording(
            kind="transcribe", text=LINE_BREAK.join(line.strip() for line in lines if line.strip()),
            profile_id=profile_id, model=self.model_id, source=LIVE_SOURCE, recorded_at=recorded_at, today=today,
            image_sha256=digest,
        )


def _as_object(answer: str) -> dict[str, Any]:
    """The answer as the JSON object it should be; an answer that is not one is kept as it came."""
    try:
        data = json.loads(answer)
    except ValueError:
        return {"unreadable": answer}
    return data if isinstance(data, dict) else {"unreadable": answer}


def write_recording(directory: Path, name: str, recording: Recording, *, secrets: Sequence[str]) -> Path:
    """Write `<name>.json`. Raises `SecretInRecording`, and writes nothing, when the content holds a secret."""
    content = json.dumps(recording.model_dump(mode="json", exclude_none=True), indent=2, ensure_ascii=False) + "\n"
    if any(secret and secret in content for secret in secrets):
        raise SecretInRecording(f"{name}.json would hold a secret and was not written.")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(content, encoding="utf-8")
    return path


@dataclass(frozen=True)
class Recorder:
    """Carries out tasks of the live check and writes what the model answered."""

    live: RecordingModel
    parser: RequestParser
    runner: AgentRunner
    gateway: GatewayService
    directory: Path
    secrets: tuple[str, ...]
    today: date  # the date of the data clock the answers are given for

    def record(self, task: Task) -> tuple[Path, ...]:
        """Writes what validated; returns the files written, none when the answer did not validate."""
        if task.kind == "photo":
            return self._record_photo(task)
        kinds = self._carry_out(task)
        now = datetime.now(UTC)
        return tuple(
            write_recording(
                self.directory, f"{kind}-{task.name}",
                self.live.recording(kind, task.text, profile_id=task.profile_id, today=self.today, recorded_at=now),
                secrets=self.secrets,
            )
            for kind in kinds
        )

    def _record_photo(self, task: Task) -> tuple[Path, ...]:
        """The transcription of the photo and the reading of its lines, when both are answers to keep."""
        image = (self.directory / task.text).read_bytes()
        digest = hashlib.sha256(image).hexdigest()
        try:
            read_image = self.parser.read_image  # type: ignore[attr-defined]  # `ModelRequestParser.read_image`
            lines, _ = read_image(image, checked_image(image).media_type, _identity(task))
        except InvalidRequest as refused:
            if refused.extensions.get("faults") or "transcription" in refused.extensions.get("missing", ()):
                logger.warning("%s: not recorded, the photo gave no lines to keep: %s", task.name, refused.detail)
                return ()
            logger.info("%s: invalid-request: %s", task.name, refused.detail)  # a missing fact: a valid answer
        now = datetime.now(UTC)
        transcription = self.live.photo_recording(digest, profile_id=task.profile_id, today=self.today, recorded_at=now)
        reading = self.live.recording("parse", transcription.text, profile_id=task.profile_id, today=self.today,
                                      recorded_at=now)
        return tuple(
            write_recording(self.directory, f"{kind}-{task.name}", recording, secrets=self.secrets)
            for kind, recording in zip(PHOTO_KINDS, (transcription, reading), strict=True)
        )

    def _carry_out(self, task: Task) -> tuple[Kind, ...]:
        """The kinds of recording that may be written for this task once it was carried out."""
        identity = _identity(task)
        try:
            if task.kind == "parse":
                logger.info("%s: %s", task.name, self.parser.parse_request(task.text, identity).model_dump_json())
                return ("parse",)
            run = self.runner.run_agent(task.text, identity, self.gateway)
            logger.info("%s: %s", task.name, run.model_dump_json(include={"steps", "report", "order_status"}))
        except InvalidRequest as refused:
            if refused.extensions.get("faults"):  # the answer did not validate twice: not an answer to keep
                logger.warning("%s: not recorded, the answer did not validate: %s", task.name, refused.detail)
                return ()
            logger.info("%s: invalid-request: %s", task.name, refused.detail)  # a missing fact: a valid answer
            return ("parse",)
        if self.live.stopped(task.text):
            logger.warning("%s: the run is not recorded, the model stopped answering", task.name)
            return ("parse",)
        return ("parse", "run")


def _identity(task: Task) -> Identity:
    return Identity(
        kind=IdentityKind.AGENT, id=f"agent:{task.profile_id}", display_name=f"{task.profile_id} agent",
        profile_id=task.profile_id,
    )


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record the Gemini model's answers for the demonstration sentences.")
    parser.add_argument("--max-calls", type=int, default=MAX_LIVE_CALLS, help="requests to the model, at most")
    parser.add_argument("--only", action="append", choices=[task.name for task in PLAN], help="one task of the plan")
    parser.add_argument("--timeout", type=float, default=REQUEST_TIMEOUT_SECONDS,
                        help="seconds the model has for each request; the gateway always gives it the default")
    return parser.parse_args(argv)


def _secrets(settings: Settings) -> tuple[str, ...]:
    held = (settings.gemini_api_key, settings.valio_aimo_api_key)
    return tuple(secret.get_secret_value() for secret in held if secret is not None)


def _record_all(settings: Settings, tasks: Sequence[Task], budget: CallBudget) -> int:
    # Imported here: the gateway imports this package through its hooks, not the other way round.
    from tta.api.wiring import build_parts

    live = RecordingModel(GeminiModel(budget, chosen_model(settings), max_retries=LIVE_CHECK_RETRIES))
    with tempfile.TemporaryDirectory() as scratch:
        # Settings that carry no secret and read no `.env`: the gateway of the live check is the replay one.
        replay = Settings.for_tests(tta_data_dir=Path(scratch), tta_replay_capture=settings.tta_replay_capture)
        parts = build_parts(replay)
        try:
            parser = ModelRequestParser(
                model=live, clock=parts.clock, product_type_keys=parts.catalog.product_type_keys(),
                profile_strictness=profile_strictness(),
            )
            recorder = Recorder(
                live=live, parser=parser, runner=ModelAgentRunner(model=live, parser=parser), gateway=parts.service,
                directory=settings.tta_fixtures_dir / AGENT_FIXTURES_FOLDER, secrets=_secrets(settings),
                today=helsinki_date(parts.clock.now()),
            )
            for task in tasks:
                for path in recorder.record(task):
                    logger.info("wrote %s", path)
        except (SupplierUnavailable, CallBudgetSpent, SecretInRecording) as stopped:
            logger.error("The live check stopped: %s", stopped)
            return EXIT_FAILED
        finally:
            parts.close()
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    arguments = _arguments(argv)
    settings = get_settings()
    if not settings.has_gemini_key:
        logger.error("GEMINI_API_KEY is not set: nothing was called and nothing was recorded.")
        return EXIT_NO_KEY
    tasks = [task for task in PLAN if not arguments.only or task.name in arguments.only]
    budget = CallBudget(sdk_transport(settings, timeout_seconds=arguments.timeout), arguments.max_calls)
    try:
        return _record_all(settings, tasks, budget)
    finally:
        logger.info("Requests sent to the model: %d of at most %d.", budget.calls, arguments.max_calls)


if __name__ == "__main__":
    raise SystemExit(main())
