"""`suggestions_for`: the one function the gateway calls (P15 R3). Tonight's recording, at both clocks.

Every figure below was measured offline in replay on the recording `2026-11-14-demo`, and is the same at the
recording's instant (Sat 14 Nov 02:52) and at the demo clock (Thu 12 Nov 14:15 Helsinki).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import AvailabilityState, DataSource, Unit
from tta.contracts.errors import SupplierUnavailable
from tta.contracts.suggestion import KIND_ORDER, EvidenceSource, Serves, SuggestionKind
from tta.customers import shipped_customer
from tta.suggestions import DropReason, SuggestionPorts, suggestions_for
from tta.suggestions.thresholds import MAX_SUGGESTIONS

HOTEL, WARD, SCHOOL, BAKERY = "hotel-kitchen", "allergy-ward", "school-kitchen", "bakery-cafe"
HOTEL_MILK = {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}
WARD_SOYA = {"text": "200 L of soya drink 464013", "product_ids": ["464013"], "quantity": 200, "unit": "L"}
SCHOOL_OAT = {"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"}
BAKERY_CREAM = {"text": "40 L of whipping cream 469346", "product_ids": ["469346"], "quantity": 40, "unit": "L"}
BAKERY_COFFEE_MILK = {"text": "60 L of coffee milk 463380", "product_ids": ["463380"], "quantity": 60, "unit": "L"}
BAKERY_IKAFFE = {"text": "30 L of Oatly iKaffe 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}


def _kinds(found: Any) -> list[tuple[SuggestionKind, str]]:
    return [(each.kind, each.product_id) for each in found.shown]


def test_the_hotels_forgotten_cream_is_shown_complete_with_its_price_and_confirmed_stock(world: Any) -> None:
    found = world.suggest(HOTEL, HOTEL_MILK)

    cream = found.shown[0]
    assert (cream.kind, cream.product_id, cream.quantity, cream.unit) == (
        SuggestionKind.FORGOTTEN_ITEM, "463797", Decimal(10), Unit.L,
    )
    assert cream.stock_confirmed is True
    assert cream.availability is not None and cream.availability.state is AvailabilityState.CONFIRMED
    assert cream.availability.usable_amount == Decimal(114)
    assert cream.effect is not None and cream.effect.net_change_eur == Decimal("33.10")
    assert cream.sentence.endswith(
        "114 sales units are confirmed in stock for delivery on Monday 16 November. "
        "Adding it costs €33.10 before tax."
    )
    assert "From a synthetic order history." in cream.sentence


def test_a_suggestion_never_adds_itself_it_carries_the_request_to_post(world: Any) -> None:
    request = world.request(HOTEL_MILK)
    offer = world.offer(HOTEL, request)
    before = offer.model_dump()

    found = suggestions_for(shipped_customer(HOTEL), request, offer, profile=world.profile(HOTEL), ports=world.ports)

    assert offer.model_dump() == before and offer.suggestions == ()
    assert all(each.accept_request is not None for each in found.shown)
    accept = found.shown[0].accept_request
    assert [line.product_ids for line in accept.lines] == [("469363",), ("463797",)]
    assert world.offer(HOTEL, accept).options[0].totals.net == Decimal("281.10")  # P15 moment 1, measured


def test_the_schools_forgotten_yoghurt_states_nothing_about_nuts_or_sesame_and_is_not_suggested(world: Any) -> None:
    found = world.suggest(SCHOOL, SCHOOL_OAT)

    assert all(each.product_id != "464517" for each in (*found.shown, *(held.suggestion for held in found.held_back)))
    yoghurt = next(each for each in found.dropped if each.product_id == "464517")
    assert (yoghurt.kind, yoghurt.reason) == (SuggestionKind.FORGOTTEN_ITEM, DropReason.ALLERGEN_NOT_RULED_OUT)
    for allergen in ("tree nuts (AN)", "peanuts (AP)", "sesame seeds (AS)"):
        assert f"The product makes no statement about {allergen}: a dietitian must decide." in yoghurt.sentence
    assert yoghurt.sentence.endswith("A product whose data does not rule out an excluded allergen is not suggested.")


def test_nothing_the_school_is_shown_leaves_an_excluded_allergen_open(world: Any) -> None:
    found = world.suggest(SCHOOL, SCHOOL_OAT)

    assert found.shown
    for each in found.shown:
        product = world.catalog.get_product(each.product_id)
        free_from = {statement.code for statement in product.allergen_statements
                     if statement.relation.value == "FREE_FROM"}
        assert {"AN", "AP", "AS"} <= free_from, each.product_id


def test_the_wards_rice_drink_is_suggested_under_its_strict_rule(world: Any) -> None:
    found = world.suggest(WARD, WARD_SOYA)

    rice = found.shown[0]
    assert (rice.kind, rice.product_id, rice.quantity) == (SuggestionKind.FORGOTTEN_ITEM, "473424", Decimal(20))
    assert rice.effect is not None and rice.effect.net_change_eur == Decimal("47.20")
    assert rice.availability is not None and rice.availability.usable_amount == Decimal(109)
    assert any("free from milk" in said for said in rice.checks)
    assert world.offer(WARD, rice.accept_request).options[0].totals.net == Decimal("449.20")  # P15 moment 2


def test_a_line_that_names_only_a_type_gets_the_usual_product_and_the_forgotten_item_of_what_was_chosen(
    world: Any,
) -> None:
    milk = {"text": "100 L of lactose-free milk", "product_type": "milk", "required_claims": ["FREE_FROM_LACTOSE"],
            "quantity": 100, "unit": "L"}
    request = world.request(milk)
    offer = world.offer(HOTEL, request)
    chosen = {line.product_id for line in offer.options[0].lines}

    found = suggestions_for(shipped_customer(HOTEL), request, offer, profile=world.profile(HOTEL), ports=world.ports)

    shown = dict(_kinds(found))
    if chosen == {"469363"}:  # the offer chose the usual milk alone: the cream is found from it, nothing else to say
        assert shown.get(SuggestionKind.FORGOTTEN_ITEM) == "463797"
        assert SuggestionKind.USUAL_PRODUCT not in shown
    else:
        assert shown.get(SuggestionKind.USUAL_PRODUCT) == "469363"
        usual = next(each for each in found.shown if each.kind is SuggestionKind.USUAL_PRODUCT)
        assert usual.accept_request.lines[0].product_ids == ("469363",)
        assert usual.accept_request.lines[0].required_claims == ("FREE_FROM_LACTOSE",)  # nothing is widened


def test_a_quantity_far_from_the_usual_one_is_told_the_usual_quantity(world: Any) -> None:
    found = world.suggest(HOTEL, {**HOTEL_MILK, "quantity": 300})
    usual = next(each for each in found.shown if each.kind is SuggestionKind.USUAL_QUANTITY)

    assert (usual.product_id, usual.quantity, usual.request_line_index) == ("469363", Decimal(100), 0)
    assert usual.sentence.startswith("This line asks for 300 L. You usually order 100 L of ")
    assert usual.accept_request.lines[0].quantity == Decimal(100)
    assert usual.evidence.thresholds["USUAL_QUANTITY_MIN_DIFFERENCE"] == Decimal("0.25")
    assert all(each.kind is not SuggestionKind.USUAL_QUANTITY for each in world.suggest(HOTEL, HOTEL_MILK).shown)


def test_at_most_three_are_shown_in_the_decided_order_one_per_kind_and_the_rest_is_held_back(world: Any) -> None:
    found = world.suggest(BAKERY, BAKERY_IKAFFE)

    assert len(found.shown) == MAX_SUGGESTIONS
    ranks = [KIND_ORDER.index(each.kind) for each in found.shown]
    assert ranks == sorted(ranks) and len(set(ranks)) == len(ranks)  # decision B32: one per kind
    assert [each.suggestion.kind for each in found.held_back][:2] == [SuggestionKind.FORGOTTEN_ITEM] * 2
    assert len({each.product_id for each in found.shown}) == len(found.shown)


def test_the_cheaper_product_states_both_prices_and_that_the_formula_is_kept(world: Any) -> None:
    found = world.suggest(BAKERY, BAKERY_IKAFFE)
    cheaper = next(each for each in found.shown if each.kind is SuggestionKind.CHEAPER_SAME_FORMULA)

    assert (cheaper.product_id, cheaper.replaces_product_id, cheaper.quantity) == ("473278", "468319", Decimal(30))
    assert cheaper.effect is not None and cheaper.effect.net_change_eur == Decimal("-42.00")
    assert "costs €1.48 per litre against €2.88 for Oatly iKaffe 0,5L (468319): 49% less." in cheaper.sentence
    assert "It keeps the formula within our tolerance. Same formula within our tolerance of 15% or 1 g" in (
        cheaper.sentence
    )
    assert "20 × 1.5 L cover the 30 L for €44.40, €42.00 less. 156 are confirmed in stock" in cheaper.sentence
    assert cheaper.evidence.source is EvidenceSource.CATALOG and cheaper.stock_confirmed is True
    assert cheaper.accept_request.lines[0].product_ids == ("473278",)


def test_the_larger_pack_is_the_same_product_and_not_the_cheaper_kind(world: Any) -> None:
    found = world.suggest(BAKERY, BAKERY_IKAFFE)
    larger = next(each for each in found.shown if each.kind is SuggestionKind.LARGER_PACK)

    assert (larger.product_id, larger.replaces_product_id) == ("464320", "468319")
    assert larger.effect is not None and larger.effect.net_change_eur == Decimal("-33.00")


def test_the_trend_of_the_schools_standing_order_speaks_when_the_request_holds_its_product(world: Any) -> None:
    found = world.suggest(SCHOOL, SCHOOL_OAT, standing_orders=world.standing_orders(SCHOOL))
    trend = next(each for each in found.shown if each.kind is SuggestionKind.QUANTITY_TREND)

    assert (trend.product_id, trend.quantity, trend.standing_order_id) == ("470863", Decimal(84), "so_school_weekly")
    assert "a median of 84 L against 70 L for the 3 before (+20%)" in trend.sentence
    assert trend.sentence.endswith("84 L is 84 sales units at €1.40 each: €117.60 before tax.")
    assert trend.accept_request.standing_order_id == "so_school_weekly"
    assert not world.suggest(SCHOOL, SCHOOL_OAT).shown or all(
        each.kind is not SuggestionKind.QUANTITY_TREND for each in world.suggest(SCHOOL, SCHOOL_OAT).shown
    )  # without the buyer's standing orders there is no trend to speak of


def test_valio_aimos_own_suggestion_is_last_one_only_marked_and_related_to_a_usual_product(world: Any) -> None:
    usual_requests = ((HOTEL, (HOTEL_MILK,)), (WARD, (WARD_SOYA,)), (BAKERY, (BAKERY_CREAM, BAKERY_COFFEE_MILK)))
    for customer_id, lines in usual_requests:
        found = world.suggest(customer_id, *lines)
        customer = shipped_customer(customer_id)
        own = [each for each in found.shown if each.kind is SuggestionKind.FROM_SUPPLIER]

        assert len(own) == 1 and found.shown[-1] is own[0], customer_id
        suggestion = own[0]
        assert (suggestion.serves, suggestion.evidence.source) == (Serves.SUPPLIER, EvidenceSource.SUPPLIER)
        assert suggestion.sentence.startswith(f"Valio Aimo suggests {suggestion.name} ({suggestion.product_id}): ")
        assert "Suggested by Valio Aimo from its catalog, not from your orders." in suggestion.sentence
        ordered = {product_id for order in customer.history for product_id in order.quantities}
        assert suggestion.product_id not in ordered | {usual.product_id for usual in customer.usual}
        assert suggestion.stock_confirmed is True and suggestion.accept_request is not None
        assert all(each.serves is Serves.BUYER for each in found.shown[:-1])


def test_valio_aimos_own_suggestion_can_be_switched_off(world: Any) -> None:
    found = world.suggest(HOTEL, HOTEL_MILK, supplier_suggestions=False)

    assert _kinds(found) == [(SuggestionKind.FORGOTTEN_ITEM, "463797")]
    assert all(each.kind is not SuggestionKind.FROM_SUPPLIER for each in found.dropped)


def test_a_product_already_in_an_order_for_the_date_is_dropped_with_the_reason(world: Any) -> None:
    found = world.suggest(HOTEL, HOTEL_MILK, already_ordered=("463797",), supplier_suggestions=False)

    assert found.shown == ()
    assert [(each.product_id, each.reason) for each in found.dropped] == [("463797", DropReason.ALREADY_ORDERED)]


def test_a_buyer_without_a_customer_file_gets_the_catalog_kinds_only(world_now: Any) -> None:
    request = world_now.request(BAKERY_IKAFFE)
    offer = world_now.offer(HOTEL, request)

    found = suggestions_for(None, request, offer, profile=world_now.profile(HOTEL), ports=world_now.ports)

    assert _kinds(found) == [(SuggestionKind.CHEAPER_SAME_FORMULA, "473278"), (SuggestionKind.LARGER_PACK, "464320")]
    assert all(each.customer_id == HOTEL for each in found.shown)


def test_an_offer_with_no_option_gets_only_what_the_history_says(world_now: Any) -> None:
    request = world_now.request(HOTEL_MILK)
    empty = world_now.offer(HOTEL, request).model_copy(update={"options": ()})

    found = suggestions_for(shipped_customer(HOTEL), request, empty, profile=world_now.profile(HOTEL),
                            ports=world_now.ports, supplier_suggestions=False)

    assert _kinds(found) == [(SuggestionKind.FORGOTTEN_ITEM, "463797")]


def test_a_supplier_that_cannot_be_reached_gives_no_suggestion_and_says_so(world_now: Any) -> None:
    class Down:
        source = DataSource.REPLAY

        def price(self, product_ids: Any, *, fresh: bool = False) -> Any:
            raise SupplierUnavailable("Valio Aimo could not be reached.")

        def availability(self, product_ids: Any, *, fresh: bool = False) -> Any:
            raise SupplierUnavailable("Valio Aimo could not be reached.")

    request = world_now.request(HOTEL_MILK)
    ports = SuggestionPorts(catalog=world_now.catalog, gateway=Down(), clock=world_now.replay.clock)

    found = suggestions_for(shipped_customer(HOTEL), request, world_now.offer(HOTEL, request),
                            profile=world_now.profile(HOTEL), ports=ports)

    assert (found.shown, found.dropped) == ((), ())
    assert len(found.notes) == 1 and found.notes[0].startswith("No suggestion was computed: ")
