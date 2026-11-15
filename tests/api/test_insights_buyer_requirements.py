"""`GET /v1/insights`, "Sales we could not make": only what Valio Aimo's own data could not cover (lane FP-I).

Scores on the 20% "autonomy and controls" (what Valio Aimo reads of a decision: that the buyer's own requirements
left products out, never which requirement) and on the 15% "exception situations" (a request nothing can be offered
for is not booked as stock Valio Aimo lacked).

The fault, seen on the page at the demo clock: City Hospital, Ward 4 (which excludes milk) asked for 100 L of
lactose-free milk. The gateway rightly offered nothing, and the back office then said "0 of 100 L of lactose-free
milk could be confirmed", with "22 products quantity not confirmed in the data" as the reason, in a recording that
holds 435 L of it confirmed. Every book below is filled through the app in replay at the demo clock (Thursday
12 Nov 2026 14:15 Helsinki); every figure was measured there.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.insights import insights
from tta.api.wiring import Parts, build_parts
from tta.audit.readers import supplier_actor
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.audit import SYSTEM_ACTOR, AuditData, AuditEvent

CAPTURE = "2026-11-14-demo"
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"
MONDAY = "2026-11-16"
TOKENS = {"hotel": "demo-agent-hotel-kitchen", "ward": "demo-agent-allergy-ward",
          "supplier": "demo-supplier-valio-aimo"}
WARD_ASKED = "100 litres of lactose-free milk by Monday"
# The headline spoken in the pitch, after the hotel's request. It must not move.
HOTEL_HEADLINE = (
    "565 L asked for could not be covered by confirmed stock of the product asked for: about €1,407 at offered "
    "prices."
)
HOTEL_SHORT = (
    "435 of 1,000 L of lactose-free milk could be confirmed: 565 L, about €1,407 at the offered price, were not."
)
NONE_COUNTED = "No quantity is counted here as a sale Valio Aimo could not make."
BUYERS_OWN = (
    "Not counted here: requests where nothing could be offered because the buyer's own requirements left products "
    "out."
)
EVERYTHING_COVERED = "Every quantity asked for was covered by confirmed stock of the product asked for."


def _milk(litres: int, words: str) -> dict[str, Any]:
    return {"needed_by": MONDAY, "lines": [{"text": words, "product_type": "milk",
                                            "required_claims": ["FREE_FROM_LACTOSE"], "quantity": litres, "unit": "L"}]}


def _ask(client: TestClient, who: str, body: dict[str, Any]) -> dict[str, Any]:
    answer = client.post("/v1/offers", json=body, headers={"Authorization": f"Bearer {TOKENS[who]}"})
    assert answer.status_code == 201, answer.text
    return answer.json()


def _missed(client: TestClient) -> dict[str, Any]:
    answer = client.get("/v1/insights", headers={"Authorization": f"Bearer {TOKENS['supplier']}"})
    assert answer.status_code == 200, answer.text
    return answer.json()["missed"]


@pytest.fixture(scope="module")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture
def gateway(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    """The gateway in replay at the demo clock, with an order book of its own for each test and the API alone."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture=CAPTURE, tta_demo_clock=DEMO_CLOCK)
    with pytest.MonkeyPatch.context() as patch:
        for name in ("tta.agent", "tta.api.mcp_surface", "tta.ui.routes"):
            patch.setitem(sys.modules, name, None)
        with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
            yield client


def test_a_request_the_buyers_own_requirements_emptied_is_not_a_sale_valio_aimo_could_not_make(
    gateway: TestClient,
) -> None:
    offer = _ask(gateway, "ward", _milk(100, WARD_ASKED))
    assert offer["options"] == []  # 26 products checked, 26 left out: each declares milk, which the ward excludes

    missed = _missed(gateway)

    assert missed["shortfalls"] == [] and missed["not_confirmed"] == [] and missed["value_net_eur"] == 0
    assert missed["top_products"] == []  # nor its products: none of them is "asked for and not confirmed"
    assert missed["sentence"] == f"{NONE_COUNTED} {BUYERS_OWN}"


def test_what_is_said_of_such_a_request_names_no_requirement_and_gives_no_count(gateway: TestClient) -> None:
    _ask(gateway, "ward", _milk(100, WARD_ASKED))

    missed = _missed(gateway)
    said = " ".join([missed["sentence"], *(row["how"] for row in missed["counted"])])

    for telling in ("allergen", "milk", "gluten", "26", "100 L", " 2 products"):
        assert telling not in said, telling
    assert any(row["figure"] == "Left out by the buyer's own requirements" for row in missed["counted"])


def test_it_is_read_from_valio_aimos_view_of_the_offer_and_from_nothing_of_the_buyers(gateway: TestClient) -> None:
    """With the buyer's facts, the buyer's sentence, its profile and whoever acted taken out of every event, the
    block is the same: what it says of the ward's request rests on what Valio Aimo may read anyway."""
    _ask(gateway, "ward", _milk(100, WARD_ASKED))
    parts: Parts = gateway.app.state.parts  # type: ignore[attr-defined]
    events = parts.store.list_audit_events()
    stripped = [
        event.model_copy(update={"data": event.data.model_copy(update={
            "facts": {}, "sentence": "", "profile_id": None, "approval_id": None, "rule_ids": (),
            "actor": supplier_actor(event.data.actor)})})
        for event in events
    ]
    now = parts.clock.now()

    # the buyer's side does hold why: 26 products left out for an allergen they declare
    assert any("ALLERGEN_DECLARED" in str(event.data.facts) for event in events)
    assert insights(stripped, now=now).missed == insights(events, now=now).missed
    assert insights(events, now=now).missed.sentence == f"{NONE_COUNTED} {BUYERS_OWN}"


def test_the_hotels_headline_stays_as_the_pitch_quotes_it(gateway: TestClient) -> None:
    _ask(gateway, "hotel", _milk(1000, "1,000 litres of lactose-free milk by Monday"))

    missed = _missed(gateway)
    short, = missed["shortfalls"]

    assert missed["sentence"] == HOTEL_HEADLINE
    assert (short["asked"], short["confirmed"], short["not_confirmed"]) == (1000.0, 435.0, 565.0)
    assert short["sentence"] == HOTEL_SHORT and short["value_net_eur"] == 1407.16
    assert {(reason["reason"], reason["products"]) for reason in short["reasons"]} == {
        ("QUANTITY_NOT_CONFIRMED", 1), ("NOT_DELIVERABLE", 1)}
    assert missed["not_confirmed"] == [{"unit": "L", "quantity": 565.0}] and missed["value_net_eur"] == 1407.16


def test_a_book_short_for_both_reasons_counts_only_what_valio_aimos_data_could_not_cover(
    gateway: TestClient,
) -> None:
    """The hotel's 1,000 L is short of confirmed stock by 565 L; the ward's 100 L is left out by the ward's own
    rule. Only the 565 L is a sale Valio Aimo could not make, and the headline's first sentence is the pitch's."""
    _ask(gateway, "hotel", _milk(1000, "1,000 litres of lactose-free milk by Monday"))
    _ask(gateway, "ward", _milk(100, WARD_ASKED))

    missed = _missed(gateway)
    short, = missed["shortfalls"]

    assert missed["sentence"] == f"{HOTEL_HEADLINE} {BUYERS_OWN}"
    assert (short["requests"], short["asked"], short["not_confirmed"]) == (1, 1000.0, 565.0)
    assert short["sentence"] == HOTEL_SHORT
    assert missed["not_confirmed"] == [{"unit": "L", "quantity": 565.0}] and missed["value_net_eur"] == 1407.16
    top = {row["product_id"]: (row["times"], row["reason"]) for row in missed["top_products"]}
    assert top == {"464306": (1, "QUANTITY_NOT_CONFIRMED"), "464440": (1, "NOT_DELIVERABLE")}  # the hotel's alone


def test_a_request_short_for_both_reasons_is_left_out_whole_where_valio_aimos_view_cannot_split_it(
    gateway: TestClient,
) -> None:
    """The ward asks for 1,000 L: its own rule leaves out the 435 L that is confirmed, and no confirmed stock
    covers the other 565 L. Valio Aimo's view of the offer holds neither the products the ward's rule left out
    nor their stock, so it cannot say that 565 L is its own part: none of the 1,000 L is counted, and never the
    whole 1,000 L as stock Valio Aimo lacked."""
    offer = _ask(gateway, "ward", _milk(1000, "1,000 litres of lactose-free milk by Monday"))
    assert offer["options"] == []

    missed = _missed(gateway)

    assert missed["shortfalls"] == [] and missed["not_confirmed"] == []
    assert missed["sentence"] == f"{NONE_COUNTED} {BUYERS_OWN}"


def test_nothing_offered_for_a_reason_in_valio_aimos_own_data_is_still_counted() -> None:
    """Steps typed by hand, as Valio Aimo's view holds them: one product matched, it cannot be delivered, nothing
    was offered. Every product that matched is accounted for by Valio Aimo's own data, so the sale is its own."""
    def step(number: int, kind: str, facts: dict[str, Any]) -> AuditEvent:
        data = AuditData(actor=SYSTEM_ACTOR, sentence="", supplier_sentence="", offer_id="off_1",
                         supplier_facts=facts, previous_hash="0" * 64, hash=f"{number:064d}")
        return AuditEvent(id=f"evt_{number}", type=f"tta.v1.{kind}", time=datetime.fromisoformat(DEMO_CLOCK),
                          data=data)

    asked = {"lines": [{"product_type": "plant_drink", "quantity": 40, "unit": "L", "required_claims": [],
                        "product_ids": []}]}
    offer = {"offer_id": "off_1", "created_at": DEMO_CLOCK, "candidates_considered": 1, "options": [],
             "excluded_by_reason": {"NOT_DELIVERABLE": 1},
             "left_out": [{"product_id": "464013", "name": "Soya drink 1 L", "request_line_index": 0,
                           "reason": "NOT_DELIVERABLE"}]}
    events = [step(1, "request.received", {}), step(2, "request.parsed", {"request": asked}),
              step(3, "offer.created", {"offer": offer})]

    missed = insights(events, now=datetime.fromisoformat(DEMO_CLOCK)).missed
    short, = missed.shortfalls

    assert (short.asked, short.confirmed, short.not_confirmed) == (40, 0, 40)
    assert [(reason.reason, reason.products) for reason in short.reasons] == [("NOT_DELIVERABLE", 1)]
    assert missed.sentence == (
        "40 L asked for could not be covered by confirmed stock of the product asked for: about €0 at offered "
        "prices."
    )


def test_a_book_where_everything_was_covered_says_so_and_no_more(gateway: TestClient) -> None:
    _ask(gateway, "hotel", _milk(100, "100 litres of lactose-free milk by Monday"))

    assert _missed(gateway)["sentence"] == EVERYTHING_COVERED
