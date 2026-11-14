"""Over MCP as over REST: catalog reads and reads of the audit trail are counted, a search names few name terms
in the demonstration, and the audit trail is answered in pages (review H2 and M3).

Scores on the 15% "open, documented standards" (an MCP host meets the same limits a REST client does) and on the
30% "working end-to-end demo".
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import pytest
from mcp.client import Client

from tta.api.limits import RateLimit

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
PROBLEMS = "https://tta.example/problems/"
TWO_CALLS = RateLimit(calls=2, window_seconds=60.0)


def _problem(result: Any, slug: str, status: int) -> dict[str, Any]:
    assert result.is_error
    problem = json.loads(result.content[0].text)
    assert (problem["type"], problem["status"]) == (PROBLEMS + slug, status)
    return problem


@pytest.mark.parametrize("rate_limit", [TWO_CALLS])
async def test_searches_and_product_reads_share_the_lookup_window_over_mcp(
    connect: Connect, rate_limit: RateLimit
) -> None:
    async with connect("agent_ward") as client:
        found = await client.call_tool("search_products", {"query": {"product_type": "plant_drink"}})
        read = await client.call_tool("get_product", {"product_id": "464056"})
        third = await client.call_tool("search_products", {"query": {"product_type": "plant_drink"}})

    assert not found.is_error and not read.is_error
    problem = _problem(third, "rate-limited", 429)
    assert "searches and reads of the catalog" in problem["detail"] and problem["retry_after_seconds"] >= 1


@pytest.mark.parametrize("rate_limit", [TWO_CALLS])
async def test_reading_the_trail_is_counted_over_mcp(connect: Connect, rate_limit: RateLimit) -> None:
    async with connect("supplier") as client:
        answers = [await client.call_tool("get_audit") for _ in range(3)]

    assert not answers[0].is_error and not answers[1].is_error
    _problem(answers[2], "rate-limited", 429)


async def test_a_search_with_five_name_terms_is_refused_over_mcp(connect: Connect) -> None:
    async with connect("agent_ward") as client:
        five = await client.call_tool(
            "search_products", {"query": {"name_terms": ["oat", "drink", "barista", "1", "l"]}}
        )

    assert "at most 4 name terms" in _problem(five, "invalid-request", 422)["detail"]


async def test_the_audit_tool_answers_in_pages_with_a_cursor(connect: Connect, scenario_2: dict[str, Any]) -> None:
    async with connect("agent_ward") as client:
        await client.call_tool("get_offer", {"request": scenario_2})
        whole = (await client.call_tool("get_audit")).structured_content
        newest = (await client.call_tool("get_audit", {"limit": 2})).structured_content
        before = (await client.call_tool("get_audit", {"limit": 2, "before": newest["next_cursor"]})).structured_content
        too_many = await client.call_tool("get_audit", {"limit": 201})

    ids = [event["id"] for event in whole["events"]]
    assert len(ids) >= 4 and (whole["next_cursor"], whole["verified"]) == (None, "whole_chain")
    assert [event["id"] for event in newest["events"]] == ids[-2:] and newest["next_cursor"] == ids[-2]
    assert [event["id"] for event in before["events"]] == ids[-4:-2]
    assert newest["chain"]["checked"] == 2 and too_many.is_error
