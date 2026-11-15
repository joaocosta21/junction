"""Suggestions on an offer, accepted as a new request, and written to the audit trail (P15 R3, R4b; L4-2d).

Scores on the 20% "solving the problem and user need" (the forgotten item and the trend arrive with the offer) and
the 20% "autonomy and controls" (a suggestion never adds itself to an order; what was shown, not shown and accepted
is logged, and Valio Aimo's view never says which requirement of the buyer's dropped one). Figures are measured
offline at the recording's own clock (Saturday 14 Nov 2026 02:52).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

import tta.api.suggesting as suggesting
from tta.api import create_app
from tta.api.fallback import FallbackGateway
from tta.api.sandbox import KITCHEN_AGENT
from tta.api.suggesting import NEVER_ADDED, NOT_COMPUTED, REASONS_NOT_READ
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity, IdentityKind
from tta.contracts.ports import GatewayService
from tta.contracts.request import PurchaseRequest
from tta.suggestions import DroppedSuggestion, SuggestionList

MONDAY = "2026-11-16"
TOKENS = {"hotel": "demo-agent-hotel-kitchen", "ward": "demo-agent-allergy-ward",
          "school": "demo-agent-school-kitchen", "bakery": "demo-agent-bakery-cafe",
          "supplier": "demo-supplier-valio-aimo"}
HOTEL_MILK = {"needed_by": MONDAY, "lines": [
    {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]}
SCHOOL_WEEK = {"needed_by": MONDAY, "lines": [
    {"text": "120 L of milk 462775", "product_ids": ["462775"], "quantity": 120, "unit": "L"},
    {"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"}]}
CREAM = "463797"  # the hotel's forgotten item: cooking cream, 10 L, +€33.10
FORGOTTEN_CREAM = "sug_forgotten_item_463797_hotel-kitchen"
SHOWN, ACCEPTED = "tta.v1.suggestions.shown", "tta.v1.suggestion.accepted"
STANDING_ORDERS = {"hotel": 1, "ward": 1, "school": 1, "bakery": 1}

HOTEL_AGENT = Identity(kind=IdentityKind.AGENT, id="agent:hotel-kitchen", display_name="Hotel kitchen agent (demo)",
                       profile_id="hotel-kitchen")
SCHOOL_AGENT = HOTEL_AGENT.model_copy(update={"id": "agent:school-kitchen", "profile_id": "school-kitchen"})

Offer = dict[str, Any]


def _auth(who: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {TOKENS[who]}"}
    return headers if key is None else {**headers, "Idempotency-Key": key}


def _offer(client: TestClient, who: str, body: dict[str, Any]) -> Offer:
    answer = client.post("/v1/offers", json=body, headers=_auth(who))
    assert answer.status_code == 201, answer.text
    return answer.json()


def _events(client: TestClient, who: str, offer_id: str, kind: str, reader: str | None = None) -> list[dict[str, Any]]:
    params = {"offer_id": offer_id} | ({"reader": reader} if reader else {})
    answer = client.get("/v1/audit", params=params, headers=_auth(who))
    assert answer.status_code == 200, answer.text
    return [event for event in answer.json()["events"] if event["type"] == kind]


def _kinds(offer: Offer) -> list[tuple[str, str]]:
    return [(each["kind"], each["product_id"]) for each in offer["suggestions"]]


def _dropped(client: TestClient, who: str, offer: Offer) -> dict[str, str]:
    """Product id -> why it was not shown, from the buyer's log of the offer."""
    shown, = _events(client, who, offer["offer_id"], SHOWN)
    return {each["product_id"]: each["reason"] for each in shown["facts"]["suggestions"]["dropped"]}


# --- on the offer -----------------------------------------------------------------------------------------


def test_the_hotels_usual_milk_gets_the_forgotten_cream_and_valio_aimos_own_suggestion_stays_silent(
    client: TestClient,
) -> None:
    offer = _offer(client, "hotel", HOTEL_MILK)

    assert offer["options"][0]["totals"]["net"] == 248.0  # the option is what it was without suggestions
    assert _kinds(offer) == [("FORGOTTEN_ITEM", CREAM)]
    forgotten, = offer["suggestions"]
    assert forgotten["effect"]["net_change_eur"] == 33.1 and forgotten["stock_confirmed"] is True
    assert forgotten["serves"] == "BUYER"
    # Silence beats a weak suggestion (SG): Valio Aimo's own candidates are logged with why they were not shown.
    assert _dropped(client, "hotel", offer) == {"462775": "STOCK_TOO_LOW", "463047": "DIETARY_CLAIM_MISSING"}
    assert all(line["product_id"] != CREAM for option in offer["options"] for line in option["lines"])
    stored = client.get(f"/v1/offers/{offer['offer_id']}", headers=_auth("hotel")).json()
    assert stored["suggestions"] == offer["suggestions"]


def test_accepting_is_a_new_request_that_builds_a_new_offer_and_is_recorded(client: TestClient) -> None:
    offer = _offer(client, "hotel", HOTEL_MILK)
    forgotten = offer["suggestions"][0]
    assert forgotten["accept_request"]["accepted_suggestion_id"] == forgotten["suggestion_id"] == FORGOTTEN_CREAM

    accepted = _offer(client, "hotel", forgotten["accept_request"])

    assert accepted["offer_id"] != offer["offer_id"]
    assert accepted["options"][0]["totals"]["net"] == 281.1  # €248.00 + €33.10
    assert [line["product_id"] for line in accepted["options"][0]["lines"]] == ["469363", CREAM]
    assert accepted["options"][0]["decision"]["verdict"] == "APPROVAL"  # accepting is not an approval
    event, = _events(client, "hotel", offer["offer_id"], ACCEPTED)
    assert accepted["offer_id"] in event["sentence"] and "accepting is not an approval" in event["sentence"]
    seen_by_valio, = _events(client, "supplier", offer["offer_id"], ACCEPTED)
    assert "forgotten item" in seen_by_valio["sentence"] and "33.10" not in seen_by_valio["sentence"]


def test_an_offer_that_shows_or_drops_a_suggestion_writes_one_event_and_the_chain_still_verifies(
    client: TestClient, parts: Parts,
) -> None:
    offer = _offer(client, "hotel", HOTEL_MILK)
    _offer(client, "hotel", offer["suggestions"][0]["accept_request"])

    shown, = _events(client, "hotel", offer["offer_id"], SHOWN)
    assert "1 suggestion was shown" in shown["sentence"] and CREAM in shown["sentence"]
    assert "2 were not shown" in shown["sentence"] and "462775" in shown["sentence"]
    verified = parts.audit.verify_chain()
    assert verified.ok, verified


def test_valio_aimos_view_never_says_which_requirement_of_the_buyers_dropped_a_suggestion(
    client: TestClient,
) -> None:
    offer = _offer(client, "school", SCHOOL_WEEK)

    buyer, = _events(client, "school", offer["offer_id"], SHOWN)
    valio, = _events(client, "supplier", offer["offer_id"], SHOWN)
    assert "tree nuts (AN)" in buyer["sentence"]  # the buyer reads why the yoghurt 464517 was not shown
    seen = json.dumps(valio)
    assert "for a requirement of the buyer's (which one is not shown)" in valio["sentence"]
    for word in ("tree nut", "peanut", "sesame", "ALLERGEN", "allergen", "464517", "(AN)", "(AP)", "(AS)"):
        assert word not in seen, word
    assert set(valio["facts"]["suggestions"]["dropped_by_reason"]) == {"BUYER_REQUIREMENT"}


def test_without_its_standing_order_the_school_gets_no_trend(client: TestClient) -> None:
    offer = _offer(client, "school", SCHOOL_WEEK)  # `Settings.for_tests` starts with an empty order book

    assert _kinds(offer) == []
    # Valio Aimo's own oat drink 470889 fits the school's allergens and stays silent: no benefit it can state.
    assert _dropped(client, "school", offer)["470889"] == "NO_STATED_BENEFIT"


def test_the_schools_oat_drink_trend_comes_from_the_standing_order_loaded_at_start(
    with_standing_orders: TestClient,
) -> None:
    offer = _offer(with_standing_orders, "school", SCHOOL_WEEK)

    assert _kinds(offer) == [("QUANTITY_TREND", "470863")]
    trend = offer["suggestions"][0]
    assert "about 84 L in your last 3 orders, 70 L in the 3 before." in trend["sentence"]
    assert "Your standing order still says 60 L. Renew once at 84 L? For 84 L: €117.60." in trend["sentence"]
    assert trend["accept_request"]["standing_order_id"] == "so_school_weekly"


def test_scenario_1_keeps_its_options_and_totals(client: TestClient, scenario_1: dict[str, Any]) -> None:
    offer = _offer(client, "hotel", scenario_1)

    best, alternative, completed = offer["options"]  # the third since decision B56
    assert sum(line["covers"] for line in best["lines"]) == 435 and best["totals"]["net"] == 1083.39
    assert [(line["product_id"], line["quantity"]) for line in best["lines"]] == [("469363", 384), ("462775", 51)]
    assert [(line["product_id"], line["quantity"]) for line in alternative["lines"]] == [("464306", 1000)]
    assert alternative["totals"]["net"] == 1010.0
    assert [(line["product_id"], line["quantity"]) for line in completed["lines"]] == [
        ("469363", 384), ("462775", 51), ("463380", 565),
    ]
    assert sum(line["covers"] for line in completed["lines"]) == 1000 and completed["totals"]["net"] == 2580.64


# --- what is already ordered, the setting, a failure --------------------------------------------------------


def test_a_product_in_an_order_waiting_for_the_same_date_is_not_suggested_again(client: TestClient) -> None:
    first = _offer(client, "hotel", HOTEL_MILK)
    with_cream = _offer(client, "hotel", first["suggestions"][0]["accept_request"])
    body = {"offer_id": with_cream["offer_id"], "option_id": with_cream["options"][0]["option_id"]}
    placed = client.post("/v1/orders", json=body, headers=_auth("hotel", "l42d-cream-1"))
    assert placed.status_code == 201 and placed.json()["status"] == "PENDING_APPROVAL"

    again = _offer(client, "hotel", HOTEL_MILK)

    assert CREAM not in [each["product_id"] for each in again["suggestions"]]
    shown, = _events(client, "hotel", again["offer_id"], SHOWN)
    dropped = {each["product_id"]: each["reason"] for each in shown["facts"]["suggestions"]["dropped"]}
    assert dropped[CREAM] == "ALREADY_ORDERED"


def test_the_setting_switches_valio_aimos_own_suggestion_off_and_keeps_the_buyers(
    settings: Settings, catalog: ProductCatalog,
) -> None:
    assert Settings.for_tests().tta_supplier_suggestions is True  # decision B31: on by default
    off = settings.model_copy(update={"tta_supplier_suggestions": False})
    with TestClient(create_app(off, parts=build_parts(off, catalog=catalog))) as client:
        offer = _offer(client, "hotel", HOTEL_MILK)

    assert _kinds(offer) == [("FORGOTTEN_ITEM", CREAM)]


def test_a_failure_in_the_suggestions_never_fails_the_offer(
    client: TestClient, parts: Parts, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("a fault with the text do-not-show-this-to-a-caller")

    monkeypatch.setattr(suggesting, "suggestions_for", broken)

    offer = _offer(client, "hotel", HOTEL_MILK)

    assert offer["options"][0]["totals"]["net"] == 248.0 and offer["suggestions"] == []
    assert NOT_COMPUTED in offer["notes"] and "do-not-show-this" not in json.dumps(offer)
    # The trail tells "not computed" from "nothing to suggest" (review S5): the event holds the reason.
    event, = _events(client, "hotel", offer["offer_id"], SHOWN)
    assert event["facts"]["suggestions"]["notes"] == [NOT_COMPUTED] and event["facts"]["suggestions"]["shown"] == []
    assert parts.audit.verify_chain().ok
    assert parts.service.get_offer_suggestions(HOTEL_AGENT, offer["offer_id"]).notes == (NOT_COMPUTED,)


def test_a_supplier_that_cannot_be_asked_for_the_suggestions_is_logged_and_recorded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    said = "No suggestion was computed: The supplier cannot be asked right now."
    monkeypatch.setattr(suggesting, "suggestions_for", lambda *args, **kwargs: SuggestionList(notes=(said,)))

    with caplog.at_level(logging.WARNING, logger="tta.api.suggesting"):
        offer = _offer(client, "hotel", HOTEL_MILK)

    assert said in offer["notes"] and offer["suggestions"] == []
    assert "the supplier could not be asked" in caplog.text
    event, = _events(client, "hotel", offer["offer_id"], SHOWN)
    assert event["facts"]["suggestions"]["notes"] == [said]


def test_a_failed_lookup_of_the_accepted_suggestion_says_so_and_not_that_no_offer_showed_it(
    client: TestClient, parts: Parts, monkeypatch: pytest.MonkeyPatch
) -> None:
    offer = _offer(client, "hotel", HOTEL_MILK)

    def broken(profile_id: str | None = None, **kwargs: Any) -> Any:
        raise RuntimeError("the trail cannot be read")

    monkeypatch.setattr(parts.store, "list_audit_events", broken)
    accepted = _offer(client, "hotel", offer["suggestions"][0]["accept_request"])
    monkeypatch.undo()

    assert any("looking up the offer that showed it failed" in note for note in accepted["notes"])
    assert not any("no earlier offer of this buyer showed it" in note for note in accepted["notes"])
    assert _events(client, "hotel", offer["offer_id"], ACCEPTED) == []


def test_reasons_that_cannot_be_read_back_are_said_and_not_shown_as_nothing_dropped(
    client: TestClient, parts: Parts, monkeypatch: pytest.MonkeyPatch
) -> None:
    offer = _offer(client, "school", SCHOOL_WEEK)
    assert parts.service.get_offer_suggestions(SCHOOL_AGENT, offer["offer_id"]).dropped  # readable as written

    validate = DroppedSuggestion.model_validate

    def refuse(value: Any) -> Any:
        return validate({"not": "a dropped suggestion"})  # what an event of another shape would raise

    monkeypatch.setattr(suggesting.DroppedSuggestion, "model_validate", staticmethod(refuse), raising=True)
    view = parts.service.get_offer_suggestions(SCHOOL_AGENT, offer["offer_id"])

    assert view.dropped == () and view.notes == (REASONS_NOT_READ,)


# --- an acceptance that is not one --------------------------------------------------------------------------


def test_a_suggestion_id_no_offer_showed_is_said_in_a_note_and_not_recorded(client: TestClient) -> None:
    offer = _offer(client, "hotel", {**HOTEL_MILK, "accepted_suggestion_id": "sug_made_up"})

    assert any("sug_made_up" in note and "no acceptance was recorded" in note for note in offer["notes"])
    assert offer["options"][0]["totals"]["net"] == 248.0
    assert _events(client, "hotel", offer["offer_id"], ACCEPTED) == []


def test_a_request_that_differs_from_the_accept_request_is_not_an_acceptance(client: TestClient) -> None:
    offer = _offer(client, "hotel", HOTEL_MILK)
    accept = offer["suggestions"][0]["accept_request"]
    more = {**accept, "lines": [accept["lines"][0], {**accept["lines"][1], "quantity": 500}]}

    amended = _offer(client, "hotel", more)

    assert any("differs from that suggestion's accept_request" in note for note in amended["notes"])
    assert _events(client, "hotel", offer["offer_id"], ACCEPTED) == []


def test_another_buyers_suggestion_cannot_be_accepted(client: TestClient) -> None:
    offer = _offer(client, "hotel", HOTEL_MILK)

    wards = _offer(client, "ward", offer["suggestions"][0]["accept_request"])

    assert any("no earlier offer of this buyer showed it" in note for note in wards["notes"])
    assert _events(client, "hotel", offer["offer_id"], ACCEPTED) == []


# --- a visitor's own kitchen, the agent run -----------------------------------------------------------------


def test_a_visitors_own_kitchen_has_no_customer_file_and_gets_no_suggestion(parts: Parts) -> None:
    assert parts.sandboxes is not None
    book = parts.sandboxes.open("l42d-own-kitchen")

    offer = book.service.create_offer(KITCHEN_AGENT, PurchaseRequest.model_validate(HOTEL_MILK))

    assert offer.options and offer.suggestions == ()
    assert [event for event in book.store.list_audit_events(offer_id=offer.offer_id) if event.type == SHOWN] == []


def test_a_book_the_shop_named_a_customer_for_gets_that_customers_suggestions(parts: Parts) -> None:
    assert parts.sandboxes is not None
    book = parts.sandboxes.open("l42d-shop-hotel")
    book.customer.name("hotel-kitchen")

    offer = book.service.create_offer(KITCHEN_AGENT, PurchaseRequest.model_validate(HOTEL_MILK))

    assert [each.product_id for each in offer.suggestions][0] == CREAM
    view = book.service.get_offer_suggestions(KITCHEN_AGENT, offer.offer_id)
    assert view.suggestions == offer.suggestions and view.note == NEVER_ADDED


class _OfferingRunner:
    """A buyer agent that only asks for an offer, through the gateway's own function."""

    model_id = "stand-in"

    def __init__(self) -> None:
        self.offers: list[Any] = []

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> Any:
        self.offers.append(tools.create_offer(identity, PurchaseRequest.model_validate(HOTEL_MILK)))
        raise RuntimeError("the stand-in stops after its offer")


def test_an_offer_made_inside_an_agent_run_carries_the_same_suggestions(
    settings: Settings, catalog: ProductCatalog,
) -> None:
    runner = _OfferingRunner()
    built = build_parts(settings, catalog=catalog, agent_runner=runner)  # type: ignore[arg-type]
    with TestClient(create_app(settings, parts=built), raise_server_exceptions=False) as client:
        client.post("/v1/agent/run", json={"text": "100 L of milk 469363 by Monday"}, headers=_auth("hotel"))

    assert [each.product_id for each in runner.offers[0].suggestions] == [CREAM]


# --- the customers' standing orders at start ----------------------------------------------------------------


@pytest.fixture
def as_shipped(settings: Settings) -> Settings:
    """The shipped default, which `Settings.for_tests` switches off: the customers' standing orders at start."""
    assert Settings.model_fields["tta_customer_standing_orders"].default is True
    return settings.model_copy(update={"tta_customer_standing_orders": True})


@pytest.fixture
def restarted(as_shipped: Settings, catalog: ProductCatalog) -> Callable[[], Iterator[TestClient]]:
    def start() -> Iterator[TestClient]:
        with TestClient(create_app(as_shipped, parts=build_parts(as_shipped, catalog=catalog))) as client:
            yield client

    return start


@pytest.fixture
def with_standing_orders(restarted: Callable[[], Iterator[TestClient]]) -> Iterator[TestClient]:
    yield from restarted()


def _standing(client: TestClient, who: str) -> list[dict[str, Any]]:
    answer = client.get("/v1/standing-orders", headers=_auth(who))
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_each_demo_customers_standing_orders_are_there_at_start_once_across_restarts(
    restarted: Callable[[], Iterator[TestClient]],
) -> None:
    held: list[dict[str, list[str]]] = []
    for _ in range(2):  # the second start finds the first one's database
        for client in restarted():
            held.append({who: sorted(each["standing_order_id"] for each in _standing(client, who))
                         for who in STANDING_ORDERS})
            created = client.get("/v1/audit", headers=_auth("hotel")).json()["events"]
            assert sum(event["type"] == "tta.v1.standing_order.created" for event in created) == 1

    assert held[0] == held[1]
    assert held[0] == {"hotel": ["so_demo_hotel_milk"], "ward": ["so_ward_plant_drinks"],
                       "school": ["so_school_weekly"], "bakery": ["so_bakery_weekly"]}


def test_outside_dev_and_demo_no_standing_order_is_set_up_at_start(tmp_path: Any, catalog: ProductCatalog) -> None:
    tokens = json.dumps({"prod-agent-token-of-32-characters-x": {
        "kind": "AGENT", "id": "agent:hotel-kitchen", "display_name": "Hotel agent", "profile_id": "hotel-kitchen"}})
    prod = Settings.for_tests(tta_env="prod", tta_data_dir=tmp_path / "var", tta_tokens=tokens,
                              tta_customer_standing_orders=True)
    with TestClient(create_app(prod, parts=build_parts(prod, catalog=catalog))) as client:
        answer = client.get("/v1/standing-orders",
                            headers={"Authorization": "Bearer prod-agent-token-of-32-characters-x"})

    assert answer.status_code == 200 and answer.json() == []


# --- the open interface -------------------------------------------------------------------------------------


def test_openapi_says_how_a_suggestion_is_accepted(client: TestClient) -> None:
    schemas = client.get("/openapi.json").json()["components"]["schemas"]

    described = schemas["Offer"]["properties"]["suggestions"]["description"]
    assert NEVER_ADDED in described
    assert NEVER_ADDED == ("Suggestions never add themselves to an order: accept one by sending its "
                           "`accept_request` as a new request.")
    assert "accepted_suggestion_id" in schemas["PurchaseRequest-Input"]["properties"]


def test_a_live_offer_carries_no_suggestion_and_spends_no_look_on_one(tmp_path: Any, catalog: ProductCatalog,
                                                                      live: Any, replay: Any) -> None:
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")
    built = build_parts(settings, catalog=catalog, gateway=FallbackGateway(live, replay))
    with TestClient(create_app(settings, parts=built)) as client:
        offer = _offer(client, "hotel", HOTEL_MILK)
        looks = live.calls
        again = _offer(client, "hotel", HOTEL_MILK)

    assert offer["source"] == "live" and offer["suggestions"] == [] and again["suggestions"] == []
    assert not any("suggestion" in note for note in offer["notes"])
    assert looks == 2  # one price and one availability call: the offer's own, none for a suggestion


def test_where_suggestions_are_off_an_acceptance_is_said_in_a_note_and_not_dropped_silently(
    tmp_path: Any, catalog: ProductCatalog, live: Any, replay: Any
) -> None:
    settings = Settings.for_tests(tta_mode="live", tta_data_dir=tmp_path / "var")
    built = build_parts(settings, catalog=catalog, gateway=FallbackGateway(live, replay))
    with TestClient(create_app(settings, parts=built)) as client:
        offer = _offer(client, "hotel", {**HOTEL_MILK, "accepted_suggestion_id": FORGOTTEN_CREAM})

    assert any(FORGOTTEN_CREAM in note and "suggestions are off in this mode" in note for note in offer["notes"])
    assert offer["options"]  # the offer itself is built as for any request
