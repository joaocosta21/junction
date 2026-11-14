"""The three examples with the buyer agent package as it ships (task T10), with no key: its recorded runs.

The other page tests run against fakes of the parser and the runner. These build the real package's parser
and runner the way the gateway does, so the demo path is checked as it runs on the day: scenarios 1 and 2
are recorded sentences and are run by the agent; scenario 3 is not, so the page goes on with the example's
typed request. No model is called: the settings hold no key.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import OrderStatus, PlacedBy
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
    assert "Ordered by the agent" in page
    assert order.status is OrderStatus.ORDERED and order.placed_by is PlacedBy.AGENT


def test_scenario_3_has_no_recording_so_the_page_goes_on_with_its_typed_request(
    agent_client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    page = run_example(agent_client, "scenario-3").text

    assert "The buyer agent could not run" in page and "typed request of this example" in page
    assert AGENT_STEPS not in page
    assert "Ordered by the agent" in page
    assert only_order(agent_client).status is OrderStatus.ORDERED
