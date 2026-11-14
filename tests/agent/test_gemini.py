"""The Gemini model behind the `AgentModel` interface: `generateContent`, over the real SDK with a mock transport.

No request leaves the machine: `httpx.MockTransport` answers in place of the Gemini API.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import httpx
import pytest
from google.genai import errors

from tta.agent.gemini import DEFAULT_MODEL, MAX_RETRIES, GeminiModel, ModelUnreachable, chosen_model, sdk_transport
from tta.agent.model import AgentModel, ExtractCall, TurnCall
from tta.agent.outage import Outage
from tta.agent.parser import ModelRequestParser
from tta.agent.runner import ModelAgentRunner
from tta.agent.tools import TOOL_DECLARATIONS
from tta.api.wiring import Parts
from tta.config import Settings
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock

KEY = "test-key-7f3a9c1e5b"  # not a real key
SIGNATURE = "c2lnbmF0dXJlLW9uZQ=="  # a thought signature as the API sends it: base64
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object"}}}}
EXTRACT = ExtractCall(system="Read the request.", text="10 litres of milk", schema=SCHEMA)
USER_INPUT = {"type": "user_input", "content": [{"type": "text", "text": "the request"}]}
TURN = TurnCall(
    system="Act through the functions.", request_text="x", history=(USER_INPUT,), tools=TOOL_DECLARATIONS, turn=1
)
USER_CONTENT = {"role": "user", "parts": [{"text": "the request"}]}
Handler = Callable[[httpx.Request], httpx.Response]
MakeParser = Callable[..., ModelRequestParser]


class FakeGemini:
    """Answers like `generateContent` and keeps every request it was sent. The last answer repeats."""

    def __init__(self, *answers: Any) -> None:
        self._answers = list(answers)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer(request)

    @property
    def bodies(self) -> list[dict[str, Any]]:
        return [json.loads(request.content) for request in self.requests]


def _answer(*parts: dict[str, Any], finish: str | None = "STOP") -> Handler:
    candidate: dict[str, Any] = {"content": {"role": "model", "parts": list(parts)}}
    if finish is not None:
        candidate["finishReason"] = finish
    body = {"candidates": [candidate], "modelVersion": DEFAULT_MODEL}
    return lambda request: httpx.Response(200, json=body)


def _text(text: str, **more: Any) -> dict[str, Any]:
    return {"text": text, **more}


def _call(name: str, args: dict[str, Any], *, call_id: str | None = None, signature: str | None = None) -> Any:
    call: dict[str, Any] = {"name": name, "args": args}
    part: dict[str, Any] = {"functionCall": call if call_id is None else {**call, "id": call_id}}
    return part if signature is None else {**part, "thoughtSignature": signature}


def _result(call_id: str, name: str, result: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    """A function result as the runner puts it in the history."""
    step = {"type": "function_result", "name": name, "call_id": call_id,
            "result": [{"type": "text", "text": json.dumps(result)}]}
    return {**step, "is_error": True} if is_error else step


def _error(status: int, message: str = "refused") -> Handler:
    body = {"error": {"code": status, "message": message, "status": "FAILED"}}
    return lambda request: httpx.Response(status, json=body)


def _model(gemini: FakeGemini, **options: Any) -> tuple[GeminiModel, list[float]]:
    """The model as the hooks build it (one retry unless a test sets another count), over the fake service."""
    slept: list[float] = []
    settings = Settings.for_tests(gemini_api_key=KEY)
    transport = sdk_transport(settings, client_args={"transport": httpx.MockTransport(gemini)})
    return GeminiModel(transport, chosen_model(settings), sleep=slept.append, **options), slept


# --- the model that is chosen -----------------------------------------------------------------------------


def test_the_model_is_the_stable_flash_model_unless_the_settings_name_another() -> None:
    assert DEFAULT_MODEL == "gemini-3.6-flash"  # the model that answered the live check on 14 Nov 2026
    assert chosen_model(Settings.for_tests()) == DEFAULT_MODEL
    assert chosen_model(Settings.for_tests(tta_gemini_model="gemini-3.6-flash")) == "gemini-3.6-flash"


def test_a_transport_cannot_be_built_without_a_key() -> None:
    with pytest.raises(SupplierUnavailable):
        sdk_transport(Settings.for_tests())


def test_the_time_out_is_also_the_deadline_the_service_is_given() -> None:
    gemini = FakeGemini(_answer(_text("{}")))
    settings = Settings.for_tests(gemini_api_key=KEY)
    client_args = {"transport": httpx.MockTransport(gemini)}

    GeminiModel(sdk_transport(settings, client_args=client_args), DEFAULT_MODEL).extract(EXTRACT)
    GeminiModel(sdk_transport(settings, client_args=client_args, timeout_seconds=90), DEFAULT_MODEL).extract(EXTRACT)

    # The SDK sends its time-out as the server's deadline: a 504 means the service did not finish in time.
    assert [request.headers["x-server-timeout"] for request in gemini.requests] == ["30", "90"]


# --- structured output ------------------------------------------------------------------------------------


def test_extract_sends_the_schema_the_instruction_and_the_text_to_generate_content() -> None:
    gemini = FakeGemini(_answer(_text("reading the request", thought=True), _text('{"lines": []}')))
    model, _ = _model(gemini)

    answer = model.extract(EXTRACT)

    assert isinstance(model, AgentModel)
    assert (model.model_id, model.recorded, model.label_for("any sentence")) == (DEFAULT_MODEL, False, DEFAULT_MODEL)
    assert answer == '{"lines": []}'  # the model's thought is not part of the answer
    (request,) = gemini.requests
    assert request.url.path == f"/v1/models/{DEFAULT_MODEL}:generateContent"  # the stable version, pinned
    (body,) = gemini.bodies
    assert body["contents"] == [{"role": "user", "parts": [{"text": EXTRACT.text}]}]
    assert body["systemInstruction"]["parts"] == [{"text": EXTRACT.system}]
    config = body["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert config["responseJsonSchema"] == SCHEMA  # sent as written, not converted
    assert list(config["thinkingConfig"].values()) == ["LOW"]
    assert "tools" not in body
    assert request.headers["x-goog-api-key"] == KEY  # the key travels in this header and nowhere else
    assert KEY not in str(request.url) and KEY not in request.content.decode()


def test_an_answer_with_no_text_is_supplier_unavailable() -> None:
    model, _ = _model(FakeGemini(_answer(_text("only a thought", thought=True))))

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert not isinstance(refused.value, ModelUnreachable)  # the model answered: no recording stands in


# --- function calling -------------------------------------------------------------------------------------


def test_next_turn_sends_the_history_and_the_functions_and_returns_the_calls() -> None:
    call = _call("place_order", {"option_id": "opt_1"}, call_id="fc_1", signature=SIGNATURE)
    gemini = FakeGemini(_answer(call))
    model, _ = _model(gemini)

    turn = model.next_turn(TURN)

    (asked,) = turn.calls
    assert (asked.id, asked.name, asked.arguments) == ("fc_1", "place_order", {"option_id": "opt_1"})
    assert turn.text is None
    (step,) = turn.steps
    assert step["type"] == "model_content" and json.loads(json.dumps(step)) == step  # plain JSON, kept as is
    (body,) = gemini.bodies
    assert body["contents"] == [USER_CONTENT]
    assert body["systemInstruction"]["parts"] == [{"text": TURN.system}]
    (tool,) = body["tools"]
    declared = {item["name"]: item for item in tool["functionDeclarations"]}
    assert list(declared) == [str(item["name"]) for item in TOOL_DECLARATIONS]
    assert declared["place_order"]["parameters"] == {  # the OpenAPI form the documentation's examples use
        "type": "OBJECT", "required": ["option_id"],
        "properties": {"option_id": {"type": "STRING", "description": TOOL_DECLARATIONS[2]["parameters"]["properties"][
            "option_id"]["description"]}},
    }
    assert all(set(declared[name]) == {"name", "description"} for name in ("get_authority", "create_offer"))
    assert "responseJsonSchema" not in body.get("generationConfig", {})


def test_automatic_function_calling_is_off_so_one_turn_is_one_request() -> None:
    class Spy:
        def __init__(self, inner: Any) -> None:
            self.inner, self.requests = inner, []

        def create(self, **request: Any) -> Any:
            self.requests.append(request)
            return self.inner.create(**request)

    gemini = FakeGemini(_answer(_call("get_authority", {}, call_id="fc_1", signature=SIGNATURE)))
    settings = Settings.for_tests(gemini_api_key=KEY)
    spy = Spy(sdk_transport(settings, client_args={"transport": httpx.MockTransport(gemini)}))

    GeminiModel(spy, DEFAULT_MODEL).next_turn(TURN)

    (request,) = spy.requests
    assert request["config"].automatic_function_calling.disable is True
    assert len(gemini.requests) == 1


def test_the_next_turn_resends_the_models_parts_unchanged_and_each_result_by_its_call_id() -> None:
    thought = _text("I will read the authority and get an offer.", thought=True)
    first = _call("get_authority", {}, call_id="fc_1", signature=SIGNATURE)
    second = _call("create_offer", {}, call_id="fc_2")  # in parallel calls only the first carries a signature
    gemini = FakeGemini(_answer(thought, first, second), _answer(_text("Done.", thoughtSignature="c2ln")))
    model, _ = _model(gemini)
    turn = model.next_turn(TURN)
    results = (_result("fc_1", "get_authority", {"profile_id": "allergy-ward"}),
               _result("fc_2", "create_offer", {"error": "invalid-request"}, is_error=True))

    model.next_turn(replace(TURN, history=(*TURN.history, *turn.steps, *results), turn=2))

    sent = gemini.bodies[1]["contents"]
    assert sent[0] == USER_CONTENT
    assert sent[1] == {"role": "model", "parts": [thought, first, second]}  # as received, signature and all
    authority = {"id": "fc_1", "name": "get_authority", "response": {"output": {"profile_id": "allergy-ward"}}}
    refused = {"id": "fc_2", "name": "create_offer", "response": {"error": {"error": "invalid-request"}}}
    assert sent[2] == {  # the results of one turn go back together, in the order of the calls
        "role": "user", "parts": [{"functionResponse": authority}, {"functionResponse": refused}],
    }
    assert len(sent) == 3


def test_a_call_without_an_id_gets_one_here_and_its_result_goes_back_without_it() -> None:
    gemini = FakeGemini(_answer(_call("get_authority", {}, signature=SIGNATURE)), _answer(_text("Done.")))
    model, _ = _model(gemini)
    turn = model.next_turn(TURN)
    (asked,) = turn.calls

    model.next_turn(replace(TURN, history=(*TURN.history, *turn.steps, _result(asked.id, asked.name, {})), turn=2))

    assert asked.id  # the runner names every call by an id
    (response,) = gemini.bodies[1]["contents"][2]["parts"]
    assert response == {"functionResponse": {"name": "get_authority", "response": {"output": {}}}}


def test_a_turn_without_a_call_carries_the_models_text() -> None:
    model, _ = _model(FakeGemini(_answer(_text("checking", thought=True), _text("The order is placed."))))

    turn = model.next_turn(TURN)

    assert turn.calls == () and turn.text == "The order is placed."


def test_a_history_step_of_an_unknown_kind_is_a_fault_of_ours() -> None:
    model, _ = _model(FakeGemini(_answer(_text("Done."))))

    with pytest.raises(ValueError):
        model.next_turn(replace(TURN, history=(USER_INPUT, {"type": "something else"})))


# --- an answer that did not finish ------------------------------------------------------------------------


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY", "MALFORMED_FUNCTION_CALL", "MISSING_THOUGHT_SIGNATURE"])
def test_an_answer_that_did_not_finish_is_supplier_unavailable_and_is_not_asked_again(finish: str) -> None:
    gemini = FakeGemini(_answer(_text("{}"), finish=finish))
    model, _ = _model(gemini)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert finish in refused.value.detail and len(gemini.requests) == 1
    assert not isinstance(refused.value, ModelUnreachable)


def test_an_answer_with_no_finish_reason_has_not_finished() -> None:
    model, _ = _model(FakeGemini(_answer(_text("{}"), finish=None)))

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert "not given" in refused.value.detail


@pytest.mark.filterwarnings("ignore:.*is not a valid FinishReason")  # the SDK warns, then keeps the value
def test_a_finish_reason_the_documentation_does_not_list_is_not_repeated_in_the_error() -> None:
    model, _ = _model(FakeGemini(_answer(_text("{}"), finish="SOMETHING_THE_SERVICE_MADE_UP")))

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert "not recognised" in refused.value.detail and "MADE_UP" not in refused.value.detail


def test_a_request_the_service_blocked_has_no_answer_and_is_not_asked_again() -> None:
    blocked = FakeGemini(lambda request: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    model, _ = _model(blocked)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert "no candidate" in refused.value.detail and len(blocked.requests) == 1


# --- time-outs, retries, and a clear error ----------------------------------------------------------------


def test_a_failure_that_may_pass_is_tried_again_once() -> None:
    gemini = FakeGemini(httpx.ReadTimeout("timed out"), _answer(_text("{}")))
    model, slept = _model(gemini)

    answer = model.extract(EXTRACT)

    assert MAX_RETRIES == 1  # one sentence waits for two attempts at most
    assert answer == "{}" and len(gemini.requests) == 2 and len(slept) == 1


def test_with_more_retries_each_wait_is_longer() -> None:
    gemini = FakeGemini(_error(503), httpx.ReadTimeout("timed out"), _answer(_text("{}")))
    model, slept = _model(gemini, max_retries=2)

    assert model.extract(EXTRACT) == "{}" and len(gemini.requests) == 3
    assert len(slept) == 2 and slept[0] < slept[1]


@pytest.mark.parametrize(
    "failure",
    [_error(408), _error(429), _error(500), _error(501), _error(503), _error(504), httpx.ConnectError("no route"),
     httpx.ReadTimeout("timed out")],
    ids=["408", "429", "500", "501", "503", "504", "no-connection", "time-out"],
)
def test_after_one_retry_the_model_cannot_be_reached(failure: Any) -> None:
    gemini = FakeGemini(failure)
    model, slept = _model(gemini)

    with pytest.raises(ModelUnreachable) as refused:
        model.next_turn(TURN)

    assert isinstance(refused.value, SupplierUnavailable)  # still answered as supplier-unavailable
    assert len(gemini.requests) == 2 and len(slept) == 1
    assert "2 attempts" in refused.value.detail
    assert "POST /v1/offers" in refused.value.detail


@pytest.mark.parametrize("status", [400, 404])
def test_a_refusal_that_will_not_pass_is_not_tried_again(status: int) -> None:
    gemini = FakeGemini(_error(status))
    model, slept = _model(gemini)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert len(gemini.requests) == 1 and slept == []
    assert str(status) in refused.value.detail
    assert not isinstance(refused.value, ModelUnreachable)  # refused, not out of reach: no recording stands in


@pytest.mark.parametrize("status", [401, 402, 403])
def test_a_key_or_billing_refusal_makes_the_model_out_of_reach_at_once(status: int) -> None:
    gemini, outage = FakeGemini(_error(status)), Outage()
    model, slept = _model(gemini, outage=outage)

    with pytest.raises(ModelUnreachable) as unavailable:  # a recording or the fixed rules may stand in
        model.extract(EXTRACT)

    assert len(gemini.requests) == 1 and slept == []  # another try cannot change a key or a balance
    assert str(status) in unavailable.value.detail and "POST /v1/offers" in unavailable.value.detail
    assert outage.is_open()  # the next sentences are not sent while it lasts


def test_the_number_of_retries_can_be_set() -> None:
    gemini = FakeGemini(_error(503))
    model, _ = _model(gemini, max_retries=0)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert len(gemini.requests) == 1 and "1 attempts" in refused.value.detail


RAW = "Raw response: <html>secret-looking body</html>"


@pytest.mark.parametrize(
    "error",
    [httpx.DecodingError(RAW), errors.UnknownApiResponseError(RAW), ValueError(RAW), KeyError(RAW)],
    ids=["decoding", "unknown-api-response", "value-error", "key-error"],
)
def test_any_other_exception_of_the_sdk_or_the_transport_is_named_by_its_class_only(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    class Raising:
        calls = 0

        def create(self, **request: Any) -> Any:
            Raising.calls += 1
            raise error

    model = GeminiModel(Raising(), DEFAULT_MODEL, sleep=lambda seconds: None)

    with caplog.at_level(logging.DEBUG), pytest.raises(ModelUnreachable) as refused:
        model.extract(EXTRACT)

    assert type(error).__name__ in refused.value.detail and Raising.calls == 2
    assert "<html>" not in refused.value.detail and "<html>" not in caplog.text
    assert refused.value.__cause__ is None and refused.value.__context__ is None


# --- an outage is remembered (FIX-9) ----------------------------------------------------------------------


def test_once_the_model_could_not_be_reached_it_is_not_asked_again_for_a_while() -> None:
    now = [0.0]
    outage = Outage(clock=lambda: now[0])
    gemini = FakeGemini(_error(503), _error(503), _answer(_text("{}")))
    model, _ = _model(gemini, outage=outage)

    with pytest.raises(ModelUnreachable):
        model.extract(EXTRACT)
    with pytest.raises(ModelUnreachable) as remembered:
        model.next_turn(TURN)
    asked_in_the_window = len(gemini.requests)
    now[0] += outage.seconds

    assert asked_in_the_window == 2 and "not asked again for 120 seconds" in remembered.value.detail
    assert model.extract(EXTRACT) == "{}" and len(gemini.requests) == 3


def test_a_refusal_or_an_unfinished_answer_is_not_an_outage() -> None:
    outage = Outage()
    model, _ = _model(FakeGemini(_error(400), _answer(_text("{}"), finish="MAX_TOKENS")), outage=outage)

    for _ in range(2):
        with pytest.raises(SupplierUnavailable):
            model.extract(EXTRACT)

    assert not outage.is_open()


# --- the key ----------------------------------------------------------------------------------------------


def test_the_key_is_in_no_error_and_no_log_line_even_when_the_service_repeats_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    gemini = FakeGemini(_error(403, f"API key {KEY} is not valid"), _error(503, f"busy, key {KEY}"))
    model, _ = _model(gemini)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(SupplierUnavailable) as refused:
            model.extract(EXTRACT)
        with pytest.raises(SupplierUnavailable) as busy:
            model.extract(EXTRACT)

    for error in (refused.value, busy.value):
        assert KEY not in error.detail and KEY not in json.dumps(error.extensions)
        assert KEY not in repr(error)
        assert error.__cause__ is None and error.__context__ is None  # the SDK's error is not chained
    assert KEY not in caplog.text
    assert "403" in caplog.text  # the failure itself is logged, by its status


def _scenario_2_model(request: httpx.Request) -> httpx.Response:
    """Plays Gemini for one run of scenario 2: structured output first, then one call per turn."""
    body = json.loads(request.content)
    if "responseJsonSchema" in body.get("generationConfig", {}):
        line = {"product_type": "plant_drink", "product_ids": [], "name_terms": [], "required_claims": [],
                "quantity": 200, "unit": "L", "exclude_allergens": ["AM", "AW"], "allergen_strictness": None,
                "pack": None}
        typed = {"needed_by": "2026-11-16", "require_confirmed": True, "lines": [line]}
        return _answer(_text(json.dumps(typed)))(request)
    script = [("get_authority", {}), ("create_offer", {}), ("place_order", {"option_id": "opt_1"})]
    done = sum(1 for content in body["contents"] for part in content["parts"] if "functionResponse" in part)
    if done == len(script):
        return _answer(_text("Ordered.", thoughtSignature="c2ln"))(request)
    name, arguments = script[done]
    return _answer(_call(name, arguments, call_id=f"fc_{done}", signature=SIGNATURE))(request)


def test_the_trace_of_a_run_on_the_gemini_model_never_contains_the_key(
    make_parser: MakeParser, demo_clock: Clock, parts: Parts, agent_ward: Identity, texts: dict[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    gemini = FakeGemini(_scenario_2_model)
    model, _ = _model(gemini)
    runner = ModelAgentRunner(model=model, parser=make_parser(model, demo_clock))

    with caplog.at_level(logging.DEBUG):
        run = runner.run_agent(texts["scenario_2"], agent_ward, parts.service)

    assert run.order_status is OrderStatus.ORDERED
    assert (run.model, run.recorded) == (DEFAULT_MODEL, False)
    assert len(gemini.requests) == 5  # one to read the request, three turns with a call, one closing turn
    assert KEY not in run.model_dump_json()
    assert KEY not in caplog.text
    assert all(KEY not in request.content.decode() for request in gemini.requests)
    audit = parts.service.get_audit(agent_ward)
    assert KEY not in audit.model_dump_json()
    last = gemini.bodies[-1]
    assert [content["role"] for content in last["contents"]] == ["user", *["model", "user"] * 3]
    signed = [part for content in last["contents"] for part in content["parts"] if "thoughtSignature" in part]
    assert [part["thoughtSignature"] for part in signed] == [SIGNATURE] * 3  # every step's signature goes back
    turns = gemini.bodies[1:]
    assert all(body["systemInstruction"] == turns[0]["systemInstruction"] for body in turns)
    instruction = json.dumps(last["systemInstruction"])
    responses = json.dumps([part for content in last["contents"] for part in content["parts"]
                            if "functionResponse" in part])
    assert "Alpro" not in instruction  # a product name reaches the model only inside a function result
    assert "Alpro" in responses
