"""`run_request` and the run log against a stub of the service: the branches replay data cannot reach."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tta.contracts.agent import AgentRun
from tta.contracts.common import AllergenStrictness, Identity, IdentityKind, Unit
from tta.contracts.errors import (
    InvalidRequest,
    NotFound,
    OfferStale,
    PolicyBlocked,
    RateLimited,
    SupplierUnavailable,
    TtaError,
)
from tta.ui.examples import EXAMPLES, example_by_key, example_for_text
from tta.ui.run import (
    ReadBy,
    RunLog,
    RunLogs,
    RunRecord,
    Substitutes,
    look_up_substitutes,
    order_key,
    run_request,
)

READ_BY_STUB = "Read by stub-model-1."
NO_MODEL_ASKED = "No model was asked"
AGENT = Identity(kind=IdentityKind.AGENT, id="agent:hotel-kitchen", display_name="Agent", profile_id="hotel-kitchen")
SCENARIO_2 = example_by_key("scenario-2")
OFFER = SimpleNamespace(offer_id="off_1", options=(SimpleNamespace(option_id="opt_1"),))
EMPTY_OFFER = SimpleNamespace(offer_id="off_2", options=())
ORDER = SimpleNamespace(order_id="ord_1")


class StubService:
    """Answers what a test sets; an exception set in place of an answer is raised. `read_request` answers a
    reading of the typed request set for it."""

    def __init__(self, **answers: Any) -> None:
        self.answers = {"create_offer": OFFER, "place_order": ORDER, **answers}
        self.has_agent_runner = "run_agent" in answers
        self.has_request_parser = "read_request" in answers
        self.calls: list[str] = []

    def _answer(self, name: str) -> Any:
        self.calls.append(name)
        answer = self.answers[name]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def run_agent(self, identity: Identity, text: str) -> Any:
        return self._answer("run_agent")

    def read_request(self, identity: Identity, text: str) -> Any:
        return SimpleNamespace(request=self._answer("read_request"), sentence=READ_BY_STUB)

    def create_offer(self, identity: Identity, request: Any) -> Any:
        self.requested = request
        return self._answer("create_offer")

    def get_offer(self, identity: Identity, offer_id: str) -> Any:
        return self._answer("get_offer")

    def place_order(self, identity: Identity, offer_id: str, option_id: str, key: str) -> Any:
        self.placed = (offer_id, option_id, key)
        return self._answer("place_order")


def _agent_run(**fields: Any) -> AgentRun:
    return AgentRun(text="t", model="m", recorded=True, report="The agent stopped.", **fields)


def test_the_page_orders_with_the_key_it_is_given_one_per_form_submission() -> None:
    service = StubService(read_request="typed")

    run_request(service, AGENT, "free text", None, order_key="page-run-0123")

    assert service.placed == ("off_1", "opt_1", "page-run-0123")


def test_the_order_key_of_a_form_is_derived_from_its_run_key_and_never_shows_it() -> None:
    key = order_key("A" * 43)

    assert key == order_key("A" * 43) != order_key("B" * 43)
    assert key.startswith("page-") and len(key) <= 100 and "A" * 8 not in key


def test_the_page_orders_the_top_option_with_a_key_the_order_book_accepts() -> None:
    service = StubService(read_request="typed")

    record = run_request(service, AGENT, "free text", None)

    assert service.calls == ["read_request", "create_offer", "place_order"]
    assert service.requested == "typed"
    assert service.placed[:2] == ("off_1", "opt_1")
    assert service.placed[2].startswith("page-") and len(service.placed[2]) <= 100
    assert (record.read_by, record.offer_id, record.order_id) == (ReadBy.PARSER, "off_1", "ord_1")
    assert record.not_ordered is None and record.agent_id == AGENT.id
    assert record.reading is not None and record.reading.sentence == READ_BY_STUB


@pytest.mark.parametrize("error", [
    PolicyBlocked("A line declares an excluded allergen (F-02)."),
    OfferStale("The price changed since the offer.", fresh_offer_id="off_9"),
    RateLimited("Too many calls."),
])
def test_an_order_the_gateway_refuses_is_kept_as_the_outcome_with_its_reason(error: TtaError) -> None:
    service = StubService(read_request="typed", place_order=error)

    record = run_request(service, AGENT, "free text", None)

    assert (record.offer_id, record.order_id) == ("off_1", None)
    assert record.not_ordered is not None
    assert (record.not_ordered.title, record.not_ordered.detail) == (error.title, error.detail)
    assert record.not_ordered.status == error.status_code


def test_an_offer_with_no_option_is_not_ordered() -> None:
    service = StubService(read_request="typed", create_offer=EMPTY_OFFER)

    record = run_request(service, AGENT, "free text", None)

    assert "place_order" not in service.calls
    assert (record.offer_id, record.order_id, record.not_ordered) == ("off_2", None, None)


def test_an_offer_that_cannot_be_built_is_the_callers_error() -> None:
    service = StubService(read_request="typed", create_offer=InvalidRequest("An exclusion needs a strictness."))

    with pytest.raises(InvalidRequest, match="strictness"):
        run_request(service, AGENT, "free text", None)


def test_an_example_carries_its_typed_request_when_the_parser_cannot_be_reached() -> None:
    service = StubService(read_request=SupplierUnavailable("No parser."))

    record = run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)

    assert service.requested == SCENARIO_2.request
    assert record.read_by is ReadBy.EXAMPLE
    assert any("No parser." in note for note in record.notes)
    assert not any(NO_MODEL_ASKED in note for note in record.notes)  # the parser was asked


def test_an_example_carries_its_typed_request_when_the_parser_misreads_it() -> None:
    service = StubService(read_request=InvalidRequest("The request names no quantity."))

    record = run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)

    assert service.requested == SCENARIO_2.request
    assert any("The request names no quantity." in note for note in record.notes)


def test_free_text_the_parser_cannot_read_is_the_callers_error() -> None:
    for error in (SupplierUnavailable("No parser."), InvalidRequest("No quantity."), RateLimited("Slow down.")):
        with pytest.raises(type(error)):
            run_request(StubService(read_request=error), AGENT, "free text", None)


@pytest.mark.parametrize("step", ["run_agent", "read_request"])
def test_an_example_needs_no_model_so_the_ceiling_on_model_calls_does_not_stop_it(step: str) -> None:
    service = StubService(**{step: RateLimited("Too many request readings and agent runs right now.")})

    record = run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)

    assert service.calls == [step, "create_offer", "place_order"]
    assert (record.read_by, record.order_id) == (ReadBy.EXAMPLE, "ord_1")
    assert any("Too many request readings and agent runs" in note for note in record.notes)


def test_the_limit_on_offers_stops_an_example_like_any_other_request() -> None:
    service = StubService(read_request=SupplierUnavailable("No parser."), create_offer=RateLimited("Slow down."))

    with pytest.raises(RateLimited):
        run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)
    assert "place_order" not in service.calls


def test_free_text_is_not_sent_to_the_parser_after_the_agent_was_rate_limited() -> None:
    service = StubService(run_agent=RateLimited("Slow down."), read_request="typed")

    with pytest.raises(RateLimited):
        run_request(service, AGENT, "free text", None)
    assert service.calls == ["run_agent"]


def test_the_agents_run_is_the_result_and_the_page_orders_nothing_itself() -> None:
    run = _agent_run(offer_id="off_7", order_id="ord_7")
    service = StubService(run_agent=run)

    record = run_request(service, AGENT, "free text", None)

    assert service.calls == ["run_agent"]
    assert (record.read_by, record.agent_run, record.offer_id, record.order_id) == (ReadBy.AGENT, run, "off_7", "ord_7")


def test_an_agent_that_stops_without_an_offer_is_shown_as_it_is_for_free_text() -> None:
    run = _agent_run()
    service = StubService(run_agent=run)

    record = run_request(service, AGENT, "free text", None)

    assert service.calls == ["run_agent"]
    assert (record.agent_run, record.offer_id, record.order_id) == (run, None, None)


def test_an_example_does_not_depend_on_the_agent_reaching_an_offer() -> None:
    service = StubService(run_agent=_agent_run())

    record = run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)

    assert service.calls == ["run_agent", "create_offer", "place_order"]  # the parser is not asked a second time
    assert (record.read_by, record.offer_id, record.order_id) == (ReadBy.EXAMPLE, "off_1", "ord_1")
    assert any("The agent stopped." in note for note in record.notes)


@pytest.mark.parametrize("error", [SupplierUnavailable("Model down."), InvalidRequest("Misread.")])
def test_an_example_does_not_depend_on_the_agent_running(error: TtaError) -> None:
    service = StubService(run_agent=error, read_request="typed")

    record = run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)

    assert service.calls == ["run_agent", "create_offer", "place_order"]  # the parser is not asked either
    assert record.read_by is ReadBy.EXAMPLE
    assert any(error.detail in note for note in record.notes)
    assert not any(NO_MODEL_ASKED in note for note in record.notes)  # the agent was asked


def test_free_text_the_agent_cannot_run_is_not_read_a_second_time_by_the_parser() -> None:
    service = StubService(run_agent=SupplierUnavailable("Model down."), read_request="typed")

    with pytest.raises(SupplierUnavailable, match="Model down."):
        run_request(service, AGENT, "free text", None)
    assert service.calls == ["run_agent"]


def test_what_the_agent_refuses_for_free_text_is_the_callers_error() -> None:
    for error in (InvalidRequest("The request names no quantity."), RateLimited("Slow down.")):
        with pytest.raises(type(error)):
            run_request(StubService(run_agent=error), AGENT, "free text", None)


def test_the_examples_are_the_demo_set_in_order_then_the_reserve_each_with_a_typed_request() -> None:
    """The demo set (docs/DEMO.md, `tta.ui.examples`): 1 to 6 in demo order, each with its customer's agent, then
    the reserve. Steps 4 and 6 have two examples each: the allergen doubt (the hotel's oat drink, the school's
    almond drink) and the formula (the bakery's crème fraîche, then its whipping cream)."""
    assert [(example.key, example.step) for example in EXAMPLES] == [
        ("scenario-1", 1), ("scenario-2", 2), ("scenario-3", 3), ("scenario-4", 4), ("almond", 4), ("pattern", 5),
        ("formula-changed", 6), ("formula", 6), ("scenario-5", None),
    ]
    assert [example.agent_id for example in EXAMPLES] == [
        "agent:hotel-kitchen", "agent:allergy-ward", "agent:hotel-kitchen", "agent:hotel-kitchen",
        "agent:school-kitchen", "agent:hotel-kitchen", "agent:bakery-cafe", "agent:bakery-cafe",
        "agent:hotel-kitchen",
    ]
    for example in EXAMPLES:
        assert example.request.lines[0].text == example.text
        assert example.request.needed_by is not None
    by_key = {example.key: example for example in EXAMPLES}
    ward = by_key["scenario-2"].request
    assert ward.require_confirmed and ward.lines[0].exclude_allergens == ("AM", "AW")
    assert by_key["scenario-3"].request.lines[0].product_ids == ("473609",)
    dietitian = by_key["scenario-4"].request.lines[0]
    assert (dietitian.product_ids, dietitian.quantity, dietitian.unit) == (("469512",), 100, Unit.L)
    assert (dietitian.exclude_allergens, dietitian.allergen_strictness) == (("AM",), AllergenStrictness.STRICT)
    usual = by_key["pattern"]
    assert (usual.request.lines[0].quantity, usual.then and usual.then[0]) == (100, "/standing-orders")
    cream = by_key["formula"].request.lines[0]
    assert (cream.product_type, cream.name_terms, cream.quantity) == ("cream", ("whipping",), 100)


def test_an_example_is_found_by_its_text_whatever_the_spacing_and_case() -> None:
    assert example_for_text("  1,000 LITRES of lactose-free   milk by Monday \n") is EXAMPLES[0]
    assert example_for_text("1,000 litres of milk by Monday") is None
    assert example_by_key("scenario-3") is EXAMPLES[2] and example_by_key("scenario-9") is None


def _record(offer_id: str) -> RunRecord:
    return RunRecord(text="t", agent_id=AGENT.id, read_by=ReadBy.EXAMPLE, offer_id=offer_id)


def test_the_run_log_runs_a_form_once_and_finds_a_run_by_its_offer() -> None:
    log = RunLog(capacity=10)

    assert log.reserve("key-1") is True
    assert log.reserve("key-1") is False  # the same form, posted again
    assert log.by_key("key-1") is None  # still running
    log.finish("key-1", _record("off_1"))

    assert log.by_key("key-1") == _record("off_1") == log.by_offer("off_1")
    assert log.by_offer("off_nobody") is None and log.by_key("key-nobody") is None


def test_a_run_that_failed_frees_its_form_for_another_try() -> None:
    log = RunLog(capacity=10)
    log.reserve("key-1")

    log.release("key-1")

    assert log.reserve("key-1") is True


def test_the_run_log_forgets_the_oldest_runs_first() -> None:
    log = RunLog(capacity=3)
    for number in range(5):
        log.reserve(f"key-{number}")
        log.finish(f"key-{number}", _record(f"off_{number}"))

    assert log.by_offer("off_0") is None and log.by_key("key-1") is None
    assert [log.by_offer(f"off_{number}") is not None for number in (2, 3, 4)] == [True, True, True]


def test_with_no_parser_at_all_an_example_says_only_that_no_model_was_asked() -> None:
    service = StubService()
    service.answers["read_request"] = SupplierUnavailable("This gateway has no request parser running.")

    record = run_request(service, AGENT, SCENARIO_2.text, SCENARIO_2)

    assert record.notes == ("Read from the typed request of this example. No model was asked.",)


def test_substitutes_looked_up_for_an_offer_without_a_run_are_kept_up_to_the_capacity() -> None:
    log = RunLog(capacity=2)
    for number in range(3):
        log.remember_substitutes(f"off_{number}", Substitutes())

    assert log.substitutes_of("off_0") is None
    assert log.substitutes_of("off_2") == Substitutes()


def test_an_offer_that_can_no_longer_be_read_gives_its_refusal_in_place_of_the_substitutes() -> None:
    service = StubService(get_offer=NotFound("No offer has this id."))

    found = look_up_substitutes(service, AGENT, "off_1")

    assert found is not None and found.found == () and found.problem is not None
    assert found.problem.detail == "No offer has this id."


class Book:
    """Stands for an order book: any object that can be weakly referred to."""


def test_each_order_book_has_a_run_log_of_its_own() -> None:
    logs, one, other = RunLogs(), Book(), Book()

    assert logs.of(one) is logs.of(one) and logs.of(one) is not logs.of(other)  # type: ignore[arg-type]
