"""`GET /v1/insights`: what the agent channel brought Valio Aimo, and where it is losing sales (lane BO).

Scores on the 20% "how decisions are logged and auditable" (the log read as figures, each with how it was counted),
on the 15% "exception situations" (the quantity asked for that confirmed stock did not cover, with the reason) and
on the 15% "credible path toward production" (a typed route for Valio Aimo's own reader). The book is filled through
the app in replay at the demo clock (Thursday 12 Nov 2026 14:15 Helsinki): every figure below was measured there.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.insights import Period, insights
from tta.api.sandbox import KITCHEN_AGENT
from tta.api.wiring import Parts, build_parts
from tta.audit.readers import supplier_actor
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Unit
from tta.contracts.request import PurchaseRequest, RequestLine

CAPTURE = "2026-11-14-demo"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
MONDAY, TUESDAY = "2026-11-16", "2026-11-17"
TOKENS = {"hotel": "demo-agent-hotel-kitchen", "bakery": "demo-agent-bakery-cafe",
          "hotel_purchasing": "demo-approver-hotel-purchasing", "bakery_owner": "demo-approver-bakery-owner",
          "supplier": "demo-supplier-valio-aimo"}
SCENARIO_1 = {"needed_by": MONDAY, "lines": [{
    "text": "1,000 litres of lactose-free milk by Monday", "product_type": "milk",
    "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 1000, "unit": "L"}]}
HOTEL_MILK = {"needed_by": MONDAY, "lines": [
    {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}]}
BAKERY_OAT = {"needed_by": TUESDAY, "lines": [
    {"text": "30 L oat drink 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}]}

DEMAND = (
    "5 requests came in through the agent channel and 5 offers went out. 4 orders were prepared: 2 confirmed by a "
    "person (€1,364.49 before tax), 0 placed by the agent alone, 1 waiting for a person (€44.40), 1 rejected and "
    "0 expired."
)
SUGGESTIONS = (
    "6 suggestions were shown with offers and 2 were accepted (33.3%); 1 of those ended in a confirmed order. "
    "Accepted suggestions added €33.10 to baskets and saved buyers €42.00."
)
MILK_SHORT = (
    "435 of 1,000 L of lactose-free milk could be confirmed: 565 L, about €1,407 at the offered price, were not."
)
MISSED = "565 L asked for could not be covered by confirmed stock: about €1,407 at offered prices."
NOTHING_YET = "Nothing has been ordered in this demonstration yet. Make a request as a customer, then come back."


def _auth(who: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {TOKENS[who]}"}
    return headers if key is None else {**headers, "Idempotency-Key": key}


def _offer(client: TestClient, who: str, body: dict[str, Any]) -> dict[str, Any]:
    answer = client.post("/v1/offers", json=body, headers=_auth(who))
    assert answer.status_code == 201, answer.text
    return answer.json()


def _order(client: TestClient, who: str, offer: dict[str, Any]) -> dict[str, Any]:
    body = {"offer_id": offer["offer_id"], "option_id": offer["options"][0]["option_id"]}
    answer = client.post("/v1/orders", json=body, headers=_auth(who, f"bo-{offer['offer_id']}"))
    assert answer.status_code == 201, answer.text
    return answer.json()


def _decide(client: TestClient, who: str, order: dict[str, Any], decision: str) -> None:
    answer = client.post(f"/v1/approvals/{order['approval_id']}/decision", json={"decision": decision},
                         headers=_auth(who))
    assert answer.status_code == 200, answer.text


def _suggested(offer: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(each["accept_request"] for each in offer["suggestions"] if each["kind"] == kind)


def _insights(client: TestClient, period: str | None = None, who: str = "supplier") -> Any:
    return client.get("/v1/insights", params={"period": period} if period else None, headers=_auth(who))


@pytest.fixture(scope="module")
def gateway(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    """The gateway in replay at the demo clock, with a data directory of its own and the API alone."""
    data: Path = tmp_path_factory.mktemp("insights")
    settings = Settings.for_tests(tta_data_dir=data / "var", tta_replay_capture=CAPTURE, tta_demo_clock=DEMO_CLOCK)
    catalog = ProductCatalog.from_settings(Settings.for_tests())
    with pytest.MonkeyPatch.context() as patch:
        for name in ("tta.agent", "tta.api.mcp_surface", "tta.ui.routes"):
            patch.setitem(sys.modules, name, None)
        with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
            yield client


@pytest.fixture(scope="module")
def filled(gateway: TestClient) -> TestClient:
    """The hotel: scenario 1 confirmed; 100 L of milk with the forgotten cooking cream accepted, confirmed. The
    bakery: 30 L of oat drink ordered and rejected, then the cheaper pack switched to and left waiting."""
    empty = _insights(gateway).json()
    assert empty["empty"] is True and empty["empty_sentence"] == NOTHING_YET
    _decide(gateway, "hotel_purchasing", _order(gateway, "hotel", _offer(gateway, "hotel", SCENARIO_1)), "APPROVE")
    milk = _offer(gateway, "hotel", HOTEL_MILK)
    with_cream = _offer(gateway, "hotel", _suggested(milk, "FORGOTTEN_ITEM"))
    _decide(gateway, "hotel_purchasing", _order(gateway, "hotel", with_cream), "APPROVE")
    oat = _offer(gateway, "bakery", BAKERY_OAT)
    _decide(gateway, "bakery_owner", _order(gateway, "bakery", oat), "REJECT")
    _order(gateway, "bakery", _offer(gateway, "bakery", _suggested(oat, "CHEAPER_SAME_FORMULA")))
    return gateway


def test_only_valio_aimos_reader_reads_the_insights(filled: TestClient) -> None:
    for who in ("hotel", "hotel_purchasing"):
        refused = _insights(filled, who=who)
        assert refused.status_code == 403, refused.text
        assert refused.json()["type"].endswith("not-authorised")
    assert filled.get("/v1/insights").status_code == 401
    assert _insights(filled, "yesterday").status_code == 422


def test_demand_through_the_agent_channel(filled: TestClient) -> None:
    demand = _insights(filled).json()["demand"]

    counts = {key: demand[key] for key in ("requests", "offers", "orders_prepared", "confirmed_by_person",
                                           "placed_by_agent", "waiting", "rejected", "expired")}
    assert counts == {"requests": 5, "offers": 5, "orders_prepared": 4, "confirmed_by_person": 2,
                      "placed_by_agent": 0, "waiting": 1, "rejected": 1, "expired": 0}
    assert (demand["confirmed_net_eur"], demand["waiting_net_eur"]) == (1364.49, 44.4)  # 1,083.39 + 281.10
    assert demand["sentence"] == DEMAND


def test_suggestions_shown_accepted_and_ordered_with_added_and_saved_apart(filled: TestClient) -> None:
    found = _insights(filled).json()["suggestions"]

    assert (found["shown"], found["accepted"], found["ordered"]) == (6, 2, 1)
    assert found["acceptance_rate"] == 0.3333
    assert (found["added_net_eur"], found["saved_net_eur"], found["not_valued"]) == (33.1, 42.0, 0)
    rows = {row["kind"]: row for row in found["by_kind"]}
    assert {kind: (row["shown"], row["accepted"], row["ordered"]) for kind, row in rows.items()} == {
        "FORGOTTEN_ITEM": (3, 1, 1), "CHEAPER_SAME_FORMULA": (1, 1, 0), "LARGER_PACK": (1, 0, 0),
        "FROM_SUPPLIER": (1, 0, 0)}
    assert rows["FORGOTTEN_ITEM"]["added_net_eur"] == 33.1 and rows["CHEAPER_SAME_FORMULA"]["saved_net_eur"] == 42.0
    assert [row["kind"] for row in found["by_kind"] if row["own"]] == ["FROM_SUPPLIER"]
    assert rows["FROM_SUPPLIER"]["label"] == "Valio Aimo's own suggestion"
    assert "is not counted" in found["own_silent"]  # decision B32: not in Valio Aimo's view, so not here
    assert found["sentence"] == SUGGESTIONS


def test_sales_not_made_by_product_type_with_the_reason_and_the_value(filled: TestClient) -> None:
    missed = _insights(filled).json()["missed"]

    short, = missed["shortfalls"]
    assert (short["label"], short["unit"]) == ("lactose-free milk", "L")
    assert (short["asked"], short["confirmed"], short["not_confirmed"]) == (1000.0, 435.0, 565.0)
    assert short["value_net_eur"] == 1407.16  # 565 L at €1,083.39 / 435 L, the price of the confirmed part
    assert short["sentence"] == MILK_SHORT
    assert {(reason["reason"], reason["products"]) for reason in short["reasons"]} == {
        ("QUANTITY_NOT_CONFIRMED", 1), ("NOT_DELIVERABLE", 1)}
    assert missed["not_confirmed"] == [{"unit": "L", "quantity": 565.0}] and missed["value_net_eur"] == 1407.16
    assert missed["sentence"] == MISSED
    top = {row["product_id"]: (row["times"], row["reason"]) for row in missed["top_products"]}
    assert top == {"464306": (1, "QUANTITY_NOT_CONFIRMED"), "464440": (1, "NOT_DELIVERABLE")}
    assert missed["substitutes"] == {"offered": 0, "accepted": 0, "refused": 0}


def test_every_block_says_how_it_was_counted_and_the_page_says_what_it_rests_on(filled: TestClient) -> None:
    found = _insights(filled).json()

    assert found["empty"] is False and found["period"] == "today"
    assert "Thursday 12 November 2026" in found["period_sentence"]
    assert "synthetic" in found["note"] and "from the recording" in found["note"]
    for block in ("demand", "suggestions", "missed"):
        assert found[block]["counted"] and all(each["figure"] and each["how"] for each in found[block]["counted"])
    everything = _insights(filled, "all").json()
    assert everything["period"] == "all" and "All time" in everything["period_sentence"]
    # one clock for the whole book, so today and all time hold the same steps
    assert all(everything[block] == found[block] for block in ("demand", "suggestions", "missed"))


def test_nothing_of_a_buyers_own_is_in_the_answer(filled: TestClient) -> None:
    text = _insights(filled, "all").text

    for private in ("hotel-kitchen", "bakery-cafe", "Hanna", "max_order", "excluded_allergens", "BUYER_REQUIREMENT",
                    "1,000 litres of lactose-free milk by Monday", "purchasing"):
        assert private not in text, private


def test_the_route_is_typed_in_the_openapi_document(filled: TestClient) -> None:
    document = filled.get("/openapi.json").json()

    operation = document["paths"]["/v1/insights"]["get"]
    assert operation["operationId"] == "get_insights" and operation["security"] == [{"bearerAuth": []}]
    period, = operation["parameters"]
    assert period["name"] == "period" and "403" in operation["responses"]
    answer = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert answer == {"$ref": "#/components/schemas/Insights"}
    assert document["components"]["schemas"]["Period"]["enum"] == ["today", "all"]


# --- what a buyer keeps to itself (review finding M1; decisions B13, B14, B32, B36) ---------------------------
# In the spirit of tests/ui/test_supplier_view.py: the same activity in two order books whose buyer differs only in
# what it excludes, read as Valio Aimo's figures. At the recording's own clock (Saturday 14 Nov 2026 02:52).

WARD, HOTEL = "allergy-ward", "hotel-kitchen"
MILK, GLUTEN, TREE_NUTS = "AM", "AW", "AN"
# What may differ when the exclusion changes the offer itself: the value of the order (another product was
# ordered: Valio Aimo's own sale), and which products were offered with a quantity that is not confirmed (an
# option the buyer's rule removed is not offered, so its product is not "asked for and not confirmed").
THE_ORDERS_THEMSELVES = {"demand.waiting_net_eur", "demand.sentence", "missed.top_products"}


def _plant_drink(litres: int, confirmed_only: bool) -> PurchaseRequest:
    line = RequestLine(text=f"{litres} litres of a milk substitute by Monday", product_type="plant_drink",
                       quantity=Decimal(litres), unit=Unit.L)
    return PurchaseRequest(needed_by=date(2026, 11, 16), require_confirmed=confirmed_only, lines=(line,))


def _book(parts: Parts, key: str, start: str, change: dict[str, Any], request: PurchaseRequest) -> Any:
    """Offer and order in a book of its own, whose buyer is a copy of `start` with `change`."""
    book = parts.sandboxes.open(key)  # type: ignore[union-attr]
    book.kitchen.start_from(start)
    book.kitchen.set_up({**book.kitchen.settings, **change})
    offer = book.service.create_offer(KITCHEN_AGENT, request)
    book.service.place_order(KITCHEN_AGENT, offer.offer_id, offer.options[0].option_id, f"bo-leak-{key}")
    return book


def _figures(parts: Parts, book: Any) -> dict[str, Any]:
    return insights(book.store.list_audit_events(), now=parts.clock.now(), period=Period.ALL).model_dump(mode="json")


def _differing(one: Any, other: Any, path: str = "") -> set[str]:
    """The fields that differ, by their path down to the first list."""
    if isinstance(one, dict) and isinstance(other, dict):
        return {found for key in one.keys() | other.keys()
                for found in _differing(one.get(key), other.get(key), f"{path}.{key}".lstrip("."))}
    return set() if one == other else {path}


def test_the_figures_are_the_same_whatever_the_buyer_excludes_when_the_offer_is_the_same(parts: Parts) -> None:
    ward_200_l = _plant_drink(200, confirmed_only=True)
    one = _book(parts, "one", WARD, {"excluded_allergens": [MILK, GLUTEN]}, ward_200_l)
    other = _book(parts, "other", WARD, {"excluded_allergens": [MILK, GLUTEN, TREE_NUTS]}, ward_200_l)

    assert _figures(parts, one) == _figures(parts, other)
    assert _figures(parts, one)["demand"]["waiting_net_eur"] == 402.0  # not an empty comparison


@pytest.mark.parametrize("excluded", [TREE_NUTS, GLUTEN])
def test_an_exclusion_that_changes_the_offer_changes_only_what_the_order_itself_shows(
    parts: Parts, excluded: str,
) -> None:
    """Excluding tree nuts removes the unconfirmed alternative from the offer; excluding gluten makes another
    product the best one, at another price. Valio Aimo reads both in the offer and the order anyway. No shortfall,
    no count of products per reason and no suggestion figure moves."""
    request = _plant_drink(80, confirmed_only=False)
    plain = _book(parts, "plain", HOTEL, {}, request)
    excluding = _book(parts, "excluding", HOTEL, {"excluded_allergens": [excluded],
                                                  "allergen_strictness": "STRICT"}, request)

    differing = _differing(_figures(parts, plain), _figures(parts, excluding))

    assert differing and differing <= THE_ORDERS_THEMSELVES


def test_the_figures_do_not_change_when_everything_valio_aimo_may_not_see_is_taken_out(filled: TestClient) -> None:
    """The structural guarantee: the figures are a function of Valio Aimo's view of each event. With the buyer's
    facts, the buyer's sentence, the buyer's profile id and whoever acted removed, they are the same."""
    parts: Parts = filled.app.state.parts  # type: ignore[attr-defined]
    events = parts.store.list_audit_events()
    stripped = [
        event.model_copy(update={"data": event.data.model_copy(update={
            "facts": {}, "sentence": "", "profile_id": None, "approval_id": None, "rule_ids": (),
            "actor": supplier_actor(event.data.actor)})})
        for event in events
    ]
    now = parts.clock.now()

    own_words = SCENARIO_1["lines"][0]["text"]  # type: ignore[index]
    assert any(own_words in str(event.data.facts) for event in events)  # the buyer's side does hold them
    assert insights(stripped, now=now) == insights(events, now=now)
