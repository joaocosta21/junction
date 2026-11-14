"""The SUBSTITUTE option of an offer, the beef backup scenario, and the totals flags (SPEC sections 5 and 13)."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.common import (
    AvailabilityState,
    CheckResult,
    ConstraintKind,
    ExclusionReason,
    Identity,
    OptionKind,
    Unit,
    Verdict,
)
from tta.contracts.offer import Offer, OfferOption, SubstituteQuery
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService, find_substitutes

A, B, C = "469363", "462775", "463380"  # lactose-free milks of category 10400, 1-litre cartons
OAT_ORIGINAL, OAT_ADDS_GLUTEN, OAT_PASSES = "473609", "464320", "475224"


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption | None:
    return next((option for option in offer.options if option.kind is kind), None)


@pytest.fixture
def serve(fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps]) -> Callable[..., OfferService]:
    def build(prices: Any, lines: Any) -> OfferService:
        return OfferService(deps_for(fake_gateway(prices, lines)))

    return build


# --- a named product that cannot be supplied in full -------------------------------------------------------

def test_a_named_product_that_cannot_be_delivered_gets_a_substitute_option(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, None), stock(B, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    assert [option.kind for option in offer.options] == [OptionKind.SUBSTITUTE]
    option = offer.options[0]
    line = option.lines[0]
    assert (line.product_id, line.quantity, line.covers) == (B, 100, 100)
    assert line.substitute is not None
    assert line.substitute.original_id == A
    assert line.substitute.original_name
    assert line.substitute.category_distance == 0
    assert line.substitute.allergen_check.passes is True
    assert line.substitute.gives_up.strip()
    assert len(line.claims) == 5
    product_id = next(check for check in option.constraint_checks if check.kind is ConstraintKind.PRODUCT_ID)
    assert (product_id.subject, product_id.result) == (A, CheckResult.NOT_MET)
    assert {e.product_id: e.reason for e in offer.excluded}[A] is ExclusionReason.NOT_DELIVERABLE
    assert option.decision is not None
    assert option.totals.net == Decimal("257.00")


def test_a_named_product_in_full_supply_gets_no_substitute_option(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 500), stock(B, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED]
    product_id = next(check for check in offer.options[0].constraint_checks if check.kind is ConstraintKind.PRODUCT_ID)
    assert product_id.result is CheckResult.MET
    assert offer.notes == ()  # no substitute was looked for


def test_when_no_substitute_fills_the_gap_the_one_that_covers_most_is_taken(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # 60 litres are missing. B is cheaper but has 1 litre; C has 30.
    service = serve(
        [price(A, "2.48"), price(B, "2.40"), price(C, "2.65")], [stock(A, 40), stock(B, 1), stock(C, 30)]
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    with_substitute = of_kind(offer, OptionKind.SUBSTITUTE)
    assert [(line.product_id, line.quantity) for line in with_substitute.lines] == [(A, 40), (C, 30)]
    assert with_substitute.coverage[0].missing == 30


def test_a_short_named_product_is_offered_first_and_the_substitute_after_it(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 40), stock(B, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED, OptionKind.SUBSTITUTE]
    assert offer.options[0].coverage[0].missing == 60
    # The second option keeps the 40 confirmed litres of the product asked for and fills the other 60.
    with_substitute = offer.options[1]
    assert [(line.product_id, line.quantity, line.substitute is not None) for line in with_substitute.lines] == [
        (A, 40, False), (B, 60, True),
    ]
    assert with_substitute.fill_ratio == 1
    assert with_substitute.totals.net == Decimal("99.20") + Decimal("154.20")
    product_id = next(c for c in with_substitute.constraint_checks if c.kind is ConstraintKind.PRODUCT_ID)
    assert product_id.result is CheckResult.NOT_MET
    assert "part of" in product_id.sentence


def test_the_substitute_is_the_one_whose_stock_fills_the_gap(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # B is cheaper but has 1 litre; C can fill the 60 litres that are missing.
    service = serve(
        [price(A, "2.48"), price(B, "2.40"), price(C, "2.65")], [stock(A, 40), stock(B, 1), stock(C, 500)]
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    with_substitute = of_kind(offer, OptionKind.SUBSTITUTE)
    assert [(line.product_id, line.quantity) for line in with_substitute.lines] == [(A, 40), (C, 60)]


def test_a_substitute_that_adds_an_allergen_is_never_offered(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # 464320 is confirmed in stock but declares gluten cereals, which the oat drink asked for does not.
    service = serve(
        [price(OAT_ORIGINAL, "1.37"), price(OAT_ADDS_GLUTEN, "1.78")],
        [stock(OAT_ORIGINAL, None), stock(OAT_ADDS_GLUTEN, 5000)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(OAT_ORIGINAL,)), agent_hotel)

    assert offer.options == ()
    assert OAT_ADDS_GLUTEN not in {line.product_id for option in offer.options for line in option.lines}
    assert any("substitute" in note.lower() for note in offer.notes)


def test_tonight_an_unconfirmed_named_product_gets_a_confirmed_substitute_ranked_first(
    service: OfferService, make_request: Any, agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(100, Unit.L, product_ids=(OAT_ORIGINAL,)), agent_hotel)

    assert [option.kind for option in offer.options] == [OptionKind.SUBSTITUTE, OptionKind.ALTERNATIVE_UNCONFIRMED]
    substitute, alternative = offer.options
    assert [(line.product_id, line.quantity) for line in substitute.lines] == [(OAT_PASSES, 100)]
    assert substitute.lines[0].availability.state is AvailabilityState.CONFIRMED
    assert substitute.lines[0].substitute.listed_by_supplier is False
    assert [(line.product_id, line.quantity) for line in alternative.lines] == [(OAT_ORIGINAL, 100)]
    assert alternative.decision.verdict is Verdict.APPROVAL


def test_the_ward_may_not_take_a_substitute_without_a_human(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_ward: Identity
) -> None:
    # 464013 and 464056 are soya drinks that state milk and gluten cereals FREE_FROM.
    service = serve([price("464013", "2.01"), price("464056", "2.14")], [stock("464013", None), stock("464056", 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=("464013",)), agent_ward)

    option = of_kind(offer, OptionKind.SUBSTITUTE)
    assert option is not None
    assert option.lines[0].product_id == "464056"
    assert option.decision.verdict is Verdict.APPROVAL
    assert "P-05" in option.decision.rule_ids


# --- ranking of substitutes with hand-built availability ---------------------------------------------------

def test_substitutes_rank_by_pack_size_then_verification_then_price(
    fake_gateway: Any, deps_for: Any, policy: Any, price: Any, stock: Any
) -> None:
    gateway = fake_gateway(
        [price(A, "2.48"), price(B, "2.57"), price(C, "2.65"), price("464306", "1.01"),
         price("464179", "27.22", per_measure="2.722")],
        [stock(A, 500), stock(B, 500), stock(C, 500), stock("464306", 999_999), stock("464179", 500)],
    )

    result = find_substitutes(A, policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery())

    orderable = [candidate.product_id for candidate in result.candidates if candidate.orderable]
    # Same category and none listed: the 1-litre cartons first (confirmed and cheapest before dearer,
    # then the one whose quantity is not confirmed), the 10-litre box last.
    assert orderable == [B, C, "464306", "464179"]
    by_id = {candidate.product_id: candidate for candidate in result.candidates}
    assert by_id[B].price_difference == Decimal("0.09")
    assert by_id["464306"].price_difference == Decimal("-1.47")
    assert "10" in by_id["464179"].gives_up
    assert result.original_id == A


def test_a_quantity_in_the_query_is_checked_against_the_stock(
    fake_gateway: Any, deps_for: Any, policy: Any, price: Any, stock: Any
) -> None:
    gateway = fake_gateway([price(A, "2.48"), price(B, "2.57")], [stock(A, 500), stock(B, 30)])

    result = find_substitutes(
        A, policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery(quantity=Decimal(100), unit=Unit.L)
    )

    candidate = next(candidate for candidate in result.candidates if candidate.product_id == B)
    quantity = next(check for check in candidate.claims if check.claim.value == "quantity")
    assert quantity.status.value == "RULED_OUT"  # 30 in stock, 100 needed
    assert candidate.orderable is True  # it can still be ordered, as a partial fill


# --- the backup scenario and the totals flags --------------------------------------------------------------

def test_tonight_30_kg_of_beef_chuck_respects_the_lot_step_and_gives_a_ceiling(
    service: OfferService, make_request: Any, agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(30, Unit.KG, product_type="beef_chuck", needed_by=None), agent_hotel)

    option = of_kind(offer, OptionKind.BEST_CONFIRMED)
    assert option is not None
    # 466988 (109 kg confirmed, 16.88 a kg) is the one product that covers 30 kg alone; 464744 has 10 kg.
    assert [(line.product_id, line.quantity) for line in option.lines] == [("466988", Decimal(30))]
    assert all(line.quantity % 3 == 0 for line in option.lines)  # lot step 3 kg
    assert option.lines[0].variable_weight is True
    assert option.totals.is_ceiling is True
    assert option.totals.net == Decimal("506.40")
    assert "ceiling" in option.summary.lower()
    assert option.decision.verdict is Verdict.APPROVAL
    assert "P-06" in option.decision.rule_ids


def test_a_line_with_deposits_marks_the_total_as_excluding_them(
    catalog: ProductCatalog, serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    with_deposit = next(product for product in catalog.products if product.has_deposits and not product.deleted)
    service = serve([price(with_deposit.id, "1.20")], [stock(with_deposit.id, 500, sales_unit=with_deposit.sales_unit)])

    offer = service.build_offer(
        make_request(10, Unit.UNIT, product_ids=(with_deposit.id,), needed_by=None), agent_hotel
    )

    option = of_kind(offer, OptionKind.BEST_CONFIRMED)
    assert option is not None
    assert option.lines[0].has_deposits is True
    assert option.totals.excludes_deposits is True
    assert "deposit" in option.summary.lower()
    assert "P-07" in option.decision.rule_ids


def test_under_confirmed_only_a_substitute_whose_quantity_is_not_confirmed_is_not_offered(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_ward: Identity
) -> None:
    service = serve(
        [price("464013", "2.01"), price("464056", "2.14")], [stock("464013", None), stock("464056", 999_999)]
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=("464013",)), agent_ward)

    assert offer.options == ()
    assert any("no substitute" in note for note in offer.notes)


def test_a_substitute_does_not_take_stock_another_request_line_already_uses(
    serve: Any, price: Any, stock: Any, agent_hotel: Identity
) -> None:
    # Line 1 takes all 100 of B. Line 2 names A, which cannot be delivered: B has nothing left to stand in with.
    request = PurchaseRequest(
        lines=(
            RequestLine(text="first", product_ids=(B,), quantity=Decimal(100), unit=Unit.L),
            RequestLine(text="second", product_ids=(A,), quantity=Decimal(50), unit=Unit.L),
        )
    )
    service = serve(
        [price(A, "2.48"), price(B, "2.57"), price(C, "2.65")], [stock(A, None), stock(B, 100), stock(C, 30)]
    )

    offer = service.build_offer(request, agent_hotel)

    option = of_kind(offer, OptionKind.SUBSTITUTE)
    assert option is not None
    stand_in = next(line for line in option.lines if line.substitute is not None)
    assert (stand_in.product_id, stand_in.quantity, stand_in.covers) == (C, 30, 30)  # a partial stand-in
    used = sum(line.quantity for line in option.lines if line.product_id == B)
    assert used == 100
