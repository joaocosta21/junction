"""The recipe plan on `/shop` (task U5): "I want to make a chocolate cake for 20 people" typed in the request box.

Scores on the 30% demo (a sentence → the ingredients with product, packs, price and stock → one offer → an order a
person confirms, all on the shop page) and the 20% "how precisely the agent matches what the buyer asked for" (the
servings scale the recipe, a wholesale pack's leftover is said, a dish the table lacks is refused with the list of
dishes, a sentence without servings is asked about). `/healthz` says that some products were recorded later.

The page sends a sentence to the reader first, as for any request; only a sentence the reader does not read as a
product request goes to `POST /shop/api/menus/plan`, which says whether it names a dish of the recipe table
(`dishes_named`, `unknown_dishes`), so the page holds no dish list. Figures measured at the recording's own clock
(Saturday 14 Nov 2026 02:52) unless said otherwise.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.ui
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.menus.recipes import dish_names, shipped_recipes
from tta.valio import ReplayGateway

API = "/shop/api"
SHOP_JS = Path(tta.ui.__file__).parent / "static" / "shop" / "js"
CAKE_20 = "I want to make a chocolate cake for 20 people by Monday"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
LATER = re.compile(r"^\d+ of the \d+ products of this offer have their price and stock from the later recording")
NOT_RECEIVED = "settings-not-received"
MENU_EXAMPLE = "A chocolate cake for 20 by Monday"


def _headers(kitchen: str = "bakery") -> dict[str, str]:
    return {"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}


def _call(client: TestClient, method: str, path: str, kitchen: str = "bakery", **kwargs: Any) -> Any:
    return client.request(method, API + path, headers=_headers(kitchen), **kwargs)


def _bakery(client: TestClient, settings: dict[str, Any]) -> None:
    assert _call(client, "PUT", "/kitchen", json=settings).status_code == 200


def _plan(client: TestClient, text: str, kitchen: str = "bakery") -> Any:
    return _call(client, "POST", "/menus/plan", kitchen, json={"text": text})


@pytest.fixture
def bakery_settings(shop_profile_settings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """What the shop page sends for Kallio Bakery (kitchens.js), which equals its profile file."""
    return shop_profile_settings["bakery-cafe"]


def _totals(offer: dict[str, Any]) -> list[Decimal]:
    return [Decimal(str(option["totals"]["net"])) for option in offer["options"]]


# --- the route ---------------------------------------------------------------------------------------------------


def test_the_bakerys_chocolate_cake_for_20_is_planned_from_the_sentence(
    client: TestClient, bakery_settings: dict[str, Any]
) -> None:
    _bakery(client, bakery_settings)

    answer = _plan(client, CAKE_20)

    assert answer.status_code == 200, answer.text
    plan = answer.json()
    assert plan["notes"][0] == "Read as: chocolate cake, 20 servings, by Monday 16 Nov."
    (cake,) = plan["dishes"]
    assert (cake["dish_id"], cake["servings"]) == ("chocolate_cake", 20)
    assert [one["recipe_product_type"] for one in cake["ingredients"]] == [
        "flour", "sugar", "eggs", "butter", "cocoa_powder", "milk", "baking_powder",
    ]
    assert all(one["role"] and one["request_line_index"] is not None for one in cake["ingredients"])
    # the products of the baking recording are said once, as the plan's last note
    assert LATER.match(plan["notes"][-1]), plan["notes"][-1]
    offer = _call(client, "GET", f"/offers/{plan['offer_id']}").json()
    assert _totals(offer) == [Decimal("15.19"), Decimal("61.02")]
    assert [option["decision"]["required_roles"] for option in offer["options"]] == [["purchasing_manager"]] * 2


def test_at_the_demo_clock_the_second_option_of_the_cake_for_20_costs_104_65(
    tmp_path: Path, catalog: ProductCatalog, bakery_settings: dict[str, Any]
) -> None:
    from tta.api.app import create_app
    from tta.api.wiring import build_parts

    settings = Settings.for_tests(tta_data_dir=tmp_path / "demo", tta_demo_clock=DEMO_CLOCK)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        _bakery(client, bakery_settings)
        plan = _plan(client, CAKE_20).json()
        offer = _call(client, "GET", f"/offers/{plan['offer_id']}").json()

    assert _totals(offer) == [Decimal("15.19"), Decimal("104.65")]


@pytest.mark.parametrize("servings", [2, 200])
def test_the_recipe_scales_for_2_and_for_200_and_each_ingredient_says_what_is_left_over(
    client: TestClient, bakery_settings: dict[str, Any], servings: int
) -> None:
    _bakery(client, bakery_settings)

    plan = _plan(client, f"I want to make a chocolate cake for {servings} people by Monday").json()

    assert plan["notes"][0] == f"Read as: chocolate cake, {servings} servings, by Monday 16 Nov."
    flour = plan["dishes"][0]["ingredients"][0]
    assert Decimal(str(flour["needed"])) == Decimal("0.02") * servings  # 20 g of flour per serving
    offer = _call(client, "GET", f"/offers/{plan['offer_id']}").json()
    assert offer["options"]
    if servings == 2:  # a wholesale pack against a small need: every ingredient that is offered says the rest
        offered = [one for one in plan["dishes"][0]["ingredients"] if "Offer" in one["sentence"]]
        assert offered and all("left over" in one["sentence"] for one in offered)


def test_the_plans_offer_is_one_of_this_customers_book_and_is_confirmed_like_any_other(
    client: TestClient, bakery_settings: dict[str, Any]
) -> None:
    _bakery(client, bakery_settings)
    plan = _plan(client, CAKE_20).json()

    other = _call(client, "GET", f"/offers/{plan['offer_id']}", "hotel")
    order = _call(client, "POST", "/orders", json={"offer_id": plan["offer_id"], "option_id": "opt_1",
                                                   "key": "test.bakery.cake"}).json()

    assert other.status_code == 404  # another customer's book has no such offer
    assert order["status"] == "PENDING_APPROVAL"  # a person confirms: sugar, eggs and butter are not covered
    assert [one["order_id"] for one in _call(client, "GET", "/approvals").json()] == [order["order_id"]]


def test_a_dish_the_table_does_not_have_is_refused_with_the_list_of_dishes(
    client: TestClient, bakery_settings: dict[str, Any]
) -> None:
    _bakery(client, bakery_settings)

    answer = _plan(client, "tiramisu for 10")

    assert answer.status_code == 422
    problem = answer.json()
    assert problem["detail"].startswith('No recipe for "tiramisu" in the recipe table. The dishes are: ')
    assert "chocolate cake" in problem["detail"] and "lasagne" in problem["detail"]
    assert (problem["dishes_named"], problem["unknown_dishes"]) == ([], ["tiramisu"])


def test_a_dish_without_servings_is_asked_about(client: TestClient, bakery_settings: dict[str, Any]) -> None:
    _bakery(client, bakery_settings)

    answer = _plan(client, "chocolate cake")

    assert answer.status_code == 422
    problem = answer.json()
    assert problem["detail"] == 'How many servings of chocolate cake? Write, for example, "chocolate cake for 20".'
    assert (problem["dishes_named"], problem["unknown_dishes"]) == (["chocolate cake"], [])


def test_a_product_request_names_no_dish_so_the_page_keeps_the_readers_question(
    client: TestClient, shop_profile_settings: dict[str, dict[str, Any]]
) -> None:
    assert _call(client, "PUT", "/kitchen", "hotel", json=shop_profile_settings["hotel-kitchen"]).status_code == 200

    answer = _plan(client, "1,000 litres of lactose-free milk by Monday", "hotel")

    assert answer.status_code == 422
    assert (answer.json()["dishes_named"], answer.json()["unknown_dishes"]) == ([], [])
    assert _call(client, "GET", "/orders", "hotel").json() == []


def test_the_plan_route_has_the_guards_of_the_other_shop_routes(client: TestClient) -> None:
    body = {"text": CAKE_20}

    no_header = client.post(API + "/menus/plan", json=body, headers={"X-Shop-Kitchen": "bakery"})
    cross_site = client.post(API + "/menus/plan", json=body, headers={**_headers(), "Sec-Fetch-Site": "cross-site"})
    no_kitchen = client.post(API + "/menus/plan", json=body, headers={"X-Shop-Request": "1"})
    not_received = _plan(client, CAKE_20)
    unknown_field = _call(client, "POST", "/menus/plan", json={"text": CAKE_20, "who": "me"})

    assert (no_header.status_code, cross_site.status_code, no_kitchen.status_code) == (403, 403, 400)
    assert not_received.status_code == 409 and not_received.json()["type"] == NOT_RECEIVED
    assert unknown_field.status_code == 422


# --- the reader, which the page asks first --------------------------------------------------------------------


@pytest.fixture
def reading_client(make_client: Any, settings: Settings, catalog: ProductCatalog) -> TestClient:
    package = pytest.importorskip("tta.agent")
    given = {
        "settings": settings,
        "clock": ReplayGateway(settings.replay_capture_dir).clock,
        "product_type_keys": catalog.product_type_keys(),
    }
    return make_client(request_parser=package.build_request_parser(**given))


@pytest.mark.parametrize("text", [CAKE_20, MENU_EXAMPLE, "tiramisu for 10", "chocolate cake"])
def test_the_reader_does_not_read_a_dish_sentence_as_a_product_request(
    reading_client: TestClient, bakery_settings: dict[str, Any], text: str
) -> None:
    """The page plans a sentence only when the reader did not read it: a reader that read the cake as a product
    would send the bakery a product offer instead of the recipe."""
    _bakery(reading_client, bakery_settings)

    answer = _call(reading_client, "POST", "/read", json={"text": text})

    assert answer.status_code != 200 or not answer.json()["request"]["lines"], answer.text


# --- /healthz says that some products were recorded later -----------------------------------------------------


@pytest.mark.parametrize("demo_clock", [None, DEMO_CLOCK])
def test_health_says_which_products_were_recorded_later(
    tmp_path: Path, catalog: ProductCatalog, demo_clock: str | None
) -> None:
    from tta.api.app import create_app
    from tta.api.wiring import build_parts

    extra = {} if demo_clock is None else {"tta_demo_clock": demo_clock}
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", **extra)
    replay = ReplayGateway(settings.replay_capture_dir)
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        clock = client.get("/healthz").json()["clock"]

    assert replay.join_sentence is not None
    assert clock["sentence"].endswith(" " + replay.join_sentence)
    assert clock["sentence"].count(replay.join_sentence) == 1
    (later,) = clock["later_recordings"]
    assert (later["name"], later["product_count"]) == ("2026-11-14-baking", 394)
    assert later["recorded_at"].startswith("2026-11-14T21:12")


# --- the page --------------------------------------------------------------------------------------------------


def _read(name: str) -> str:
    return (SHOP_JS / name).read_text(encoding="utf-8")


def test_the_page_asks_the_plan_route_and_holds_no_dish_list() -> None:
    every = {path.name: path.read_text(encoding="utf-8") for path in SHOP_JS.rglob("*.js")}
    names = [name for each in dish_names(shipped_recipes()).values() for name in each]

    assert 'call(kitchen, "POST", "/menus/plan", { text })' in _read("api.js")
    assert "plan.js" in every and "dishes_named" in _read("views/assistant.js")
    for file, source in every.items():
        folded = source.casefold().replace(MENU_EXAMPLE.casefold(), "")
        assert [name for name in names if re.search(rf"\b{re.escape(name)}\b", folded)] == [], file


def test_the_bakerys_menu_example_is_kept_out_of_the_examples_the_reading_table_reads() -> None:
    """tests/agent/test_reading_table.py reads each customer's `examples: [` as product requests: a dish sentence is
    not one, so the chip lives in `MENU_EXAMPLES`."""
    source = _read("kitchens.js")

    assert source.count(f'"{MENU_EXAMPLE}"') == 1
    assert source.index(f'"{MENU_EXAMPLE}"') > source.index("export const MENU_EXAMPLES")
    assert "examples: [" not in source[source.index("export const MENU_EXAMPLES"):]
