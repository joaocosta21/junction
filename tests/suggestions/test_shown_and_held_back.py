"""Decision B32 on tonight's recording: one suggestion per kind and three in all; Valio Aimo's own suggestion stays
silent when only another pack kind than the usual product passes, when one pack is in stock, or when it has no
benefit to state (lane SG); and the switch that turns Valio Aimo's own off says nothing about it.

Measured offline in replay on the recording `2026-11-14-demo`, at the recording's instant and at the demo clock.
"""

from __future__ import annotations

from typing import Any

from tta.contracts.suggestion import Serves, SuggestionKind
from tta.suggestions import DropReason
from tta.suggestions.events import suggestions_shown_facts, suggestions_shown_supplier_facts
from tta.suggestions.ranking import HoldReason

K = SuggestionKind
HOTEL, WARD, SCHOOL, BAKERY = "hotel-kitchen", "allergy-ward", "school-kitchen", "bakery-cafe"
HOTEL_MILK = {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}
WARD_SOYA = {"text": "200 L of soya drink 464013", "product_ids": ["464013"], "quantity": 200, "unit": "L"}
SCHOOL_MILK = {"text": "120 L of milk 462775", "product_ids": ["462775"], "quantity": 120, "unit": "L"}
SCHOOL_OAT = {"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"}
BAKERY_IKAFFE = {"text": "30 L of Oatly iKaffe 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}
BAKERY_CREAM = {"text": "40 L of whipping cream 469346", "product_ids": ["469346"], "quantity": 40, "unit": "L"}
BAKERY_COFFEE_MILK = {"text": "60 L of coffee milk 463380", "product_ids": ["463380"], "quantity": 60, "unit": "L"}


def _shown(found: Any) -> list[tuple[SuggestionKind, str]]:
    return [(each.kind, each.product_id) for each in found.shown]


def _every_kind(found: Any) -> set[SuggestionKind]:
    return {*(each.kind for each in found.shown), *(each.suggestion.kind for each in found.held_back),
            *(each.kind for each in found.dropped)}


def test_the_bakerys_cheaper_line_is_shown_beside_one_forgotten_item(world: Any) -> None:
    found = world.suggest(BAKERY, BAKERY_IKAFFE)

    assert _shown(found) == [(K.FORGOTTEN_ITEM, "463380"), (K.CHEAPER_SAME_FORMULA, "473278"),
                             (K.LARGER_PACK, "464320")]
    cheaper = found.shown[1]
    assert cheaper.effect is not None and str(cheaper.effect.net_change_eur) == "-42.00"
    held = [(each.suggestion.kind, each.suggestion.product_id, each.reason, each.summary) for each in found.held_back]
    assert held[:2] == [
        (K.FORGOTTEN_ITEM, "469346", HoldReason.KIND_ALREADY_SHOWN, "another forgotten item ranks higher"),
        (K.FORGOTTEN_ITEM, "464727", HoldReason.KIND_ALREADY_SHOWN, "another forgotten item ranks higher"),
    ]


def test_no_two_suggestions_of_one_kind_are_shown_for_any_customers_usual_request(world: Any) -> None:
    usual = {HOTEL: (HOTEL_MILK,), WARD: (WARD_SOYA,), SCHOOL: (SCHOOL_MILK, SCHOOL_OAT),
             BAKERY: (BAKERY_CREAM, BAKERY_COFFEE_MILK)}
    for customer_id, lines in usual.items():
        found = world.suggest(customer_id, *lines, standing_orders=world.standing_orders(customer_id))
        kinds = [each.kind for each in found.shown]

        assert len(kinds) == len(set(kinds)) <= 3, customer_id
        assert all(each.summary for each in found.held_back), customer_id


def test_valio_aimos_own_portion_milk_is_not_put_to_the_school_for_its_bulk_milk(world: Any) -> None:
    found = world.suggest(SCHOOL, SCHOOL_MILK, SCHOOL_OAT)

    assert all(each.product_id != "463203" for each in (*found.shown, *(h.suggestion for h in found.held_back)))
    # Another pack kind is tried last and silenced before the guard; the school's five tries end before it.
    assert all(each.reason == DropReason.OTHER_PACK_KIND for each in found.dropped if each.product_id == "463203")


def test_valio_aimos_own_suggestion_with_one_pack_in_stock_is_not_suggested_to_the_ward(world: Any) -> None:
    found = world.suggest(WARD, WARD_SOYA)

    assert all(each.product_id != "460509" for each in found.shown)
    silent = next(each for each in found.dropped if each.product_id == "460509")
    # For the ward's own 200 L, 1 pack is short: the guard's own stock check says so before decision B32 does.
    assert (silent.kind, silent.reason) == (K.FROM_SUPPLIER, DropReason.STOCK_TOO_LOW)
    assert silent.sentence == "1 pack is confirmed in stock and 200 are needed for 200 L."
    assert silent.summary == "1 pack is confirmed in stock and 200 are needed"


def test_valio_aimo_never_reads_why_its_own_suggestion_stayed_silent(world: Any) -> None:
    for customer_id, lines in ((SCHOOL, (SCHOOL_MILK, SCHOOL_OAT)), (SCHOOL, (SCHOOL_OAT,))):
        found = world.suggest(customer_id, *lines)
        silenced = [each for each in found.dropped if each.reason in (
            DropReason.OTHER_PACK_KIND, DropReason.ONE_UNIT_IN_STOCK, DropReason.NO_STATED_BENEFIT)]
        assert silenced, customer_id

        facts = suggestions_shown_supplier_facts(found, offer_id="off_1")

        assert all(reason not in str(facts) for reason in (DropReason.OTHER_PACK_KIND, DropReason.ONE_UNIT_IN_STOCK,
                                                           DropReason.NO_STATED_BENEFIT))
        assert all(each.product_id not in str(facts) for each in silenced)
        assert facts["dropped_count"] == len(found.dropped) - len(silenced)
        buyers = suggestions_shown_facts(found, offer_id="off_1")
        assert {each["reason"] for each in buyers["dropped"]} >= {each.reason for each in silenced}


def test_switched_off_valio_aimos_own_suggestion_is_nowhere_and_nothing_is_said_of_it(world: Any) -> None:
    for customer_id, lines in ((HOTEL, (HOTEL_MILK,)), (BAKERY, (BAKERY_IKAFFE,)), (WARD, (WARD_SOYA,)),
                               (SCHOOL, (SCHOOL_MILK, SCHOOL_OAT))):
        found = world.suggest(customer_id, *lines, supplier_suggestions=False)

        assert K.FROM_SUPPLIER not in _every_kind(found), customer_id
        assert found.notes == (), customer_id
        assert all(each.serves is Serves.BUYER for each in found.shown)
        for facts in (suggestions_shown_facts(found, offer_id="off_1"),
                      suggestions_shown_supplier_facts(found, offer_id="off_1")):
            text = str(facts)
            assert "FROM_SUPPLIER" not in text and "Valio Aimo suggests" not in text, customer_id
            assert "Valio Aimo's own" not in text, customer_id
