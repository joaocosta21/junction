"""Catalog search: product type, name terms (English first, then Finnish), claims, category prefix, fallback."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import pytest

from tta.catalog import ProductCatalog, ProductType
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import Product
from tta.contracts.request import ProductQuery

MILK_CATEGORY = "10400"
MILKS = 74  # catalog: the 91 products of category 10400 without the 17 below
SOUR_MILKS = {
    "463373", "463439", "469331", "469457", "469491", "472492", "475433", "475534", "476855", "476957", "477050",
}
LACTOSE_FREE_SOUR_MILKS = {"469331", "472492", "476957", "477050"}
COFFEE_DRINK = "469266"  # "Valio Latte original coffee drink", lactose free
SOY_YOGHURT = "472516"
# Milk for coffee is a type of its own: Valio Aimo, 14 Nov 2026, "no be explicit". All four are lactose free.
COFFEE_MILKS = {"462626", "464237", "473142", "463380"}


def _claim_ids(raw: dict[str, Any]) -> set[str]:
    return {
        value["id"]
        for group in raw["synkkaData"].get("classifications", [])
        if group["name"] == "nutritionalClaim"
        for value in group["values"]
    }


def _lactose_free_code(raw_products: list[dict[str, Any]]) -> str:
    """The claim code is read from the data: the nutritional claim that is FREE_FROM the Synkka id LACTOSE."""
    codes = {
        value["id"]
        for raw in raw_products
        for group in raw["synkkaData"].get("classifications", [])
        if group["name"] == "nutritionalClaim"
        for value in group["values"]
        if value.get("synkkaId") == "LACTOSE" and value.get("unit") == "FREE_FROM"
    }
    assert len(codes) == 1
    return codes.pop()


def test_lactose_free_milk_is_exactly_the_26_milks_of_category_10400(
    catalog: ProductCatalog, raw_products: list[dict[str, Any]]
) -> None:
    claim = _lactose_free_code(raw_products)
    with_claim = sorted(
        raw["id"] for raw in raw_products if raw["category"] == MILK_CATEGORY and claim in _claim_ids(raw)
    )
    not_milk = LACTOSE_FREE_SOUR_MILKS | COFFEE_MILKS | {COFFEE_DRINK}

    result = catalog.search(ProductQuery(product_type="milk", required_claims=(claim,)))

    # Category 10400 has 35 products with the claim: 26 milks, 4 sour milks, 4 coffee milks and a coffee drink.
    assert len(with_claim) == 35 and not_milk < set(with_claim)
    assert [product.id for product in result.products] == [pid for pid in with_claim if pid not in not_milk]
    assert result.total == 26
    assert result.categories == (MILK_CATEGORY,)
    assert result.unmatched_terms == ()


def test_milk_leaves_out_sour_milk_coffee_milk_the_coffee_drink_and_the_soy_yoghurt(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="milk", limit=1000))

    ids = {product.id for product in result.products}
    assert result.total == MILKS
    assert not ids & (SOUR_MILKS | COFFEE_MILKS | {COFFEE_DRINK, SOY_YOGHURT})
    assert all(re.search(r"\bmilk", (product.name_en or "").casefold()) for product in result.products)
    # The plain lactose-free milks of the demo capture, and the portion pack, are still candidates.
    assert {"469363", "462775", "463203", "464306"} <= ids


def test_coffee_milk_is_a_product_type_of_its_own_with_a_note_on_milk(catalog: ProductCatalog) -> None:
    every = catalog.search(ProductQuery(product_type="coffee_milk", limit=1000))
    lactose_free = catalog.search(ProductQuery(product_type="coffee_milk", required_claims=("FREE_FROM_LACTOSE",)))

    assert {product.id for product in every.products} == COFFEE_MILKS
    assert every.categories == (MILK_CATEGORY,)
    assert {product.id for product in lactose_free.products} == COFFEE_MILKS
    assert catalog.product_type_note("milk") == (
        "Coffee milk was left out: a request for milk gets no milk for coffee and no flavoured coffee milk. "
        "Ask for coffee milk by name (product type coffee_milk) to get it."
    )
    assert catalog.product_type_note("coffee_milk") is None and catalog.product_type_note("no-such-type") is None


def test_sour_milk_is_a_product_type_of_its_own(catalog: ProductCatalog) -> None:
    every = catalog.search(ProductQuery(product_type="sour_milk", limit=1000))
    lactose_free = catalog.search(ProductQuery(product_type="sour_milk", required_claims=("FREE_FROM_LACTOSE",)))

    assert {product.id for product in every.products} == SOUR_MILKS
    assert every.categories == (MILK_CATEGORY,)
    assert {product.id for product in lactose_free.products} == LACTOSE_FREE_SOUR_MILKS


def test_milk_sour_milk_and_coffee_milk_share_no_product_and_cover_all_but_two_of_the_category(
    catalog: ProductCatalog,
) -> None:
    milk = {product.id for product in catalog.search(ProductQuery(product_type="milk", limit=1000)).products}
    sour = {product.id for product in catalog.search(ProductQuery(product_type="sour_milk", limit=1000)).products}
    coffee = {product.id for product in catalog.search(ProductQuery(product_type="coffee_milk", limit=1000)).products}
    category = {product.id for product in catalog.products if product.category == MILK_CATEGORY}

    assert not milk & sour and not milk & coffee and not sour & coffee
    assert category - milk - sour - coffee == {COFFEE_DRINK, SOY_YOGHURT}


def _named(product_id: str, english: str | None, finnish: str | None) -> Product:
    return Product(
        id=product_id, name_en=english, name_fi=finnish, category=MILK_CATEGORY, sales_unit="ST", base_unit="ST",
        allowed_lot_size=Decimal(1),
    )


def test_exclude_terms_match_english_at_the_start_of_a_word_and_finnish_anywhere() -> None:
    products = [
        _named("460001", "Skimmed milk 1 l", "Rasvaton maito 1 l"),
        _named("460002", "Sour milk 1 l", "Hapanmaito 1 l"),  # English, start of a word
        _named("460003", "Resourceful milk 1 l", "Maito 1 l"),  # "sour" inside an English word: kept
        _named("460004", None, "Rasvatonpiimä 1 l"),  # Finnish, inside a joined word
        _named("460005", "AB SOUR-milk 1 l", None),  # capitals and a hyphen
    ]
    milk = ProductType(
        key="milk", categories=(MILK_CATEGORY,), exclude_terms=("Sour", "piimä"), products=2, derived_from="test"
    )
    plain = ProductType(key="plain", categories=(MILK_CATEGORY,), products=5, derived_from="test")
    catalog = ProductCatalog(products, {"milk": milk, "plain": plain})

    narrowed = catalog.search(ProductQuery(product_type="milk"))
    whole = catalog.search(ProductQuery(product_type="plain"))

    assert [product.id for product in narrowed.products] == ["460001", "460003"]
    assert whole.total == 5


def test_exclude_terms_and_name_terms_must_both_hold() -> None:
    products = [
        _named("460001", "Oat drink 1 l", None),
        _named("460002", "Oat drink barista 1 l", None),
        _named("460003", "Oat cooking base 1 l", None),
    ]
    drink = ProductType(
        key="drink", categories=(MILK_CATEGORY,), name_terms=("drink",), exclude_terms=("barista",), products=1,
        derived_from="test",
    )
    catalog = ProductCatalog(products, {"drink": drink})

    result = catalog.search(ProductQuery(product_type="drink"))

    assert [product.id for product in result.products] == ["460001"]


def test_soya_drink_is_found_under_plant_drink(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="plant_drink"))

    assert "464056" in {product.id for product in result.products}
    assert result.total == len(result.products)


def test_chuck_rolls_are_found_under_beef_chuck(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="beef_chuck"))

    ids = {product.id for product in result.products}
    assert {"464744", "466988"} <= ids
    assert all(product.category == "18720" for product in result.products)
    # 464108 is "beef backbone" in English and "etuselkä" in Finnish: the type's Finnish term finds it.
    assert "464108" in ids


def test_name_term_with_no_match_returns_nothing_and_names_the_term(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(name_terms=("milk", "xyzzyqq")))

    assert result.products == ()
    assert result.total == 0
    assert result.unmatched_terms == ("xyzzyqq",)
    assert result.note is not None and "xyzzyqq" in result.note


def test_name_term_failing_inside_a_product_type_is_named(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="milk", name_terms=("salmon",)))

    assert result.products == ()
    assert result.unmatched_terms == ("salmon",)


def test_terms_that_never_occur_together_return_nothing_and_say_so(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="milk", name_terms=("arla", "valio")))

    assert result.products == ()
    assert result.unmatched_terms == ()
    assert result.note is not None and "together" in result.note


def test_english_terms_match_at_the_start_of_a_word(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(category_prefix="18720", name_terms=("tea",)))

    # "Flanksteak" contains "tea", in English and in Finnish, but no word of a beef name starts with it.
    assert result.products == ()
    assert result.unmatched_terms == ("tea",)


def test_finnish_names_are_matched_inside_joined_words(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="milk", name_terms=("maito",), limit=1000))

    # "kevytmaitojuoma" (semi-skimmed milk drink) has "maito" in the middle of a word.
    assert "464306" in {product.id for product in result.products}
    assert result.unmatched_terms == ()


def test_a_term_is_also_looked_for_in_finnish_names(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(category_prefix="187", name_terms=("etuselkä",)))

    ids = {product.id for product in result.products}
    assert "464744" in ids and "464108" in ids
    assert "466988" not in ids  # "Well Beef Naudan Chuck roll": no "etuselkä" in either name


def test_every_name_term_must_match(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="plant_drink", name_terms=("Soya", "BARISTA")))

    assert "464056" in {product.id for product in result.products}
    assert all("soya" in (product.name_en or "").casefold() for product in result.products)
    assert all("barista" in (product.name_en or "").casefold() for product in result.products)


def test_without_a_product_type_the_search_keeps_the_categories_with_most_matches(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(name_terms=("milk",)))

    assert result.categories == (MILK_CATEGORY,)
    assert all(product.category == MILK_CATEGORY for product in result.products)
    assert result.total == 88
    # 275 English names have a word starting with "milk"; one more product has it only in its Finnish name.
    assert result.note is not None and "276" in result.note and MILK_CATEGORY in result.note


def test_a_finnish_word_finds_the_same_category_without_a_product_type(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(name_terms=("maito",)))

    # "maito" starts a word in 2 English names, both chocolate bars, and is in the Finnish name of the milks.
    assert result.categories == (MILK_CATEGORY,)
    assert "464306" in {product.id for product in result.products}


def test_english_matches_come_first_then_finnish_ones(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(category_prefix="10901", name_terms=("kaura",)))

    in_english = [bool(re.search(r"\bkaura", (product.name_en or "").casefold())) for product in result.products]
    first_finnish = in_english.index(False)
    english_ids = [product.id for product in result.products[:first_finnish]]
    finnish_ids = [product.id for product in result.products[first_finnish:]]
    assert 0 < first_finnish < len(in_english)
    assert not any(in_english[first_finnish:])
    assert english_ids == sorted(english_ids) and finnish_ids == sorted(finnish_ids)


def test_fallback_keeps_every_category_close_to_the_largest(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(name_terms=("salmon",)))

    # 25 fresh, 21 frozen and 15 ready-meal matches: each at least half of the largest.
    assert result.categories == ("18701", "41720", "17300")
    assert result.total == 61


def test_fallback_changes_nothing_when_one_category_holds_every_match(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(name_terms=("etuselkä",)))

    assert result.categories == ("18720",)
    assert result.total == 5
    assert result.note == "5 products match."


def test_category_prefix_filters_and_is_not_narrowed(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(category_prefix="104", name_terms=("milk",), limit=1000))

    assert result.total > 88
    assert all(product.category.startswith("104") for product in result.products)
    assert MILK_CATEGORY in result.categories and len(result.categories) > 1


def test_product_ids_are_checked_against_the_catalog(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_ids=("464306", "459999", "463203")))

    assert [product.id for product in result.products] == ["463203", "464306"]
    assert result.note is not None and "459999" in result.note


def test_claims_alone_are_a_valid_search(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(required_claims=("FREE_FROM_LACTOSE",), limit=5))

    assert result.total == 4_178
    assert len(result.products) == 5
    assert result.note is not None and "5" in result.note and "4178" in result.note.replace(",", "")


def test_claim_code_that_no_product_carries_returns_nothing_and_names_it(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="milk", required_claims=("LACTOSE_FREE",)))

    assert result.products == ()
    assert result.note is not None and "LACTOSE_FREE" in result.note and "FREE_FROM_LACTOSE" in result.note


def test_a_claim_is_not_matched_by_a_name(catalog: ProductCatalog) -> None:
    with_claim = catalog.search(ProductQuery(product_type="milk", required_claims=("FREE_FROM_LACTOSE",)))
    by_name = catalog.search(ProductQuery(product_type="milk", name_terms=("lactose", "free")))

    assert all("FREE_FROM_LACTOSE" in product.nutritional_claims for product in with_claim.products)
    assert {p.id for p in by_name.products} != {p.id for p in with_claim.products}


def test_results_are_ordered_by_id_and_repeatable(catalog: ProductCatalog) -> None:
    query = ProductQuery(product_type="beef", limit=1000)

    first = catalog.search(query)
    second = catalog.search(query)

    ids = [product.id for product in first.products]
    assert ids == sorted(ids)
    assert first == second


def test_limit_cuts_the_list_and_total_keeps_the_count(catalog: ProductCatalog) -> None:
    result = catalog.search(ProductQuery(product_type="milk", limit=10))

    assert len(result.products) == 10
    assert result.total == MILKS
    assert [product.id for product in result.products] == sorted(product.id for product in result.products)


def test_unknown_product_type_is_an_invalid_request_that_lists_the_keys(catalog: ProductCatalog) -> None:
    with pytest.raises(InvalidRequest) as raised:
        catalog.search(ProductQuery(product_type="unicorn_milk"))

    assert "unicorn_milk" in raised.value.detail
    assert "plant_drink" in raised.value.detail


def test_a_search_without_any_filter_is_an_invalid_request(catalog: ProductCatalog) -> None:
    with pytest.raises(InvalidRequest):
        catalog.search(ProductQuery())


def test_a_blank_term_or_claim_is_refused_by_the_query_itself() -> None:
    # The contract strips and bounds every term, so a blank one never reaches the search.
    with pytest.raises(ValueError, match="at least 1 character"):
        ProductQuery(name_terms=("  ",), required_claims=("",))


# --- A name term and the word before it (found by the reader lane, 14 Nov 2026) --------------------------------


def test_skimmed_milk_is_not_filled_with_semi_skimmed_milk(catalog: ProductCatalog) -> None:
    # Before: 46 milks, 29 of them semi-skimmed ("semi skimmed" has a word that starts with "skimmed").
    skimmed = catalog.search(ProductQuery(product_type="milk", name_terms=("skimmed",), limit=1000))
    semi = catalog.search(ProductQuery(product_type="milk", name_terms=("semi-skimmed",), limit=1000))

    assert skimmed.total == 17 and semi.total == 29
    assert not {product.id for product in skimmed.products} & {product.id for product in semi.products}
    assert "463171" in {product.id for product in skimmed.products}  # Valio skimmed milk 1 l
    assert "469363" in {product.id for product in semi.products}  # Arla Semi skimmed milkdrink 1 L
    assert "469363" not in {product.id for product in skimmed.products}


def test_salted_butter_was_never_filled_with_unsalted_butter(catalog: ProductCatalog) -> None:
    # "unsalted" is one word, so "salted" never matched it: 8 salted and 2 unsalted of 15 butters (3 of 19
    # before 15 Nov 2026, when the unsalted butter for laminating 464761 left the type).
    salted = catalog.search(ProductQuery(product_type="butter", name_terms=("salted",), limit=1000))
    unsalted = catalog.search(ProductQuery(product_type="butter", name_terms=("unsalted",), limit=1000))

    assert (salted.total, unsalted.total) == (8, 2)
    assert not {product.id for product in salted.products} & {product.id for product in unsalted.products}
    assert "463744" in {product.id for product in salted.products}  # "less salted" is salted


def test_a_word_of_opposite_meaning_before_the_term_is_no_match() -> None:
    from tta.catalog.text import ProductNames, normalise

    def names(english: str) -> ProductNames:
        return ProductNames(english=f" {normalise(english)}", finnish=" ")

    assert names("Arla Semi-skimmed milk 1 L").has("skimmed") is False
    assert names("Arla Semi-skimmed milk 1 L").has("semi skimmed") is True
    assert names("Skimmed milk, not semi skimmed").has("skimmed") is True  # one clean occurrence is enough
    assert names("Non-alcoholic sparkling wine").has("alcoholic") is False
    assert names("Lightly salted butter").has("salted") is True  # a word of degree, not of opposite meaning
    assert names("Fat free milk").has("fat free") is True
