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
    assert cream.sentence == (
        "With this milk you usually also order Arla Pro Cooking cream 10% (463797): it was in 7 of your last 8 "
        "orders, 10 L each time, and it is not in this request. Adding 10 L costs €33.10. 114 L confirmed for "
        "Monday 16 November. From a synthetic order history."
    )


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
        assert f"The product makes no statement about {allergen}: a person must decide." in yoghurt.sentence
    assert yoghurt.sentence.endswith("A product whose data does not rule out an excluded allergen is not suggested.")


def test_nothing_the_school_is_shown_leaves_an_excluded_allergen_open(world: Any) -> None:
    found = world.suggest(SCHOOL, SCHOOL_OAT, standing_orders=world.standing_orders(SCHOOL))

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
    assert usual.sentence == (
        "You usually order about 100 L of Arla Semi skimmed milkdrink (469363): between 98 and 104 L in your last 6 "
        "orders. This request says 300 L. Order 100 L instead? For 100 L: €248.00. 384 L confirmed for Monday 16 "
        "November. From a synthetic order history."
    )
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
    assert cheaper.sentence == (
        "Because you buy Oatly iKaffe 0.5 L (468319), we suggest Oatly iKaffe Oat drink 1.5 L (473278): the same "
        "formula, €1.48 a litre instead of €2.88. For your 30 L: €44.40, €42.00 less. 234 L confirmed for Monday 16 "
        "November."
    )
    assert cheaper.checks[0].startswith("Same formula within our tolerance of 15% or 1 g")  # the page's "Why?"
    assert cheaper.effect.unit_price_before_eur == Decimal("2.88") and cheaper.effect.saving_ratio > 0
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
    assert trend.sentence == (
        "Your orders of Oatly Oat Drink Semi (470863) are growing: about 84 L in your last 3 orders, 70 L in the 3 "
        "before. Your standing order still says 60 L. Renew once at 84 L? For 84 L: €117.60. 1,414 L confirmed for "
        "Monday 16 November. From a synthetic order history."
    )
    assert trend.accept_request.standing_order_id == "so_school_weekly"
    assert not world.suggest(SCHOOL, SCHOOL_OAT).shown or all(
        each.kind is not SuggestionKind.QUANTITY_TREND for each in world.suggest(SCHOOL, SCHOOL_OAT).shown
    )  # without the buyer's standing orders there is no trend to speak of


def test_valio_aimos_own_suggestion_is_last_one_only_marked_and_related_to_a_usual_product(world: Any) -> None:
    # Of the usual requests, only the bakery's cream and coffee milk get one (lane SG): the others stay silent.
    found = world.suggest(BAKERY, BAKERY_CREAM, BAKERY_COFFEE_MILK)
    customer = shipped_customer(BAKERY)
    own = [each for each in found.shown if each.kind is SuggestionKind.FROM_SUPPLIER]

    assert len(own) == 1 and found.shown[-1] is own[0]
    suggestion = own[0]
    assert (suggestion.serves, suggestion.evidence.source) == (Serves.SUPPLIER, EvidenceSource.SUPPLIER)
    assert suggestion.sentence.startswith("Because you buy Oatly iKaffe 0.5 L (468319), Valio Aimo suggests ")
    assert suggestion.sentence.endswith("Suggested by Valio Aimo, not from your orders.")
    assert "From a synthetic order history." not in suggestion.sentence
    ordered = {product_id for order in customer.history for product_id in order.quantities}
    assert suggestion.product_id not in ordered | {usual.product_id for usual in customer.usual}
    assert suggestion.stock_confirmed is True and suggestion.accept_request is not None
    assert all(each.serves is Serves.BUYER for each in found.shown[:-1])
    for customer_id, lines in ((HOTEL, (HOTEL_MILK,)), (WARD, (WARD_SOYA,))):
        assert all(each.kind is not SuggestionKind.FROM_SUPPLIER for each in world.suggest(customer_id, *lines).shown)


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


def test_a_product_type_the_catalog_does_not_have_is_said_on_the_suggestion_list(world_now: Any) -> None:
    # Review finding S15: before, a mistyped type in a customer file gave a silent "no related product".
    from tta.customers import shipped_customer
    from tta.suggestions import suggestions_for
    from tta.suggestions.history import history_of
    from tta.suggestions.supplier import related_products

    hotel = shipped_customer("hotel-kitchen")
    assert hotel is not None
    mistyped = hotel.model_copy(update={
        "usual": tuple(usual.model_copy(update={"product_type": "mlik"}) for usual in hotel.usual),
    })
    request = world_now.request({"text": "milk", "product_ids": ["469363"], "quantity": "100", "unit": "L"})
    offer = world_now.offer("hotel-kitchen", request)

    found = suggestions_for(mistyped, request, offer, profile=world_now.profile("hotel-kitchen"),
                            ports=world_now.ports)

    first = mistyped.usual[0].product_id
    assert len(found.notes) == 1
    assert found.notes[0].startswith(
        f"The customer file names a product type the catalog does not have: mlik (for {first})."
    )
    assert found.notes[0].endswith("No related product could be suggested from it.")
    assert related_products(mistyped, history_of(mistyped, {}), request, (), world_now.catalog) == ()
    plain = suggestions_for(hotel, request, offer, profile=world_now.profile("hotel-kitchen"), ports=world_now.ports)
    assert plain.notes == ()
