"""A flour for a kitchen that excludes gluten (lane FP-M), in replay.

Scores on the 15% "robustness to exception situations" and the 20% "how precisely the agent matches what the buyer
asked for": at the allergy ward every wheat flour declares cereals containing gluten, and the oven pancake's flour
read "none of 21 products can be offered (21 declares an excluded allergen); the recipe lists no alternative". The
recipe now names an alternative that does the same job, the gluten-free all-purpose flour mixes, by product id.
Naming a product is not a statement about its allergens: each one passes or fails the buyer's allergen rule by
its own data, in the offer, like any product.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date, datetime
from pathlib import Path

import pytest

from tta.allergens.exclusion import check_exclusions
from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import AllergenOutcome, AllergenStrictness, ExclusionReason, Identity
from tta.contracts.menu import IngredientStatus, MenuRequest
from tta.menus import Recipe, plan_menu
from tta.menus.recipes import product_ids_of

MONDAY = date(2026, 11, 16)
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
MIXES = ("472562", "473319", "473484")


@pytest.fixture
def demo_parts(tmp_path: Path, catalog: ProductCatalog) -> Iterator[Parts]:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_demo_clock=DEMO_CLOCK)
    built = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=1000))
    yield built
    built.close()


def _pancake(servings: int) -> MenuRequest:
    return MenuRequest.model_validate(
        {"dishes": [{"dish_id": "oven_pancake", "servings": servings}], "needed_by": MONDAY.isoformat()}
    )


def test_the_pancakes_flour_has_an_alternative_named_by_the_ids_of_the_gluten_free_flour_mixes(
    recipes: Mapping[str, Recipe], catalog: ProductCatalog
) -> None:
    flour = next(each for each in recipes["oven_pancake"].ingredients if each.product_type == "flour")

    assert [(each.product_type, each.name_terms) for each in flour.alternatives] == [("gluten_free_flour_mix", ())]
    assert "gluten" in flour.alternatives[0].reason
    assert product_ids_of(recipes, "gluten_free_flour_mix") == MIXES
    for product_id in MIXES:
        product = catalog.get_product(product_id)
        assert product.category == "21310" and "Gluten-free All-purpose flour mix" in product.name_en


def test_at_the_ward_a_gluten_free_flour_mix_stands_in_and_each_mix_passes_the_allergen_rule_by_its_own_data(
    demo_parts: Parts, agent_ward: Identity, recipes: Mapping[str, Recipe]
) -> None:
    """Measured on 15 Nov 2026 at the demo clock, "oven pancake for 30 by Monday" as the allergy ward (milk and
    cereals containing gluten excluded, the strict rule). The two Virtasalmen mixes state they are free from both
    and fit. The Fazer mix is not deliverable in the recording; by its own data it would not be suggested as safe
    either (the next test)."""
    plan = plan_menu(demo_parts.service, agent_ward, _pancake(30), recipes)
    offer = demo_parts.service.get_offer(agent_ward, plan.offer_id)

    flour = next(each for each in plan.dishes[0].ingredients if each.recipe_product_type == "flour")
    index = flour.request_line_index
    assert flour.status is IngredientStatus.STANDS_IN and flour.product_type == "gluten_free_flour_mix"
    assert flour.sentence.startswith(
        "Gluten free flour mix stands in for flour, gives the batter body. Flour: none of 21 products can be offered "
        "by Mon 16 Nov 2026 (21 declares an excluded allergen). A gluten-free all-purpose flour mix gives the batter "
        "the same body; the pancake is a little more crumbly. Allergens: Virtasalmen Viljatuote Gluten-free "
        "All-purpose flour mix 3kg (473319) declares no allergen."
    )
    assert offer.request.lines[index].product_ids == MIXES and offer.request.lines[index].stands_in_for == "flour"
    offered = [line for line in offer.options[0].lines if line.request_line_index == index]
    assert [line.product_id for line in offered] == ["473319"]
    assert offered[0].allergen_check.outcome is AllergenOutcome.PASS and offered[0].allergen_check.all_explicit
    left_out = {item.product_id: item.reason for item in offer.excluded if item.request_line_index == index}
    assert left_out == {"472562": ExclusionReason.NOT_DELIVERABLE}
    assert "F-09" in offer.options[0].decision.rule_ids  # a stand-in is a person's to confirm
    assert [item.product_type for item in plan.cannot_be_sourced] == ["eggs", "sugar"]


def test_the_wards_allergen_rule_reads_each_mix_by_its_own_data_and_the_one_with_oats_is_a_persons_question(
    demo_parts: Parts, agent_ward: Identity, catalog: ProductCatalog
) -> None:
    """A name that says "gluten-free" settles nothing. The Fazer mix states it is free from cereals containing
    gluten and declares oats: under the ward's rule that is a doubt for a person, never a product offered as safe."""
    profile = demo_parts.service.get_authority(agent_ward).profile
    checks = {}
    for product_id in MIXES:
        product = catalog.get_product(product_id)
        checks[product_id] = check_exclusions(
            product.allergen_statements, profile.excluded_allergens, profile.allergen_strictness,
            ingredients=product.key_ingredients,
        )

    assert tuple(profile.excluded_allergens) == ("AM", "AW")
    assert profile.allergen_strictness is AllergenStrictness.STRICT
    assert {key: (check.outcome, check.all_explicit) for key, check in checks.items()} == {
        "472562": (AllergenOutcome.TO_HUMAN, False),
        "473319": (AllergenOutcome.PASS, True),
        "473484": (AllergenOutcome.PASS, True),
    }
    assert checks["472562"].findings[1].sentence == (
        "The product declares that it contains oats (GO) and the buyer excludes cereals containing gluten (AW); "
        "oats can be gluten-free or not: a person must decide."
    )
