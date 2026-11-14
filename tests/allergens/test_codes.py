"""The code table: every allergen code of the catalog, its GS1 name, and the families."""

from __future__ import annotations

from typing import Any

import pytest

from tta.allergens import codes

ALLERGEN_GROUPS = ("allergen", "nonAllergen")
CATALOG_CODE_COUNT = 45  # 44 codes in `allergen` plus `UN`, which appears only in `nonAllergen`


def _catalog_codes(raw_products: list[dict[str, Any]]) -> set[str]:
    return {
        value["id"]
        for product in raw_products
        for group in product.get("synkkaData", {}).get("classifications", [])
        if group.get("name") in ALLERGEN_GROUPS
        for value in group.get("values", [])
    }


def test_table_holds_exactly_the_codes_of_the_catalog(raw_products: list[dict[str, Any]]) -> None:
    catalog_codes = _catalog_codes(raw_products)

    assert len(catalog_codes) == CATALOG_CODE_COUNT
    assert set(codes.ALLERGEN_CODES) == catalog_codes


def test_every_code_has_a_gs1_name_and_a_short_label() -> None:
    for code, entry in codes.ALLERGEN_CODES.items():
        assert entry.code == code
        assert entry.gs1_name.strip()
        assert entry.label.strip()


@pytest.mark.parametrize(
    ("code", "gs1_name"),
    [
        ("AM", "Milk and its derivatives"),
        ("AW", "Cereals and its derivatives"),
        ("GK", "Khorasan wheat and its derivatives"),
        ("ML", "Lactose"),
        ("UN", "Shellfish and its derivatives"),
        ("X99", "Does not contain declaration obligatory allergens"),
    ],
)
def test_gs1_name_is_the_name_of_the_gs1_code_list(code: str, gs1_name: str) -> None:
    assert codes.gs1_name(code) == gs1_name


def test_gs1_name_of_an_unknown_code_is_none() -> None:
    assert codes.gs1_name("ZZ") is None


def test_gluten_cereals_are_the_family_under_aw() -> None:
    assert set(codes.members_of("AW")) == {"UW", "GB", "NR", "GO", "GS", "GK"}


def test_tree_nut_species_are_the_family_under_an() -> None:
    assert set(codes.members_of("AN")) == {"SA", "SH", "SW", "SC", "ST", "SM", "SP", "SR"}


def test_lactose_is_under_milk_and_fish_species_under_fish() -> None:
    assert codes.members_of("AM") == ("ML",)
    assert set(codes.members_of("AF")) == {"ABD", "ADQ"}


def test_corn_is_not_a_gluten_cereal() -> None:
    assert "NM" not in codes.members_of("AW")
    assert codes.parent_of("NM") is None


def test_parent_of_a_member_is_its_family_code() -> None:
    assert codes.parent_of("UW") == "AW"
    assert codes.parent_of("SA") == "AN"
    assert codes.parent_of("ML") == "AM"


def test_a_family_code_has_no_parent_and_a_plain_code_no_members() -> None:
    assert codes.parent_of("AW") is None
    assert codes.members_of("AE") == ()
    assert codes.members_of("ZZ") == ()


def test_every_family_code_and_member_is_in_the_table() -> None:
    for parent, members in codes.FAMILIES.items():
        assert codes.is_known_code(parent)
        assert all(codes.is_known_code(member) for member in members)


def test_families_are_one_level_deep() -> None:
    for members in codes.FAMILIES.values():
        assert all(codes.members_of(member) == () for member in members)


def test_is_known_code() -> None:
    assert codes.is_known_code("AM")
    assert not codes.is_known_code("am")
    assert not codes.is_known_code("ZZ")


def test_describe_gives_the_label_and_the_code() -> None:
    assert codes.describe("AM") == "milk (AM)"
    assert codes.describe("AW") == "cereals containing gluten (AW)"


def test_describe_an_unknown_code_names_only_the_code() -> None:
    assert codes.describe("ZZ") == "allergen code (ZZ)"


def test_describe_with_a_note_puts_it_next_to_the_code() -> None:
    assert codes.describe("AN", "may contain") == "tree nuts (AN, may contain)"
    assert codes.describe("ZZ", "contains") == "allergen code (ZZ, contains)"
