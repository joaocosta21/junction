"""The audit facts of "suggestions shown" and "suggestion accepted" (P15 R4a): plain dicts, JSON all the way down."""

from __future__ import annotations

import json
from typing import Any

from tta.contracts.suggestion import SuggestionKind
from tta.suggestions import suggestion_accepted_facts, suggestions_shown_facts
from tta.suggestions.events import (
    ACCEPTED_EVENT,
    SHOWN_EVENT,
    suggestion_accepted_supplier_facts,
    suggestions_shown_supplier_facts,
)

SCHOOL = "school-kitchen"
LINES = ({"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"},)
HOTEL_MILK = {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}


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
    assert facts["dropped_count"] == len(found.dropped) >= 1
    assert facts["dropped_by_reason"] == {"BUYER_REQUIREMENT": len(found.dropped)}
    assert [each["product_id"] for each in facts["shown"]] == [each.product_id for each in found.shown]
    assert {"orders_considered", "orders_matching", "kind", "quantity"} <= set(facts["shown"][0])


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
