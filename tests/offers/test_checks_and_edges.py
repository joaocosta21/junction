"""Constraint checks, sentences and the less travelled paths of the offer builder."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.common import (
    AllergenStrictness,
    CheckResult,
    ConstraintKind,
    Identity,
    OptionKind,
    PackPreference,
    Unit,
    Verdict,
)
from tta.contracts.offer import Offer, OfferOption, SubstituteQuery
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers.candidates import Need, evaluate
from tta.offers.checks import constraint_checks
from tta.offers.deps import look_up
from tta.offers.lines import coverage_of, line_for
from tta.offers.options import Draft
from tta.offers.planning import LineOutcome, _confirmed_only
from tta.offers.substitutes import MAX_POOL

A, B, C = "469363", "462775", "463380"  # lactose-free milks, 1-litre cartons; only B is also fat-free
REGULAR_MILK = "463149"  # Valio Plus skimmed milk 1 l: milk without the lactose-free claim
MONDAY = date(2026, 11, 16)


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption:
    return next(option for option in offer.options if option.kind is kind)


def results(option: OfferOption) -> dict[tuple[int | None, ConstraintKind, str], CheckResult]:
    return {(check.request_line_index, check.kind, check.subject): check.result for check in option.constraint_checks}


@pytest.fixture
def serve(fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps]) -> Callable[..., OfferService]:
    def build(prices: Any, lines: Any) -> OfferService:
        return OfferService(deps_for(fake_gateway(prices, lines)))

    return build


def need(**overrides: Any) -> Need:
    values: dict[str, Any] = dict(
        index=0, quantity=Decimal(10), unit=Unit.L, pack=PackPreference.BULK, excluded=(), strictness=None,
        needed_by=MONDAY, require_confirmed=False,
    )
    return Need(**{**values, **overrides})


# --- requests by words -------------------------------------------------------------------------------------

def test_tonight_a_request_by_name_terms_gets_a_name_term_check(
    service: OfferService, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        lines=(RequestLine(text="12 iKaffe", name_terms=("ikaffe",), quantity=Decimal(12), unit=Unit.UNIT),)
    )

    offer = service.build_offer(request, agent_hotel)

    option = of_kind(offer, OptionKind.BEST_CONFIRMED)
    assert results(option)[(0, ConstraintKind.NAME_TERM, "ikaffe")] is CheckResult.MET
    assert all("ikaffe" in line.name.lower() for line in option.lines)
    assert option.coverage[0].covered == 12


# --- a request line nothing is offered for -----------------------------------------------------------------

def test_a_request_line_with_no_product_is_reported_in_the_option_and_in_the_notes(
    serve: Any, price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        needed_by=MONDAY,
        lines=(
            RequestLine(text="milk", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                        quantity=Decimal(100), unit=Unit.L),
            RequestLine(text="beef", product_type="beef_chuck", quantity=Decimal(30), unit=Unit.KG),
        ),
    )
    offer = serve([price(A, "2.48")], [stock(A, 500)]).build_offer(request, agent_hotel)

    option = of_kind(offer, OptionKind.BEST_CONFIRMED)
    found = results(option)
    assert {line.request_line_index for line in option.lines} == {0}
    assert found[(1, ConstraintKind.PRODUCT_TYPE, "beef_chuck")] is CheckResult.NOT_MET
    assert found[(1, ConstraintKind.QUANTITY, "30 kg")] is CheckResult.NOT_MET
    assert found[(1, ConstraintKind.PACK, "BULK")] is CheckResult.NOT_MET
    assert found[(0, ConstraintKind.QUANTITY, "100 L")] is CheckResult.MET
    assert option.fill_ratio == 0
    assert "covers 1 of the 2 request lines in full" in option.summary
    assert option.summary.endswith(
        "Covered: 0 of 30 kg of beef chuck, request line 2; 100 of 100 L of milk, request line 1."
    )
    assert any(note.startswith("Request line 2: no product can be offered") for note in offer.notes)
    assert "P-03" in option.decision.rule_ids


def test_a_request_line_with_nothing_offered_leaves_the_date_and_confirmed_only_not_met(
    serve: Any, price: Any, stock: Any, agent_hotel: Identity
) -> None:
    # The milk line is confirmed and in time. Nothing is offered for the beef line: neither check is met.
    request = PurchaseRequest(
        needed_by=MONDAY,
        require_confirmed=True,
        lines=(
            RequestLine(text="milk", product_type="milk", required_claims=("FREE_FROM_LACTOSE",),
                        quantity=Decimal(100), unit=Unit.L),
            RequestLine(text="beef", product_type="beef_chuck", quantity=Decimal(30), unit=Unit.KG),
        ),
    )
    offer = serve([price(A, "2.48")], [stock(A, 500)]).build_offer(request, agent_hotel)

    option = of_kind(offer, OptionKind.BEST_CONFIRMED)
    whole = {check.kind: check for check in option.constraint_checks if check.request_line_index is None}
    assert {line.request_line_index for line in option.lines} == {0}
    for kind in (ConstraintKind.NEEDED_BY, ConstraintKind.CONFIRMED_ONLY):
        assert whole[kind].result is CheckResult.NOT_MET, kind
        assert "request line 2" in whole[kind].sentence, kind


def test_the_checks_name_every_request_line_that_has_nothing_offered(
    catalog: ProductCatalog, fake_gateway: Any, deps_for: Any, price: Any, stock: Any, now: datetime
) -> None:
    lookup = look_up(deps_for(fake_gateway([price(A, "2.48")], [stock(A, 500)])), [A])
    needs = [need(index=index, require_confirmed=True) for index in range(3)]
    candidate = evaluate(catalog.get_product(A), needs[0], lookup, catalog)
    line = line_for(candidate, needs[0], Decimal(10), Decimal(10), now)
    asked = RequestLine(text="x", product_ids=(A,), quantity=Decimal(10), unit=Unit.L)
    request = PurchaseRequest(needed_by=MONDAY, require_confirmed=True, lines=(asked, asked, asked))

    checks = constraint_checks(request, needs, [line], coverage_of(request.lines, [line]), catalog)

    whole = {check.kind: check for check in checks if check.request_line_index is None}
    for kind in (ConstraintKind.NEEDED_BY, ConstraintKind.CONFIRMED_ONLY):
        assert whole[kind].result is CheckResult.NOT_MET, kind
        assert "request lines 2 and 3" in whole[kind].sentence, kind


def test_two_lines_covered_in_full_say_so_in_the_summary(
    serve: Any, price: Any, stock: Any, agent_hotel: Identity
) -> None:
    request = PurchaseRequest(
        lines=(
            RequestLine(text="a", product_ids=(A,), quantity=Decimal(10), unit=Unit.UNIT),
            RequestLine(text="b", product_ids=(B,), quantity=Decimal(10), unit=Unit.UNIT),
        )
    )
    service = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 500), stock(B, 500)])

    offer = service.build_offer(request, agent_hotel)

    assert "all 2 request lines in full" in of_kind(offer, OptionKind.BEST_CONFIRMED).summary


# --- tax ---------------------------------------------------------------------------------------------------

def test_without_a_tax_rate_the_tax_is_the_difference_of_the_two_prices_valio_states(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    bare = price(A, "2.00", tax_rate=None)
    with_tax = bare.catalog_price.model_copy(update={"value_with_tax": Decimal("2.27")})
    service = serve([bare.model_copy(update={"catalog_price": with_tax})], [stock(A, 500)])

    offer = service.build_offer(make_request(10, Unit.UNIT, product_ids=(A,), needed_by=None), agent_hotel)

    line = of_kind(offer, OptionKind.BEST_CONFIRMED).lines[0]
    assert line.tax_rate is None
    assert (line.net, line.tax, line.gross) == (Decimal("20.00"), Decimal("2.70"), Decimal("22.70"))


# --- the delivery date -------------------------------------------------------------------------------------

def test_a_delivery_valio_gives_no_cut_off_for_is_unverified_for_a_dated_request(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(A, "2.48")], [stock(A, 500, closing_time=None)])

    offer = service.build_offer(make_request(100), agent_hotel)

    option = of_kind(offer, OptionKind.BEST_CONFIRMED)
    assert results(option)[(None, ConstraintKind.NEEDED_BY, "2026-11-16")] is CheckResult.UNVERIFIED
    assert option.valid_until is None  # no cut-off: the option cannot say until when it can be ordered


def test_under_confirmed_only_a_product_with_an_unconfirmed_delivery_date_is_left_out_with_a_note(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 500, closing_time=None), stock(B, 500)])

    offer = service.build_offer(make_request(100, require_confirmed=True), agent_hotel)

    assert [line.product_id for line in of_kind(offer, OptionKind.BEST_CONFIRMED).lines] == [B]
    assert any(A in note and "confirmed data only" in note for note in offer.notes)


# --- substitutes and nutritional claims --------------------------------------------------------------------

def test_what_the_buyer_gives_up_names_a_claim_the_substitute_does_not_carry(
    fake_gateway: Any, deps_for: Any, policy: Any, price: Any, stock: Any
) -> None:
    gateway = fake_gateway(
        [price(A, "2.48"), price(REGULAR_MILK, "1.10")], [stock(A, None), stock(REGULAR_MILK, 500)]
    )

    result = find_substitutes(A, policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery())

    regular = next(candidate for candidate in result.candidates if candidate.product_id == REGULAR_MILK)
    assert regular.passes is True  # it adds no allergen: both are milk
    assert regular.orderable is True
    assert regular.claims_lost == ("FREE_FROM_LACTOSE",)
    assert "FREE_FROM_LACTOSE" in regular.gives_up
    assert "FREE_FROM_LACTOSE" in regular.sentence


def test_a_substitute_that_keeps_every_claim_ranks_before_a_cheaper_one_that_loses_a_claim(
    fake_gateway: Any, deps_for: Any, policy: Any, price: Any, stock: Any
) -> None:
    gateway = fake_gateway(
        [price(A, "2.48"), price(REGULAR_MILK, "1.10"), price(B, "2.57")],
        [stock(A, None), stock(REGULAR_MILK, 500), stock(B, 500)],
    )

    result = find_substitutes(A, policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery())

    orderable = [candidate for candidate in result.candidates if candidate.orderable]
    assert [(candidate.product_id, candidate.claims_lost) for candidate in orderable] == [
        (B, ()), (REGULAR_MILK, ("FREE_FROM_LACTOSE",)),
    ]


def test_the_stand_in_of_an_offer_keeps_the_claims_of_the_original_when_one_can(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # The request names the lactose-free milk by id and lists no claim. The regular milk is cheaper.
    service = serve(
        [price(A, "2.48"), price(REGULAR_MILK, "1.10"), price(B, "2.57")],
        [stock(A, None), stock(REGULAR_MILK, 500), stock(B, 500)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    line = of_kind(offer, OptionKind.SUBSTITUTE).lines[0]
    assert line.product_id == B
    assert line.substitute.claims_lost == ()


def test_a_stand_in_that_drops_a_claim_of_the_original_goes_to_a_human(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # Question 1 of T07: regular milk in place of a lactose-free milk named by id. Both declare milk, so
    # the allergen rule passes; rule F-08 reads `claims_lost` and sends the order to a human.
    service = serve([price(A, "2.48"), price(REGULAR_MILK, "1.10")], [stock(A, None), stock(REGULAR_MILK, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(A,)), agent_hotel)

    option = of_kind(offer, OptionKind.SUBSTITUTE)
    line = option.lines[0]
    assert (line.product_id, line.quantity) == (REGULAR_MILK, 100)
    assert line.substitute.claims_lost == ("FREE_FROM_LACTOSE",)
    assert "FREE_FROM_LACTOSE" in line.substitute.gives_up
    assert option.decision.verdict is Verdict.APPROVAL
    assert "F-08" in option.decision.rule_ids


def test_a_substitute_in_an_offer_carries_every_claim_the_request_line_requires(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # The regular milk is cheaper and would rank first; the request asks for lactose-free.
    service = serve(
        [price(A, "2.48"), price(REGULAR_MILK, "1.10"), price(B, "2.57")],
        [stock(A, None), stock(REGULAR_MILK, 500), stock(B, 500)],
    )
    request = make_request(100, Unit.L, product_ids=(A,), required_claims=("FREE_FROM_LACTOSE",))

    offer = service.build_offer(request, agent_hotel)

    option = of_kind(offer, OptionKind.SUBSTITUTE)
    assert [line.product_id for line in option.lines] == [B]
    assert results(option)[(0, ConstraintKind.CLAIM, "FREE_FROM_LACTOSE")] is CheckResult.MET


def test_a_stand_in_carries_a_required_claim_even_when_the_original_does_not(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # The request asks for fat-free. C keeps every claim of the original and is cheaper, but only B is fat-free.
    service = serve(
        [price(A, "2.48"), price(C, "2.40"), price(B, "2.57")], [stock(A, None), stock(C, 500), stock(B, 500)]
    )
    request = make_request(100, Unit.L, product_ids=(A,), required_claims=("FREE_FROM_FAT",))

    offer = service.build_offer(request, agent_hotel)

    option = of_kind(offer, OptionKind.SUBSTITUTE)
    assert [line.product_id for line in option.lines] == [B]
    assert results(option)[(0, ConstraintKind.CLAIM, "FREE_FROM_FAT")] is CheckResult.MET


def test_the_candidates_of_a_large_category_group_stop_at_one_call(
    catalog: ProductCatalog, fake_gateway: Any, deps_for: Any, policy: Any
) -> None:
    original = next(product for product in catalog.products if product.category.startswith("417"))  # 2,851 products
    gateway = fake_gateway()

    result = find_substitutes(original.id, policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery())

    calls = [(endpoint, len(ids)) for endpoint, ids, _ in gateway.calls]
    assert calls == [("price", MAX_POOL + 1), ("availability", MAX_POOL + 1)]
    assert any(str(MAX_POOL) in note for note in result.notes)
    assert all(not candidate.orderable for candidate in result.candidates)


# --- the checks, on lines that do not fit what is asked ----------------------------------------------------

def test_the_checks_name_what_a_line_does_not_meet(
    catalog: ProductCatalog, fake_gateway: Any, deps_for: Any, price: Any, stock: Any, now: datetime
) -> None:
    late = stock(A, 500, available_date=date(2026, 11, 18))
    lookup = look_up(deps_for(fake_gateway([price(A, "2.48")], [late])), [A])
    asked = need(excluded=("AM",), strictness=AllergenStrictness.STRICT, pack=PackPreference.PORTION,
                 require_confirmed=True)
    line = line_for(evaluate(catalog.get_product(A), asked, lookup, catalog), asked, Decimal(10), Decimal(10), now)
    request = PurchaseRequest(
        needed_by=MONDAY,
        require_confirmed=True,
        lines=(
            RequestLine(text="x", product_type="plant_drink", name_terms=("oat",), required_claims=("VEGAN",),
                        quantity=Decimal(10), unit=Unit.L, pack=PackPreference.PORTION),
        ),
    )

    checks = constraint_checks(request, [asked], [line], coverage_of(request.lines, [line]), catalog)

    found = {(check.kind, check.subject): check for check in checks}
    for key in [
        (ConstraintKind.PRODUCT_TYPE, "plant_drink"), (ConstraintKind.NAME_TERM, "oat"),
        (ConstraintKind.CLAIM, "VEGAN"), (ConstraintKind.PACK, "PORTION"), (ConstraintKind.ALLERGEN, "AM"),
        (ConstraintKind.NEEDED_BY, "2026-11-16"), (ConstraintKind.CONFIRMED_ONLY, "require_confirmed"),
    ]:
        assert found[key].result is CheckResult.NOT_MET, key
        assert found[key].sentence.strip()
    assert A in found[(ConstraintKind.PRODUCT_TYPE, "plant_drink")].sentence
    assert found[(ConstraintKind.QUANTITY, "10 L")].result is CheckResult.MET


def test_confirmed_only_keeps_only_options_whose_every_line_is_confirmed_for_order(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(A, "2.48"), price(B, "2.57")], [stock(A, 500), stock(B, 999_999)])
    request = make_request(100)
    offer = service.build_offer(request, agent_hotel)
    drafts = [Draft(option.kind, option.lines) for option in offer.options]
    assert [draft.kind for draft in drafts] == [OptionKind.BEST_CONFIRMED, OptionKind.ALTERNATIVE_UNCONFIRMED]
    asked = request.lines[0]
    strict = LineOutcome(need=need(require_confirmed=True), asked=asked, considered=2, fitting=(), excluded=())
    relaxed = LineOutcome(need=need(), asked=asked, considered=2, fitting=(), excluded=())

    kept, notes = _confirmed_only([strict], drafts)
    untouched, no_notes = _confirmed_only([relaxed], drafts)

    assert [draft.kind for draft in kept] == [OptionKind.BEST_CONFIRMED]
    assert len(notes) == 1 and "1 option left out" in notes[0]
    assert (len(untouched), no_notes) == (2, ())
