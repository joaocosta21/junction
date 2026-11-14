"""Which candidate stands in for a gap (lane L2a-2): confirmed like-for-like stock first, the request's word on
the formula (P10 item F5), and a request in pieces converted by content (P9b item Q14-1). Hand-built answers
over the real catalog; the figures of the recording are in `test_data_truth_cream.py`."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import AvailabilityState, Identity, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption, SubstituteQuery
from tta.offers import OfferDeps, OfferService, find_substitutes

# Lactose-free creams of one category. COOKING is a 10 % cooking cream: a different formula from every other.
# Lane FC2, since the contents decide the formula: CREAM (Arla Pro) lists a lactase enzyme that neither ARLA
# nor VALIO lists, so no cream keeps its formula, although the figures agree (fat 35 g and 38 g against 36 g).
# Where a test is about a stand-in that keeps the formula, the cream asked for is ARLA: VALIO keeps its formula
# (another brand, the same components, fat 38 g against 35 g) and so does VALIO_10_L (Valio's cream in a
# 10-litre box). The other way round VALIO loses nothing either, but ARLA does not carry VALIO's claim
# VEGETARIAN, so it is no like-for-like replacement for it.
CREAM, ARLA, VALIO, COOKING = "469346", "464727", "464194", "463797"
VALIO_10_L = "463366"
PLACEHOLDER = 999_999  # the amount Valio reports when it does not know the stock
OAT, OAT_CASE = "473609", "471690"  # a 1-litre carton, and the case of 10 litres Valio lists as its substitute


@pytest.fixture
def serve(fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps]) -> Callable[..., OfferService]:
    def build(prices: Any, lines: Any) -> OfferService:
        return OfferService(deps_for(fake_gateway(prices, lines)))

    return build


def of_kind(offer: Offer, kind: OptionKind) -> OfferOption | None:
    return next((option for option in offer.options if option.kind is kind), None)


def with_stand_in(offer: Offer) -> OfferOption | None:
    """The first option that holds a substitute. Since the Python review's item P2 its kind is
    ALTERNATIVE_UNCONFIRMED when the stand-in's quantity is not confirmed, and SUBSTITUTE when it is."""
    return next((option for option in offer.options if any(line.substitute for line in option.lines)), None)


def picked(option: OfferOption) -> list[tuple[str, Decimal]]:
    return [(line.product_id, line.quantity) for line in option.lines]


# --- confirmed like-for-like stock before a quantity that is not confirmed ----------------------------------

def test_confirmed_stock_of_the_same_formula_stands_in_before_an_unconfirmed_product(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve(
        [price(ARLA, "7.37"), price(VALIO, "3.91"), price(VALIO_10_L, "36.00")],
        [stock(ARLA, 48), stock(VALIO, 37), stock(VALIO_10_L, PLACEHOLDER)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(ARLA,)), agent_hotel)

    assert [option.kind for option in offer.options] == [
        OptionKind.BEST_CONFIRMED, OptionKind.SUBSTITUTE, OptionKind.ALTERNATIVE_UNCONFIRMED,
    ]
    _, with_substitute, alternative = offer.options
    # The 37 confirmed litres fill the gap as far as they go, and the option says what is still missing.
    assert picked(with_substitute) == [(ARLA, 48), (VALIO, 37)]
    assert with_substitute.coverage[0].missing == 15
    assert "85 L of the 100 L asked for (15 L missing)" in with_substitute.summary
    assert all(line.availability.state is AvailabilityState.CONFIRMED for line in with_substitute.lines)
    # Only then the product whose quantity Valio does not confirm, for the whole gap, labelled.
    assert picked(alternative) == [(ARLA, 48), (VALIO_10_L, 52)]
    assert alternative.title == "Alternative: quantity not confirmed"
    assert f"({VALIO_10_L}), a substitute for" in alternative.summary
    assert "Valio does not confirm the quantity in stock" in alternative.summary
    assert alternative.lines[1].substitute.original_id == ARLA


def test_with_no_confirmed_like_for_like_stock_the_unconfirmed_product_stands_in_as_before(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(CREAM, "5.77"), price(VALIO, "3.91")], [stock(CREAM, 48), stock(VALIO, PLACEHOLDER)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,)), agent_hotel)

    # The stand-in's quantity is not confirmed, so the option is an alternative and says so (review item P2).
    assert [option.kind for option in offer.options] == [
        OptionKind.BEST_CONFIRMED, OptionKind.ALTERNATIVE_UNCONFIRMED,
    ]
    assert picked(offer.options[1]) == [(CREAM, 48), (VALIO, 52)]
    assert offer.options[1].title == "Alternative: quantity not confirmed"
    assert "Valio does not confirm the quantity in stock for 52 L of it" in offer.options[1].summary


def test_confirmed_stock_that_fills_the_whole_gap_needs_no_unconfirmed_alternative(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve(
        [price(CREAM, "5.77"), price(ARLA, "7.37"), price(VALIO, "3.91")],
        [stock(CREAM, 48), stock(ARLA, 500), stock(VALIO, PLACEHOLDER)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,)), agent_hotel)

    assert [option.kind for option in offer.options] == [OptionKind.BEST_CONFIRMED, OptionKind.SUBSTITUTE]
    assert picked(offer.options[1]) == [(CREAM, 48), (ARLA, 52)]


def test_a_confirmed_product_of_another_formula_does_not_jump_ahead(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # The cooking cream is confirmed, but it is no like-for-like replacement: the ranking's own order holds.
    service = serve(
        [price(CREAM, "5.77"), price(COOKING, "3.31"), price(VALIO, "3.91")],
        [stock(CREAM, 48), stock(COOKING, 500), stock(VALIO, PLACEHOLDER)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,)), agent_hotel)

    assert picked(with_stand_in(offer)) == [(CREAM, 48), (VALIO, 52)]


# --- the request's word on the formula ----------------------------------------------------------------------

@pytest.mark.parametrize("said", [True, False, None])
def test_the_request_lines_word_on_the_formula_is_copied_to_every_offer_line(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity, said: bool | None
) -> None:
    service = serve([price(CREAM, "5.77"), price(ARLA, "7.37")], [stock(CREAM, 48), stock(ARLA, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,), keep_formula=said), agent_hotel)

    lines = [line for option in offer.options for line in option.lines]
    assert lines and all(line.keep_formula is said for line in lines)


def test_where_the_formula_matters_a_formula_changing_substitute_is_only_a_labelled_alternative(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(CREAM, "5.77"), price(COOKING, "3.31")], [stock(CREAM, 48), stock(COOKING, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,), keep_formula=True), agent_hotel)

    first, second = offer.options
    assert (first.kind, picked(first)) == (OptionKind.BEST_CONFIRMED, [(CREAM, 48)])
    assert (
        "No substitute that keeps the formula can be ordered: 48 L are offered and the rest is left for a person."
    ) in first.summary
    assert second.kind is OptionKind.SUBSTITUTE
    assert second.title == "Alternative: a substitute that does not keep the formula"
    assert picked(second) == [(CREAM, 48), (COOKING, 52)]
    assert "this one does not keep it, so a person decides" in second.summary
    assert second.lines[1].substitute.formula.keeps_formula is False
    assert "F-11" in second.decision.rule_ids  # the rule reads `keep_formula` and the line's formula
    assert any("no substitute that keeps the formula can be ordered" in note for note in offer.notes)


def test_without_the_requests_word_the_same_substitute_is_the_usual_option(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(CREAM, "5.77"), price(COOKING, "3.31")], [stock(CREAM, 48), stock(COOKING, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,)), agent_hotel)

    second = offer.options[1]
    assert second.title == "With a substitute for a product that cannot be supplied in full"
    assert "No substitute that keeps the formula" not in offer.options[0].summary
    assert "F-11" not in second.decision.rule_ids


def test_where_the_formula_matters_a_substitute_that_keeps_it_stands_in_as_usual(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve(
        [price(ARLA, "7.37"), price(COOKING, "3.31"), price(VALIO, "3.91")],
        [stock(ARLA, 48), stock(COOKING, 500), stock(VALIO, PLACEHOLDER)],
    )

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(ARLA,), keep_formula=True), agent_hotel)

    with_substitute = with_stand_in(offer)
    assert picked(with_substitute) == [(ARLA, 48), (VALIO, 52)]
    assert with_substitute.title == "Alternative: quantity not confirmed"  # 52 L of it are not confirmed
    assert COOKING not in {line.product_id for option in offer.options for line in option.lines}
    assert "F-11" not in with_substitute.decision.rule_ids


def test_a_named_product_with_no_stock_and_no_formula_keeper_leaves_the_line_to_a_person(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(CREAM, "5.77"), price(COOKING, "3.31")], [stock(CREAM, None), stock(COOKING, 500)])

    offer = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,), keep_formula=True), agent_hotel)

    assert [option.title for option in offer.options] == ["Alternative: a substitute that does not keep the formula"]
    assert "F-11" in offer.options[0].decision.rule_ids
    assert any("the request says the formula matters" in note for note in offer.notes)


# --- a request in pieces is converted by content ------------------------------------------------------------

@pytest.mark.parametrize(("pieces", "cases"), [(100, 10), (95, 10), (101, 11)])
def test_a_request_in_pieces_gets_a_substitute_counted_by_its_content(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity, pieces: int, cases: int
) -> None:
    # 473609 is a 1-litre carton; 471690 is a case of 10 litres. Before, 100 pieces became 100 cases.
    service = serve(
        [price(OAT, "1.37"), price(OAT_CASE, "15.55", per_measure="1.555")],
        [stock(OAT, None), stock(OAT_CASE, PLACEHOLDER, sales_unit="KI", logistic_model="Terminal")],
    )

    offer = service.build_offer(make_request(pieces, Unit.UNIT, product_ids=(OAT,), needed_by=None), agent_hotel)

    line = offer.options[0].lines[0]
    assert (line.product_id, line.quantity, line.sales_unit) == (OAT_CASE, cases, "KI")
    assert line.covers == pieces  # in the request's unit: the pieces asked for
    assert offer.options[0].coverage[0].missing == 0
    assert offer.options[0].totals.net == Decimal("15.55") * cases


def test_a_substitute_query_in_pieces_counts_by_content_and_says_so(
    fake_gateway: Any, deps_for: Any, policy: Any, price: Any, stock: Any
) -> None:
    gateway = fake_gateway(
        [price(OAT, "1.37"), price(OAT_CASE, "15.55", per_measure="1.555")],
        [stock(OAT, None), stock(OAT_CASE, PLACEHOLDER, sales_unit="KI", logistic_model="Terminal")],
    )

    result = find_substitutes(
        OAT, policy.get_profile("hotel-kitchen"), deps_for(gateway), SubstituteQuery(quantity=Decimal(100))
    )

    assert "100 sales units of the product asked for hold 100 L" in result.notes[-1]


# --- one request line filled by several products (P10 item F11) ---------------------------------------------

def test_two_products_of_one_formula_that_fill_a_line_get_no_sentence(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(ARLA, "7.37"), price(VALIO, "3.91")], [stock(ARLA, 37), stock(VALIO, 40)])

    option = service.build_offer(make_request(70, Unit.L, product_ids=(ARLA, VALIO)), agent_hotel).options[0]

    assert {line.product_id for line in option.lines} == {ARLA, VALIO}
    assert "differs in formula" not in option.summary


def test_two_products_that_fill_a_line_and_differ_in_formula_are_said(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    service = serve([price(COOKING, "3.31"), price(VALIO, "3.91")], [stock(COOKING, 40), stock(VALIO, 40)])

    option = service.build_offer(make_request(70, Unit.L, product_ids=(COOKING, VALIO)), agent_hotel).options[0]

    assert picked(option) == [(COOKING, 40), (VALIO, 30)]
    assert (
        " Valio whipping cream 1 l UHT lactose free (464194) differs in formula from Arla Pro Cooking cream 10% 1 L "
        "UHT lactose free (463797), which fills the same request line: contains stabiliser (carrageenan) and lacks "
        "MILK PRODUCTS, modified maize starch, stabilizers (E471, E466); fat 38 g, not 10 g, saturated fat 22 g, "
        "not 6.5 g, carbohydrate 2.8 g, not 5.1 g, sugars 2.8 g, not 4.2 g."
    ) in option.summary


def test_where_the_formula_matters_the_unconfirmed_product_asked_for_comes_before_a_formula_changing_stand_in(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # The cream asked for has no confirmed quantity; the only stand-in is a confirmed cooking cream.
    service = serve([price(CREAM, "5.77"), price(COOKING, "3.31")], [stock(CREAM, PLACEHOLDER), stock(COOKING, 500)])

    with_word = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,), keep_formula=True), agent_hotel)
    without = service.build_offer(make_request(100, Unit.L, product_ids=(CREAM,)), agent_hotel)

    assert [(option.title, picked(option)) for option in with_word.options] == [
        ("Alternative: quantity not confirmed", [(CREAM, 100)]),
        ("Alternative: a substitute that does not keep the formula", [(COOKING, 100)]),
    ]
    # Without the request's word the confirmed stand-in is the suggestion, as before.
    assert [picked(option) for option in without.options] == [[(COOKING, 100)], [(CREAM, 100)]]


def test_two_products_that_differ_only_in_contents_name_the_components(
    serve: Any, price: Any, stock: Any, make_request: Any, agent_hotel: Identity
) -> None:
    # Lane FC2. 469346 lists a lactase enzyme and 464727 does not; their six figures are within tolerance, so
    # the sentence used to end "…the same request line: ." with nothing after the colon.
    cream, other = "469346", "464727"
    service = serve([price(cream, "5.32"), price(other, "5.40")], [stock(cream, 40), stock(other, 40)])

    option = service.build_offer(make_request(70, Unit.L, product_ids=(cream, other)), agent_hotel).options[0]

    assert "which fills the same request line: lacks lactase enzyme." in option.summary
    assert "request line: ." not in option.summary
