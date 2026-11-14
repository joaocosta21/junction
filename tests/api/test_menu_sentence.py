"""POST /v1/menus/plan and the MCP tool `plan_menu` take a sentence beside the typed dishes (task CK).

"I want to make a chocolate cake for 20 people" as the bakery gives the plan the typed dishes give; what the
sentence leaves open is refused (422) with the question and the list of dishes, never guessed. In replay over the
recording `2026-11-14-demo` joined with `2026-11-14-baking`, at the recording's clock and at the demo clock
(Thu 12 Nov 2026 14:15 Helsinki).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, hooks, mcp_surface
from tta.api.limits import RateLimit
from tta.api.mcp_surface import GatewayTools
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.menu import MenuPlan
from tta.menus.sentence import MenuAsk

BAKERY = {"Authorization": "Bearer demo-agent-bakery-cafe"}
OWNER = {"Authorization": "Bearer demo-approver-bakery-owner"}
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
NOT_SHOWN = (hooks.AGENT_MODULE, hooks.MCP_MODULE, hooks.PAGES_MODULE)
SENTENCE = "I want to make a chocolate cake for 20 people by Monday"
TYPED = {"dishes": [{"dish_id": "chocolate_cake", "servings": 20}], "needed_by": "2026-11-16"}
DISHES = (
    "The dishes are: beef stew, creamy chicken pasta, salmon with rice, oven pancake, macaroni casserole, rice "
    "porridge, lasagne, cheese omelette, berry quark dessert and chocolate cake."
)
LATER = (
    "394 of the 1,163 recorded products were recorded later than the rest: on Saturday 14 Nov at 21:12 (recording "
    "2026-11-14-baking), against Saturday 14 Nov at 02:52 for the other 769 (recording 2026-11-14-demo, which "
    "gives the clock). Valio Aimo said on 14 Nov 2026 that its test data is static, which is why two recordings "
    "of the same Saturday are read as one."
)


@pytest.fixture(scope="module")
def whole_catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(params=[None, DEMO_CLOCK], ids=["default-clock", "demo-clock"])
def cake_settings(request: pytest.FixtureRequest, tmp_path: Path) -> Settings:
    return Settings.for_tests(tta_data_dir=tmp_path / "var", tta_demo_clock=request.param)


@pytest.fixture
def cake_parts(cake_settings: Settings, whole_catalog: ProductCatalog) -> Iterator[Parts]:
    built = build_parts(cake_settings, catalog=whole_catalog, rate_limit=RateLimit(calls=1000))
    yield built
    # closed by the application's lifespan when a client was opened on it; closing twice is harmless


@pytest.fixture
def cake_api(
    cake_settings: Settings, cake_parts: Parts, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    real = hooks.optional_module
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in NOT_SHOWN else real(name))
    with TestClient(create_app(cake_settings, parts=cake_parts)) as client:
        yield client


def _plan(api: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    response = api.post("/v1/menus/plan", json=body, headers=BAKERY)
    assert response.status_code == 200, response.text
    return response.json()


def _refused(api: TestClient, body: dict[str, Any]) -> str:
    response = api.post("/v1/menus/plan", json=body, headers=BAKERY)
    assert response.status_code == 422, response.text
    assert response.json()["type"].endswith("invalid-request")
    return response.json()["detail"]


def _comparable(plan: dict[str, Any], api: TestClient) -> dict[str, Any]:
    """The plan and its offer without what differs between two askings: ids, times and the read-as note."""
    offer = api.get(f"/v1/offers/{plan['offer_id']}", headers=BAKERY).json()
    options = [
        {
            "title": option["title"], "net": option["totals"]["net"], "gross": option["totals"]["gross"],
            "rules": [rule["rule_id"] for rule in option["decision"]["fired"]],
            "lines": [(line["product_id"], line["quantity"], line["net"]) for line in option["lines"]],
        }
        for option in offer["options"]
    ]
    notes = [note for note in plan["notes"] if not note.startswith("Read as:")]
    return {"request": plan["request"], "dishes": plan["dishes"], "lines": plan["lines"], "notes": notes,
            "cannot_be_sourced": plan["cannot_be_sourced"], "options": options}


def test_the_sentence_and_the_typed_dishes_give_the_same_plan(cake_api: TestClient) -> None:
    said, typed = _plan(cake_api, {"text": SENTENCE}), _plan(cake_api, TYPED)

    assert said["notes"][0] == "Read as: chocolate cake, 20 servings, by Monday 16 Nov."
    assert not any(note.startswith("Read as:") for note in typed["notes"])
    assert said["request"] == typed["request"] == {
        "dishes": [{"dish_id": "chocolate_cake", "servings": 20}], "stock": [], "needed_by": "2026-11-16",
        "exclude_allergens": [], "allergen_strictness": None, "require_confirmed": False,
    }
    assert _comparable(said, cake_api) == _comparable(typed, cake_api)
    assert [option["net"] for option in _comparable(said, cake_api)["options"]][0] == 15.19


def test_the_plan_says_which_products_were_recorded_later_and_when(
    cake_api: TestClient, cake_settings: Settings
) -> None:
    """Flour, sugar, eggs, butter, cocoa powder and baking powder are of the later recording; the milk is of the
    first (two milks at the recording's clock, one at the demo clock)."""
    plan = _plan(cake_api, {"text": "chocolate cake for 20"})

    later = plan["notes"][-1]
    offered = 8 if cake_settings.tta_demo_clock is None else 7
    assert later.startswith(
        f"6 of the {offered} products of this offer have their price and stock from the later recording ("
    )
    assert later.endswith(LATER)
    assert "463047" not in later.split(")")[0] and "460856" in later.split(")")[0]


def test_a_plan_of_the_first_recording_alone_carries_no_such_note(cake_api: TestClient) -> None:
    plan = _plan(cake_api, {"dishes": [{"dish_id": "berry_quark_dessert", "servings": 20}],
                            "stock": [{"product_type": "sugar", "quantity": 1, "unit": "KG"}]})

    assert not any("later recording" in note for note in plan["notes"])


def test_typed_fields_win_over_the_sentence_and_the_note_says_so(cake_api: TestClient) -> None:
    plan = _plan(cake_api, {**TYPED, "needed_by": "2026-11-17", "text": "lasagne for 50 by Monday"})

    assert plan["request"]["dishes"] == TYPED["dishes"] and plan["request"]["needed_by"] == "2026-11-17"
    assert plan["notes"][0] == (
        "Read as: lasagne, 50 servings, by Monday 16 Nov. The typed dishes were used, not the sentence's. The "
        "typed date was used, not the sentence's."
    )


def test_a_day_in_the_sentence_is_counted_from_the_gateways_clock(
    cake_api: TestClient, cake_settings: Settings
) -> None:
    """"On Friday" said on Saturday 14 Nov is the 20th; said on the demo clock's Thursday 12 Nov it is the 13th."""
    plan = _plan(cake_api, {"text": "a chocolate cake for twenty guests on Friday"})

    friday = "2026-11-20" if cake_settings.tta_demo_clock is None else "2026-11-13"
    assert plan["request"]["needed_by"] == friday
    assert plan["request"]["dishes"] == [{"dish_id": "chocolate_cake", "servings": 20}]


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({}, 'Name at least one dish: in `dishes`, or in `text` as a sentence, for example "chocolate cake for 20". '
             + DISHES),
        ({"text": "   "}, 'Name at least one dish: in `dishes`, or in `text` as a sentence, for example "chocolate '
                          'cake for 20". ' + DISHES),
        ({"text": "what is the weather"}, "The sentence names no dish of the recipe table. " + DISHES),
        ({"text": "I want to make tiramisu for 10 people"}, 'No recipe for "tiramisu" in the recipe table. ' + DISHES),
        ({"text": "tiramisu for 10 and chocolate cake for 20"},
         'No recipe for "tiramisu" in the recipe table. ' + DISHES),
        ({"text": "I want to make a chocolate cake"},
         'How many servings of chocolate cake? Write, for example, "chocolate cake for 20".'),
        ({"text": "chocolate cake for 2.5 people"},
         '"2.5" is not read as a number of servings of chocolate cake. Write a whole number from 1 to 5,000 in '
         'digits, for example "chocolate cake for 20".'),
        ({"text": "chocolate cake for 20 on Friday or Monday"},
         "The sentence names 2 days (Monday 16 Nov and Friday 20 Nov). Which day is it needed by?"),
    ],
)
def test_what_cannot_be_read_without_a_guess_is_refused_with_the_question(
    whole_catalog: ProductCatalog, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: dict[str, Any], detail: str
) -> None:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var")
    real = hooks.optional_module
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in NOT_SHOWN else real(name))
    parts = build_parts(settings, catalog=whole_catalog, rate_limit=RateLimit(calls=1000))
    with TestClient(create_app(settings, parts=parts)) as api:
        assert _refused(api, body) == detail
        assert api.get("/v1/audit", headers=BAKERY).json()["events"] == []  # nothing was asked of the gateway


def test_a_text_longer_than_the_limit_is_refused_by_the_schema(cake_api: TestClient) -> None:
    response = cake_api.post("/v1/menus/plan", json={"text": "chocolate cake for 20 " * 40}, headers=BAKERY)

    assert response.status_code == 422


def test_the_cake_is_prepared_and_the_owner_confirms_it(cake_api: TestClient) -> None:
    """Request, lookup, order, approval: the sentence ends as an order the bakery's owner confirms."""
    plan = _plan(cake_api, {"text": SENTENCE})
    offer = cake_api.get(f"/v1/offers/{plan['offer_id']}", headers=BAKERY).json()
    full = offer["options"][1]

    placed = cake_api.post(
        "/v1/orders", json={"offer_id": plan["offer_id"], "option_id": full["option_id"]},
        headers={**BAKERY, "Idempotency-Key": "cake-for-20"},
    )
    assert placed.status_code in (200, 201, 202), placed.text
    assert placed.json()["status"] == "PENDING_APPROVAL"
    waiting = [each for each in cake_api.get("/v1/approvals", headers=OWNER).json()
               if each["order_id"] == placed.json()["order_id"]]
    assert len(waiting) == 1 and waiting[0]["required_roles"] == ["purchasing_manager"]
    decided = cake_api.post(
        f"/v1/approvals/{waiting[0]['approval_id']}/decision",
        json={"decision": "APPROVE", "note": "A cake for 20 on Monday; the sack of sugar is used within the month."},
        headers=OWNER,
    )
    assert decided.status_code == 200, decided.text
    assert (decided.json()["status"], decided.json()["placed_by"]) == ("ORDERED", "HUMAN_APPROVAL")


def test_the_openapi_names_the_sentence_and_its_example(cake_api: TestClient) -> None:
    spec = cake_api.get("/openapi.json").json()

    body = spec["paths"]["/v1/menus/plan"]["post"]["requestBody"]["content"]["application/json"]
    assert body["schema"]["$ref"].endswith("/MenuAsk")
    assert body["examples"]["a_sentence"]["value"] == {"text": SENTENCE}
    ask = spec["components"]["schemas"]["MenuAsk"]
    assert "text" in ask["properties"] and "dishes" not in ask.get("required", [])


# --- the MCP tool ----------------------------------------------------------------------------------------------


def _tools(parts: Parts, monkeypatch: pytest.MonkeyPatch, settings: Settings) -> GatewayTools:
    """The tools of the MCP surface, called as the bakery's agent: the bearer check and the settings the tool
    reads are put in place of the HTTP layer's."""
    tools = GatewayTools(parts.service, parts.tokens.identify)
    bakery = parts.tokens.identify("demo-agent-bakery-cafe")
    monkeypatch.setattr(tools, "_caller", lambda: bakery)
    monkeypatch.setattr(mcp_surface, "get_settings", lambda: settings)
    return tools


def test_the_mcp_tool_takes_the_sentence_and_gives_the_rest_routes_plan(
    cake_parts: Parts, cake_settings: Settings, cake_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _tools(cake_parts, monkeypatch, cake_settings)

    plan = tools.plan_menu(MenuAsk(text=SENTENCE))
    rest = _plan(cake_api, {"text": SENTENCE})

    assert isinstance(plan, MenuPlan)
    assert plan.notes[0] == rest["notes"][0] == "Read as: chocolate cake, 20 servings, by Monday 16 Nov."
    assert plan.notes[-1] == rest["notes"][-1] and plan.notes[-1].endswith(LATER)
    assert [each.sentence for each in plan.dishes[0].ingredients] == [
        each["sentence"] for each in rest["dishes"][0]["ingredients"]
    ]


def test_the_mcp_tool_answers_an_open_question_as_a_problem(
    cake_parts: Parts, cake_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = _tools(cake_parts, monkeypatch, cake_settings)

    answer = tools.plan_menu(MenuAsk(text="tiramisu for 10"))

    assert answer.is_error and answer.structured_content["status"] == 422
    assert answer.structured_content["detail"] == 'No recipe for "tiramisu" in the recipe table. ' + DISHES


def test_the_mcp_tools_argument_is_the_same_body_as_the_rest_route() -> None:
    schema: Callable[[], dict[str, Any]] = MenuAsk.model_json_schema

    assert {"text", "dishes", "stock", "needed_by"} <= set(schema()["properties"])
    assert "dishes" not in schema().get("required", [])
