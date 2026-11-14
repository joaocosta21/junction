"""The audit facts of "suggestions shown" and "suggestion accepted" (P15 R4a): plain dicts, JSON all the way down."""

from __future__ import annotations

import json
from typing import Any

from tta.audit import AuditTrail
from tta.contracts.audit import EVENT_TYPE_PREFIX, Actor, ActorKind, AuditEventType
from tta.contracts.common import AuditReader
from tta.contracts.suggestion import SuggestionKind
from tta.store import SqliteStore
from tta.suggestions import DropReason, suggestion_accepted_facts, suggestions_shown_facts
from tta.suggestions.events import (
    ACCEPTED_EVENT,
    SHOWN_EVENT,
    record_suggestion_accepted,
    record_suggestions_shown,
    suggestion_accepted_supplier_facts,
    suggestions_shown_supplier_facts,
)

SCHOOL = "school-kitchen"
LINES = ({"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"},)
HOTEL_MILK = {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}
BAKERY_IKAFFE = {"text": "30 L of Oatly iKaffe 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}
AGENT = Actor(kind=ActorKind.AGENT, id="agent:school-kitchen", display_name="School kitchen agent")
CHEF = Actor(kind=ActorKind.HUMAN, id="human:hanna", role="purchasing_manager", display_name="Hanna Laine")


def test_suggestions_shown_names_each_one_with_its_evidence_and_each_drop_with_its_reason(world_now: Any) -> None:
    found = world_now.suggest(SCHOOL, *LINES, standing_orders=world_now.standing_orders(SCHOOL))

    facts = suggestions_shown_facts(found, offer_id="off_1")

    assert json.loads(json.dumps(facts)) == facts  # plain JSON: nothing the audit trail cannot hash
    assert (facts["event"], facts["offer_id"]) == (SHOWN_EVENT, "off_1")
    trend = next(each for each in facts["shown"] if each["kind"] == SuggestionKind.QUANTITY_TREND)
    assert (trend["product_id"], trend["quantity"], trend["unit"]) == ("470863", "84.000", "L")
    assert trend["evidence"]["values"] == [66, 70, 74, 80, 84, 90] and trend["evidence"]["synthetic"]
    assert trend["stock_confirmed"] is True and trend["checks"]
    yoghurt = next(each for each in facts["dropped"] if each["product_id"] == "464517")
    assert (yoghurt["kind"], yoghurt["reason"]) == ("FORGOTTEN_ITEM", "ALLERGEN_NOT_RULED_OUT")
    assert "tree nuts (AN)" in yoghurt["sentence"]
    assert facts["synthetic_history"] is True


def test_valio_aimos_facts_say_what_was_shown_and_never_why_one_was_dropped(world_now: Any) -> None:
    found = world_now.suggest(SCHOOL, *LINES, standing_orders=world_now.standing_orders(SCHOOL))

    facts = suggestions_shown_supplier_facts(found, offer_id="off_1")

    text = json.dumps(facts)
    assert all(word not in text for word in ("tree nuts", "peanuts", "sesame", "464517", "ALLERGEN", "sentence"))
    silent = [each for each in found.dropped if each.reason == DropReason.NO_STATED_BENEFIT]
    assert silent and all(each.product_id not in text for each in silent)  # Valio Aimo's own, silent (lane SG)
    assert facts["dropped_count"] == len(found.dropped) - len(silent) >= 1
    assert facts["dropped_by_reason"] == {"BUYER_REQUIREMENT": len(found.dropped) - len(silent)}
    assert [each["product_id"] for each in facts["shown"]] == [each.product_id for each in found.shown]
    assert {"kind", "quantity", "name"} <= set(facts["shown"][0])
    for history_figure in ("orders_considered", "orders_matching", "evidence", "values", "synthetic"):
        assert history_figure not in text  # never a figure of the buyer's history (decision of S1's brief)


def test_suggestion_accepted_names_the_suggestion_who_accepted_it_and_the_new_offer(world_now: Any) -> None:
    cream = world_now.suggest("hotel-kitchen", HOTEL_MILK).shown[0]

    facts = suggestion_accepted_facts(cream, offer_id="off_1", new_offer_id="off_2", accepted_by="Hanna Laine")
    for_valio = suggestion_accepted_supplier_facts(cream, offer_id="off_1", new_offer_id="off_2")

    assert json.loads(json.dumps(facts)) == facts
    assert (facts["event"], facts["offer_id"], facts["new_offer_id"], facts["accepted_by"]) == (
        ACCEPTED_EVENT, "off_1", "off_2", "Hanna Laine",
    )
    assert (facts["kind"], facts["product_id"], facts["net_change_eur"]) == ("FORGOTTEN_ITEM", "463797", "33.10")
    assert facts["evidence"]["orders_matching"] == 7 and facts["evidence"]["orders_considered"] == 8
    assert "accepted_by" not in for_valio and "evidence" not in for_valio and "sentence" not in for_valio
    assert (for_valio["product_id"], for_valio["new_offer_id"]) == ("463797", "off_2")


def test_each_held_back_suggestion_keeps_its_reason_for_both_readers(world_now: Any) -> None:
    found = world_now.suggest("bakery-cafe", BAKERY_IKAFFE)

    buyers = suggestions_shown_facts(found, offer_id="off_1")["held_back"]
    valios = suggestions_shown_supplier_facts(found, offer_id="off_1")["held_back"]

    assert [(each["product_id"], each["reason"], each["summary"]) for each in buyers][:2] == [
        ("469346", "KIND_ALREADY_SHOWN", "another forgotten item ranks higher"),
        ("464727", "KIND_ALREADY_SHOWN", "another forgotten item ranks higher"),
    ]
    assert [(each["product_id"], each["reason"]) for each in valios] == [
        (each["product_id"], each["reason"]) for each in buyers
    ]
    assert all("summary" not in each and "sentence" not in each for each in valios)


def test_the_shown_event_is_written_with_both_views_and_found_again_by_its_offer(world_now: Any) -> None:
    trail = AuditTrail(SqliteStore(), world_now.replay.clock)
    found = world_now.suggest("school-kitchen", *LINES, standing_orders=world_now.standing_orders(SCHOOL))

    event = record_suggestions_shown(trail, AGENT, found, offer_id="off_1", profile_id=SCHOOL)

    assert event.type == f"{EVENT_TYPE_PREFIX}{AuditEventType.SUGGESTIONS_SHOWN.value}"
    assert (event.subject, event.data.offer_id, event.data.profile_id) == ("offer/off_1", "off_1", SCHOOL)
    assert event.data.facts["suggestions"] == suggestions_shown_facts(found, offer_id="off_1")
    assert event.data.supplier_facts == {"suggestions": suggestions_shown_supplier_facts(found, offer_id="off_1")}
    assert event.data.sentence.startswith(f"{len(found.shown)} suggestion")
    assert "464517" in event.data.sentence and "464517" not in event.data.supplier_sentence
    assert trail.view(AuditReader.BUYER, offer_id="off_1").events[0].id == event.id
    assert trail.verify_chain().ok


def test_the_accepted_event_is_written_with_who_accepted_and_the_new_offer(world_now: Any) -> None:
    trail = AuditTrail(SqliteStore(), world_now.replay.clock)
    cream = world_now.suggest("hotel-kitchen", HOTEL_MILK).shown[0]

    event = record_suggestion_accepted(trail, CHEF, cream, offer_id="off_1", new_offer_id="off_2",
                                       profile_id="hotel-kitchen")

    assert event.type == f"{EVENT_TYPE_PREFIX}{AuditEventType.SUGGESTION_ACCEPTED.value}"
    assert event.data.facts["suggestion"] == suggestion_accepted_facts(
        cream, offer_id="off_1", new_offer_id="off_2", accepted_by="Hanna Laine",
    )
    assert event.data.supplier_facts == {
        "suggestion": suggestion_accepted_supplier_facts(cream, offer_id="off_1", new_offer_id="off_2"),
    }
    assert event.data.sentence.startswith("Hanna Laine (purchasing manager) accepted the forgotten item ")
    assert event.data.supplier_sentence.startswith("The buyer's purchasing manager accepted a forgotten item ")
