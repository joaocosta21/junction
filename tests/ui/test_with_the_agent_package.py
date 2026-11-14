"""The three examples with the buyer agent package as it ships (task T10), with no key: its recorded runs.

The other page tests run against fakes of the parser and the runner. These build the real package's parser
and runner the way the gateway does, so the demo path is checked as it runs on the day: scenarios 1 and 2
are recorded sentences and are run by the agent; scenario 3 is not, so the page goes on with the example's
typed request. No model is called: the settings hold no key.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import OrderStatus
from tta.valio import ReplayGateway

Post = Callable[..., Any]
MakeClient = Callable[..., TestClient]
AGENT_PACKAGE = "tta.agent"
AGENT_STEPS = 'id="agent"'


@pytest.fixture
def agent_client(make_client: MakeClient, settings: Settings, catalog: ProductCatalog) -> TestClient:
    package = pytest.importorskip(AGENT_PACKAGE)
    assert not settings.has_gemini_key  # recorded runs only
    given = {
        "settings": settings,
        "clock": ReplayGateway(settings.replay_capture_dir).clock,
        "product_type_keys": catalog.product_type_keys(),
    }
    return make_client(
        request_parser=package.build_request_parser(**given), agent_runner=package.build_agent_runner(**given)
    )


def test_scenario_1_is_run_by_the_agent_and_sent_for_approval(
    agent_client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    page = run_example(agent_client, "scenario-1").text

    assert AGENT_STEPS in page and "read and run by the buyer agent" in page
    assert "Sent for approval" in page
    assert only_order(agent_client).status is OrderStatus.PENDING_APPROVAL


def test_scenario_2_is_run_by_the_agent_and_ordered_by_it_alone(
    agent_client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    page = run_example(agent_client, "scenario-2").text
    order = only_order(agent_client, "agent:allergy-ward")

    assert AGENT_STEPS in page
    assert "Sent for approval" in page
    assert order.status is OrderStatus.PENDING_APPROVAL and order.placed_by is None


def test_scenario_3_has_no_recording_so_the_page_goes_on_with_its_typed_request(
    agent_client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    page = run_example(agent_client, "scenario-3").text

    assert "The buyer agent could not run" in page and "typed request of this example" in page
    assert AGENT_STEPS not in page
    assert "Sent for approval" in page
    assert only_order(agent_client).status is OrderStatus.PENDING_APPROVAL


def test_with_the_parser_alone_the_page_says_the_request_was_read_from_its_recording(
    make_client: MakeClient, settings: Settings, catalog: ProductCatalog, run_example: Post
) -> None:
    # Task FIX-10, finding 5: the reading's own sentence, built here from the recording's own time, so that
    # a new recording of the sentence changes nothing in this test.
    package = pytest.importorskip(AGENT_PACKAGE)
    labels = pytest.importorskip(AGENT_PACKAGE + ".labels")
    given = {
        "settings": settings,
        "clock": ReplayGateway(settings.replay_capture_dir).clock,
        "product_type_keys": catalog.product_type_keys(),
    }
    client = make_client(request_parser=package.build_request_parser(**given))
    recording = json.loads((settings.tta_fixtures_dir / "agent" / "parse-scenario-1.json").read_text(encoding="utf-8"))
    made = labels.made_on(datetime.fromisoformat(recording["recorded_at"]))

    page = run_example(client, "scenario-1").text
    how = page[page.index('class="how"'):page.index('class="source"')]

    assert f"Read from a recording of {recording['model']} made on {made}; no model was asked." in how
    assert "Sent for approval" in page
