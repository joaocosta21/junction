"""Valio Aimo's own suggestion speaks only with a benefit a buyer cares about (lane SG, the owner's rule of 14 Nov).

The owner saw the hotel, asking for milk, offered one carton of a whipping cream "like the cooking cream you
usually order". The rule now: the same kind of thing the customer already uses (type, use, flavour), one benefit
computed from the data in front of it (a lower price for the same formula, stock where the usual product is short,
a claim or label the usual product lacks, fewer packs), the customer's own quantity, a short sentence; otherwise
silence. Measured offline in replay on the recording `2026-11-14-demo`, at the recording's instant and at the demo
clock (Thu 12 Nov 2026 14:15 Helsinki); every figure below is the same at both.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from tta.audit import AuditTrail
from tta.catalog.kinds import uses_of
from tta.contracts.audit import Actor, ActorKind
from tta.contracts.availability import AvailabilityAssessment
from tta.contracts.common import AvailabilityState, Unit
from tta.contracts.product import Product
from tta.contracts.suggestion import EvidenceSource, Serves, Suggestion, SuggestionEvidence, SuggestionKind
from tta.customers import shipped_customer
from tta.store import SqliteStore
from tta.suggestions import DropReason, SuggestionList, SuggestionPorts, suggestions_for
from tta.suggestions.events import record_suggestions_shown
from tta.suggestions.guard import DroppedSuggestion
from tta.suggestions.history import history_of
from tta.suggestions.supplier import Related, related_products, silenced
from tta.suggestions.supplier_benefits import BenefitKind, Measured, benefits

K = SuggestionKind
HOTEL, WARD, SCHOOL, BAKERY = "hotel-kitchen", "allergy-ward", "school-kitchen", "bakery-cafe"
MONDAY = date(2026, 11, 16)
HOTEL_MILK = {"text": "100 L of milk 469363", "product_ids": ["469363"], "quantity": 100, "unit": "L"}
# The brief's request as the hotel's page sends it: the offer chooses 469363 and 462775 for it.
HOTEL_1000_LACTOSE_FREE = {"text": "1000 litres of lactose-free milk by Monday", "product_type": "milk",
                           "required_claims": ["FREE_FROM_LACTOSE"], "quantity": 1000, "unit": "L"}
WARD_SOYA = {"text": "200 L of soya drink 464013", "product_ids": ["464013"], "quantity": 200, "unit": "L"}
SCHOOL_MILK = {"text": "120 L of milk 462775", "product_ids": ["462775"], "quantity": 120, "unit": "L"}
SCHOOL_OAT = {"text": "60 L of oat drink 470863", "product_ids": ["470863"], "quantity": 60, "unit": "L"}
BAKERY_CREAM = {"text": "40 L of whipping cream 469346", "product_ids": ["469346"], "quantity": 40, "unit": "L"}
BAKERY_COFFEE_MILK = {"text": "60 L of coffee milk 463380", "product_ids": ["463380"], "quantity": 60, "unit": "L"}
BAKERY_IKAFFE = {"text": "30 L of Oatly iKaffe 468319", "product_ids": ["468319"], "quantity": 30, "unit": "L"}
SILENCED = (DropReason.OTHER_PACK_KIND, DropReason.ONE_UNIT_IN_STOCK, DropReason.NO_STATED_BENEFIT)


def _own(found: SuggestionList) -> list[Suggestion]:
    return [each for each in found.shown if each.kind is K.FROM_SUPPLIER]


def _everywhere(found: SuggestionList) -> set[str]:
    return {*(each.product_id for each in found.shown), *(each.suggestion.product_id for each in found.held_back),
            *(each.product_id for each in found.dropped)}


# --- the reproduction -----------------------------------------------------------------------------------------


def test_the_hotel_asking_for_milk_is_never_offered_the_whipping_cream(world: Any) -> None:
    # Before: "Valio Aimo suggests Arla Pro Whipping cream 1 L UHT lactose free (469346): a cream of the brand
    # Arla Pro, like the Arla Pro Cooking cream 10% 1 L UHT lactose free (463797) you usually order, ...
    # Adding it costs €5.77 before tax." A cooking-cream buyer is never offered a whipping cream.
    found = world.suggest(HOTEL, HOTEL_1000_LACTOSE_FREE)

    assert "469346" not in _everywhere(found)
    assert _own(found) == []
    hotel = shipped_customer(HOTEL)
    request = world.request(HOTEL_1000_LACTOSE_FREE)
    pool = related_products(hotel, history_of(hotel), request, ("469363", "462775"), world.catalog)
    for each in pool:
        product, usual = (world.catalog.get_product(pid) for pid in (each.suggestion.product_id, each.anchor_id))
        assert uses_of(product) == uses_of(usual), product.id  # cooking for cooking, whipping for whipping


# --- each benefit -------------------------------------------------------------------------------------------------


def test_a_lower_price_for_the_same_formula_is_said_with_both_prices_for_the_usual_quantity(world: Any) -> None:
    found = world.suggest(BAKERY, BAKERY_CREAM, BAKERY_COFFEE_MILK)

    (own,) = _own(found)
    assert (own.product_id, own.replaces_product_id, own.quantity, own.unit) == ("473278", "468319", 30, Unit.L)
    assert own.sentence == (
        "Because you buy Oatly iKaffe 0.5 L (468319), Valio Aimo suggests Oatly iKaffe Oat drink 1.5 L (473278): "
        "the same kind of plant drink, with the same formula, €1.48 a litre instead of €2.88. For your usual 30 L: "
        "€44.40, €42.00 less. 234 L confirmed for Monday 16 November. Suggested by Valio Aimo, not from your orders."
    )
    assert own.checks[0].startswith("Valio Aimo's reason, computed: the same formula as Oatly iKaffe (468319)")
    assert own.evidence.thresholds == {"CHEAPER_MIN_SAVING": Decimal("0.05")}
    assert own.evidence.values[0] == Decimal(30)  # the usual quantity: the median of the bakery's last 6 orders
    assert own.effect is not None and own.effect.net_change_eur == Decimal("44.40")  # it adds a line of 30 L
    assert (own.effect.unit_price_before_eur, own.effect.unit_price_after_eur) == (Decimal("2.88"), Decimal("1.48"))
    line = own.accept_request.lines[-1]
    assert (line.product_ids, line.quantity, line.unit) == (("473278",), Decimal(30), Unit.L)  # never one unit


class _Stock:
    """The recording, with the confirmed stock of a few products set by hand: built data for one benefit."""

    def __init__(self, inner: Any, stock: dict[str, int]) -> None:
        self.inner, self.stock = inner, stock
        self.source, self.time_basis = inner.source, getattr(inner, "time_basis", None)

    def price(self, product_ids: Any, *, fresh: bool = False) -> Any:
        return self.inner.price(product_ids)

    def availability(self, product_ids: Any, *, fresh: bool = False) -> Any:
        found = self.inner.availability(product_ids)
        return found.model_copy(update={"lines": tuple(self._set(line) for line in found.lines)})

    def _set(self, line: Any) -> Any:
        if line.product_id not in self.stock or line.schedule_line is None:
            return line
        amount = Decimal(self.stock[line.product_id])
        return line.model_copy(update={"schedule_line": line.schedule_line.model_copy(
            update={"available_amount": amount})})


def _with_stock(world: Any, customer_id: str, line: dict[str, Any], stock: dict[str, int]) -> SuggestionList:
    request = world.request(line)
    ports = SuggestionPorts(catalog=world.catalog, gateway=_Stock(world.replay, stock), clock=world.replay.clock)
    return suggestions_for(shipped_customer(customer_id), request, world.offer(customer_id, request),
                           profile=world.profile(customer_id), ports=ports)


def test_stock_where_the_usual_product_is_short_is_said_first_and_a_label_second(world_now: Any) -> None:
    found = _with_stock(world_now, HOTEL, HOTEL_MILK, {"469363": 12, "462775": 200})

    (own,) = _own(found)
    assert own.sentence == (
        "Because you buy Arla Semi skimmed milkdrink (469363), Valio Aimo suggests Arla Milkdrink (462775): the same "
        "kind of milk, with 200 L confirmed for Monday 16 November where yours has only 12 L; it also has the Finnish "
        "Heart Symbol yours does not have. For your 100 L: €257.00, €9.00 more. Suggested by Valio Aimo, not from "
        "your orders."
    )
    assert own.checks[0] == (
        "Valio Aimo's reason, computed: 100 L needs 100 packs of Arla Semi skimmed milkdrink (469363), which has 12 "
        "packs confirmed for Monday 16 November; Arla Milkdrink (462775) has 200 packs confirmed and needs 100 packs."
    )
    assert own.evidence.values == (Decimal(100), Decimal(12), Decimal(200), Decimal(100), Decimal(100))
    # The request names the usual milk: accepting puts 462775 in its line, so the order changes by the difference.
    assert own.request_line_index == 0 and own.accept_request.lines[0].product_ids == ("462775",)
    assert own.effect is not None and own.effect.net_change_eur == Decimal("9.00")


def test_a_label_the_usual_product_lacks_is_named_in_words(world_now: Any) -> None:
    found = _with_stock(world_now, HOTEL, HOTEL_MILK, {"462775": 200})

    (own,) = _own(found)
    assert own.sentence == (
        "Because you buy Arla Semi skimmed milkdrink (469363), Valio Aimo suggests Arla Milkdrink (462775): the same "
        "kind of milk, with the Finnish Heart Symbol yours does not have. For your 100 L: €257.00, €9.00 more. 200 L "
        "confirmed for Monday 16 November. Suggested by Valio Aimo, not from your orders."
    )
    assert own.checks[0] == ("Valio Aimo's reason, computed: Valio Aimo's product data gives 462775 the label "
                             "FINNISH_HEART_SYMBOL and does not give it to 469363.")


def _product(product_id: str, **fields: Any) -> Product:
    return Product.model_validate({"id": product_id, "name_en": f"Kitchen cream {product_id} 1 L", "brand": "Test",
                                   "category": "10520", "sales_unit": "ST", "base_unit": "ST",
                                   "allowed_lot_size": 1, **fields})


def _measured(product: Product, *, units: int, per_unit: str, usable: int = 500, price: str = "3.00",
              quantity: int = 10) -> Measured:
    return Measured(product=product, quantity=Decimal(quantity), unit=Unit.L, state=AvailabilityState.CONFIRMED,
                    units=Decimal(units), unit_price=Decimal(price), usable=Decimal(usable),
                    per_unit=Decimal(per_unit), available_date=MONDAY, measure=Unit.L,
                    pack_in_measure=Decimal(per_unit))


def test_fewer_packs_for_the_usual_quantity_is_a_benefit_with_the_count_said() -> None:
    usual = _measured(_product("100001"), units=10, per_unit="1", price="3.00")
    larger = _measured(_product("100002"), units=2, per_unit="5", price="16.00")

    (found,) = benefits(usual, larger, MONDAY, "your usual 10 L")

    assert found.kind is BenefitKind.FEWER_PACKS
    assert found.clause == "in 5 L packs: 2 packs for your usual 10 L instead of 10"
    assert found.thresholds == {"LARGER_PACK_MAX_OVER": Decimal("0.10")}
    over = _measured(_product("100003"), units=1, per_unit="20", price="50.00")
    assert benefits(usual, over, MONDAY, "your usual 10 L") == ()  # 20 L for 10 L is no better fit


def test_a_dietary_claim_the_usual_product_lacks_comes_before_a_label() -> None:
    usual = _measured(_product("100001", labels=["SVANEN"]), units=10, per_unit="1")
    other = _measured(_product("100002", nutritional_claims=["FREE_FROM_LACTOSE"],
                               labels=["SVANEN", "EU_ORGANIC_FARMING"]), units=10, per_unit="1")

    (found,) = benefits(usual, other, MONDAY, "your usual 10 L")

    assert (found.kind, found.clause) == (
        BenefitKind.CLAIM_OR_LABEL_YOURS_LACKS, "marked lactose-free where yours is not")
    labelled = _measured(_product("100003", labels=["SVANEN", "EU_ORGANIC_FARMING"]), units=10, per_unit="1")
    assert benefits(usual, labelled, MONDAY, "x")[0].clause == "with the EU organic label yours does not have"
    unnamed = _measured(_product("100004", labels=["OFFICIAL_ECO_LABEL_SUN"]), units=10, per_unit="1")
    assert benefits(usual, unnamed, MONDAY, "x") == ()  # a label we cannot name is not said


def test_the_same_product_data_states_no_benefit() -> None:
    usual = _measured(_product("100001"), units=10, per_unit="1")

    assert benefits(usual, _measured(_product("100002"), units=10, per_unit="1"), MONDAY, "x") == ()


# --- silence ------------------------------------------------------------------------------------------------------


def test_with_no_benefit_valio_aimo_stays_silent_and_only_the_buyers_log_says_so(world: Any) -> None:
    found = world.suggest(SCHOOL, SCHOOL_OAT)

    assert _own(found) == []
    silent = next(each for each in found.dropped if each.product_id == "470889")
    assert (silent.kind, silent.reason, silent.summary) == (
        K.FROM_SUPPLIER, DropReason.NO_STATED_BENEFIT, "it offers no benefit Valio Aimo can state")
    assert silent.sentence == (
        "Valio Aimo had nothing to suggest that offers a stated benefit: Oatly Oat Drink Whole (470889) passed every "
        "check, and the data shows no lower price for the same formula, no stock where your Oatly Oat Drink Semi "
        "(470863) is short, no claim or label yours lacks and no fewer packs for your 60 L."
    )


def _dropped(product_id: str, reason: DropReason) -> DroppedSuggestion:
    return DroppedSuggestion(suggestion_id=f"sug_from_supplier_{product_id}_test", kind=K.FROM_SUPPLIER,
                             product_id=product_id, name=f"Silent product {product_id}", reason=reason.value,
                             sentence=f"Valio Aimo's own suggestion stays silent: {reason.value}.", summary="silent")


def test_valio_aimo_never_reads_a_count_a_reason_or_a_product_of_its_own_silent_suggestions(demo_clock: Any) -> None:
    found = SuggestionList(dropped=tuple(_dropped(f"10000{index}", reason) for index, reason in enumerate(SILENCED)))
    trail = AuditTrail(SqliteStore(), demo_clock)  # in memory: no data directory is written
    actor = Actor(kind=ActorKind.AGENT, id="agent:test", display_name="Test agent")

    event = record_suggestions_shown(trail, actor, found, offer_id="off_1", profile_id=HOTEL)

    valio = f"{event.data.supplier_sentence} {event.data.supplier_facts}"
    for index, reason in enumerate(SILENCED):
        assert reason.value not in valio and f"10000{index}" not in valio
        assert f"10000{index}" in event.data.sentence  # the buyer's log names each one
    assert "'dropped_count': 0" in valio and "'dropped_by_reason': {}" in valio


def test_one_pack_in_stock_is_still_silenced_when_the_usual_quantity_is_one_pack() -> None:
    evidence = SuggestionEvidence(source=EvidenceSource.SUPPLIER, synthetic=True, orders_considered=8,
                                  orders_matching=0)
    assessment = AvailabilityAssessment(product_id="460509", state=AvailabilityState.CONFIRMED,
                                        usable_amount=Decimal(1), sentence="1 confirmed.")
    passed = Suggestion(suggestion_id="sug_from_supplier_460509_test", kind=K.FROM_SUPPLIER, serves=Serves.SUPPLIER,
                        customer_id="test", product_id="460509", name="Alpro Soya drink, Original 1L",
                        quantity=Decimal(1), unit=Unit.UNIT, sentence="Suggested.", evidence=evidence,
                        availability=assessment)

    silent = silenced(Related(suggestion=passed, anchor_id="464013"), passed)

    assert silent is not None and silent.reason == DropReason.ONE_UNIT_IN_STOCK
    assert silent.sentence == ("Valio Aimo's own suggestion stays silent: 1 pack of Alpro Soya drink, Original "
                               "(460509) is confirmed in stock.")


# --- the four shipped customers, each usual request, at both clocks ---------------------------------------------

USUAL = {
    HOTEL: (HOTEL_MILK,), WARD: (WARD_SOYA,), SCHOOL: (SCHOOL_MILK, SCHOOL_OAT),
    BAKERY: (BAKERY_CREAM, BAKERY_COFFEE_MILK),
}
# What Valio Aimo's own suggestion is for each usual request: the product shown, or None and why it is silent.
OWN = {HOTEL: None, WARD: None, SCHOOL: None, BAKERY: "473278"}
WHY_SILENT = {
    HOTEL: {("462775", "STOCK_TOO_LOW"), ("463047", "DIETARY_CLAIM_MISSING")},
    WARD: {("460509", "STOCK_TOO_LOW")},
    SCHOOL: {("463047", "ALLERGEN_NOT_RULED_OUT"), ("469363", "ALLERGEN_NOT_RULED_OUT"),
             ("460825", "ALLERGEN_NOT_RULED_OUT"), ("470889", "NO_STATED_BENEFIT"), ("472145", "NO_STATED_BENEFIT")},
}
# The buyer's own kinds, measured on the code before this lane (commit e53519c): only their words changed.
BUYERS_KINDS = {
    HOTEL: [(K.FORGOTTEN_ITEM, "463797", Decimal(10))],
    WARD: [(K.FORGOTTEN_ITEM, "473424", Decimal(20))],
    SCHOOL: [(K.QUANTITY_TREND, "470863", Decimal(84))],
    BAKERY: [(K.FORGOTTEN_ITEM, "468319", Decimal(30))],
}


@pytest.mark.parametrize("customer_id", [HOTEL, WARD, SCHOOL, BAKERY])
def test_valio_aimos_own_suggestion_for_each_customers_usual_request(world: Any, customer_id: str) -> None:
    found = world.suggest(customer_id, *USUAL[customer_id], standing_orders=world.standing_orders(customer_id))

    own = _own(found)
    assert [each.product_id for each in own] == ([OWN[customer_id]] if OWN[customer_id] else [])
    buyers = [(each.kind, each.product_id, each.quantity) for each in found.shown if each.serves is Serves.BUYER]
    assert buyers == BUYERS_KINDS[customer_id]
    if not own:
        why = {(each.product_id, each.reason) for each in found.dropped if each.kind is K.FROM_SUPPLIER}
        assert why == WHY_SILENT[customer_id]
    for each in found.shown:
        assert "sales unit" not in each.sentence and "before tax" not in each.sentence
        assert each.sentence.endswith("From a synthetic order history.") is (each.serves is Serves.BUYER)


def test_stock_is_said_only_against_a_usual_product_with_a_known_shortage() -> None:
    covered = _measured(_product("100002"), units=10, per_unit="1", usable=200)
    short = Measured(product=_product("100001"), quantity=Decimal(10), unit=Unit.L, state=AvailabilityState.CONFIRMED,
                     units=Decimal(10), usable=Decimal(4), per_unit=Decimal(1), unit_price=Decimal("3.00"))
    unanswered = Measured(product=_product("100001"), quantity=Decimal(10), unit=Unit.L,
                          state=AvailabilityState.NOT_DELIVERABLE, units=Decimal(10), per_unit=Decimal(1),
                          recorded=False)

    (said,) = benefits(short, covered, MONDAY, "your usual 10 L")
    assert said.clause == "with 200 L confirmed for Monday 16 November where yours has only 4 L"
    assert benefits(unanswered, covered, MONDAY, "your usual 10 L") == ()  # no answer recorded: not "short"
    not_confirmed = Measured(product=_product("100001"), quantity=Decimal(10), unit=Unit.L,
                             state=AvailabilityState.QUANTITY_NOT_CONFIRMED, units=Decimal(10), per_unit=Decimal(1))
    (said,) = benefits(not_confirmed, covered, None, "x")
    assert said.clause == "with 200 L confirmed where yours has none confirmed"
