"""P10 F3: the formula outcome orders the substitutes after the dietary claims, and the sentence says what is
given up in numbers. Capture of 14 Nov, default clock (the recording's instant), read offline."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.common import AvailabilityState, Identity, OptionKind, PackPreference, Unit
from tta.contracts.offer import SubstituteCandidate, SubstituteQuery
from tta.contracts.product import FormulaCheck, FormulaOutcome, PackSize, Product
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers.candidates import Need
from tta.offers.formula import compare_formula
from tta.offers.substitute_wording import NOTHING_GIVEN_UP, gives_up
from tta.offers.substitutes import FORMULA_ORDER, rank_substitutes

VALIO_WHIPPING = "464194"  # Valio whipping cream 1 l, 38% fat
ARLA_PRO_WHIPPING = "469346"  # Arla Pro whipping cream 1 L, 36% fat: 48 L confirmed in the recording
VEGETABLE_MIX = "463975"  # Arla Pro Ruoka 15% "vegetable mix": before, it filled 52 of the 100 L, verdict AUTO
COOKING_CREAM = "464249"  # Valio cooking cream 15%
COOKING_ALTERNATIVE = "469162"  # Valio cooking cream alternative 15%: rapeseed oil. Before, rank 2 for 464194
LACTOSE_FREE_WHIPPING = "469126"  # Valio whipping cream 2 dl lactose free
SAME_FIGURES_NOT_LACTOSE_FREE = "469050"  # Valio Keittiön whipping cream 2 dl: the same six figures


def _passing(candidates: tuple[SubstituteCandidate, ...]) -> list[SubstituteCandidate]:
    return [candidate for candidate in candidates if candidate.passes and not candidate.claims_lost]


def test_candidates_that_keep_the_formula_come_before_those_that_do_not(
    service: OfferService, catalog: ProductCatalog, agent_hotel: Identity
) -> None:
    original = catalog.get_product(VALIO_WHIPPING)

    result = service.find_substitutes(VALIO_WHIPPING, agent_hotel, SubstituteQuery())

    order = [
        FORMULA_ORDER[compare_formula(original, catalog.get_product(candidate.product_id)).outcome]
        for candidate in _passing(result.candidates)
    ]
    ids = [candidate.product_id for candidate in result.candidates]
    assert order == sorted(order)
    assert {0, 1, 3} <= set(order)  # same product in another pack, same brand, different
    assert ids[0] == "463837"  # the same cream in 2 dl
    # Before: the 15% vegetable-oil alternative was rank 2 and the 15% cooking cream rank 3, ahead of every
    # other whipping cream. Now every whipping cream that keeps the formula comes first, and the alternative
    # is product type vegetable_cream, not cream: it is held back while a cream can be ordered.
    assert COOKING_ALTERNATIVE not in ids
    assert ids.index("465193") < ids.index(COOKING_CREAM)
    assert ids.index("464699") < ids.index(COOKING_CREAM)


def test_what_is_given_up_is_said_in_numbers(service: OfferService, agent_hotel: Identity) -> None:
    result = service.find_substitutes(VALIO_WHIPPING, agent_hotel, SubstituteQuery())
    by_id = {candidate.product_id: candidate for candidate in result.candidates}

    # Before, this sentence in full: "Compared with Valio whipping cream 1 l UHT lactose free: Valio does not list
    # it as a substitute; Valio does not confirm the quantity in stock."
    assert by_id[COOKING_CREAM].gives_up == (
        "Not a like-for-like replacement: made for cooking; the product asked for is made for whipping; a "
        "different formula (fat 15 g, not 38 g, saturated fat 8.8 g, not 22 g, carbohydrate 5.3 g, not 2.8 g). "
        "Compared with Valio whipping cream 1 l UHT lactose free: Valio does not list it as a substitute; Valio "
        "does not confirm the quantity in stock. Different formula: fat 15 g, not 38 g; saturated fat 8.8 g, not "
        "22 g; carbohydrate 5.3 g, not 2.8 g per 100 g. Only this product's ingredient list names a modified "
        "starch. Only the original's ingredient list names a stabiliser."
    )
    assert by_id["463837"].gives_up.endswith(
        "The data shows no difference in formula: same brand, and the six nutrition figures per 100 g are equal."
    )
    assert "Same formula within our tolerance of 15% or 1 g per nutrient (salt 0.25 g): fat 35 g against 38 g" in (
        by_id["465193"].gives_up
    )


def test_100_litres_of_whipping_cream_are_no_longer_topped_up_with_a_vegetable_fat_blend(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(100, Unit.L, product_ids=(ARLA_PRO_WHIPPING,)), agent_hotel)

    confirmed = next(option for option in offer.options if option.kind is OptionKind.BEST_CONFIRMED)
    substitute = next(option for option in offer.options if option.kind is OptionKind.SUBSTITUTE)
    alternative = next(option for option in offer.options if option.kind is OptionKind.ALTERNATIVE_UNCONFIRMED)
    assert [(line.product_id, line.quantity) for line in confirmed.lines] == [(ARLA_PRO_WHIPPING, 48)]
    assert VEGETABLE_MIX not in {line.product_id for option in offer.options for line in option.lines}
    # Lane L2a-2: confirmed stock of the same formula first. 464727 (Arla, 37 L confirmed) fills the gap as far
    # as it goes and 15 L stay missing; the cream whose quantity Valio does not confirm is the labelled
    # alternative for the whole 52 L. Before, that one was the stand-in.
    confirmed_stand_in = substitute.lines[1]
    assert (confirmed_stand_in.product_id, confirmed_stand_in.quantity) == ("464727", 37)
    assert substitute.coverage[0].missing == 15
    assert str(substitute.totals.net) == "549.65"
    stand_in = alternative.lines[1]
    assert (stand_in.product_id, stand_in.quantity) == (VALIO_WHIPPING, 52)
    assert stand_in.substitute.gives_up == (
        "Replaceable: same type, same use, not flavoured, same formula within tolerance. "
        "Compared with Arla Pro Whipping cream 1 L UHT lactose free: the brand is Valio, not Arla Pro; Valio does "
        "not list it as a substitute; Valio does not confirm the quantity in stock. Same formula within our "
        "tolerance of 15% or 1 g per nutrient (salt 0.25 g): fat 38 g against 36 g; saturated fat 22 g against "
        "23 g; protein 2 g against 2.2 g; carbohydrate 2.8 g against 2.9 g; sugars 2.8 g against 2.9 g; salt "
        "0.07 g against 0.06 g per 100 g."
    )
    assert str(alternative.totals.net) == "480.28"


def test_the_formula_never_lifts_a_candidate_over_a_lost_dietary_claim(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
    catalog: ProductCatalog,
) -> None:
    # 469050 has the six figures and the brand of 469126 and is not lactose-free. 464249 is a 15% cooking cream
    # that is lactose-free. Only those two can be had.
    original = catalog.get_product(LACTOSE_FREE_WHIPPING)
    assert compare_formula(original, catalog.get_product(SAME_FIGURES_NOT_LACTOSE_FREE)).outcome is (
        FormulaOutcome.SAME_PRODUCT_OTHER_PACK
    )
    prices = [price(LACTOSE_FREE_WHIPPING, "1.50"), price(SAME_FIGURES_NOT_LACTOSE_FREE, "1.00"),
              price(COOKING_CREAM, "2.63")]
    lines = [stock(LACTOSE_FREE_WHIPPING, None), stock(SAME_FIGURES_NOT_LACTOSE_FREE, 500),
             stock(COOKING_CREAM, 500)]

    result = find_substitutes(
        LACTOSE_FREE_WHIPPING, policy.get_profile("hotel-kitchen"), deps_for(fake_gateway(prices, lines)),
        SubstituteQuery(),
    )

    orderable = [candidate.product_id for candidate in result.candidates if candidate.orderable]
    assert orderable == [COOKING_CREAM]  # the safe product wins; the same formula without the claim is held back
    assert SAME_FIGURES_NOT_LACTOSE_FREE not in {candidate.product_id for candidate in result.candidates}


def test_every_judged_candidate_carries_its_formula_check(
    replay_deps: OfferDeps, catalog: ProductCatalog
) -> None:
    need = Need(
        index=0, quantity=None, unit=Unit.UNIT, pack=PackPreference.ANY, excluded=(), strictness=None,
        needed_by=None, require_confirmed=False,
    )

    ranking = rank_substitutes(catalog.get_product(ARLA_PRO_WHIPPING), need, replay_deps)

    by_id = {judged.candidate.product.id: judged for judged in ranking.ranked}
    assert VEGETABLE_MIX not in by_id  # product type vegetable_cream: held back while a cream can be ordered
    assert all(judged.replaceable.sentence for judged in ranking.ranked)
    assert by_id[VALIO_WHIPPING].formula.outcome is FormulaOutcome.OTHER_BRAND
    assert by_id["464727"].formula.keeps_formula


@pytest.mark.parametrize(
    ("original", "other", "words"),
    [
        # Scenario 3. The listed substitute's figures are per 100 g and the original's per 100 ml: two drinks.
        ("473609", "471690", "Different formula: fat 1.5 g, not 3 g, per 100 g against per 100 ml. Figures per "
                             "100 g compared with per 100 ml as they stand: for a drink the two are about 3% "
                             "apart (our rule)."),
        # Lane L2a-2 (P10 item F9): an additive only one ingredient list names is said after the figures.
        ("473609", "475224", "Different formula: carbohydrate 7.8 g, not 6.6 g; sugars 1.6 g, not 3.5 g per 100 ml. "
                             "Only this product's ingredient list names a stabiliser."),
        ("473609", "468465", "Different formula: fat 1 g, not 3 g per 100 ml. Only the original's ingredient list "
                             "names an acidity regulator."),
    ],
)
def test_scenario_3_says_the_formula_of_each_candidate(
    service: OfferService, agent_hotel: Identity, original: str, other: str, words: str
) -> None:
    result = service.find_substitutes(original, agent_hotel, SubstituteQuery())

    candidate = next(each for each in result.candidates if each.product_id == other)
    assert candidate.gives_up.endswith(words)


def _bare(formula: FormulaCheck) -> tuple[Any, Any]:
    """A listed candidate of the same brand, category and (unknown) pack size, with no price to compare."""
    product = Product(
        id="2", name_en="Cream B", brand="Valio", category="10401", sales_unit="ST", base_unit="ST",
        allowed_lot_size=Decimal(1),
    )
    original = product.model_copy(update={"id": "1", "name_en": "Cream A"})
    candidate = SimpleNamespace(product=product, pack=PackSize(), state=AvailabilityState.CONFIRMED, price=None)
    judged = SimpleNamespace(
        claims_not_carried=(), listed=True, distance=0, candidate=candidate, formula=formula,
        replaceable=SimpleNamespace(sentence="Verdict."),
    )
    return judged, SimpleNamespace(original=original, original_pack=PackSize(), original_price=None)


def test_nothing_given_up_is_only_said_when_the_formula_shows_no_difference_either() -> None:
    same = FormulaCheck(outcome=FormulaOutcome.SAME_PRODUCT_OTHER_PACK, sentence="The data shows no difference.")
    different = FormulaCheck(outcome=FormulaOutcome.DIFFERENT, sentence="Different formula: fat 15 g, not 36 g.")
    unknown = FormulaCheck(outcome=FormulaOutcome.NOT_KNOWN, sentence="The formula cannot be compared: no figures.")

    assert gives_up(*_bare(same)) == f"Verdict. {NOTHING_GIVEN_UP} The data shows no difference."
    assert gives_up(*_bare(different)) == "Verdict. Compared with Cream A: Different formula: fat 15 g, not 36 g."
    assert gives_up(*_bare(unknown)) == "Verdict. Compared with Cream A: The formula cannot be compared: no figures."
