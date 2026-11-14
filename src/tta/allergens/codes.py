"""The allergen codes of the catalog, their GS1 names and the code families (SPEC section 6).

The codes are GS1 AllergenTypeCode values. `gs1_name` is the Name column of GS1 code list T4078
(https://gs1.se/en/guides/documentation/code-lists/t4078-allergen-type-code/, read on 14 Nov 2026).
`label` is our short wording for sentences shown to people. Which codes the catalog uses, and the
families, are in AIMO/docs/SCHEMA-AND-CODES.md sections 2.1, 2.3 and 3.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

# GS1: "Does not contain declaration obligatory allergens". A general statement about the product,
# not a statement about one allergen (AIMO/docs/SCHEMA-AND-CODES.md section 3.4).
GENERAL_STATEMENT_CODE = "X99"
GLUTEN_CEREALS_CODE = "AW"
# Oats are listed under the gluten cereals, yet gluten-free oats are a legitimate product
# (AIMO/docs/SCHEMA-AND-CODES.md section 4.3): 76 catalog products state AW as FREE_FROM and declare GO.
OATS_CODE = "GO"


@dataclass(frozen=True)
class AllergenCode:
    """One GS1 allergen type code used in the catalog."""

    code: str
    gs1_name: str
    label: str


_TABLE: tuple[AllergenCode, ...] = (
    AllergenCode("ABD", "Tuna and its derivatives", "tuna"),
    AllergenCode("AC", "Crustaceans and its derivatives", "crustaceans"),
    AllergenCode("ADQ", "Pollock and its derivatives", "pollock"),
    AllergenCode("AE", "Eggs and its derivatives", "eggs"),
    AllergenCode("AF", "Fish and its derivatives", "fish"),
    AllergenCode("AM", "Milk and its derivatives", "milk"),
    AllergenCode("AN", "Tree nuts (Nuts) and its derivatives", "tree nuts"),
    AllergenCode("AP", "Peanuts and its derivatives", "peanuts"),
    AllergenCode("AS", "Sesame Seeds and its derivatives", "sesame seeds"),
    AllergenCode("AU", "Sulfur Dioxide and Sulfits", "sulphur dioxide and sulphites"),
    # GS1 describes AW as "cereal grains containing gluten (protein) and their derivatives".
    AllergenCode("AW", "Cereals and its derivatives", "cereals containing gluten"),
    AllergenCode("AY", "Soybean and its derivatives", "soybeans"),
    AllergenCode("BC", "Celery and its derivatives", "celery"),
    AllergenCode("BF", "Beef and its derivatives", "beef"),
    AllergenCode("BM", "Mustard and its derivatives", "mustard"),
    AllergenCode("BP", "Linalool", "linalool"),
    AllergenCode("CM", "Chicken Meat and its derivatives", "chicken meat"),
    AllergenCode("GB", "Barley and its derivatives", "barley"),
    AllergenCode("GK", "Khorasan wheat and its derivatives", "khorasan wheat"),
    AllergenCode("GO", "Oats and its derivatives", "oats"),
    AllergenCode("GS", "Spelt and its derivatives", "spelt"),
    AllergenCode("ML", "Lactose", "lactose"),
    AllergenCode("NC", "Cocoa and its derivatives", "cocoa"),
    AllergenCode("NE", "Peas and its derivatives", "peas"),
    AllergenCode("NK", "Coriander and its derivatives", "coriander"),
    AllergenCode("NL", "Lupine and its derivatives", "lupin"),
    AllergenCode("NM", "Corn and Its derivatives", "corn"),
    AllergenCode("NP", "Pod Fruits and its derivatives", "pod fruits"),
    AllergenCode("NR", "Rye and its derivatives", "rye"),
    AllergenCode("NW", "Carrots and its derivatives", "carrots"),
    AllergenCode("PN", "Pine nuts and its derivatives", "pine nuts"),
    AllergenCode("PO", "Pork and its derivatives", "pork"),
    AllergenCode("SA", "Almond and its derivatives", "almonds"),
    AllergenCode("SC", "Cashews and its derivatives", "cashews"),
    AllergenCode("SH", "Hazelnut and its derivatives", "hazelnuts"),
    AllergenCode("SM", "Macadamia Nut and its derivatives", "macadamia nuts"),
    AllergenCode("SO", "Coconuts and its derivatives", "coconut"),
    AllergenCode("SP", "Pecan Nut and its derivatives", "pecan nuts"),
    AllergenCode("SR", "Brazil Nut and its derivatives", "Brazil nuts"),
    AllergenCode("ST", "Pistachio and its derivatives", "pistachios"),
    AllergenCode("SW", "Walnut and its derivatives", "walnuts"),
    AllergenCode("UM", "Molluscs and its derivatives", "molluscs"),
    AllergenCode("UN", "Shellfish and its derivatives", "shellfish"),
    AllergenCode("UW", "Wheat and its derivatives", "wheat"),
    AllergenCode(GENERAL_STATEMENT_CODE, "Does not contain declaration obligatory allergens",
                 "no declaration-obligatory allergens"),
)

ALLERGEN_CODES: Mapping[str, AllergenCode] = MappingProxyType({entry.code: entry for entry in _TABLE})

# Family code → its member codes, one level deep (AIMO/docs/SCHEMA-AND-CODES.md section 3.1 and 3.3).
FAMILIES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        GLUTEN_CEREALS_CODE: ("UW", "GB", "NR", OATS_CODE, "GS", "GK"),
        "AN": ("SA", "SH", "SW", "SC", "ST", "SM", "SP", "SR"),
        "AM": ("ML",),
        "AF": ("ABD", "ADQ"),
    }
)

_PARENT_OF: Mapping[str, str] = MappingProxyType(
    {member: family for family, members in FAMILIES.items() for member in members}
)


def is_known_code(code: str) -> bool:
    """True for a code of the table. Codes are upper case and are not normalised."""
    return code in ALLERGEN_CODES


def gs1_name(code: str) -> str | None:
    entry = ALLERGEN_CODES.get(code)
    return entry.gs1_name if entry else None


def members_of(code: str) -> tuple[str, ...]:
    """The member codes of a family code; empty for any other code."""
    return FAMILIES.get(code, ())


def parent_of(code: str) -> str | None:
    """The family code a member belongs to; `None` for any other code."""
    return _PARENT_OF.get(code)


def describe(code: str, note: str | None = None) -> str:
    """The wording used in sentences: `milk (AM)`, or `milk (AM, may contain)` with a note.

    A code outside the table is named by its code alone.
    """
    entry = ALLERGEN_CODES.get(code)
    name = entry.label if entry else "allergen code"
    return f"{name} ({code}, {note})" if note else f"{name} ({code})"
