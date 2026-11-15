"""The safe product wins (review P4, item M1; Valio Aimo, 14 Nov 2026: "it is better to not have gluten if you
are unsure").

With an allergen excluded, the first option holds only products whose data rules the allergen out. A product
whose data leaves a doubt is never the suggestion: it is offered as "Alternative: allergen not ruled out", and
a dietitian decides. Scores on the 20% "autonomy and controls" and the 20% "how precisely the agent matches".
Replay over tonight's capture at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest

from tta.contracts.common import AllergenStrictness, ClaimName, ClaimStatus, Identity, OptionKind, Unit
from tta.contracts.offer import Offer, OfferOption
from tta.offers import OfferService

SAFE_SOYA = "464013"  # Alpro No Sugars Soya drink 1L: states free from gluten cereals, €2.01, 478 confirmed
DOUBTFUL_OAT = "475224"  # Fazer Aito Barista oat drink: declares oats, says nothing final on gluten, €1.74
DOUBT_TITLE = "Alternative: allergen not ruled out"


def allergen_status(option: OfferOption) -> set[ClaimStatus]:
    return {check.status for line in option.lines for check in line.claims if check.claim is ClaimName.ALLERGENS}


def titled(offer: Offer, title: str) -> list[OfferOption]:
    return [option for option in offer.options if option.title.startswith(title)]


def plant_drink(make_request: Callable[..., Any], quantity: int, rule: AllergenStrictness, **line: Any) -> Any:
    return make_request(
        quantity, product_type="plant_drink", exclude_allergens=("AW",), allergen_strictness=rule, **line
    )


@pytest.fixture(scope="module")
def ten_litres(service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity) -> Offer:
    """The hotel kitchen: 10 litres of plant drink, no gluten, the strict rule."""
    return service.build_offer(plant_drink(make_request, 10, AllergenStrictness.STRICT), agent_hotel)


def test_the_first_option_is_the_product_whose_data_rules_the_allergen_out(ten_litres: Offer) -> None:
    first = ten_litres.options[0]

    assert first.kind is OptionKind.BEST_CONFIRMED
    assert first.product_ids == (SAFE_SOYA,)
    assert first.totals.net == Decimal("20.10")
    assert allergen_status(first) == {ClaimStatus.CONFIRMED}
    assert "P-04" not in first.decision.rule_ids  # nothing for a dietitian to decide


def test_the_cheaper_doubtful_product_is_a_labelled_alternative_for_the_dietitian(ten_litres: Offer) -> None:
    (alternative,) = titled(ten_litres, DOUBT_TITLE)

    assert alternative.title == DOUBT_TITLE
    assert alternative.rank > 1
    assert alternative.product_ids == (DOUBTFUL_OAT,)
    assert alternative.totals.net == Decimal("17.40")
    assert allergen_status(alternative) == {ClaimStatus.UNKNOWN}
    assert "P-04" in alternative.decision.rule_ids
    assert alternative.summary == (
        "Fazer Aito Professional Barista Oat drink, gluten-free 1L UHT (475224) for the 10 L asked for, €17.40 before "
        "tax. The product data does not rule out cereals containing gluten (AW), so a person must decide."
    )


def test_the_headline_says_what_the_safe_product_costs_over_the_doubtful_one(ten_litres: Offer) -> None:
    assert ten_litres.options[0].summary == (
        "1 confirmed product covers the 10 L asked for, for €20.10 before tax. Its data rules out every excluded "
        "allergen; the alternative whose data does not costs €2.70 less."
    )


def test_no_option_before_a_safe_one_holds_a_doubtful_product(ten_litres: Offer) -> None:
    statuses = [allergen_status(option) == {ClaimStatus.CONFIRMED} for option in ten_litres.options]

    assert statuses == sorted(statuses, reverse=True)  # every safe option before every doubtful one


def test_safe_first_holds_under_the_declared_only_rule_too(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(plant_drink(make_request, 10, AllergenStrictness.DECLARED_ONLY), agent_hotel)

    assert offer.options[0].product_ids == (SAFE_SOYA,)
    assert allergen_status(offer.options[0]) == {ClaimStatus.CONFIRMED}


def test_when_no_safe_product_exists_the_offer_says_so_and_only_labelled_alternatives_remain(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    request = plant_drink(make_request, 10, AllergenStrictness.STRICT, name_terms=("oat",))

    offer = service.build_offer(request, agent_hotel)

    assert offer.options
    assert all("allergen not ruled out" in option.title for option in offer.options)
    assert all("P-04" in option.decision.rule_ids for option in offer.options)
    assert (
        "Request line 1: no product whose data rules out cereals containing gluten (AW) can be offered, so no "
        "option is suggested as safe: a person must decide on each alternative."
    ) in offer.notes


def test_under_declared_only_a_product_with_no_statement_is_a_labelled_alternative_and_no_dietitian_is_named(
    build: Callable[..., Offer], price: Callable[..., Any], stock: Callable[..., Any], make_request: Callable[..., Any]
) -> None:
    """Lactose-free milk 469363 makes no statement about soya (AY): unverified, so it is not the safe option."""
    request = make_request(100, exclude_allergens=("AY",), allergen_strictness=AllergenStrictness.DECLARED_ONLY)

    offer = build([price("469363", "2.48")], [stock("469363", 5000)], request)

    (only,) = offer.options
    assert only.title == DOUBT_TITLE
    assert "P-04" not in only.decision.rule_ids
    assert only.summary.endswith(
        "The product data does not rule out soybeans (AY), so the person who confirms the order must decide."
        " Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk."
    )


def test_without_an_exclusion_nothing_changes(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    offer = service.build_offer(make_request(10, product_type="plant_drink"), agent_hotel)

    assert offer.options[0].kind is OptionKind.BEST_CONFIRMED
    assert offer.options[0].summary == "1 confirmed product covers the 10 L asked for, for €13.30 before tax."
    assert not any("allergen not ruled out" in option.title for option in offer.options)


def test_a_doubtful_product_named_by_id_comes_after_a_safe_substitute_for_it(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    """Review P4, rule R2: the buyer named Elovena oat drink 469512, which says nothing about milk. The first
    option is still a product whose data rules milk out, and the named one is the labelled alternative."""
    request = make_request(
        10, Unit.UNIT, product_ids=("469512",), exclude_allergens=("AM",), allergen_strictness=AllergenStrictness.STRICT
    )

    offer = service.build_offer(request, agent_hotel)

    first, second = offer.options[:2]
    assert first.kind is OptionKind.SUBSTITUTE
    assert allergen_status(first) == {ClaimStatus.CONFIRMED}
    assert (second.title, second.product_ids) == (DOUBT_TITLE, ("469512",))
    assert not any("no option is suggested as safe" in note for note in offer.notes)


# --- a safe substitute is titled by its real reason (lane FC2) ----------------------------------------------

SAFE_SWAP_TITLE = "With a substitute whose data rules out the allergen you exclude"


def test_a_substitute_chosen_for_an_allergen_is_not_titled_as_a_supply_problem(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    """The hotel, 100 L of Elovena barista oat drink 469512 without milk. 100 of it are confirmed in stock: it
    can be supplied. It was replaced because its data states nothing about milk. Before, the first option was
    titled "With a substitute for a product that cannot be supplied in full"."""
    request = make_request(
        100, Unit.L, product_ids=("469512",), exclude_allergens=("AM",), allergen_strictness=AllergenStrictness.STRICT
    )

    first, second = service.build_offer(request, agent_hotel).options[:2]

    assert (first.kind, first.title, first.product_ids) == (OptionKind.SUBSTITUTE, SAFE_SWAP_TITLE, ("473424",))
    assert first.summary == (
        "Alpro Rice drink 1L (473424) in place of Elovena 1l oat drink barista (469512): the 100 L asked for, for "
        "€236.00 before tax. Elovena 1l oat drink barista (469512) states nothing about milk (AM), which is "
        "excluded; Alpro Rice drink 1L (473424) is free from it. Its data rules out every excluded allergen; the "
        "alternative whose data does not costs €28.00 less."
    )
    assert (second.title, second.product_ids) == (DOUBT_TITLE, ("469512",))  # the product asked for can be supplied


def test_a_substitute_for_a_product_that_cannot_be_supplied_keeps_its_title(
    service: OfferService, make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    # Scenario 3 without an exclusion: 473609 has no confirmed stock, and that is why it is replaced.
    offer = service.build_offer(make_request(100, Unit.L, product_ids=("473609",)), agent_hotel)

    assert offer.options[0].title == "With a substitute for a product that cannot be supplied in full"
    assert "is free from it" not in offer.options[0].summary
