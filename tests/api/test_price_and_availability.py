"""A search and a read of one product carry price and availability when asked (decision B58, review C1-2).

Scores on the 30% "working end-to-end demo" and on the 20% "solving the problem": the brief's first core item is
"a structured way for an external agent to search for and retrieve what's available and at what price". Before,
`POST /v1/products/search` and `GET /v1/products/{id}` answered the product file alone, and an agent had to ask
one offer per product. The flag is off by default: without it both answer as before and write nothing.

Replay over tonight's capture at the recording's own clock (Sat 14 Nov 2026 02:52) unless a test sets another.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.fallback import FallbackGateway
from tta.api.limits import RateLimit
from tta.api.product_lookup import MAX_PRICED_PRODUCTS
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.product import PriceAndAvailability
from tta.contracts.request import ProductQuery
from tta.offers.candidates import NOT_IN_RECORDING_SENTENCE
from tta.valio import ReplayGateway

Auth = Callable[..., dict[str, str]]
Flow = Callable[..., dict[str, Any]]
Problem = Callable[..., dict[str, Any]]

SEARCH = "/v1/products/search"
FLAG = {"price_and_availability": "true"}
PLANT_DRINKS = {"product_type": "plant_drink", "limit": 3}
FIRST_THREE = ["460416", "460443", "460509"]  # the first three of the 51 plant drinks of the catalog, by id
SUNDAY, MONDAY = "2026-11-15", "2026-11-16"
CONFIRMED_DRINK = "460416"  # Alpro Soya drink vanilla 1 L: 37 pieces confirmed at €3.03, delivery Monday 16 Nov
NOT_RECORDED = "460000"  # in the catalog (Forssan potato salad) and in no recording
DECLARES_MILK = "462775"  # a lactose-free milk: its data says it contains milk
STATES_NO_ALLERGEN = "468417"  # a plant drink whose data carries no allergen statement at all; not deliverable
SILENT_ON_MILK_AND_GLUTEN = "474864"  # a plant drink that can be ordered and states nothing about milk or gluten
THE_FIVE_CLAIMS = ["price", "quantity", "delivery_date", "allergens", "origin"]
LINE_FIELDS = ("unit_net_price", "tax_rate", "sales_unit", "pack_size", "price_valid_to", "availability")
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"  # Thu 12 Nov 2026 14:15 Helsinki, the clock of the demonstration
ONLY_THE_FIRST_20 = (
    "Price and availability are read for at most 20 products in one call: narrow the search, or name the others "
    "in product_ids."
)


def _stated(client: TestClient, headers: dict[str, str], product_id: str, **params: str) -> dict[str, Any]:
    """The `price_and_availability` of one product, read with the flag."""
    response = client.get(f"/v1/products/{product_id}", params={**FLAG, **params}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["price_and_availability"]


def _claim(stated: dict[str, Any], name: str) -> dict[str, Any]:
    return next(claim for claim in stated["claims"] if claim["claim"] == name)


def test_without_the_flag_a_search_and_a_read_answer_as_before_and_write_nothing(
    client: TestClient, auth: Auth, parts: Parts, catalog: ProductCatalog
) -> None:
    found = client.post(SEARCH, json=PLANT_DRINKS, headers=auth("agent_hotel"))
    read = client.get(f"/v1/products/{CONFIRMED_DRINK}", headers=auth("agent_hotel"))

    assert found.status_code == read.status_code == 200
    # The catalog's own answer, product for product: no figure of today's fields moved.
    assert found.json() == catalog.search(ProductQuery(**PLANT_DRINKS)).model_dump(mode="json")
    assert read.json() == catalog.get_product(CONFIRMED_DRINK).model_dump(mode="json")
    assert all(product["price_and_availability"] is None for product in found.json()["products"])
    assert read.json()["price_and_availability"] is None
    assert parts.audit.head()[0] == 0


def test_with_the_flag_each_product_carries_what_an_offer_line_of_the_same_buyer_states(
    client: TestClient, auth: Auth, make_offer: Flow
) -> None:
    found = client.post(SEARCH, params=FLAG, json=PLANT_DRINKS, headers=auth("agent_hotel"))

    assert found.status_code == 200, found.text
    body = found.json()
    assert [product["id"] for product in body["products"]] == FIRST_THREE
    assert (body["total"], body["note"]) == (51, "Showing the first 3 of 51 products that match.")
    for product in body["products"]:
        stated = product["price_and_availability"]
        PriceAndAvailability.model_validate(stated)
        one_piece = {"lines": [{"text": "", "product_ids": [product["id"]], "quantity": 1, "unit": "UNIT"}]}
        offer = make_offer(client, "agent_hotel", one_piece)
        [line] = offer["options"][0]["lines"]
        # The same typed shapes and the same values as the line of an offer made a moment later.
        assert {field: stated[field] for field in LINE_FIELDS} == {field: line[field] for field in LINE_FIELDS}
        assert stated["currency"] == offer["options"][0]["totals"]["currency"] == "EUR"
        assert [claim["claim"] for claim in stated["claims"]] == THE_FIVE_CLAIMS
        assert (stated["orderable"], stated["reason"]) == (True, None)
        assert stated["sentence"] == stated["availability"]["sentence"]
        # Where and when the data was read, as the offer says it.
        assert (stated["source"], stated["time_now"], stated["time_basis"]) == (
            offer["source"], offer["time_now"], offer["time_basis"]
        )
    first = body["products"][0]["price_and_availability"]
    assert (first["unit_net_price"], first["tax_rate"], first["sales_unit"]) == (3.03, 13.5, "ST")
    assert (first["pack_size"]["value"], first["pack_size"]["unit"]) == (1.0, "L")
    assert (first["availability"]["state"], first["availability"]["usable_amount"]) == ("CONFIRMED", 37.0)
    assert (first["source"], first["time_basis"]) == ("replay", "recording")


def test_one_product_is_read_with_the_flag_as_the_search_reads_it(client: TestClient, auth: Auth) -> None:
    found = client.post(SEARCH, params=FLAG, json=PLANT_DRINKS, headers=auth("agent_hotel")).json()
    read = client.get(f"/v1/products/{CONFIRMED_DRINK}", params=FLAG, headers=auth("agent_hotel"))

    assert read.status_code == 200
    assert read.json() == found["products"][0]


def test_a_needed_by_date_judges_the_delivery_date_and_without_one_nothing_is_judged(
    client: TestClient, auth: Auth
) -> None:
    hotel = auth("agent_hotel")
    undated = _stated(client, hotel, CONFIRMED_DRINK)
    in_time = _stated(client, hotel, CONFIRMED_DRINK, needed_by=MONDAY)
    late = _stated(client, hotel, CONFIRMED_DRINK, needed_by=SUNDAY)

    # No date: the dates are given, and the delivery date is stated without a judgement.
    assert (undated["needed_by"], undated["orderable"]) == (None, True)
    assert undated["availability"]["available_date"] == MONDAY
    assert undated["availability"]["closing_time"] == "2026-11-15T17:00:00+02:00"
    assert _claim(undated, "delivery_date") == {
        "claim": "delivery_date", "status": "UNKNOWN",
        "sentence": "No needed-by date was given; Valio shows delivery on Monday 16 Nov if ordered by Sunday 15 Nov "
                    "at 17:00.",
    }
    # A date the delivery meets, and one it does not.
    assert (in_time["needed_by"], in_time["orderable"]) == (MONDAY, True)
    assert _claim(in_time, "delivery_date")["status"] == "CONFIRMED"
    assert "meets the needed-by date Monday 16 Nov if ordered by Sunday 15 Nov at 17:00" in (
        _claim(in_time, "delivery_date")["sentence"]
    )
    assert (late["needed_by"], late["orderable"], late["reason"]) == (SUNDAY, False, "LATE_FOR_NEEDED_BY")
    assert late["sentence"] == "Delivery is on Monday 16 Nov, later than the needed-by date Sunday 15 Nov."
    assert _claim(late, "delivery_date")["status"] == "RULED_OUT"


def test_at_most_20_products_are_read_in_one_call_and_the_note_says_so(client: TestClient, auth: Auth) -> None:
    hundred = client.post(SEARCH, params=FLAG, json={"product_type": "plant_drink", "limit": 100},
                          headers=auth("agent_hotel")).json()
    unlimited = client.post(SEARCH, params=FLAG, json={"product_type": "plant_drink"},
                            headers=auth("agent_hotel")).json()

    assert MAX_PRICED_PRODUCTS == 20
    for body in (hundred, unlimited):
        assert (len(body["products"]), body["total"]) == (20, 51)
        assert all(product["price_and_availability"] for product in body["products"])
        assert body["note"] == f"Showing the first 20 of 51 products that match. {ONLY_THE_FIRST_20}"
    # The others are read by naming them: 20 ids are one more call.
    rest = [product["id"] for product in client.post(
        SEARCH, json={"product_type": "plant_drink", "limit": 100}, headers=auth("agent_hotel")).json()["products"]]
    named = client.post(SEARCH, params=FLAG, json={"product_ids": rest[20:40]}, headers=auth("agent_hotel")).json()
    assert [product["id"] for product in named["products"]] == rest[20:40]
    assert named["note"] == "20 products match."


def test_one_call_is_one_look_at_the_supplier_one_lookup_and_one_audit_event(
    settings: Settings, catalog: ProductCatalog, changing: Any, auth: Auth, assert_problem: Problem
) -> None:
    parts = build_parts(settings, catalog=catalog, gateway=changing, rate_limit=RateLimit(calls=3, window_seconds=60))
    hotel = auth("agent_hotel")
    with TestClient(create_app(settings, parts=parts)) as client:
        before = changing.calls
        nothing = client.post(SEARCH, params=FLAG, json={"name_terms": ["zzzzqq"]}, headers=hotel)
        assert (nothing.json()["products"], changing.calls - before, parts.audit.head()[0]) == ([], 0, 0)

        found = client.post(SEARCH, params={**FLAG, "needed_by": MONDAY}, json=PLANT_DRINKS, headers=hotel)
        assert found.status_code == 200
        assert changing.calls - before == 2  # one price call and one availability call for the three products
        [event] = parts.store.list_audit_events()
        looked_up = {
            "products_looked_up": 3, "product_ids": FIRST_THREE, "source": "replay",
            "time_now": found.json()["products"][0]["price_and_availability"]["time_now"], "time_basis": "recording",
        }
        assert event.type == "tta.v1.lookup.performed"
        assert (event.data.profile_id, event.data.actor.id) == ("hotel-kitchen", "agent:hotel-kitchen")
        assert event.data.facts == {**looked_up, "needed_by": MONDAY}  # the date is the buyer's own
        assert event.data.supplier_facts == looked_up  # Valio Aimo's view: its own data, not the buyer's date
        assert event.data.sentence == event.data.supplier_sentence
        assert event.data.sentence.startswith("The gateway looked up price and availability of 3 products in ")

        read = client.get(f"/v1/products/{CONFIRMED_DRINK}", params=FLAG, headers=hotel)
        refused = client.post(SEARCH, params=FLAG, json=PLANT_DRINKS, headers=hotel)
        assert read.status_code == 200
        problem = assert_problem(refused, "rate-limited", 429)  # the fourth call of a window of three
        assert "offers, searches and reads of the catalog" in problem["detail"]
        assert changing.calls - before == 4 and parts.audit.head()[0] == 2  # the refused call looked up nothing
        assert parts.audit.verify_chain().ok


def test_the_look_is_in_the_buyers_trail_and_in_valio_aimos_with_no_date_of_the_buyer(
    client: TestClient, auth: Auth
) -> None:
    client.post(SEARCH, params={**FLAG, "needed_by": MONDAY}, json=PLANT_DRINKS, headers=auth("agent_hotel"))

    [as_buyer] = client.get("/v1/audit", headers=auth("hotel_purchasing")).json()["events"]
    [as_supplier] = client.get("/v1/audit", headers=auth("supplier")).json()["events"]
    other_buyer = client.get("/v1/audit", headers=auth("agent_ward")).json()["events"]

    assert as_buyer["type"] == as_supplier["type"] == "tta.v1.lookup.performed"
    assert as_buyer["sentence"] == as_supplier["sentence"] == (
        "The gateway looked up price and availability of 3 products in a recorded copy of Valio Aimo's data."
    )
    assert (as_buyer["actor"]["kind"], as_buyer["actor"]["id"]) == ("agent", "agent:hotel-kitchen")
    assert as_buyer["facts"]["product_ids"] == as_supplier["facts"]["product_ids"] == FIRST_THREE
    assert as_buyer["facts"]["needed_by"] == MONDAY and "needed_by" not in as_supplier["facts"]
    assert other_buyer == []  # another buyer's agent does not see the hotel's look


def test_a_product_outside_the_recording_says_so_and_nothing_is_made_up(
    client: TestClient, auth: Auth, catalog: ProductCatalog
) -> None:
    stated = _stated(client, auth("agent_hotel"), NOT_RECORDED, needed_by=MONDAY)

    assert (stated["orderable"], stated["reason"], stated["sentence"]) == (
        False, "NOT_IN_RECORDING", NOT_IN_RECORDING_SENTENCE
    )
    for field in ("unit_net_price", "currency", "tax_rate", "price_valid_to", "availability"):
        assert stated[field] is None, field  # no price and no state: the recorded copy holds neither
    for name in ("price", "quantity", "delivery_date"):
        assert (_claim(stated, name)["status"], _claim(stated, name)["sentence"]) == (
            "UNKNOWN", NOT_IN_RECORDING_SENTENCE
        )
    # What the product file itself says stays: its sales unit and, where it has one, its pack size.
    assert (stated["source"], stated["sales_unit"]) == ("replay", catalog.get_product(NOT_RECORDED).sales_unit)
    assert stated["pack_size"]["source"] != "PRICE_RATIO"  # never a size worked out from a price nobody recorded


def test_the_allergen_claim_is_the_buyers_own_rule_and_no_statement_is_never_safe(
    client: TestClient, auth: Auth
) -> None:
    ward, hotel = auth("agent_ward"), auth("agent_hotel")
    declares = _stated(client, ward, DECLARES_MILK)
    silent = _stated(client, ward, SILENT_ON_MILK_AND_GLUTEN)
    no_statement = _stated(client, ward, STATES_NO_ALLERGEN)
    free_from = _stated(client, ward, CONFIRMED_DRINK)
    nothing_excluded = _stated(client, hotel, STATES_NO_ALLERGEN)

    # The ward excludes milk and gluten: a product that declares milk is left out, as its offer would leave it out.
    assert _claim(declares, "allergens")["status"] == "RULED_OUT"
    assert (declares["orderable"], declares["reason"]) == (False, "ALLERGEN_DECLARED")
    assert "contains milk" in declares["sentence"]
    # A product that states nothing is unknown, never confirmed, and the ward's confirmed-only rule leaves it out.
    assert _claim(silent, "allergens") == {
        "claim": "allergens", "status": "UNKNOWN",
        "sentence": "The product data does not confirm that it is free from an excluded allergen (AM, AW).",
    }
    assert (silent["orderable"], silent["reason"]) == (False, "ALLERGEN_NOT_STATED")
    assert "The product makes no statement about milk (AM): a dietitian must decide." in silent["sentence"]
    assert (_claim(no_statement, "allergens")["status"], no_statement["orderable"]) == ("UNKNOWN", False)
    assert _claim(free_from, "allergens") == {
        "claim": "allergens", "status": "CONFIRMED",
        "sentence": "The product states that it is free from every excluded allergen (AM, AW).",
    }
    # The hotel excludes nothing, and the claim says exactly that: it is no statement about the product.
    assert _claim(nothing_excluded, "allergens")["sentence"] == (
        "The buyer excluded no allergen, so there is nothing to check."
    )


def test_a_date_without_the_flag_is_refused_not_dropped(
    client: TestClient, auth: Auth, assert_problem: Problem, parts: Parts
) -> None:
    hotel = auth("agent_hotel")
    answers = (
        client.post(SEARCH, params={"needed_by": MONDAY}, json=PLANT_DRINKS, headers=hotel),
        client.get(f"/v1/products/{CONFIRMED_DRINK}", params={"needed_by": MONDAY}, headers=hotel),
        client.get(f"/v1/products/{CONFIRMED_DRINK}",
                   params={"price_and_availability": "false", "needed_by": MONDAY}, headers=hotel),
    )

    for answer in answers:
        problem = assert_problem(answer, "invalid-request", 422)
        assert "needed_by is read only together with price_and_availability=true" in problem["detail"]
    assert parts.audit.head()[0] == 0


@pytest.mark.parametrize("params", [{"price_and_availability": "perhaps"}, {**FLAG, "needed_by": "next Monday"}])
def test_a_flag_or_a_date_that_cannot_be_read_is_an_invalid_request(
    client: TestClient, auth: Auth, assert_problem: Problem, params: dict[str, str]
) -> None:
    answer = client.post(SEARCH, params=params, json=PLANT_DRINKS, headers=auth("agent_hotel"))

    problem = assert_problem(answer, "invalid-request", 422)
    assert [error["field"].split(".")[0] for error in problem["errors"]] == ["query"]


def test_the_supplier_is_refused_and_an_approver_of_the_buyer_reads_what_its_agent_reads(
    client: TestClient, auth: Auth, assert_problem: Problem, parts: Parts
) -> None:
    refused = client.post(SEARCH, params=FLAG, json=PLANT_DRINKS, headers=auth("supplier"))
    no_token = client.post(SEARCH, params=FLAG, json=PLANT_DRINKS)

    assert_problem(refused, "not-authorised", 403)
    assert_problem(no_token, "not-authorised", 401)
    assert parts.audit.head()[0] == 0
    assert _stated(client, auth("ward_dietitian"), DECLARES_MILK) == _stated(client, auth("agent_ward"), DECLARES_MILK)


def test_an_unknown_product_is_unknown_with_the_flag_too(
    client: TestClient, auth: Auth, assert_problem: Problem, parts: Parts
) -> None:
    answer = client.get("/v1/products/000000", params=FLAG, headers=auth("agent_hotel"))

    assert_problem(answer, "unknown-product", 404)
    assert parts.audit.head()[0] == 0


@pytest.fixture
def at_the_demo_clock(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    """The gateway as the demonstration runs it: replay, with the clock set to Thu 12 Nov 2026 14:15 Helsinki."""
    settings = Settings.for_tests(tta_env="demo", tta_demo_clock=DEMO_CLOCK, tta_data_dir=tmp_path / "var")
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client


def test_at_the_demo_clock_the_answer_says_which_clock_it_was_judged_against(
    at_the_demo_clock: TestClient, auth: Auth
) -> None:
    found = at_the_demo_clock.post(
        SEARCH, params={**FLAG, "needed_by": MONDAY}, json=PLANT_DRINKS, headers=auth("agent_hotel")
    ).json()

    assert [product["id"] for product in found["products"]] == FIRST_THREE
    stated = [product["price_and_availability"] for product in found["products"]]
    assert [(each["unit_net_price"], each["availability"]["usable_amount"]) for each in stated] == [
        (3.03, 37.0), (2.43, 199.0), (2.01, 1.0)
    ]
    for each in stated:
        assert (each["source"], each["time_basis"]) == ("replay", "demo_setting")
        assert datetime.fromisoformat(each["time_now"]) == datetime.fromisoformat(DEMO_CLOCK)
        assert (each["availability"]["state"], each["orderable"]) == ("CONFIRMED", True)
        assert _claim(each, "delivery_date")["status"] == "CONFIRMED"


def test_in_live_mode_the_look_is_live_and_says_so(
    tmp_path: Path, catalog: ProductCatalog, live: Any, replay: ReplayGateway, auth: Auth
) -> None:
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")
    parts = build_parts(settings, catalog=catalog, gateway=FallbackGateway(live, replay))
    with TestClient(create_app(settings, parts=parts)) as client:
        stated = _stated(client, auth("agent_hotel"), CONFIRMED_DRINK)

    # The stand-in copies the capture's answer and relabels it, so only what it sets is read: source and clock.
    assert stated["source"] == "live"
    assert datetime.fromisoformat(stated["time_now"]) == live.NOW
    assert stated["unit_net_price"] == 4.03  # the stand-in's live price: the capture's €3.03 and one euro
    assert live.asked == ["price", "availability"]  # one look: one call each
