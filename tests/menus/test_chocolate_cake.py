"""A chocolate cake for 2, 20 and 200 as the bakery (task CK), in replay at both clocks.

Figures measured offline on the recording `2026-11-14-demo` joined with `2026-11-14-baking` (the baking products were
recorded the same Saturday at 21:12; Valio Aimo said on 14 Nov 2026 that its test data is static). Default clock:
the recording's instant, Sat 14 Nov 2026 02:52. Demo clock: Thu 12 Nov 2026 14:15 Helsinki. At both clocks flour,
cocoa powder, milk and baking powder have confirmed stock; no granulated sugar, whole egg or unsalted butter has:
their quantity is not confirmed, so the best confirmed option is partial and the full one waits for a person.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from tta.api.limits import RateLimit
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import AvailabilityState, Identity, IdentityKind, OrderStatus, Verdict
from tta.contracts.menu import IngredientStatus, MenuPlan, MenuRequest
from tta.contracts.offer import Offer
from tta.menus import Recipe, plan_menu
from tta.menus.needs import as_recipe, expand, group, purchase_request
from tta.menus.recipes import RecipeLoadError, RecipeTable, dish_names, load_recipes, product_ids_of

MONDAY = "2026-11-16"
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
CLOCKS = {"default": None, "demo": DEMO_CLOCK}
BAKERY = Identity(kind=IdentityKind.AGENT, id="agent:bakery-cafe", display_name="Kallio Bakery agent",
                  profile_id="bakery-cafe")
FLOUR, COCOA, MILK, BAKING_POWDER = "460856", "475703", "463047", "466228"
# The sugar and the whole egg of the alternative, by servings. Since lane FC2 the offer takes the lowest total for a
# small need: the 500 g sugar and the 1 kg egg for 2 and 20 servings (0.04 and 0.4 kg of each), and the 10 x 1 kg
# sugar and the 5 kg egg for 200 (4 kg of each). Before, it took the 25 kg sugar sack (460460) for 40 g.
SUGAR_AND_EGGS = {2: ("461329", "468269"), 20: ("461329", "468269"), 200: ("460334", "475201")}
# Net totals before tax: (the best confirmed option, the alternative whose quantity is not confirmed). Measured at
# both clocks on 15 Nov 2026; the alternative was 61.02 / 99.73 (default) and 104.65 / 129.12 (demo) before FC2.
TOTALS = {
    ("default", 2): ("15.19", "22.50"), ("default", 20): ("15.19", "22.50"), ("default", 200): ("39.66", "84.32"),
    ("demo", 2): ("15.19", "22.50"), ("demo", 20): ("15.19", "22.50"), ("demo", 200): ("39.66", "84.32"),
}
# The unsalted butter of the alternative: the 500 g block at both clocks. Before FC2 the demo clock took the 4x5 kg
# laminating butter (464761), whose cut-off has not passed on Thursday: the lowest total now wins there too.
BUTTER = {"default": "464411", "demo": "464411"}


@pytest.fixture(params=sorted(CLOCKS))
def clock(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def bakery_parts(tmp_path: Path, catalog: ProductCatalog, clock: str) -> Iterator[Parts]:
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_demo_clock=CLOCKS[clock])
    built = build_parts(settings, catalog=catalog, rate_limit=RateLimit(calls=1000))
    yield built
    built.close()


def _cake(servings: int) -> MenuRequest:
    return MenuRequest.model_validate(
        {"dishes": [{"dish_id": "chocolate_cake", "servings": servings}], "needed_by": MONDAY}
    )


def _planned(parts: Parts, recipes: Mapping[str, Recipe], servings: int) -> tuple[MenuPlan, Offer]:
    plan = plan_menu(parts.service, BAKERY, _cake(servings), recipes)
    return plan, parts.service.get_offer(BAKERY, plan.offer_id)


def _sentence(plan: MenuPlan, product_type: str) -> str:
    return next(each.sentence for each in plan.dishes[0].ingredients if each.recipe_product_type == product_type)


# --- the recipe table ------------------------------------------------------------------------------------------


def test_the_cake_is_in_the_table_with_a_role_for_every_ingredient(recipes: Mapping[str, Recipe]) -> None:
    cake = recipes["chocolate_cake"]

    assert cake.name == "Chocolate cake (suklaakakku)"
    assert [(each.product_type, each.name_terms, each.per_serving, each.unit.value) for each in cake.ingredients] == [
        ("flour", ("semi",), Decimal("0.02"), "KG"), ("sugar", ("granulated",), Decimal("0.02"), "KG"),
        ("eggs", ("whole",), Decimal("0.02"), "KG"), ("butter", ("unsalted",), Decimal("0.015"), "KG"),
        ("cocoa_powder", (), Decimal("0.005"), "KG"), ("milk", (), Decimal("0.015"), "L"),
        ("baking_powder", (), Decimal("0.001"), "KG"),
    ]
    assert all(each.role for each in cake.ingredients)
    assert [alt.product_type for each in cake.ingredients for alt in each.alternatives] == ["plant_drink"]


def test_cocoa_and_baking_powder_are_named_by_product_ids_that_are_them(
    recipes: Mapping[str, Recipe], catalog: ProductCatalog, raw_products: list[dict]
) -> None:
    """The product-type table has no cocoa powder and no baking powder yet: the recipe table names the products.
    Read by the Finnish name over the whole catalog: "kaakaojauhe" in category 22540, "leivinjauhe" in 22601."""
    if {"cocoa_powder", "baking_powder"} & set(catalog.product_type_keys()):
        pytest.skip("the product-type table holds the type now: the recipe table's list is ignored")
    cocoa, baking = product_ids_of(recipes, "cocoa_powder"), product_ids_of(recipes, "baking_powder")

    assert len(cocoa) == 5 and len(baking) == 6
    for ids, category, word in ((cocoa, "22540", "kaakaojauhe"), (baking, "22601", "leivinjauhe")):
        whole = [
            str(product["id"]) for product in raw_products if product.get("category") == category and any(
                name.get("language") == "fi" and word in name.get("value", "").casefold()
                for name in product.get("synkkaData", {}).get("names", [])
            )
        ]
        assert sorted(ids) == sorted(whole)
    assert product_ids_of(recipes, "flour") == ()


def test_a_named_ingredient_becomes_a_request_line_of_product_ids_and_small_amounts_keep_their_grams(
    recipes: Mapping[str, Recipe]
) -> None:
    request = _cake(20)

    lines = purchase_request(request, group(expand(request, recipes), as_recipe), recipes).lines

    assert [(line.product_type, line.name_terms, line.quantity) for line in lines] == [
        ("flour", ("semi",), Decimal("0.4")), ("sugar", ("granulated",), Decimal("0.4")),
        ("eggs", ("whole",), Decimal("0.4")), ("butter", ("unsalted",), Decimal("0.3")),
        (None, (), Decimal("0.1")), ("milk", (), Decimal("0.3")), (None, (), Decimal("0.02")),
    ]
    assert lines[4].product_ids == product_ids_of(recipes, "cocoa_powder")
    assert lines[6].product_ids == product_ids_of(recipes, "baking_powder")
    assert lines[4].text == "0.1 kg cocoa powder for Chocolate cake (suklaakakku) (20 servings)"


@pytest.mark.parametrize(("servings", "flour"), [(2, "0.04"), (49, "0.98"), (50, "1"), (60, "2"), (200, "4")])
def test_below_one_kilogram_the_line_asks_to_the_gram_and_from_one_up_in_whole_kilograms(
    recipes: Mapping[str, Recipe], servings: int, flour: str
) -> None:
    request = _cake(servings)

    assert group(expand(request, recipes), as_recipe)[0].quantity == Decimal(flour)


def test_the_product_type_table_wins_over_a_named_ingredient_of_the_same_key(tmp_path: Path) -> None:
    table = tmp_path / "recipes.yaml"
    table.write_text(
        "named_products:\n  cocoa_powder: {product_ids: ['475703']}\n  flour: {product_ids: ['460856']}\n"
        "dishes:\n  cake:\n    name: Cake\n    ingredients:\n"
        "      - {product_type: flour, per_serving: 0.02, unit: KG, role: structure}\n"
        "      - {product_type: cocoa_powder, per_serving: 0.005, unit: KG, role: flavour}\n",
        encoding="utf-8",
    )

    loaded = load_recipes(("flour",), table)

    assert isinstance(loaded, RecipeTable) and loaded.named_products == {"cocoa_powder": ("475703",)}


@pytest.mark.parametrize(
    "section",
    [
        "named_products:\n  cocoa_powder: {product_ids: 475703}\n",
        "named_products:\n  cocoa_powder: {product_ids: ['../x']}\n",
        "named_products: [cocoa_powder]\n",
        "also_called:\n  tiramisu: [tiramisù]\n",
        "also_called:\n  cake: [7]\n",
        "also_called:\n  cake: [pie]\n  pie: [tart]\n",
        "also_called: cake\n",
    ],
)
def test_a_named_products_or_also_called_section_that_cannot_be_trusted_does_not_load(
    tmp_path: Path, section: str
) -> None:
    table = tmp_path / "recipes.yaml"
    dish = "    name: {name}\n    ingredients:\n      - {{product_type: flour, per_serving: 0.02, unit: KG, role: r}}\n"
    table.write_text(
        section + "dishes:\n  cake:\n" + dish.format(name="Cake") + "  pie:\n" + dish.format(name="Pie"), "utf-8"
    )

    with pytest.raises(RecipeLoadError):
        load_recipes(("flour",), table)


def test_the_dishes_go_by_their_id_words_their_name_and_the_tables_other_names(recipes: Mapping[str, Recipe]) -> None:
    names = dish_names(recipes)

    assert names["chocolate_cake"] == ("chocolate cake", "suklaakakku")
    assert names["oven_pancake"] == ("oven pancake", "pannukakku", "pancake")
    assert names["salmon_with_rice"][:2] == ("salmon with rice", "salmon with rice and cream sauce")
    every = [name for own in names.values() for name in own]
    assert len(every) == len(set(every))  # a name is one dish's


# --- the plan --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("servings", [2, 20, 200])
def test_the_cake_is_one_offer_of_seven_lines_with_two_options_and_a_person_confirms_either(
    bakery_parts: Parts, recipes: Mapping[str, Recipe], clock: str, servings: int
) -> None:
    plan, offer = _planned(bakery_parts, recipes, servings)

    assert len(plan.offers_asked) == 1 and plan.cannot_be_sourced == ()
    assert {each.status for each in plan.dishes[0].ingredients} == {IngredientStatus.ORDERED_AS_IN_RECIPE}
    assert [line.request_line_index for line in plan.lines] == list(range(7))
    best, alternative = offer.options
    confirmed_net, alternative_net = TOTALS[clock, servings]
    assert (best.totals.net, alternative.totals.net) == (Decimal(confirmed_net), Decimal(alternative_net))
    # The best confirmed option: flour, cocoa powder, milk and baking powder. Sugar, eggs and butter have no
    # confirmed stock, so it is partial: below the bakery's 100% minimum (P-03) and the date is not met (F-07).
    assert [line.product_id for line in best.lines] == [FLOUR, COCOA, MILK, BAKING_POWDER]
    assert {line.availability.state for line in best.lines} == {AvailabilityState.CONFIRMED}
    assert best.fill_ratio == 0 and best.decision.rule_ids == ("F-07", "P-03")
    # The alternative covers every line; what Valio Aimo does not confirm goes to a person (F-01), per product.
    assert alternative.fill_ratio == 1 and set(alternative.decision.rule_ids) == {"F-01"}
    sugar, eggs = SUGAR_AND_EGGS[servings]
    assert [line.product_id for line in alternative.lines][:5] == [FLOUR, sugar, eggs, BUTTER[clock], COCOA]
    unconfirmed = [line.product_id for line in alternative.lines
                   if line.availability.state is AvailabilityState.QUANTITY_NOT_CONFIRMED]
    assert unconfirmed[:3] == [sugar, eggs, BUTTER[clock]]
    assert {best.decision.verdict, alternative.decision.verdict} == {Verdict.APPROVAL}
    assert Decimal(alternative_net) < 300  # the bakery's limit per order (P-01) is not reached, at 200 servings too


def test_for_two_servings_each_sentence_says_the_pack_and_what_is_left_over(
    bakery_parts: Parts, recipes: Mapping[str, Recipe], clock: str
) -> None:
    plan, _ = _planned(bakery_parts, recipes, 2)

    assert _sentence(plan, "flour") == (
        "0.04 kg to order as flour (semi), on line 1 of the offer. Offered: 1 × Myllyn Paras Emännän Semi Coarse "
        "Wheat Flour 2kg (460856) for €2.57 before tax, 976 sales units confirmed in stock. 0.04 kg is needed and "
        "the pack holds 2 kg, so 1.96 kg is left over."
    )
    assert _sentence(plan, "baking_powder").endswith(
        "Offered: 1 × Santa Maria 700G Baking Powder (466228) for €6.14 before tax, 31 sales units confirmed in "
        "stock. 0.002 kg is needed and the pack holds 0.7 kg, so 0.698 kg is left over."
    )
    sugar = _sentence(plan, "sugar")
    assert "It is not in option 1 (Best confirmed option (partial fill)): it has no confirmed stock." in sugar
    assert sugar.endswith(
        "Option 2 offers 1 × Dansukker Rawsugar Granulated 500g (461329) for €1.98 before tax, quantity not "
        "confirmed. 0.04 kg is needed and the pack holds 0.5 kg, so 0.46 kg is left over."
    )
    assert _sentence(plan, "milk").endswith("0.03 L is needed and the pack holds 1 L, so 0.97 L is left over.")


def test_for_two_hundred_servings_the_packs_are_counted_and_an_exact_fit_says_so(
    bakery_parts: Parts, recipes: Mapping[str, Recipe], clock: str
) -> None:
    plan, _ = _planned(bakery_parts, recipes, 200)

    assert _sentence(plan, "flour").endswith(
        "Offered: 2 × Myllyn Paras Emännän Semi Coarse Wheat Flour 2kg (460856) for €5.14 before tax, 976 sales "
        "units confirmed in stock. 4 kg is needed and the packs hold exactly that."
    )
    assert _sentence(plan, "cocoa_powder").endswith(
        "Offered: 5 × Fazer Cacao cocoa powder 200g (475703) for €22.35 before tax, 308 sales units confirmed in "
        "stock. 1 kg is needed and the packs hold exactly that."
    )
    assert _sentence(plan, "eggs").endswith("4 kg is needed and the pack holds 5 kg, so 1 kg is left over.")


def test_the_notes_give_each_options_total_and_who_must_confirm(
    bakery_parts: Parts, recipes: Mapping[str, Recipe], clock: str
) -> None:
    plan, _ = _planned(bakery_parts, recipes, 20)
    confirmed_net, alternative_net = TOTALS[clock, 20]

    first, second = [note for note in plan.notes if note.startswith(("Option 1, ", "Option 2, "))]
    # Lane FIX-M (review row C3-F8): nothing is late and four of seven ingredients are covered in full, so the
    # note counts them and no longer says a date is not met or a share of one request line.
    assert first.startswith(
        f"Option 1, Best confirmed option (partial fill): €{confirmed_net} before tax, €17.24 with tax. 4 of the 7 "
        "ingredients are covered in full: flour, cocoa powder, milk and baking powder. Sugar"
    )
    assert "no confirmed stock" in first and "is not met" not in first and "0%" not in first
    assert second.startswith(f"Option 2, Alternative: quantity not confirmed: €{alternative_net} before tax, ")
    assert first.endswith("It needs the purchasing manager.") and second.endswith("It needs the purchasing manager.")


def test_the_milk_is_regular_milk_first_and_the_offer_says_what_stands_in(
    bakery_parts: Parts, recipes: Mapping[str, Recipe], clock: str
) -> None:
    """What is already built holds for a plan's line: a request for milk is filled with regular milk first, and a
    low-lactose milk is a named alternative. The offer carries the suggestions; the plan does not repeat them."""
    _, offer = _planned(bakery_parts, recipes, 20)

    assert any("filled with regular milk first" in note for note in offer.notes)
    assert "low-lactose milk, offered as a named alternative to regular milk" in offer.options[0].summary
    assert all(line.substitute is None for option in offer.options for line in option.lines)


def test_the_cake_is_ordered_like_any_offer_and_waits_for_the_owner(
    bakery_parts: Parts, recipes: Mapping[str, Recipe], clock: str
) -> None:
    plan, offer = _planned(bakery_parts, recipes, 20)

    order = bakery_parts.service.place_order(BAKERY, plan.offer_id, offer.options[1].option_id, f"cake-{clock}")

    assert order.status is OrderStatus.PENDING_APPROVAL
    owner = next(identity for identity in bakery_parts.tokens.identities if identity.id == "human:bakery-owner")
    waiting = bakery_parts.service.list_approvals(owner)
    assert [approval.order_id for approval in waiting] == [order.order_id]
