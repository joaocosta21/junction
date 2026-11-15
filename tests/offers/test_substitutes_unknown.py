"""Review finding S11: what the reader does not know is never read as "the same".

Before, a flavour no word list knew read as "not flavoured" and a product of none of our product types was not
judged on type at all, so such a swap read "Replaceable" and no rule fired. Now a name that differs from the
original's in a word the data does not explain makes the candidate a last resort (rule F-12 sends it to a
person), a pair Valio lists stays and says the difference, and an original without a product type is never
called "Replaceable" without the qualification.

Capture of 14 Nov, read offline, at the default clock (the recording's instant) unless a test says "demo".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.offer import SubstituteQuery
from tta.contracts.product import FormulaCheck, FormulaOutcome, Product, ReplaceCheck, ReplaceVerdict
from tta.offers import OfferDeps, find_substitutes
from tta.offers.formula import compare_formula
from tta.offers.substitutes import claims_lost, replace_check
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
BARISTA, LISTED_DELIGHT = "473609", "471690"
MILK_POWDER, INSTANT_POWDER = "469148", "462224"  # Valio skimmed milk powder "high heat" and "instant"
MEDIUM_HEAT_POWDER = "473756"  # the same powder, "medium heat", 25 kg
CREME_FRAICHE, TZATZIKI = "477055", "470260"  # category 10419, no product type of ours for either
SAME = FormulaCheck(outcome=FormulaOutcome.OTHER_BRAND, sentence="The six figures are within tolerance.")
NO_TYPE = "the product asked for has no product type of ours, so only its category was compared"


def _named(english: str, brand: str, product_id: str = "1") -> Product:
    return Product(
        id=product_id, name_en=english, brand=brand, category="99999", sales_unit="ST", base_unit="ST",
        allowed_lot_size=Decimal(1),
    )


@pytest.fixture(scope="module")
def judge(catalog: ProductCatalog) -> Callable[..., ReplaceCheck]:
    def run(original_id: str, other_id: str, *, listed: bool = False) -> ReplaceCheck:
        original, other = catalog.get_product(original_id), catalog.get_product(other_id)
        return replace_check(original, other, compare_formula(original, other), claims_lost(original, other),
                             listed=listed)

    return run


@pytest.fixture(scope="module")
def demo_deps(deps_for: Callable[..., OfferDeps]) -> OfferDeps:
    return deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))


def test_a_variant_word_the_data_does_not_explain_is_never_replaceable() -> None:
    check = replace_check(_named("Kesä Xyzzy Ice Cream 5 L", "Kesä"), _named("Kesä Vanilla Ice Cream 5 L", "Kesä"),
                          SAME)

    assert check.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE
    assert check.name_difference is True
    assert (check.original_name_words, check.name_words) == (("Xyzzy",), ("Vanilla",))
    assert check.reasons[-1] == (
        "it cannot be shown to be like for like: the names differ in Xyzzy against Vanilla, which the data "
        "does not explain"
    )
    # The flavour reason no longer claims the original is plain: its name has a word nobody can read.
    assert check.reasons[0] == "flavoured with vanilla; the product asked for names no flavour our lists know"


def test_the_milk_powders_high_heat_and_instant_are_no_longer_called_replaceable(judge: Callable[..., Any]) -> None:
    check = judge(MILK_POWDER, INSTANT_POWDER)  # before: "Replaceable: same category, same use, not flavoured, ..."

    assert check.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE
    assert check.sentence == (
        "Not a like-for-like replacement: it cannot be shown to be like for like: the names differ in high heat "
        "against instant, which the data does not explain."
    )


def test_a_pair_valio_lists_says_the_difference_and_stays(judge: Callable[..., Any], demo_deps: OfferDeps,
                                                          policy: Any) -> None:
    check = judge(BARISTA, LISTED_DELIGHT, listed=True)

    assert check.sentence == (
        "Not a like-for-like replacement: a different formula (fat 1.5 g, not 3 g); it cannot be shown to be like "
        "for like: its name adds Delight, which the data does not explain."
    )
    profile = policy.get_profile("hotel-kitchen")
    result = find_substitutes(BARISTA, profile, demo_deps, SubstituteQuery(quantity=Decimal(100)))
    delight = next(each for each in result.candidates if each.product_id == LISTED_DELIGHT)
    assert delight.listed_by_supplier is True and delight.last_resort is False  # Valio's own judgement stays


def test_an_original_without_a_product_type_says_so_and_is_never_plainly_replaceable() -> None:
    original = _named("Kesä beetroot patty 2 kg", "Kesä")
    other = _named("Talvi beetroot patty 2 kg", "Talvi", "2")

    check = replace_check(original, other, SAME)

    assert check.type_not_judged is True and check.no_shared_word is False
    assert check.verdict is ReplaceVerdict.NOT_SHOWN
    assert check.sentence == (
        f"Replaceable as far as the data shows: same category, same use, no flavour named; {NO_TYPE}."
    )


def test_a_same_category_candidate_that_shares_no_product_word_is_not_like_for_like(
    judge: Callable[..., Any],
) -> None:
    check = judge(CREME_FRAICHE, TZATZIKI)

    assert check.type_not_judged is True and check.no_shared_word is True
    assert check.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE
    assert (
        "it cannot be shown to be the same kind of product: its name shares no product word with the name of the "
        f"product asked for, and {NO_TYPE}"
    ) in check.reasons


def test_no_candidate_for_a_product_without_a_type_reads_replaceable(catalog: ProductCatalog) -> None:
    original = catalog.get_product(MILK_POWDER)
    verdicts = {
        replace_check(original, other, compare_formula(original, other), claims_lost(original, other)).verdict
        for other in catalog.same_category(MILK_POWDER, 5)
    }

    assert ReplaceVerdict.REPLACEABLE not in verdicts


def test_an_unexplained_variant_stays_in_its_place_and_always_goes_to_a_person(
    demo_deps: OfferDeps, policy: Any
) -> None:
    # Demo clock: the "medium heat" powder is the stand-in offered for the "high heat" one. Before 15 Nov 2026
    # it was the "instant" one (10 kg for €27.12): its name does not say "heat", the word that says which milk
    # powder is asked for, so it is no candidate any more (decision B65), and a note counts it.
    profile = policy.get_profile("hotel-kitchen")
    result = find_substitutes(MILK_POWDER, profile, demo_deps, SubstituteQuery(quantity=Decimal(1)))

    medium = next(each for each in result.candidates if each.product_id == MEDIUM_HEAT_POWDER)
    assert medium.last_resort is True  # rule F-12 reads this mark
    assert "It cannot be shown to be like for like with the product asked for, so a person decides" in (
        medium.sentence
    )
    ids = [each.product_id for each in result.candidates]
    assert INSTANT_POWDER not in ids and "469195" not in ids  # the instant and the whole milk powder
    assert (
        "12 products of the same category are left out: by their names they are another kind of product than "
        "Valio skimmed milk powder high heat 20 kg, and are never offered in its place."
    ) in result.notes
    for each in result.candidates:
        unexplained = each.replaceable.name_difference and each.formula.outcome is not FormulaOutcome.DIFFERENT
        if unexplained and not each.listed_by_supplier and each.passes:
            assert each.last_resort is True


def test_the_offer_sends_the_unexplained_variant_to_a_person_with_rule_f_12(
    demo_deps: OfferDeps, make_request: Callable[..., Any], agent_hotel: Any
) -> None:
    from tta.contracts.common import Unit
    from tta.offers import OfferService

    offer = OfferService(demo_deps).build_offer(
        make_request(quantity=Decimal(10), unit=Unit.KG, product_ids=(MILK_POWDER,)), agent_hotel
    )

    option = next(each for each in offer.options if any(line.substitute for line in each.lines))
    assert [line.product_id for line in option.lines] == [MEDIUM_HEAT_POWDER]  # before 15 Nov: the instant one
    assert str(option.totals.net) == "67.79"  # one 25 kg sack; the instant one was 10 kg for €27.12
    assert "F-12" in option.decision.rule_ids  # before: ("F-01",)
    assert option.rank == 2  # after the product asked for
