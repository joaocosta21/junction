"""The two suggestion events (P15 R4a, R4b): `suggestions.shown` and `suggestion.accepted`, a sentence for each reader.

The facts are the plain dicts `tta.suggestions.events` builds, written here by hand: the audit package reads them
as data. The buyer reads every suggestion shown, each one not shown with its reason, each one held back. Valio Aimo
reads counts and kinds and its own suggestion by name: never why one was dropped for the buyer's requirements,
never a figure of the buyer's history.
"""

from __future__ import annotations

from typing import Any

import pytest

from tta.audit import AuditTrail
from tta.audit.facts import SUPPLIER_VIEW
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.common import AuditReader

EVIDENCE = {"source": "SYNTHETIC_HISTORY", "synthetic": True, "orders_considered": 8, "orders_matching": 7,
            "first_order": "2026-09-21", "last_order": "2026-11-09", "values": [10, 10, 12], "thresholds": {}}
CREAM = {
    "suggestion_id": "sug_forgotten_item_463797_hotel-kitchen", "kind": "FORGOTTEN_ITEM", "serves": "BUYER",
    "product_id": "463797", "quantity": "10.000", "unit": "L", "replaces_product_id": None,
    "name": "Arla Pro Cooking cream 10% 1 L UHT lactose free", "sentence": "In 7 of your last 8 orders ...",
    "evidence": EVIDENCE, "net_change_eur": "33.10", "stock_confirmed": True, "checks": [],
}
CHEAPER = {**CREAM, "suggestion_id": "sug_cheaper_same_formula_473278_bakery-cafe", "kind": "CHEAPER_SAME_FORMULA",
           "product_id": "473278", "quantity": "30", "replaces_product_id": "468319",
           "name": "Oatly iKaffe Oat drink 1,5L", "net_change_eur": "-42.00"}
OWN = {**CREAM, "suggestion_id": "sug_from_supplier_462775_hotel-kitchen", "kind": "FROM_SUPPLIER",
       "serves": "SUPPLIER", "product_id": "462775", "quantity": "1", "unit": "UNIT",
       "name": "Arla Milkdrink 1L lactose free fat free UHT Suomesta", "net_change_eur": "2.57"}
YOGHURT = {"suggestion_id": "sug_forgotten_item_464517_school-kitchen", "kind": "FORGOTTEN_ITEM",
           "product_id": "464517", "name": "AIMO NATURAL YOGURT 5KG 2% LACTOSE FREE",
           "reason": "ALLERGEN_NOT_RULED_OUT",
           "sentence": "The product makes no statement about tree nuts (AN): a dietitian must decide.",
           "summary": "its data does not rule out tree nuts (AN)"}
WHIPPING = {"suggestion_id": "sug_forgotten_item_469346_bakery-cafe", "kind": "FORGOTTEN_ITEM", "serves": "BUYER",
            "product_id": "469346", "quantity": "40", "unit": "L", "replaces_product_id": None,
            "name": "Arla Pro Whipping cream 1 L UHT lactose free", "reason": "KIND_ALREADY_SHOWN",
            "summary": "another forgotten item ranks higher"}


def _brief(entry: dict[str, Any]) -> dict[str, Any]:
    keys = ("suggestion_id", "kind", "serves", "product_id", "name", "quantity", "unit", "replaces_product_id")
    return {key: entry[key] for key in keys}


BUYERS = {"event": "suggestions.shown", "offer_id": "off_1", "shown": [CREAM, CHEAPER, OWN], "dropped": [YOGHURT],
          "held_back": [WHIPPING], "notes": [], "synthetic_history": True}
VALIOS = {"event": "suggestions.shown", "offer_id": "off_1", "shown": [_brief(each) for each in (CREAM, CHEAPER, OWN)],
          "dropped_count": 1, "dropped_by_reason": {"BUYER_REQUIREMENT": 1},
          "held_back": [{**_brief(WHIPPING), "reason": "KIND_ALREADY_SHOWN"}]}
AGENT = Actor(kind=ActorKind.AGENT, id="agent:hotel-kitchen", display_name="Hotel kitchen agent")
CHEF = Actor(kind=ActorKind.HUMAN, id="human:hanna", role="purchasing_manager", display_name="Hanna Laine")


def _shown(trail: AuditTrail, buyers: dict[str, Any], valios: dict[str, Any]) -> Any:
    facts = {"suggestions": buyers, SUPPLIER_VIEW: {"suggestions": valios}}
    return trail.record(AuditEventType.SUGGESTIONS_SHOWN, AGENT,
                        AuditContext(offer_id="off_1", profile_id="hotel-kitchen", facts=facts))


def _accepted(trail: AuditTrail, actor: Actor, suggestion: dict[str, Any]) -> Any:
    buyers = {"event": "suggestion.accepted", "offer_id": "off_1", "new_offer_id": "off_2",
              "accepted_by": actor.display_name, **suggestion}
    valios = {"event": "suggestion.accepted", "offer_id": "off_1", "new_offer_id": "off_2", **_brief(suggestion)}
    facts = {"suggestion": buyers, SUPPLIER_VIEW: {"suggestion": valios}}
    return trail.record(AuditEventType.SUGGESTION_ACCEPTED, actor,
                        AuditContext(offer_id="off_1", profile_id="hotel-kitchen", facts=facts))


def test_the_two_event_types_are_named_as_proposed() -> None:
    assert (AuditEventType.SUGGESTIONS_SHOWN.value, AuditEventType.SUGGESTION_ACCEPTED.value) == (
        "suggestions.shown", "suggestion.accepted",
    )


def test_the_buyer_reads_each_suggestion_shown_each_one_not_shown_and_each_one_held_back(trail: AuditTrail) -> None:
    event = _shown(trail, BUYERS, VALIOS)

    assert event.type == "tta.v1.suggestions.shown" and event.subject == "offer/off_1"
    assert event.data.sentence == (
        "3 suggestions were shown with offer off_1: the forgotten item Arla Pro Cooking cream 10% 1 L UHT lactose "
        "free (463797), 10 litres, €33.10 more before tax; the cheaper product with the same formula Oatly iKaffe "
        "Oat drink 1,5L (473278) in place of 468319, 30 litres, €42.00 less before tax; Valio Aimo's own "
        "suggestion Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775), 1 unit, €2.57 more before tax. "
        "1 was not shown: AIMO NATURAL YOGURT 5KG 2% LACTOSE FREE (464517), a forgotten item: its data does not "
        "rule out tree nuts (AN). 1 was held back: Arla Pro Whipping cream 1 L UHT lactose free (469346), a "
        "forgotten item: another forgotten item ranks higher. From a synthetic order history."
    )
    assert event.data.facts["suggestions"] == BUYERS
    assert SUPPLIER_VIEW not in event.data.facts  # the buyer's facts hold the full dict, not Valio's copy too


def test_valio_aimo_reads_counts_and_kinds_and_its_own_suggestion_by_name(trail: AuditTrail) -> None:
    event = _shown(trail, BUYERS, VALIOS)

    assert event.data.supplier_sentence == (
        "3 suggestions were shown to the buyer with offer off_1: a forgotten item, a cheaper product with the same "
        "formula and Valio Aimo's own suggestion Arla Milkdrink 1L lactose free fat free UHT Suomesta (462775). "
        "1 was not shown: 1 for a requirement of the buyer's (which one is not shown). 1 more passed every check "
        "and was held back: one suggestion per kind and three at most are shown."
    )
    assert event.data.supplier_facts == {"suggestions": VALIOS}
    text = event.data.supplier_sentence + str(event.data.supplier_facts)
    for buyers_own in ("tree nuts", "464517", "ALLERGEN", "orders_considered", "orders_matching", "synthetic"):
        assert buyers_own not in text


def test_each_reader_s_view_of_the_trail_gets_its_own_sentence_and_facts(trail: AuditTrail) -> None:
    _shown(trail, BUYERS, VALIOS)

    buyer = trail.view(AuditReader.BUYER, offer_id="off_1").events[0]
    supplier = trail.view(AuditReader.SUPPLIER, offer_id="off_1").events[0]

    assert buyer.facts["suggestions"]["dropped"][0]["reason"] == "ALLERGEN_NOT_RULED_OUT"
    assert supplier.facts == {"suggestions": VALIOS} and supplier.sentence.startswith("3 suggestions were shown to")
    assert supplier.actor == Actor(kind=ActorKind.AGENT, id="agent:hotel-kitchen")


def test_nothing_shown_and_nothing_computed_is_said_as_such(trail: AuditTrail) -> None:
    buyers = {**BUYERS, "shown": [], "dropped": [], "held_back": [], "synthetic_history": False,
              "notes": ["No suggestion was computed: Valio Aimo could not be reached."]}
    valios = {**VALIOS, "shown": [], "dropped_count": 0, "dropped_by_reason": {}, "held_back": []}

    event = _shown(trail, buyers, valios)

    assert event.data.sentence == (
        "No suggestion was shown with offer off_1. No suggestion was computed: Valio Aimo could not be reached."
    )
    assert event.data.supplier_sentence == "No suggestion was shown to the buyer with offer off_1."


def test_a_valio_aimo_suggestion_left_silent_is_in_the_buyers_sentence_only(trail: AuditTrail) -> None:
    silent = {**YOGHURT, "kind": "FROM_SUPPLIER", "product_id": "463203", "reason": "OTHER_PACK_KIND",
              "name": "Arla Portion milk 100x2 cl lactose free 1,5% UHT",
              "summary": "it is a portion pack and your usual milk is not"}
    buyers = {**BUYERS, "shown": [CREAM], "dropped": [silent], "held_back": []}
    valios = {**VALIOS, "shown": [_brief(CREAM)], "dropped_count": 0, "dropped_by_reason": {}, "held_back": []}

    event = _shown(trail, buyers, valios)

    assert "1 was not shown: Arla Portion milk 100x2 cl lactose free 1,5% UHT (463203), Valio Aimo's own " \
           "suggestion: it is a portion pack and your usual milk is not." in event.data.sentence
    assert event.data.supplier_sentence == (
        "1 suggestion was shown to the buyer with offer off_1: a forgotten item."
    )


def test_the_buyer_reads_who_accepted_which_suggestion_and_the_new_offer(trail: AuditTrail) -> None:
    event = _accepted(trail, CHEF, CREAM)

    assert event.type == "tta.v1.suggestion.accepted" and event.subject == "offer/off_1"
    assert event.data.sentence == (
        "Hanna Laine (purchasing manager) accepted the forgotten item Arla Pro Cooking cream 10% 1 L UHT lactose "
        "free (463797), 10 litres, €33.10 more before tax, suggested with offer off_1. The amended request became "
        "offer off_2, checked against every rule again: accepting is not an approval."
    )
    assert event.data.facts["suggestion"]["accepted_by"] == "Hanna Laine"


@pytest.mark.parametrize(
    ("actor", "suggestion", "expected"),
    [
        (CHEF, CREAM, "The buyer's purchasing manager accepted a forgotten item suggested with offer off_1. "
                      "The amended request became offer off_2."),
        (AGENT, OWN, "The buyer's agent accepted Valio Aimo's own suggestion Arla Milkdrink 1L lactose free fat "
                     "free UHT Suomesta (462775), suggested with offer off_1. The amended request became offer "
                     "off_2."),
    ],
)
def test_valio_aimo_reads_that_a_suggestion_was_accepted_by_role_and_kind(
    trail: AuditTrail, actor: Actor, suggestion: dict[str, Any], expected: str,
) -> None:
    event = _accepted(trail, actor, suggestion)

    assert event.data.supplier_sentence == expected
    assert "Hanna" not in event.data.supplier_sentence + str(event.data.supplier_facts)
    assert event.data.supplier_facts["suggestion"]["new_offer_id"] == "off_2"


def test_facts_that_are_not_the_shape_written_are_read_as_not_recorded(trail: AuditTrail) -> None:
    broken = {"suggestions": {"shown": "everything", "dropped": [1, None]}, SUPPLIER_VIEW: ["not", "a", "dict"]}

    event = trail.record(AuditEventType.SUGGESTIONS_SHOWN, AGENT, AuditContext(offer_id="off_1", facts=broken))

    assert event.data.sentence == "Suggestions were shown with offer off_1; which ones is not recorded."
    assert event.data.supplier_sentence == "Suggestions were shown to the buyer with offer off_1; which ones is " \
                                           "not recorded."
    assert event.data.supplier_facts == {}
