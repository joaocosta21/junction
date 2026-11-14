"""The result of a request is read once and said as it is (task FIX-10, findings 5, 8, 11, 12).

Scores on the 20% "solving the problem" (who read the request is said, a recording is never passed off as
the model) and the 30% demo (a view of a result looks nothing up again, and never denies an order).
"""

from __future__ import annotations

import html
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import service as service_module
from tta.config import Settings
from tta.contracts.agent import AgentRun, AgentStep, Reading, ReadingSource
from tta.contracts.common import Identity
from tta.contracts.ports import GatewayService
from tta.ui.examples import EXAMPLES

Post = Callable[..., Any]
MakeClient = Callable[..., TestClient]
SCENARIO_3 = EXAMPLES[2]
NO_LONGER_KNOWN = "How this was read is no longer known"
# The fake parser's own sentence: the page must show the sentence the reading carries, whatever it is.
RECORDING_SENTENCE = "Read from a recording of fake-model-1 (a sentence of the fake parser of this test)."


class RecordingParser:
    """A parser that read the text from a recording (task FIX-9's `read`)."""

    def __init__(self, request: Any) -> None:
        self._request = request

    def read(self, text: str, identity: Identity) -> Reading:
        return Reading(
            request=self._request, source=ReadingSource.RECORDING, model="gemini-3.6-flash",
            recorded_at=datetime(2026, 11, 14, 6, 14, tzinfo=UTC), sentence=RECORDING_SENTENCE,
        )

    def parse_request(self, text: str, identity: Identity) -> Any:
        return self._request


class RunnerOf:
    """A buyer agent that orders the example's request and names itself as the given model."""

    def __init__(self, model: str, *, recorded: bool) -> None:
        self._model, self._recorded = model, recorded

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        offer = tools.create_offer(identity, EXAMPLES[1].request)
        order = tools.place_order(identity, offer.offer_id, offer.options[0].option_id, "agent-1")
        step = AgentStep(index=1, tool="place_order", ok=True, sentence=order.status_sentence)
        return AgentRun(
            text=text, model=self._model, recorded=self._recorded, steps=(step,), offer_id=offer.offer_id,
            order_id=order.order_id, order_status=order.status, report=order.status_sentence,
        )


def _spy(monkeypatch: pytest.MonkeyPatch, service: Any, name: str) -> list[int]:
    calls: list[int] = []
    real = getattr(service, name)

    def counted(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(service, name, counted)
    return calls


# --- finding 5: the reading's own sentence -----------------------------------------------------------------


def test_a_request_read_from_a_recording_says_so_where_the_page_says_how_it_was_read(
    make_client: MakeClient, run_text: Post
) -> None:
    client = make_client(request_parser=RecordingParser(EXAMPLES[1].request))

    page = run_text(client, "two hundred litres of soya drink, no milk, no gluten", who="agent:allergy-ward").text
    how = page[page.index('class="how"'):page.index('class="source"')]

    assert RECORDING_SENTENCE in how


# --- finding 8: substitutes are looked up once, when the request runs --------------------------------------


def test_the_substitutes_are_looked_up_once_at_run_time_and_not_again_on_each_view(
    client: TestClient, run_example: Post, own_book: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    lookups = _spy(monkeypatch, own_book(client).service, "find_substitutes")
    result = run_example(client, "scenario-3")

    for _ in range(5):
        view = client.get(str(result.url)).text

    assert len(lookups) == 1
    assert "471881" in view[view.index('id="substitutes"'):]


def test_a_view_without_its_run_offers_a_lookup_button_and_looks_nothing_up_by_itself(
    client: TestClient, own_book: Callable[..., Any], identities: Callable[..., Any], form_fields: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    book = own_book(client)
    offer = book.service.create_offer(identities(client)["agent:hotel-kitchen"], SCENARIO_3.request)  # no page run
    lookups = _spy(monkeypatch, book.service, "find_substitutes")

    view = client.get("/", params={"offer": offer.offer_id}).text
    looked_up = client.post("/substitutes", data={"csrf": form_fields(client)["csrf"], "offer": offer.offer_id})
    again = client.get("/", params={"offer": offer.offer_id}).text

    assert len(lookups) == 1
    assert 'action="/substitutes"' in view and "Look up substitutes" in view and "471881" not in view
    assert looked_up.status_code == 200 and "471881" in looked_up.text
    assert "471881" in again  # kept: the next view looks nothing up


def test_the_lookup_button_needs_a_post_with_the_form_token(client: TestClient) -> None:
    assert client.get("/substitutes").status_code == 405
    assert client.post("/substitutes", data={"csrf": "x" * 43, "offer": "off_1"}).status_code == 403


# --- finding 11: a result never denies an order that exists -----------------------------------------------


def test_a_result_finds_its_order_beyond_the_newest_hundred_and_says_its_run_is_no_longer_known(
    client: TestClient, own_book: Callable[..., Any], identities: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "MAX_LIST_ITEMS", 1)  # stands for the 100 of a list
    book, ward = own_book(client), identities(client)["agent:allergy-ward"]
    first = book.service.create_offer(ward, EXAMPLES[1].request)
    book.service.place_order(ward, first.offer_id, first.options[0].option_id, "k-1")
    later = book.service.create_offer(ward, EXAMPLES[1].request)
    book.service.place_order(ward, later.offer_id, later.options[0].option_id, "k-2")
    client.cookies.set("tta_agent", ward.id)

    page = client.get("/", params={"offer": first.offer_id}).text

    assert "No order has been placed" not in page and "Prepared: confirm to order" in page
    assert NO_LONGER_KNOWN in page


def test_a_result_whose_run_is_kept_does_not_say_its_reading_is_unknown(client: TestClient, run_example: Post) -> None:
    assert NO_LONGER_KNOWN not in run_example(client, "scenario-2").text


# --- finding 12: the words say what happened ---------------------------------------------------------------


def test_no_model_was_asked_is_said_only_when_no_model_was_asked(
    client: TestClient, make_client: MakeClient, run_example: Post, fakes: Any
) -> None:
    without_a_model = run_example(client, "scenario-3").text
    after_the_agent = run_example(make_client(agent_runner=fakes.DownRunner()), "scenario-3").text

    assert "No model was asked" in without_a_model
    assert "No model was asked" not in after_the_agent and "typed request of this example" in after_the_agent


@pytest.mark.parametrize(
    ("model", "recorded", "key", "said"),
    [
        ("hand-built", True, None, "answers written by hand, not by a model"),
        ("recorded", True, None, "a recording of the model's earlier answers"),
        ("recorded", True, "a-gemini-key", "Gemini did not answer"),
        ("gemini-3.6-flash", False, "a-gemini-key", "Run live by gemini-3.6-flash"),
    ],
)
def test_the_agent_card_names_a_hand_built_a_recorded_a_fall_back_and_a_live_run_as_what_they_are(
    settings: Settings, make_client: MakeClient, run_example: Post, monkeypatch: pytest.MonkeyPatch,
    model: str, recorded: bool, key: str | None, said: str,
) -> None:
    if key is not None:
        monkeypatch.setattr(type(settings), "has_gemini_key", property(lambda self: True))
    client = make_client(agent_runner=RunnerOf(model, recorded=recorded))

    page = run_example(client, "scenario-2").text
    card = page[page.index('id="agent"'):]

    assert said in html.unescape(card)
    assert "Model <code>" not in card


def test_a_substitute_whose_quantity_is_not_confirmed_can_be_ordered_only_with_approval(
    client: TestClient, run_example: Post
) -> None:
    page = run_example(client, "scenario-3").text
    substitutes = page[page.index('id="substitutes"'):page.index('id="excluded"')]
    unconfirmed = substitutes[substitutes.index("(468465)"):]
    unconfirmed = unconfirmed[:unconfirmed.index("</li>")]

    assert "Can be ordered, needs approval" in unconfirmed
