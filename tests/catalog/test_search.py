"""Catalog search: product type, name terms (English first, then Finnish), claims, category prefix, fallback."""

from __future__ import annotations

import re
from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.contracts.errors import InvalidRequest
from tta.contracts.request import ProductQuery

MILK_CATEGORY = "10400"


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


def test_lactose_free_milk_is_exactly_the_35_products_of_category_10400(
    catalog: ProductCatalog, raw_products: list[dict[str, Any]]
) -> None:
    claim = _lactose_free_code(raw_products)
    expected = sorted(
        raw["id"] for raw in raw_products if raw["category"] == MILK_CATEGORY and claim in _claim_ids(raw)
    )

    result = catalog.search(ProductQuery(product_type="milk", required_claims=(claim,)))

    assert len(expected) == 35
    assert [product.id for product in result.products] == expected
    assert result.total == 35
    assert result.categories == (MILK_CATEGORY,)
    assert result.unmatched_terms == ()


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
    assert result.total == 91
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
