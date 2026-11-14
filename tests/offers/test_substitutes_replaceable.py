"""L2a-R: can one product really replace another in a kitchen?

Decided by the team on 14 Nov 2026 (the rules and the word lists are ours, `tta.catalog.kinds`):
a flavoured product does not replace a plain one, nor a plain one a flavoured one; a substitute is the same
product type unless Valio lists the pair; a product made for the same use comes first; and each candidate
says in one sentence whether it replaces the original like for like. The case that showed it: at the demo
clock the substitute offered for the barista oat drink 473609 was 17 cases of 474724, a nutty-vanilla one.

Capture of 14 Nov, read offline, at the default clock (the recording's instant) unless a test says "demo".
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity, OptionKind, Unit
from tta.contracts.offer import SubstituteQuery, SubstituteResult
from tta.contracts.product import ReplaceCheck, ReplaceVerdict
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers.formula import compare_formula
from tta.offers.substitute_wording import LAST_RESORT_OTHER_KIND
from tta.offers.substitutes import claims_lost, replace_check
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
BARISTA = "473609"  # Oddlygood Barista oat drink 1 l: plain, made for coffee
NUTTY_VANILLA = "474724"  # Oddlygood Barista oat drink nutty vanilla: the same six figures within tolerance
LISTED_DELIGHT = "471690"  # Oddlygood Barista "Delight": listed by Valio, fat 1.5 g against 3 g
FAZER_BARISTA = "475224"
PLAIN_OAT = "468465"  # Oddlygood oat drink, for drinking
LOW_LACTOSE_MILK = "463047"  # Arla whole milk, low lactose
CAFE_MILK = "463380"  # Arla Cafè milk: product type coffee_milk. Before, rank 1 for 463047
MILK_POWDER = "469148"  # no product type of ours
LEMON_JUICE = "469312"  # Kung Markatta Organic Lemon juice 1 L: product type juice
OTHER_LEMON_JUICE = "475731"  # Bonne Lemon juice 1L: product type juice
LISTED_CONCENTRATE = "467809"  # DeliMax Lemon juice concentrate 5L: listed by Valio for 469312, no type of ours


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


def _ids(result: SubstituteResult) -> list[str]:
    return [candidate.product_id for candidate in result.candidates]


# --- The one sentence -------------------------------------------------------------------------------------


def test_a_flavoured_drink_is_not_a_like_for_like_replacement_for_a_plain_one(judge: Callable[..., Any]) -> None:
    check = judge(BARISTA, NUTTY_VANILLA)

    assert check.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE
    assert check.plain_against_flavoured is True and check.leaves_the_list is True
    assert (check.original_flavours, check.flavours) == ((), ("nut", "vanilla"))
    # The name says it, and since the contents decide the formula (lane FC) so does the ingredient list: the
    # six figures are within tolerance, and the flavoured drink names flavourings the plain one does not.
    assert check.sentence == (
        "Not a like-for-like replacement: flavoured with nut and vanilla; the product asked for is not flavoured; "
        "a different formula (contains flavourings, which the product asked for does not)."
    )


def test_a_plain_product_does_not_replace_a_flavoured_one_either(judge: Callable[..., Any]) -> None:
    check = judge(NUTTY_VANILLA, BARISTA)

    assert check.plain_against_flavoured is True
    assert "not flavoured; the product asked for is flavoured with nut and vanilla" in check.sentence


def test_another_flavour_of_a_flavoured_product_is_said_and_does_not_leave_the_list(
    judge: Callable[..., Any],
) -> None:
    # Valio lists a mango yoghurt for a strawberry one (476665 and 464005), and 17 more such pairs.
    check = judge("476665", "464005", listed=True)

    assert check.other_flavour is True
    assert check.plain_against_flavoured is False and check.leaves_the_list is False
    assert check.reasons[0] == "another flavour (mango, not strawberry)"


def test_a_coffee_milk_is_not_a_like_for_like_replacement_for_a_milk(judge: Callable[..., Any]) -> None:
    check = judge(LOW_LACTOSE_MILK, CAFE_MILK)

    assert check.other_type is True and check.leaves_the_list is True
    assert (check.original_types, check.types) == (("milk",), ("coffee_milk",))
    assert check.sentence == (
        "Not a like-for-like replacement: another product type (coffee milk, not milk); made for coffee; the "
        "product asked for is not."
    )


def test_a_replaceable_candidate_says_so_in_the_owners_words(judge: Callable[..., Any]) -> None:
    assert judge("464727", "464194").sentence == (  # Arla whipping cream and Valio whipping cream, 1 litre each
        "Replaceable: same type, same use, no flavour named, same formula within tolerance."
    )
    assert judge("464727", "464194").verdict is ReplaceVerdict.REPLACEABLE
    # Lane FC2: until the contents decided the formula this example was Arla Pro's 469346, whose six figures
    # agree with Valio's; its ingredient list names a lactase enzyme that Valio's does not.
    assert judge("469346", "464194").sentence == (
        "Not a like-for-like replacement: a different formula (lacks lactase enzyme, which the product asked for "
        "contains)."
    )
    # Where no product type of ours covers the original, the type is not judged. Before review finding S11
    # this pair read "Replaceable: same category, same use, not flavoured, same formula within tolerance.";
    # "high heat" against "instant" is now said (tests/offers/test_substitutes_unknown.py).
    powder = judge(MILK_POWDER, "462224")
    assert powder.other_type is False and powder.original_types == () and powder.type_not_judged is True
    assert powder.verdict is ReplaceVerdict.NOT_LIKE_FOR_LIKE


def test_a_different_formula_another_use_and_a_lost_claim_are_each_a_reason_with_numbers(
    judge: Callable[..., Any],
) -> None:
    # Since review finding S11 the listed pair also says the variant word of its name.
    assert judge(BARISTA, LISTED_DELIGHT, listed=True).sentence == (
        "Not a like-for-like replacement: a different formula (fat 1.5 g, not 3 g); it cannot be shown to be like "
        "for like: its name adds Delight, which the data does not explain."
    )
    assert judge(BARISTA, PLAIN_OAT).sentence == (
        "Not a like-for-like replacement: not made for coffee, as the product asked for is; a different formula "
        "(contains gluten-free OAT (10 %), which the product asked for does not; lacks gluten-free OAT flour 10 %, "
        "acidity regulator (potassium phosphates), which the product asked for contains; fat 1 g, not 3 g)."
    )
    assert judge("464194", "464249").reasons[0] == "made for cooking; the product asked for is made for whipping"
    assert "it does not carry the claim FREE_FROM_LACTOSE" in judge("469363", "463149").reasons  # regular milk


def test_a_formula_that_cannot_be_compared_is_never_called_replaceable(judge: Callable[..., Any]) -> None:
    unknown = judge("460027", "460170", listed=True)  # two tomatoes: no nutrition figures

    assert unknown.reasons == ()
    assert unknown.verdict is ReplaceVerdict.NOT_SHOWN
    assert unknown.sentence == (
        "Replaceable as far as the data shows: same category, same use, no flavour named; the product asked for "
        "has no product type of ours, so only its category was compared; the formula cannot be compared."
    )


# --- The list ---------------------------------------------------------------------------------------------


def test_no_flavoured_drink_is_listed_for_the_plain_barista_drink_while_a_plain_one_can_be_ordered(
    service: OfferService, agent_hotel: Identity
) -> None:
    result = service.find_substitutes(BARISTA, agent_hotel, SubstituteQuery())

    # Before: ranks 1 to 3 were 472879 (pumpkin spice), 474957 (gingerbread) and 474724 (nutty vanilla).
    assert not {"472879", "474957", NUTTY_VANILLA, "471424", "472303", "472387"} & set(_ids(result))
    assert (
        "12 candidates that are not the same kind of product (11 flavoured where the original is not, or the "
        "reverse and 1 of another product type) are held back as a last resort: 4 of the same kind can be ordered."
    ) in result.notes
    assert all(candidate.gives_up.startswith(("Replaceable", "Not a like-for-like replacement: "))
               for candidate in result.candidates)


def test_a_drink_made_for_coffee_comes_before_a_drinking_oat_drink(
    service: OfferService, catalog: ProductCatalog, agent_hotel: Identity
) -> None:
    result = service.find_substitutes(BARISTA, agent_hotel, SubstituteQuery())

    passing = [candidate for candidate in result.candidates if candidate.passes]
    for_coffee = ["barista" in (catalog.get_product(candidate.product_id).name_en or "").lower()
                  for candidate in passing]
    assert for_coffee == sorted(for_coffee, reverse=True)  # every barista drink first
    assert True in for_coffee and False in for_coffee
    by_id = {candidate.product_id: candidate for candidate in passing}
    assert by_id[FAZER_BARISTA].rank < by_id[PLAIN_OAT].rank  # before: the same, by formula alone
    assert "not made for coffee, as the product asked for is" in by_id[PLAIN_OAT].gives_up


def test_at_the_demo_clock_the_suggestion_is_valios_listed_drink_and_not_the_nutty_vanilla_one(
    demo_deps: OfferDeps, make_request: Callable[..., Any], agent_hotel: Identity, policy: Any
) -> None:
    result = find_substitutes(BARISTA, policy.get_profile("hotel-kitchen"), demo_deps, SubstituteQuery())
    offer = OfferService(demo_deps).build_offer(make_request(100, Unit.L, product_ids=(BARISTA,)), agent_hotel)

    assert NUTTY_VANILLA not in _ids(result)
    first = result.candidates[0]
    # Before: 471690 was rank 11 of 13 ("the formula cannot be compared") and the offer took 17 cases of
    # 474724 for €235.45.
    assert (first.product_id, first.orderable, first.listed_by_supplier) == (LISTED_DELIGHT, True, True)
    assert first.formula is not None and first.formula.mixed_basis is True
    # Lane FC2: confirmed stock of the same kind that covers the line comes first: 100 of another barista oat
    # drink, 475224. Valio's listed drink is the labelled alternative, because its quantity is not confirmed at
    # the demo clock (Python review, P2). Before, it was the only stand-in and no confirmed option was offered.
    confirmed, option = (each for each in offer.options if any(line.substitute for line in each.lines))
    assert (confirmed.kind, confirmed.rank, str(confirmed.totals.net)) == (OptionKind.SUBSTITUTE, 1, "174.00")
    assert [(line.product_id, int(line.quantity)) for line in confirmed.lines] == [("475224", 100)]
    assert (option.kind, option.title) == (OptionKind.ALTERNATIVE_UNCONFIRMED, "Alternative: quantity not confirmed")
    assert [(line.product_id, int(line.quantity)) for line in option.lines] == [(LISTED_DELIGHT, 10)]
    assert str(option.totals.net) == "155.50"
    assert option.lines[0].substitute.gives_up.startswith(
        "Not a like-for-like replacement: a different formula (fat 1.5 g, not 3 g); it cannot be shown to be like "
        "for like: its name adds Delight, which the data does not explain. Compared with "
    )


def test_a_coffee_milk_no_longer_stands_first_for_a_milk(service: OfferService, agent_hotel: Identity) -> None:
    result = service.find_substitutes(LOW_LACTOSE_MILK, agent_hotel, SubstituteQuery())

    # Before: 463380 Arla Cafè milk was rank 1.
    assert CAFE_MILK not in _ids(result)
    assert result.candidates[0].product_id == "464073"  # Valio whole milk 1 l lactose free UHT
    assert result.candidates[0].gives_up.startswith(
        "Replaceable: same type, same use, no flavour named, same formula within tolerance."
    )
    assert any("10 of another product type" in note for note in result.notes)


def test_a_pair_valio_lists_from_another_type_stays_after_every_candidate_of_the_same_type(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
) -> None:
    # Valio lists a lemon juice concentrate (467809, category 21401, no product type of ours) for a lemon
    # juice (469312, product type juice). Both it and another lemon juice (475731) can be ordered here.
    deps = deps_for(fake_gateway(
        [price(LEMON_JUICE, "3.00"), price(OTHER_LEMON_JUICE, "3.50"), price(LISTED_CONCENTRATE, "2.00")],
        [stock(LEMON_JUICE, None), stock(OTHER_LEMON_JUICE, 100), stock(LISTED_CONCENTRATE, 100)],
    ))

    result = find_substitutes(LEMON_JUICE, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())

    by_id = {candidate.product_id: candidate for candidate in result.candidates}
    listed = by_id[LISTED_CONCENTRATE]  # it stays: Valio lists the pair
    assert listed.orderable is True and listed.last_resort is False
    assert "another product type (of no product type we know, not juice; Valio lists the pair)" in listed.gives_up
    same_type = [candidate for candidate in result.candidates if candidate.passes and candidate is not listed]
    assert same_type and all(candidate.rank < listed.rank for candidate in same_type)
    assert by_id[OTHER_LEMON_JUICE].rank == 1


def test_a_candidate_of_another_type_that_valio_does_not_list_is_a_last_resort(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
) -> None:
    # Only the milk for coffee can be had for the low-lactose milk.
    deps = deps_for(fake_gateway([price(LOW_LACTOSE_MILK, "2.01"), price(CAFE_MILK, "1.90")],
                                 [stock(LOW_LACTOSE_MILK, None), stock(CAFE_MILK, 500)]))

    result = find_substitutes(LOW_LACTOSE_MILK, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())

    orderable = [candidate for candidate in result.candidates if candidate.orderable]
    assert [(candidate.product_id, candidate.last_resort) for candidate in orderable] == [(CAFE_MILK, True)]
    assert orderable[0].sentence.endswith(LAST_RESORT_OTHER_KIND)


def test_when_only_a_flavoured_drink_can_be_ordered_it_is_a_last_resort_and_says_so(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], policy: Any, price: Any, stock: Any,
    make_request: Callable[..., Any], agent_hotel: Identity,
) -> None:
    deps = deps_for(fake_gateway([price(BARISTA, "1.37"), price(NUTTY_VANILLA, "13.85")],
                                 [stock(BARISTA, None), stock(NUTTY_VANILLA, 500, sales_unit="KI")]))

    result = find_substitutes(BARISTA, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())
    offer = OfferService(deps).build_offer(make_request(100, Unit.L, product_ids=(BARISTA,)), agent_hotel)

    orderable = [candidate for candidate in result.candidates if candidate.orderable]
    assert [candidate.product_id for candidate in orderable] == [NUTTY_VANILLA]
    assert orderable[0].last_resort is True
    assert orderable[0].sentence.endswith(LAST_RESORT_OTHER_KIND)
    assert orderable[0].gives_up.startswith(
        "Not a like-for-like replacement: flavoured with nut and vanilla; the product asked for is not flavoured; "
        "a different formula (contains flavourings, which the product asked for does not). "
    )
    assert not any("held back" in note for note in result.notes)
    option = next(each for each in offer.options if each.kind is OptionKind.SUBSTITUTE)
    assert option.lines[0].product_id == NUTTY_VANILLA
    assert option.lines[0].substitute.last_resort is True  # the fact a policy rule can read


def test_one_plain_candidate_that_can_be_ordered_keeps_the_flavoured_one_out_of_the_offer(
    fake_gateway: Callable[..., Any], deps_for: Callable[..., OfferDeps], price: Any, stock: Any,
    make_request: Callable[..., Any], agent_hotel: Identity,
) -> None:
    # The plain barista drink has 10 L confirmed of the 100 L asked for; the nutty-vanilla one has 500 cases.
    deps = deps_for(fake_gateway(
        [price(BARISTA, "1.37"), price(FAZER_BARISTA, "1.74"), price(NUTTY_VANILLA, "13.85")],
        [stock(BARISTA, None), stock(FAZER_BARISTA, 10), stock(NUTTY_VANILLA, 500, sales_unit="KI")],
    ))

    offer = OfferService(deps).build_offer(make_request(100, Unit.L, product_ids=(BARISTA,)), agent_hotel)

    taken = {line.product_id for option in offer.options for line in option.lines}
    assert NUTTY_VANILLA not in taken
    assert FAZER_BARISTA in taken


def test_a_price_difference_under_half_a_cent_is_not_said_as_dearer(demo_deps: OfferDeps, policy: Any) -> None:
    result = find_substitutes(MILK_POWDER, policy.get_profile("hotel-kitchen"), demo_deps, SubstituteQuery())

    same_powder = next(candidate for candidate in result.candidates if candidate.product_id == "462224")
    # Before: "it costs €0.00 more per kg" (€2.7120 against €2.7115 per kg).
    assert "more per kg" not in same_powder.gives_up
    assert same_powder.gives_up.startswith(
        "Not a like-for-like replacement: it cannot be shown to be like for like: the names differ in high heat "
        "against instant, which the data does not explain. Compared with "
    )


# --- Against Valio's own judgement ------------------------------------------------------------------------


def test_how_the_pairs_valio_lists_split_under_our_rules(catalog: ProductCatalog) -> None:
    checks = []
    for original in catalog.products:
        for other_id in catalog.listed_substitutes(original.id):
            other = catalog.get_product(other_id)
            checks.append(replace_check(original, other, compare_formula(original, other),
                                        claims_lost(original, other), listed=True))

    assert len(checks) == 249
    # Whole catalog. A first draft called any two different flavours "not replaceable" and removed 22 listed
    # pairs (Valio lists a mango yoghurt for a strawberry one); the rule was loosened to flavoured against plain.
    assert sum(check.plain_against_flavoured for check in checks) == 4
    assert sum(check.other_flavour for check in checks) == 18
    assert sum(check.other_type for check in checks) == 2  # both stay in the list: Valio lists them
    assert sum(check.other_use for check in checks) == 2
    assert {verdict: sum(check.verdict is verdict for check in checks) for verdict in ReplaceVerdict} == {
        ReplaceVerdict.REPLACEABLE: 17, ReplaceVerdict.NOT_SHOWN: 68, ReplaceVerdict.NOT_LIKE_FOR_LIKE: 164,
    }
    # Review finding S11. Before: 73 replaceable, 72 not shown, 104 not like for like. Then 32, 95 and 122
    # while the six figures alone decided the formula; since the two ingredient lists are compared first
    # (lanes FC and FC2: 145 of the 249 pairs differ in formula, 53 cannot be compared) 17, 68 and 164.
    assert sum(check.name_difference for check in checks) == 46  # each stays listed and says the words
    assert sum(check.type_not_judged for check in checks) == 164  # the original is of none of our product types
    assert sum(check.no_shared_word for check in checks) == 13  # and the two names share no product word
