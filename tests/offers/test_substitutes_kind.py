"""Review finding C3-F2, decision B65: a product that is another kind of product by its name is no substitute.

A check of 35 products found, in place of the product asked for: egg white for liquid egg yolk, flank for
brisket, a drinking chocolate for cocoa powder, baking powder and a bilberry filling for sodium bicarbonate,
chocolate sugar strands for a couverture, vanilla sugar for marzipan, almond paste and pralines, crème fraîche
for tzatziki, whipping cream for a vanilla sauce, crème brûlée for panna cotta. "No option beats a wrong
option": such a product now leaves the ranking, so neither the list nor an offer can hold it, and where nothing
is the same kind the answer says so.

Recordings of 14 Nov read offline at the demo clock (Thu 12 Nov 2026, 14:15 Helsinki).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest

from tta.config import Settings
from tta.contracts.common import Identity, IdentityKind, Unit
from tta.contracts.offer import Offer, SubstituteQuery, SubstituteResult
from tta.contracts.product import ReplaceVerdict
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
HOTEL, SCHOOL, BAKERY = "hotel-kitchen", "school-kitchen", "bakery-cafe"
YOLK, OTHER_YOLK, EGG_WHITE, WHOLE_EGG = "469500", "475366", "475374", "475201"
BRISKET, OTHER_BRISKET, FLANK = "469890", "474852", "466952"
COCOA_POWDER, VAN_HOUTEN, DRINKING_CHOCOLATE = "475703", "470594", "475204"
BICARBONATE, OTHER_BICARBONATE, BAKING_POWDER, BILBERRY_FILLING = "465668", "476713", "466228", "469116"
GUANAJA, MANJARI, DARK_BUTTONS, SUGAR_STRANDS = "462859", "462889", "466730", "476667"
VANILLA_SUGARS = ("465651", "476631")
PANNA_COTTA = "471006"
BARISTA, NUTTY_VANILLA = "473609", "474724"


@pytest.fixture(scope="module")
def demo_deps(deps_for: Callable[..., OfferDeps]) -> OfferDeps:
    return deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))


@pytest.fixture(scope="module")
def ranked(demo_deps: OfferDeps, policy: Any) -> Callable[..., SubstituteResult]:
    def run(profile_id: str, product_id: str, quantity: int) -> SubstituteResult:
        query = SubstituteQuery(quantity=Decimal(quantity))
        return find_substitutes(product_id, policy.get_profile(profile_id), demo_deps, query)

    return run


@pytest.fixture(scope="module")
def offered(demo_deps: OfferDeps, make_request: Callable[..., Any]) -> Callable[..., Offer]:
    def run(profile_id: str, product_id: str, quantity: int, unit: Unit = Unit.UNIT) -> Offer:
        identity = Identity(kind=IdentityKind.AGENT, id=f"agent:{profile_id}", display_name="A test agent",
                            profile_id=profile_id)
        return OfferService(demo_deps).build_offer(make_request(quantity, unit, product_ids=(product_id,)), identity)

    return run


def _first_orderable(result: SubstituteResult) -> str | None:
    return next((each.product_id for each in result.candidates if each.orderable), None)


@pytest.mark.parametrize(
    ("profile_id", "original", "quantity", "wrong", "first"),
    [
        # before: the only option was egg white 475374; the yolk 475366 was at rank 6
        (HOTEL, YOLK, 4, {EGG_WHITE, WHOLE_EGG}, OTHER_YOLK),
        (BAKERY, YOLK, 4, {EGG_WHITE, WHOLE_EGG}, OTHER_YOLK),
        # before: flank 466952 first; Cedar River Brisket (80 kg confirmed) not among the 10 shown
        (HOTEL, BRISKET, 20, {FLANK}, OTHER_BRISKET),
        # before: Clipper drinking chocolate first; Van Houten cocoa powder below it for lacking VEGAN
        (HOTEL, COCOA_POWDER, 500, {DRINKING_CHOCOLATE, "461042"}, VAN_HOUTEN),
        # before: baking powder, then a bilberry filling
        (HOTEL, BICARBONATE, 100, {BAKING_POWDER, BILBERRY_FILLING}, OTHER_BICARBONATE),
        # before, at the school: 75 x chocolate sugar strands as the allergen-safe choice
        (SCHOOL, GUANAJA, 10, {SUGAR_STRANDS}, DARK_BUTTONS),
        (SCHOOL, "465048", 10, {SUGAR_STRANDS}, None),  # milk chocolate crocant
        # before, at the school: vanilla sugar for marzipan, almond paste and pralines
        (SCHOOL, "464954", 10, set(VANILLA_SUGARS), None),
        (SCHOOL, "476558", 10, set(VANILLA_SUGARS), None),
        (SCHOOL, "462885", 10, set(VANILLA_SUGARS), None),
        (SCHOOL, "462908", 10, set(VANILLA_SUGARS), None),
        (HOTEL, "470260", 200, {"477055"}, None),  # tzatziki: before, crème fraîche; the tzatzikis are past cut-off
        (HOTEL, "470340", 600, {"470341", "469752"}, None),  # Oatly vanilla sauce: before, whipping cream
        (HOTEL, PANNA_COTTA, 20, {"471124"}, None),  # panna cotta: before, crème brûlée
        (HOTEL, "471105", 400, {"470832"}, None),  # tiramisu: before, a soft ice cream mix
    ],
)
def test_another_kind_of_product_is_not_ranked_and_the_same_kind_comes_first(
    ranked: Callable[..., SubstituteResult], profile_id: str, original: str, quantity: int, wrong: set[str],
    first: str | None,
) -> None:
    result = ranked(profile_id, original, quantity)

    assert not wrong & {each.product_id for each in result.candidates}
    assert _first_orderable(result) == first
    assert any("left out: by" in note and "another kind of product than" in note for note in result.notes)


@pytest.mark.parametrize(
    ("original", "quantity", "first"),
    [
        ("469363", 1000, "464399"),  # lactose-free milk: the same milk in another pack
        ("469556", 50, "464073"),  # whole milk
        ("463380", 1000, "464237"),  # milk for coffee: another milk for coffee
        ("469346", 100, "464194"),  # whipping cream
        ("463797", 300, "464249"),  # cooking cream
        ("464411", 40, "464205"),  # unsalted butter: the same butter in a 4 x 5 kg case
        ("465168", 5, "477044"),  # quark
        (MANJARI, 5, GUANAJA),  # a dark couverture of the same producer
        ("468445", 10, "467464"),  # shell eggs
        ("460791", 2500, "476417"),  # wheat flour
        ("461040", 60, "465687"),  # vanilla sugar
        (BARISTA, 100, "471690"),  # the drink Valio lists; the offer takes the confirmed 475224 before it
    ],
)
def test_the_substitutes_a_cook_accepts_stay_as_they_were(
    ranked: Callable[..., SubstituteResult], original: str, quantity: int, first: str
) -> None:
    assert _first_orderable(ranked(HOTEL, original, quantity)) == first


def test_a_tenderloin_is_replaced_by_a_tenderloin_before_another_cut_with_the_same_mark(
    ranked: Callable[..., SubstituteResult],
) -> None:
    result = ranked(HOTEL, "473463", 20)  # Atria Guaranteed Tender Beef Tenderloin

    ids = [each.product_id for each in result.candidates]
    assert ids[0] == "463059"  # Naturkött Beef Tenderloin, 129 kg confirmed; before: 463053, also a tenderloin
    names = [each.name.casefold() for each in result.candidates]
    last_tenderloin = max(index for index, name in enumerate(names) if "tenderloin" in name)
    first_other = min(index for index, name in enumerate(names) if "tenderloin" not in name)
    assert last_tenderloin < first_other  # "Guaranteed Tender" striploin and topside come after every tenderloin


def test_the_offer_for_egg_yolk_holds_egg_yolk(offered: Callable[..., Offer]) -> None:
    for profile_id in (HOTEL, BAKERY):
        offer = offered(profile_id, YOLK, 4)

        lines = [line for option in offer.options for line in option.lines]
        assert {line.product_id for line in lines} == {OTHER_YOLK}  # before: 475374, egg white
        assert lines[0].substitute.original_id == YOLK
        assert str(offer.options[0].totals.net) == "194.28"  # 4 x 5 kg, quantity not confirmed: a person decides


def test_no_offer_puts_baking_powder_or_a_filling_in_place_of_sodium_bicarbonate(
    offered: Callable[..., Offer],
) -> None:
    offer = offered(HOTEL, BICARBONATE, 100)

    taken = {line.product_id for option in offer.options for line in option.lines}
    assert taken == {BICARBONATE, OTHER_BICARBONATE}  # before: 466228 baking powder and 469116 bilberry filling
    stand_in = next(line for option in offer.options for line in option.lines if line.substitute)
    assert stand_in.substitute.last_resort is True  # it lacks VEGAN and VEGETARIAN: a person decides


def test_the_school_is_offered_a_dark_couverture_for_a_dark_couverture(offered: Callable[..., Offer]) -> None:
    offer = offered(SCHOOL, GUANAJA, 10)

    stand_ins = [line for option in offer.options for line in option.lines if line.substitute]
    assert [line.product_id for line in stand_ins] == [DARK_BUTTONS]  # before: 75 x sugar strands, €655.50
    assert all(option.decision.verdict.value == "APPROVAL" for option in offer.options)


def test_a_product_nothing_can_stand_in_for_says_so(
    ranked: Callable[..., SubstituteResult], offered: Callable[..., Offer]
) -> None:
    result = ranked(HOTEL, PANNA_COTTA, 20)

    assert result.candidates == ()
    # The allergen rule decides first: of the 15 products of the category, 5 add an allergen and are counted
    # under that reason as before; the other 10 are left out for their kind.
    assert (
        "5 candidates of the same category that Valio does not list fail the allergen rule and are not shown: "
        "each adds an allergen or declares one this buyer excludes."
    ) in result.notes
    assert (
        "10 products of the same category are left out: by their names they are another kind of product than "
        "Elle&Vire Panna Cotta 1L, and are never offered in its place."
    ) in result.notes
    assert (
        "No product can stand in for Elle&Vire Panna Cotta 1L: none of its category is the same kind of product "
        "by its name."
    ) in result.notes
    offer = offered(HOTEL, PANNA_COTTA, 20)
    assert not [line for option in offer.options for line in option.lines if line.substitute]


def test_a_same_kind_product_that_lacks_a_claim_comes_before_another_kind_that_keeps_it(
    ranked: Callable[..., SubstituteResult],
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
) -> None:
    # The cocoa powder asked for is the only one labelled VEGAN: every other cocoa powder lacks the claim and
    # is still what the buyer is shown, as a last resort for a person.
    cocoa = ranked(HOTEL, COCOA_POWDER, 500)
    first = cocoa.candidates[0]
    assert (first.product_id, first.claims_lost, first.last_resort) == (VAN_HOUTEN, ("VEGAN",), True)

    # Hand-built stock for plain french fries labelled VEGAN (461660): plain fries with no such label, and
    # seasoned fries that keep it. Before, the seasoned ones came first for keeping the claim.
    fries, plain_no_label, seasoned = "461660", "470501", "470514"
    deps = deps_for(fake_gateway(
        [price(fries, "5.00"), price(plain_no_label, "6.00"), price(seasoned, "20.00")],
        [stock(fries, None), stock(plain_no_label, 500), stock(seasoned, 500)],
    ))

    result = find_substitutes(fries, policy.get_profile(HOTEL), deps, SubstituteQuery())

    orderable = [each for each in result.candidates if each.orderable]
    assert [each.product_id for each in orderable] == [plain_no_label, seasoned]
    assert orderable[0].claims_lost == ("VEGAN", "VEGETARIAN") and orderable[1].claims_lost == ()
    assert all(each.last_resort for each in orderable)  # both go to a person


def test_a_product_that_lacks_a_lactose_free_claim_still_comes_after_one_that_keeps_it(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
) -> None:
    # Valio, answer B7: when unsure, the safe product. A whipping cream with no lactose-free label (469050)
    # stays behind another kind of product that keeps the label (463825, a flavoured cooking cream): the kind
    # comes first only where the claim lost is VEGAN or VEGETARIAN.
    lactose_free_cream, no_label, flavoured_keeper = "469126", "469050", "463825"
    deps = deps_for(fake_gateway(
        [price(lactose_free_cream, "1.50"), price(no_label, "1.20"), price(flavoured_keeper, "2.00")],
        [stock(lactose_free_cream, None), stock(no_label, 500), stock(flavoured_keeper, 500)],
    ))

    result = find_substitutes(lactose_free_cream, policy.get_profile(HOTEL), deps, SubstituteQuery())

    orderable = [each for each in result.candidates if each.orderable]
    assert [each.product_id for each in orderable] == [flavoured_keeper, no_label]
    assert orderable[0].claims_lost == () and orderable[1].claims_lost == ("FREE_FROM_LACTOSE",)
    assert all(each.last_resort for each in orderable)  # both go to a person


def test_a_candidate_that_is_another_kind_by_its_name_says_which_word_is_missing(
    catalog: Any, demo_deps: OfferDeps
) -> None:
    from tta.offers.formula import compare_formula
    from tta.offers.substitutes import _kind_by_name, replace_check

    yolk, white = catalog.get_product(YOLK), catalog.get_product(EGG_WHITE)

    check = replace_check(yolk, white, compare_formula(yolk, white), kind=_kind_by_name(yolk, demo_deps.catalog))

    assert check.no_shared_word is True and check.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE
    assert check.reasons[-1] == (
        "it is not shown to be the same kind of product: its name does not say yolk, as the name of the product "
        "asked for does"
    )
    # A product of a type that says its kind is not read by its name: milk for milk shares no kind word check.
    milk = catalog.get_product("469363")
    assert _kind_by_name(milk, demo_deps.catalog) is None
