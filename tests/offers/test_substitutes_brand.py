"""Where the formula matters, the same brand comes first (Valio Aimo's people, in person, 15 Nov 2026: "when
formula and chemistry are required, give priority to a product of the same brand that is known to have the same
formula").

Among candidates of the same use and flavour, the ranking already put one shown to keep the formula of the
same brand before one of another brand (`FORMULA_ORDER`). What is new, only where the formula matters for the
line: a candidate shown to keep the formula comes before the use and the flavour a name says; among the
candidates whose formula cannot be compared, the brand orders them; and the trade-off sentence says the brand
and the formula in plain words. Recording of 14 Nov, read offline; two candidates are edited in one test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import PackPreference, Unit
from tta.contracts.offer import SubstituteQuery
from tta.contracts.product import FormulaOutcome, Product
from tta.offers import OfferDeps, find_substitutes
from tta.offers.candidates import Need
from tta.offers.substitute_trade_off import SAME_BRAND_SAME_FORMULA
from tta.offers.substitutes import rank_substitutes
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
VALIO_WHIPPING = "464194"  # Valio whipping cream 1 l, brand Valio
SAME_CREAM_10_L = "463366"  # Valio whipping cream 38 % 10 l: same brand, the six figures equal
ORGANIC = "464699"  # Valio whipping cream 1 l organic: a formula shown to differ
SMALL, FOOD_SERVICE = "469126", "465193"  # two Valio whipping creams, 2 dl and 1,75 l food service; edited below
SAID = "the request says the formula matters"
NEED = Need(
    index=0, quantity=None, unit=Unit.UNIT, pack=PackPreference.ANY, excluded=(), strictness=None, needed_by=None,
    require_confirmed=False,
)


class _TwoWithoutFigures:
    """The real catalog, with the nutrition figures of two whipping creams taken away, so that their formula
    cannot be compared, and the smaller one given another brand; and the category cut to four products."""

    _EDITS: dict[str, dict[str, Any]] = {
        SMALL: {"nutrition": None, "brand": "Another Dairy"},
        FOOD_SERVICE: {"nutrition": None},
    }

    def __init__(self, inner: ProductCatalog) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def _edited(self, product: Product | None) -> Product | None:
        if product is None or product.id not in self._EDITS:
            return product
        return product.model_copy(update=self._EDITS[product.id])

    def get_product(self, product_id: str) -> Product | None:
        return self._edited(self._inner.get_product(product_id))

    def same_category(self, product_id: str, digits: int = 5) -> tuple[Product, ...]:
        """Four of the category, so that the list's limit of ten leaves none of them out."""
        kept = (SAME_CREAM_10_L, ORGANIC, SMALL, FOOD_SERVICE)
        found = self._inner.same_category(product_id, digits)
        return tuple(edited for each in found if each.id in kept and (edited := self._edited(each)) is not None)


def _ranked(deps: OfferDeps, catalog: ProductCatalog, formula_said: str) -> tuple[list[str], dict[str, Any]]:
    edited = replace(deps, catalog=_TwoWithoutFigures(catalog))
    ranking = rank_substitutes(edited.catalog.get_product(VALIO_WHIPPING), replace(NEED, formula_said=formula_said),
                               edited)
    ids = [judged.candidate.product.id for judged in ranking.ranked]
    return ids, {judged.candidate.product.id: judged for judged in ranking.ranked}


def test_where_the_formula_matters_the_same_brand_comes_first_among_formulas_that_cannot_be_compared(
    replay_deps: OfferDeps, catalog: ProductCatalog
) -> None:
    ids, by_id = _ranked(replay_deps, catalog, SAID)

    assert by_id[SMALL].formula.outcome is by_id[FOOD_SERVICE].formula.outcome is FormulaOutcome.NOT_KNOWN
    assert by_id[FOOD_SERVICE].candidate.product.brand == "Valio" != by_id[SMALL].candidate.product.brand
    assert ids.index(FOOD_SERVICE) < ids.index(SMALL)  # the same brand first
    # Never before a candidate that is shown to keep the formula; and a formula shown to differ stays where
    # it was, before both.
    assert ids[0] == "463837" and by_id[ids[0]].formula.outcome is FormulaOutcome.SAME_PRODUCT_OTHER_PACK
    assert ids.index(SAME_CREAM_10_L) < ids.index(ORGANIC) < ids.index(FOOD_SERVICE)
    assert by_id[ORGANIC].formula.outcome is FormulaOutcome.DIFFERENT


def test_where_the_formula_does_not_matter_the_order_is_as_before(
    replay_deps: OfferDeps, catalog: ProductCatalog
) -> None:
    matters, _ = _ranked(replay_deps, catalog, SAID)
    ids, _ = _ranked(replay_deps, catalog, "")

    # As before: the one whose name says no variant ("food service") comes first, whatever the brand.
    assert ids.index(SMALL) < ids.index(FOOD_SERVICE)
    assert [each for each in ids if each not in (SMALL, FOOD_SERVICE)] == [
        each for each in matters if each not in (SMALL, FOOD_SERVICE)
    ]  # nothing else moves


def test_the_trade_off_says_the_same_brand_and_the_same_formula_where_the_formula_matters(
    replay_deps: OfferDeps, policy: Any
) -> None:
    bakery = find_substitutes(VALIO_WHIPPING, policy.get_profile("bakery-cafe"), replay_deps, SubstituteQuery())
    hotel = find_substitutes(VALIO_WHIPPING, policy.get_profile("hotel-kitchen"), replay_deps, SubstituteQuery())

    said = {each.product_id: each.gives_up for each in bakery.candidates}
    # The bakery's profile says the formula matters on every line: the list is ranked with it and says so.
    assert said[SAME_CREAM_10_L].startswith(
        "Replaceable: same type, same use, no flavour named, same formula within tolerance. It is the same brand "
        "and the same formula as the product asked for, and the formula matters here. Compared with Valio "
        "whipping cream 1 l UHT lactose free:"
    )
    assert SAME_BRAND_SAME_FORMULA in said[SMALL]  # same brand, figures within tolerance
    assert SAME_BRAND_SAME_FORMULA not in said[ORGANIC]  # the same brand, a formula shown to differ: not said
    # The hotel's profile does not say so, and no request line is there to say it: nothing is added.
    assert not any(SAME_BRAND_SAME_FORMULA in each.gives_up for each in hotel.candidates)
    assert [each.product_id for each in hotel.candidates] == [each.product_id for each in bakery.candidates]


def test_a_stand_in_line_says_it_when_the_request_says_the_formula_matters(
    service: Any, make_request: Callable[..., Any], agent_hotel: Any
) -> None:
    asked = make_request(60, Unit.L, product_ids=(VALIO_WHIPPING,), keep_formula=True)
    plain = make_request(60, Unit.L, product_ids=(VALIO_WHIPPING,))

    def stand_ins(request: Any) -> list[Any]:
        offer = service.build_offer(request, agent_hotel)
        return [line for option in offer.options for line in option.lines if line.substitute is not None]

    with_formula, without = stand_ins(asked), stand_ins(plain)
    kept = [line for line in with_formula if line.substitute.formula.outcome in (
        FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND)]
    assert kept and all(SAME_BRAND_SAME_FORMULA in line.substitute.gives_up for line in kept)
    assert without and not any(SAME_BRAND_SAME_FORMULA in line.substitute.gives_up for line in without)


@pytest.fixture(scope="module")
def demo_deps(deps_for: Callable[..., OfferDeps]) -> OfferDeps:
    return deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))


@pytest.mark.parametrize(
    ("original", "same_brand_same_formula", "first_before"),
    [
        # Oatly Oat Drink Whole: Oatly iKaffe has its contents and figures; Oatly No Sugars 1,5% does not.
        ("470889", "464320", "472145"),
        # Valio coffee cream 10 % 3,3 dl: Valio low fat cream 1 l has its six figures and its components; the
        # litre named "coffee cream" has not.
        ("461548", "464221", "463442"),
    ],
)
def test_where_the_formula_matters_the_same_brand_and_formula_come_before_the_use_a_name_says(
    demo_deps: OfferDeps, policy: Any, original: str, same_brand_same_formula: str, first_before: str
) -> None:
    bakery = find_substitutes(original, policy.get_profile("bakery-cafe"), demo_deps, SubstituteQuery())
    hotel = find_substitutes(original, policy.get_profile("hotel-kitchen"), demo_deps, SubstituteQuery())

    first = bakery.candidates[0]
    assert first.product_id == same_brand_same_formula and first.passes and first.orderable
    assert first.formula.outcome in (FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND)
    assert first.replaceable.other_use  # its name says another use: that is still said, and a person still decides
    assert SAME_BRAND_SAME_FORMULA in first.gives_up
    assert first.gives_up.startswith("Not a like-for-like replacement: ")
    # The hotel's profile does not say the formula matters: its list is as it was.
    assert hotel.candidates[0].product_id == first_before
    assert hotel.candidates[0].formula.outcome is FormulaOutcome.DIFFERENT
    assert {each.product_id for each in hotel.candidates} == {each.product_id for each in bakery.candidates}
