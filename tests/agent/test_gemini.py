"""The Gemini model behind the `AgentModel` interface, over the real SDK with a mock HTTP transport.

No request leaves the machine: `httpx.MockTransport` answers in place of the Gemini API.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from tta.agent.gemini import DEFAULT_MODEL, GeminiModel, chosen_model, sdk_transport
from tta.agent.model import AgentModel, ExtractCall, TurnCall
from tta.agent.parser import ModelRequestParser
from tta.agent.runner import ModelAgentRunner
from tta.api.wiring import Parts
from tta.config import Settings
from tta.contracts.common import Identity, OrderStatus
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.ports import Clock

KEY = "test-key-7f3a9c1e5b"  # not a real key
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object"}}}}
EXTRACT = ExtractCall(system="Read the request.", text="10 litres of milk", schema=SCHEMA)
TOOLS = ({"type": "function", "name": "get_authority", "description": "Read the authority."},)
USER_INPUT = {"type": "user_input", "content": [{"type": "text", "text": "the request"}]}
TURN = TurnCall(system="Act through the functions.", request_text="x", history=(USER_INPUT,), tools=TOOLS, turn=1)
Handler = Callable[[httpx.Request], httpx.Response]
MakeParser = Callable[..., ModelRequestParser]


class FakeGemini:
    """Answers like the Interactions API and keeps every request it was sent. The last answer repeats."""

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


def _interaction(*steps: dict[str, Any], status: str = "completed") -> Handler:
    body = {"id": "int_1", "status": status, "model": DEFAULT_MODEL, "steps": list(steps)}
    return lambda request: httpx.Response(200, json=body)


def _text(text: str) -> dict[str, Any]:
    return {"type": "model_output", "content": [{"type": "text", "text": text}]}


def _error(status: int, message: str = "refused") -> Handler:
    body = {"error": {"code": status, "message": message, "status": "FAILED"}}
    return lambda request: httpx.Response(status, json=body)


def _model(gemini: FakeGemini, **retries: int) -> tuple[GeminiModel, list[float]]:
    """The model as the hooks build it (two retries unless a test lowers them), over the fake service."""
    slept: list[float] = []
    settings = Settings.for_tests(gemini_api_key=KEY)
    transport = sdk_transport(settings, client_args={"transport": httpx.MockTransport(gemini)})
    return GeminiModel(transport, chosen_model(settings), sleep=slept.append, **retries), slept


# --- the model that is chosen -----------------------------------------------------------------------------


def test_the_model_is_the_stable_flash_model_unless_the_settings_name_another() -> None:
    assert DEFAULT_MODEL == "gemini-3.8-flash"
    assert chosen_model(Settings.for_tests()) == DEFAULT_MODEL
    assert chosen_model(Settings.for_tests(tta_gemini_model="gemini-3.6-flash")) == "gemini-3.6-flash"


def test_a_transport_cannot_be_built_without_a_key() -> None:
    with pytest.raises(SupplierUnavailable):
        sdk_transport(Settings.for_tests())


# --- structured output ------------------------------------------------------------------------------------


def test_extract_sends_the_schema_the_instruction_and_the_text_and_returns_the_json_text() -> None:
    gemini = FakeGemini(_interaction({"type": "thought", "signature": "c2ln"}, _text('{"lines": []}')))
    model, _ = _model(gemini)

    answer = model.extract(EXTRACT)

    assert isinstance(model, AgentModel)
    assert (model.model_id, model.recorded, model.label_for("any sentence")) == (DEFAULT_MODEL, False, DEFAULT_MODEL)
    assert answer == '{"lines": []}'
    (body,) = gemini.bodies
    assert body["model"] == DEFAULT_MODEL
    assert body["store"] is False  # the buyer's text is not kept by the model's provider
    assert body["system_instruction"] == EXTRACT.system
    assert body["input"] == EXTRACT.text
    assert body["response_format"] == {"type": "text", "mime_type": "application/json", "schema": SCHEMA}
    assert body["generation_config"] == {"thinking_level": "low"}
    assert "tools" not in body
    (request,) = gemini.requests
    assert request.headers["x-goog-api-key"] == KEY  # the key travels in this header and nowhere else
    assert KEY not in str(request.url) and KEY not in request.content.decode()


def test_an_answer_with_no_text_is_supplier_unavailable() -> None:
    model, _ = _model(FakeGemini(_interaction({"type": "thought", "signature": "c2ln"})))

    with pytest.raises(SupplierUnavailable):
        model.extract(EXTRACT)


# --- function calling -------------------------------------------------------------------------------------


def test_next_turn_sends_history_and_functions_and_returns_the_calls_with_the_steps_as_received() -> None:
    thought = {"type": "thought", "signature": "c2lnbmF0dXJl"}
    call = {"type": "function_call", "id": "fc_1", "name": "place_order", "arguments": {"option_id": "opt_1"}}
    gemini = FakeGemini(_interaction(thought, call, status="requires_action"))
    model, _ = _model(gemini)

    turn = model.next_turn(TURN)

    (asked,) = turn.calls
    assert (asked.id, asked.name, asked.arguments) == ("fc_1", "place_order", {"option_id": "opt_1"})
    assert list(turn.steps) == [thought, call]  # sent back unchanged: the thought step carries the signature
    assert turn.text is None
    (body,) = gemini.bodies
    assert body["input"] == [USER_INPUT] and body["tools"] == list(TOOLS)
    assert body["system_instruction"] == TURN.system and body["store"] is False
    assert "response_format" not in body


def test_a_turn_without_a_call_carries_the_models_text() -> None:
    model, _ = _model(FakeGemini(_interaction(_text("The order is placed."))))

    turn = model.next_turn(TURN)

    assert turn.calls == () and turn.text == "The order is placed."


@pytest.mark.parametrize("status", ["failed", "incomplete", "requires_continuation", "cancelled"])
def test_an_interaction_that_did_not_finish_is_supplier_unavailable_and_is_not_asked_again(status: str) -> None:
    gemini = FakeGemini(_interaction(_text("{}"), status=status))
    model, _ = _model(gemini)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert status in refused.value.detail and len(gemini.requests) == 1


def test_a_status_the_documentation_does_not_list_is_not_repeated_in_the_error() -> None:
    model, _ = _model(FakeGemini(_interaction(_text("{}"), status="something the service made up")))

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert "not recognised" in refused.value.detail and "made up" not in refused.value.detail


# --- time-outs, retries, and a clear error ----------------------------------------------------------------


def test_a_failure_that_may_pass_is_tried_again_twice() -> None:
    gemini = FakeGemini(_error(503), httpx.ReadTimeout("timed out"), _interaction(_text("{}")))
    model, slept = _model(gemini)

    answer = model.extract(EXTRACT)

    assert answer == "{}" and len(gemini.requests) == 3
    assert len(slept) == 2 and slept[0] < slept[1]  # waits longer before the second retry


@pytest.mark.parametrize("failure", [_error(429), _error(500), httpx.ConnectError("no route"),
                                     httpx.ReadTimeout("timed out")])
def test_after_two_retries_the_model_is_supplier_unavailable(failure: Any) -> None:
    gemini = FakeGemini(failure)
    model, slept = _model(gemini)

    with pytest.raises(SupplierUnavailable) as refused:
        model.next_turn(TURN)

    assert len(gemini.requests) == 3 and len(slept) == 2
    assert "3 attempts" in refused.value.detail
    assert "POST /v1/offers" in refused.value.detail


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_refusal_that_will_not_pass_is_not_tried_again(status: int) -> None:
    gemini = FakeGemini(_error(status))
    model, slept = _model(gemini)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert len(gemini.requests) == 1 and slept == []
    assert str(status) in refused.value.detail


def test_the_number_of_retries_can_be_lowered() -> None:
    gemini = FakeGemini(_error(503))
    model, _ = _model(gemini, max_retries=1)

    with pytest.raises(SupplierUnavailable) as refused:
        model.extract(EXTRACT)

    assert len(gemini.requests) == 2 and "2 attempts" in refused.value.detail


def test_a_fault_that_is_not_the_models_is_not_hidden() -> None:
    class Broken:
        def create(self, **request: Any) -> Any:
            raise KeyError("a fault of ours")

    model = GeminiModel(Broken(), DEFAULT_MODEL)

    with pytest.raises(KeyError):
        model.extract(EXTRACT)


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
    if "response_format" in body:
        line = {"product_type": "plant_drink", "product_ids": [], "name_terms": [], "required_claims": [],
                "quantity": 200, "unit": "L", "exclude_allergens": ["AM", "AW"], "allergen_strictness": None,
                "pack": None}
        typed = {"needed_by": "2026-11-16", "require_confirmed": True, "lines": [line]}
        return _interaction(_text(json.dumps(typed)))(request)
    script = [("get_authority", {}), ("create_offer", {}), ("place_order", {"option_id": "opt_1"})]
    done = sum(1 for step in body["input"] if step["type"] == "function_result")
    if done == len(script):
        return _interaction(_text("Ordered."))(request)
    name, arguments = script[done]
    call = {"type": "function_call", "id": f"fc_{done}", "name": name, "arguments": arguments}
    return _interaction({"type": "thought", "signature": "c2ln"}, call, status="requires_action")(request)


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
    assert [step["type"] for step in last["input"]][:3] == ["user_input", "thought", "function_call"]
    assert all(body["system_instruction"] == gemini.bodies[1]["system_instruction"] for body in gemini.bodies[1:])
    assert "Alpro" not in last["system_instruction"]  # a product name reaches the model only inside a function result
    assert "Alpro" in json.dumps([step for step in last["input"] if step["type"] == "function_result"])
