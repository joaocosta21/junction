"""A tool refuses what the REST route refuses: an argument it does not take, and arguments that do not validate
(review C1-7 and C4-F10).

Scores on the 20% "autonomy and controls" and on the 15% "open, documented standards". Before, `place_order` with
`unit_net_price: 0.01` and `quantity: 9999` was placed at the offered price and the agent was never told its
fields were dropped, a foreign `profile_id` on `get_offer` was dropped too, and a call with missing arguments was
answered in the SDK's own words ("place_orderArguments", an address of the validation library). Now every such
call is answered with the problem document of RFC 9457 the REST route sends: `invalid-request`, with each field
and, for a field the tool does not have, REST's own words.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx
import pytest
from mcp.client import Client
from mcp.types import CallToolResult

from tta.api.errors import UNKNOWN_FIELD
from tta.api.mcp_surface import TOOL_NAMES
from tta.api.wiring import Parts

pytestmark = pytest.mark.anyio

Connect = Callable[..., AbstractAsyncContextManager[Client]]
Headers = dict[str, str]
Auth = Callable[[str], Headers]

INVALID_REQUEST = "https://tta.example/problems/invalid-request"
LIBRARY_WORDS = ("Arguments", "pydantic", "errors.pydantic.dev", "validation error for", "input_value", "Traceback")
NOT_A_FIELD = {"field": "arguments", "problem": "a field this request does not have"}


def _refused(answer: CallToolResult) -> dict[str, Any]:
    """Check that the answer is the problem document of an invalid request, in no library's words."""
    assert answer.is_error is True
    problem = answer.structured_content
    assert problem is not None, answer.content
    assert (problem["type"], problem["status"], problem["title"]) == (INVALID_REQUEST, 422, "The request is not valid")
    [block] = answer.content
    assert json.loads(block.text) == problem  # the model reads the document a program reads
    for words in LIBRARY_WORDS:
        assert words not in block.text, words
    return problem


async def test_an_order_with_a_price_and_a_quantity_of_the_agents_own_is_refused_and_nothing_is_placed(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, parts: Parts, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as client:
        offer = (await client.call_tool("get_offer", {"request": scenario_2})).structured_content
        order = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}
        answer = await client.call_tool(
            "place_order", {**order, "idempotency_key": "strict-1", "unit_net_price": 0.01, "quantity": 9999}
        )
        placed = await client.call_tool("place_order", {**order, "idempotency_key": "strict-1"})
    over_rest = await rest.post(
        "/v1/orders", json={**order, "unit_net_price": 0.01, "quantity": 9999},
        headers={**auth("agent_ward"), "Idempotency-Key": "strict-rest-1"},
    )

    problem = _refused(answer)
    assert problem["errors"] == [NOT_A_FIELD, NOT_A_FIELD]  # one per field the tool does not have, never its name
    assert NOT_A_FIELD["problem"] == UNKNOWN_FIELD  # the words of the REST refusal
    assert "unit_net_price" not in json.dumps(problem) and "9999" not in json.dumps(problem)
    assert "This tool takes: offer_id, option_id, idempotency_key." in problem["detail"]
    # REST refuses the same body in the same words, naming the place the field sits in.
    assert over_rest.status_code == 422
    assert [error["problem"] for error in over_rest.json()["errors"]] == [UNKNOWN_FIELD, UNKNOWN_FIELD]
    # The refused call placed nothing; the same call without the two fields is placed at the offered price.
    assert not placed.is_error
    assert placed.structured_content["option"]["totals"]["net"] == 402.0
    assert len(parts.store.list_orders()) == 1


async def test_a_foreign_buyer_profile_on_an_offer_is_refused_and_no_offer_is_made(
    connect: Connect, parts: Parts, scenario_2: dict[str, Any]
) -> None:
    async with connect("agent_ward") as client:
        answer = await client.call_tool("get_offer", {"request": scenario_2, "profile_id": "hotel-kitchen"})

    problem = _refused(answer)
    assert problem["errors"] == [NOT_A_FIELD]
    assert "hotel-kitchen" not in json.dumps(problem)
    assert "This tool takes: request." in problem["detail"]
    assert parts.audit.head()[0] == 0  # nothing was built or recorded


@pytest.mark.parametrize("tool", TOOL_NAMES)
async def test_every_tool_refuses_an_argument_it_does_not_take(connect: Connect, parts: Parts, tool: str) -> None:
    async with connect("agent_ward") as client:
        answer = await client.call_tool(tool, {"an_argument_nobody_defined": 1})

    problem = _refused(answer)
    assert NOT_A_FIELD in problem["errors"]
    assert "an_argument_nobody_defined" not in json.dumps(problem)
    assert parts.audit.head()[0] == 0


async def test_every_tool_says_in_its_schema_that_it_takes_no_other_argument(connect: Connect) -> None:
    async with connect("agent_ward") as client:
        tools = (await client.list_tools()).tools

    assert {tool.name for tool in tools} == set(TOOL_NAMES)
    for tool in tools:
        assert tool.input_schema["additionalProperties"] is False, tool.name


async def test_missing_arguments_are_answered_with_the_problem_document_not_the_librarys_text(
    connect: Connect, parts: Parts
) -> None:
    async with connect("agent_ward") as client:
        answer = await client.call_tool("place_order", {"offer_id": "off_0123456789ab"})

    problem = _refused(answer)
    assert problem["errors"] == [
        {"field": "arguments.option_id", "problem": "Field required"},
        {"field": "arguments.idempotency_key", "problem": "Field required"},
    ]
    assert problem["detail"] == (
        "The request does not match what this route takes. arguments.option_id: Field required; "
        "arguments.idempotency_key: Field required."
    )
    assert parts.store.list_orders() == ()


async def test_a_request_that_does_not_validate_names_the_field_inside_the_argument(
    connect: Connect, rest: httpx.AsyncClient, auth: Auth, parts: Parts
) -> None:
    no_quantity = {"lines": [{"text": "some milk", "unit": "L", "made_up": True}]}
    async with connect("agent_ward") as client:
        answer = await client.call_tool("get_offer", {"request": no_quantity})
        bad_key = await client.call_tool("place_order", {
            "offer_id": "off_0123456789ab", "option_id": "opt_1", "idempotency_key": "a key with spaces",
        })
    over_rest = await rest.post("/v1/offers", json=no_quantity, headers=auth("agent_ward"))

    problem = _refused(answer)
    # The same two findings as REST gives, under `arguments.request` where REST says `body`.
    assert problem["errors"] == [
        {**error, "field": error["field"].replace("body", "arguments.request", 1)}
        for error in over_rest.json()["errors"]
    ]
    assert {"field": "arguments.request.lines.0.quantity", "problem": "Field required"} in problem["errors"]
    assert {"field": "arguments.request.lines.0", "problem": UNKNOWN_FIELD} in problem["errors"]
    assert "some milk" not in json.dumps(problem)  # nothing the caller sent is repeated
    assert _refused(bad_key)["errors"][0]["field"] == "arguments.idempotency_key"
    assert "a key with spaces" not in json.dumps(bad_key.structured_content)
    assert parts.audit.head()[0] == 0
