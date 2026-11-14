"""Exclusions and request handling of the offer builder, over hand-built data (SPEC sections 3 to 5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import (
    AllergenStrictness,
    AvailabilityState,
    CheckResult,
    ConstraintKind,
    ExclusionReason,
    Identity,
    OptionKind,
    PackPreference,
    Unit,
    Verdict,
)
from tta.contracts.errors import InvalidRequest, NotAuthorised, UnknownProduct
from tta.contracts.offer import Offer
from tta.contracts.ports import OfferBuilder, OfferRevalidator
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService, build_offer

# Three lactose-free milks of category 10400, each a 1-litre carton sold by the piece (ST).
# C was 463380, Arla Cafè milk, until milk for coffee became a product type of its own (14 Nov 2026).
A, B, C = "469363", "462775", "464201"
UNCONFIRMED = "464306"
PLACEHOLDER = 999_999

Build = Callable[..., Offer]


# --- exclusions --------------------------------------------------------------------------------------------

def test_each_availability_state_that_cannot_be_ordered_is_an_exclusion(
    build: Build, price: Any, stock: Any, reasons: Any
) -> None:
    offer = build(
        [price(A, "2.48"), price(B, "2.57"), price(C, "2.65"), price(UNCONFIRMED, "1.01")],
        [stock(A, 500, sales_block=True), stock(B, None), stock(C, 0),
         stock(UNCONFIRMED, 500, closing_time=datetime.fromisoformat("2026-11-14T02:52:45+02:00"))],
    )

    assert reasons(offer)[A] is ExclusionReason.BLOCKED
    assert reasons(offer)[B] is ExclusionReason.NOT_DELIVERABLE
    assert reasons(offer)[C] is ExclusionReason.OUT_OF_STOCK
    assert reasons(offer)[UNCONFIRMED] is ExclusionReason.CUTOFF_PASSED  # a cut-off equal to now has passed
    assert offer.options == ()


def test_a_cut_off_that_has_passed_excludes_a_product_without_a_needed_by_date_too(
    build: Build, price: Any, stock: Any, make_request: Any, reasons: Any
) -> None:
    passed = datetime.fromisoformat("2026-11-12T15:00:00+02:00")
    offer = build([price(A, "2.48")], [stock(A, 5000, closing_time=passed)], make_request(1000, needed_by=None))

    assert reasons(offer)[A] is ExclusionReason.CUTOFF_PASSED


def test_a_delivery_after_the_needed_by_date_is_excluded_as_late(
    build: Build, price: Any, stock: Any, best: Any, reasons: Any
) -> None:
    offer = build(
        [price(A, "2.48"), price(B, "2.57")],
        [stock(A, 5000, available_date=date(2026, 11, 17)), stock(B, 5000)],
    )

    assert reasons(offer)[A] is ExclusionReason.LATE_FOR_NEEDED_BY
    assert "Tuesday 17 Nov" in next(e.sentence for e in offer.excluded if e.product_id == A)
    assert [line.product_id for line in best(offer).lines] == [B]


@pytest.mark.parametrize(
    ("overrides", "word"),
    [
        ({"currency": "SEK"}, "SEK"),
        ({"value": "0"}, "0.00"),
        ({"value": "-1.50"}, "1.50"),
        ({"valid_from": datetime.fromisoformat("2026-12-01T00:00:00+02:00")}, "1 Dec 2026"),
        ({"valid_to": datetime.fromisoformat("2026-11-14T02:52:45+02:00")}, "14 Nov 2026"),
    ],
)
def test_a_price_that_cannot_be_relied_on_excludes_the_product(
    build: Build, price: Any, stock: Any, overrides: dict[str, Any], word: str, best: Any, reasons: Any
) -> None:
    values = {"value": "2.48", **overrides}
    offer = build([price(A, values.pop("value"), per_measure="2.48", **values), price(B, "2.57")],
                  [stock(A, 5000), stock(B, 5000)])

    assert reasons(offer)[A] is ExclusionReason.PRICE_UNAVAILABLE
    assert word in next(e.sentence for e in offer.excluded if e.product_id == A)
    assert [line.product_id for line in best(offer).lines] == [B]


def test_a_product_valio_returns_no_price_for_is_excluded(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any, reasons: Any
) -> None:
    request = make_request(10, Unit.UNIT, product_ids=(A, B))
    offer = build([price(B, "2.57")], [stock(A, 5000), stock(B, 5000)], request)

    assert reasons(offer)[A] is ExclusionReason.PRICE_UNAVAILABLE
    assert [line.product_id for line in best(offer).lines] == [B]


def test_a_portion_request_keeps_only_portion_packs(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any, reasons: Any
) -> None:
    request = make_request(10, Unit.L, pack=PackPreference.PORTION)
    offer = build(
        [price("463203", "15.09", per_measure="7.545"), price(A, "2.48")],
        [stock("463203", 192, sales_unit="KI"), stock(A, 5000)],
        request,
    )

    assert [(line.product_id, line.quantity, line.covers) for line in best(offer).lines] == [("463203", 5, 10)]
    assert reasons(offer)[A] is ExclusionReason.NOT_A_PORTION_PACK
    assert "portion" in next(e.sentence for e in offer.excluded if e.product_id == A)
    pack = next(check for check in best(offer).constraint_checks if check.kind is ConstraintKind.PACK)
    assert (pack.subject, pack.result) == ("PORTION", CheckResult.MET)


def test_a_pack_size_that_rests_on_another_sales_unit_is_unknown(
    build: Build, price: Any, stock: Any, best: Any, reasons: Any
) -> None:
    # Valio sells A by the case (KI) here while the product file describes the piece (ST), and the price
    # carries no comparison in litres: the size of what is sold is not known.
    kg_price = price(A, "2.48", per_measure="2.48", measure="KG")
    offer = build([kg_price, price(B, "2.57")], [stock(A, 5000, sales_unit="KI"), stock(B, 5000)])

    assert reasons(offer)[A] is ExclusionReason.PACK_SIZE_UNKNOWN
    assert [line.product_id for line in best(offer).lines] == [B]


def test_a_pack_size_from_the_price_holds_when_valio_sells_another_sales_unit(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    # Sold by the case of 10 litres (KI) while the product file describes the 1-litre piece (ST): the
    # comparison price follows the unit Valio sells, so 100 litres are 10 cases.
    offer = build([price(A, "24.80", per_measure="2.48")], [stock(A, 500, sales_unit="KI")], make_request(100))

    line = best(offer).lines[0]
    assert (line.product_id, line.quantity, line.sales_unit, line.covers) == (A, 10, "KI", 100)
    assert (line.pack_size.value, line.pack_size.source.value) == (10, "PRICE_RATIO")
    assert line.net == Decimal("248.00")


# --- the request -------------------------------------------------------------------------------------------

def test_an_unknown_product_id_is_an_unknown_product_error(build: Build, make_request: Any) -> None:
    with pytest.raises(UnknownProduct):
        build([], [], make_request(5, Unit.UNIT, product_ids=("000000",)))


def test_an_exclusion_without_a_strictness_is_an_invalid_request(build: Build, make_request: Any) -> None:
    with pytest.raises(InvalidRequest):
        build([], [], make_request(100, exclude_allergens=("AM",)))


def test_an_unknown_allergen_code_is_an_invalid_request(build: Build, make_request: Any) -> None:
    request = make_request(100, exclude_allergens=("QQ",), allergen_strictness=AllergenStrictness.STRICT)

    with pytest.raises(InvalidRequest):
        build([], [], request)


def test_a_caller_without_a_buyer_profile_gets_no_offer(build: Build, supplier_reader: Identity) -> None:
    with pytest.raises(NotAuthorised):
        build([], [], identity=supplier_reader)


def test_a_request_can_add_an_exclusion_and_every_line_then_carries_the_check(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    request = make_request(100, exclude_allergens=("AY",), allergen_strictness=AllergenStrictness.DECLARED_ONLY)
    offer = build([price(A, "2.48")], [stock(A, 5000)], request)

    line = best(offer).lines[0]
    assert line.allergen_check is not None
    assert line.allergen_check.strictness is AllergenStrictness.DECLARED_ONLY
    assert [finding.excluded_code for finding in line.allergen_check.findings] == ["AY"]
    soya = next(check for check in best(offer).constraint_checks if check.kind is ConstraintKind.ALLERGEN)
    # The milk makes no statement about soya: under DECLARED_ONLY it passes, shown as unverified.
    assert (soya.subject, soya.result) == ("AY", CheckResult.UNVERIFIED)


def test_an_excluded_allergen_the_product_states_free_from_is_met(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    request = make_request(100, exclude_allergens=("ML",), allergen_strictness=AllergenStrictness.STRICT)
    offer = build([price(A, "2.48")], [stock(A, 5000)], request)

    lactose = next(check for check in best(offer).constraint_checks if check.kind is ConstraintKind.ALLERGEN)
    assert (lactose.subject, lactose.result) == ("ML", CheckResult.MET)


def test_a_request_excluding_milk_gets_no_lactose_free_milk(
    build: Build, price: Any, stock: Any, make_request: Any, reasons: Any
) -> None:
    # A nutritional claim is never an allergen statement: lactose-free milk still declares milk.
    request = make_request(100, exclude_allergens=("AM",), allergen_strictness=AllergenStrictness.STRICT)
    offer = build([price(A, "2.48")], [stock(A, 5000)], request)

    assert offer.options == ()
    assert reasons(offer)[A] is ExclusionReason.ALLERGEN_DECLARED


def test_a_request_in_sales_units_needs_no_pack_size(
    build: Build, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    offer = build([price(A, "2.48")], [stock(A, 50)], make_request(24, Unit.UNIT, product_ids=(A,), needed_by=None))

    option = best(offer)
    lines = [(line.product_id, line.quantity, line.covers, line.sales_unit) for line in option.lines]
    assert lines == [(A, 24, 24, "ST")]
    assert option.coverage[0].unit is Unit.UNIT
    kinds = {check.kind for check in option.constraint_checks}
    assert ConstraintKind.PRODUCT_ID in kinds
    assert ConstraintKind.NEEDED_BY not in kinds  # no date was asked for
    assert ConstraintKind.PACK not in kinds  # sales units: any pack
    assert option.decision is not None
    assert option.decision.verdict is Verdict.APPROVAL  # 59.52 EUR, every gating claim confirmed, no date asked


def test_two_request_lines_are_covered_in_one_option_with_the_lowest_fill_ratio(
    build: Build, price: Any, stock: Any, best: Any
) -> None:
    request = PurchaseRequest(
        needed_by=date(2026, 11, 16),
        lines=(
            RequestLine(text="milk", product_ids=(A,), quantity=Decimal(100), unit=Unit.L),
            RequestLine(text="more milk", product_ids=(B,), quantity=Decimal(100), unit=Unit.L),
        ),
    )
    offer = build([price(A, "2.48"), price(B, "2.57")], [stock(A, 500), stock(B, 25)], request)

    option = best(offer)
    assert [(line.request_line_index, line.product_id, line.quantity) for line in option.lines] == [
        (0, A, 100), (1, B, 25),
    ]
    assert [(c.request_line_index, c.covered, c.missing) for c in option.coverage] == [(0, 100, 0), (1, 25, 75)]
    assert option.fill_ratio == Decimal("0.25")
    assert option.totals.net == Decimal("248.00") + Decimal("64.25")
    assert {check.request_line_index for check in option.constraint_checks} == {0, 1, None}


def test_the_days_spend_reaches_the_policy(build: Build, price: Any, stock: Any, make_request: Any, best: Any) -> None:
    request = make_request(100)
    quiet = build([price(A, "2.48")], [stock(A, 5000)], request)
    busy = build([price(A, "2.48")], [stock(A, 5000)], request, day_spend=Decimal("2900"))

    assert best(quiet).decision.verdict is Verdict.APPROVAL
    assert "P-02" in best(busy).decision.rule_ids  # 2,900 + 248 is above the 3,000 EUR a day of hotel-kitchen
    assert best(busy).decision.verdict is Verdict.APPROVAL


def test_confirmed_only_leaves_the_unconfirmed_product_out_and_says_so(
    build: Build, price: Any, stock: Any, make_request: Any, reasons: Any
) -> None:
    offer = build(
        [price(UNCONFIRMED, "1.01"), price(A, "2.48")], [stock(UNCONFIRMED, PLACEHOLDER), stock(A, 5000)],
        make_request(100, require_confirmed=True),
    )

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED]
    type_note, left_out = offer.notes  # the note of product type milk comes first (coffee milk is another type)
    assert type_note.startswith("Request line 1: Coffee milk was left out:")
    assert UNCONFIRMED in left_out and "confirmed data only" in left_out.lower()
    assert reasons(offer)[UNCONFIRMED] is ExclusionReason.QUANTITY_NOT_CONFIRMED  # listed, not only in the note


def test_the_module_function_takes_the_profile_and_the_dependencies(
    fake_gateway: Any, deps_for: Any, policy: Any, price: Any, stock: Any, make_request: Any, best: Any
) -> None:
    deps = deps_for(fake_gateway([price(A, "2.48")], [stock(A, 5000)]))

    offer = build_offer(make_request(100), policy.get_profile("hotel-kitchen"), deps, agent_id="agent:test")

    assert offer.agent_id == "agent:test"
    assert offer.profile_id == "hotel-kitchen"
    assert offer.created_at == deps.clock.now()
    assert [line.product_id for line in best(offer).lines] == [A]
    assert best(offer).lines[0].availability.state is AvailabilityState.CONFIRMED


def test_a_deleted_product_named_by_id_is_treated_as_unknown(
    catalog: Any, fake_gateway: Any, policy: Any, price: Any, stock: Any, make_request: Any
) -> None:
    from tta.catalog import ProductCatalog, load_product_types

    deleted = catalog.get_product(A).model_copy(update={"deleted": True})
    small_catalog = ProductCatalog([deleted, catalog.get_product(B)], load_product_types())
    gateway = fake_gateway([price(A, "2.48")], [stock(A, 5000)])
    deps = OfferDeps(
        catalog=small_catalog, gateway=gateway, policy=policy, clock=gateway, day_spend=lambda _: Decimal(0)
    )

    with pytest.raises(UnknownProduct):
        build_offer(
            make_request(5, Unit.UNIT, product_ids=(A,)), policy.get_profile("hotel-kitchen"), deps, agent_id="agent:t"
        )


def test_an_unknown_product_type_is_an_invalid_request(build: Build, make_request: Any) -> None:
    with pytest.raises(InvalidRequest):
        build([], [], make_request(5, product_type="unobtainium"))
    with pytest.raises(InvalidRequest):
        build([], [], make_request(5, Unit.UNIT, product_type="unobtainium", product_ids=(A,)))


def test_a_product_the_answer_leaves_out_reads_as_not_deliverable(
    catalog: Any, policy: Any, price: Any, make_request: Any, now: datetime, reasons: Any
) -> None:
    from tta.contracts.availability import AvailabilityResponse, PriceResponse
    from tta.contracts.common import DataSource

    class SilentGateway:
        """Answers with no line at all, whatever is asked."""

        source = DataSource.REPLAY

        def now(self) -> datetime:
            return now

        def price(self, product_ids: Any, *, fresh: bool = False) -> PriceResponse:
            return PriceResponse(currency="EUR", lines=(price(A, "2.48"),), source=DataSource.REPLAY)

        def availability(self, product_ids: Any, *, fresh: bool = False) -> AvailabilityResponse:
            return AvailabilityResponse(time_now=now, lines=(), source=DataSource.REPLAY)

    gateway = SilentGateway()
    deps = OfferDeps(catalog=catalog, gateway=gateway, policy=policy, clock=gateway, day_spend=lambda _: Decimal(0))

    offer = build_offer(
        make_request(5, Unit.UNIT, product_ids=(A,)), policy.get_profile("allergy-ward"), deps, agent_id="agent:t"
    )

    assert reasons(offer)[A] is ExclusionReason.ALLERGEN_DECLARED  # the ward excludes milk: named before supply

    plain = build_offer(
        make_request(5, Unit.UNIT, product_ids=(A,)), policy.get_profile("hotel-kitchen"), deps, agent_id="agent:t"
    )
    assert reasons(plain)[A] is ExclusionReason.NOT_DELIVERABLE


def test_a_request_cannot_weaken_the_allergen_rule_of_the_profile(
    build: Build, price: Any, stock: Any, make_request: Any, agent_ward: Identity, best: Any, reasons: Any
) -> None:
    # 464013 is a soya drink that states milk and gluten cereals FREE_FROM. The ward's rule is STRICT.
    request = make_request(
        50, product_ids=("464013",), exclude_allergens=("AY",), allergen_strictness=AllergenStrictness.DECLARED_ONLY
    )
    offer = build([price("464013", "2.01")], [stock("464013", 500)], request, identity=agent_ward)

    assert reasons(offer)["464013"] is ExclusionReason.ALLERGEN_DECLARED  # the request added soya

    plain = build([price("464013", "2.01")], [stock("464013", 500)],
                  make_request(50, product_ids=("464013",), allergen_strictness=AllergenStrictness.DECLARED_ONLY),
                  identity=agent_ward)
    check = best(plain).lines[0].allergen_check
    assert check.strictness is AllergenStrictness.STRICT
    assert [finding.excluded_code for finding in check.findings] == ["AM", "AW"]


def test_two_request_lines_do_not_spend_the_same_stock_twice(
    build: Build, price: Any, stock: Any, best: Any
) -> None:
    request = PurchaseRequest(
        lines=(
            RequestLine(text="first", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                        quantity=Decimal(100), unit=Unit.L),
            RequestLine(text="second", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                        quantity=Decimal(100), unit=Unit.L),
        )
    )
    offer = build([price(A, "2.48")], [stock(A, 150)], request)

    option = best(offer)
    assert [(line.request_line_index, line.quantity) for line in option.lines] == [(0, 100), (1, 50)]
    assert [(entry.covered, entry.missing) for entry in option.coverage] == [(100, 0), (50, 50)]
    assert sum(line.quantity for line in option.lines) <= 150


def test_the_service_satisfies_the_two_ports(replay_deps: OfferDeps) -> None:
    service = OfferService(replay_deps)

    assert isinstance(service, OfferBuilder)
    assert isinstance(service, OfferRevalidator)
