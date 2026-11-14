"""A catalog product, reduced to what the system uses (SPEC section 3, AIMO/docs/PRODUCT-DATA.md)."""

from __future__ import annotations

from enum import StrEnum

from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import Contract, Number, PackSizeSource, Quantity, Unit


class UnitSize(Contract):
    """One packaging level of a product: how many base units it holds."""

    unit_id: str
    size_in_base_units: Number
    gtin: str | None = None


class UnitConversion(Contract):
    """Measured size of one packaging level (synkkaData.unitConversions)."""

    packaging_type: str
    volume_l: Number | None = None
    net_weight_kg: Number | None = None


class Deposit(Contract):
    material: str
    unit: str
    quantity: Number


class NutritionBasis(StrEnum):
    """What the nutrition figures are stated for: 100 grams or 100 millilitres."""

    G = "G"
    ML = "ML"


class Nutrition(Contract):
    """The six nutrients the formula measure compares, in grams per 100 g or per 100 ml.

    Read from `synkkaData.nutritionalContent`. A nutrient the file does not state per 100 g or ml in grams
    stays `None`: nothing is imputed. Energy is left out on purpose (AIMO/build/replan/P10-formula.md 4.2).
    """

    fat: Number | None = None
    saturated_fat: Number | None = None
    protein: Number | None = None
    carbohydrate: Number | None = None
    sugars: Number | None = None
    salt: Number | None = None
    basis: NutritionBasis

    @property
    def is_complete(self) -> bool:
        """All six nutrients are stated."""
        values = (self.fat, self.saturated_fat, self.protein, self.carbohydrate, self.sugars, self.salt)
        return all(value is not None for value in values)


class FormulaOutcome(StrEnum):
    """How a product's formula compares with another's, best first. The measure and its tolerances are ours."""

    SAME_PRODUCT_OTHER_PACK = "SAME_PRODUCT_OTHER_PACK"  # same brand, the six figures equal, same fat source
    SAME_BRAND = "SAME_BRAND"  # same brand, every figure within tolerance, same fat source
    OTHER_BRAND = "OTHER_BRAND"  # another brand (or one not stated), within tolerance, same fat source
    DIFFERENT = "DIFFERENT"  # a figure outside tolerance, or another fat source
    NOT_KNOWN = "NOT_KNOWN"  # the data cannot tell; never read as the same


class NutrientDifference(Contract):
    """One nutrient on which two products differ, in grams per 100 g or ml."""

    nutrient: str  # a field name of `Nutrition`, for example "saturated_fat"
    original: Number
    other: Number
    within_tolerance: bool


class FormulaCheck(Contract):
    """The formula of one product measured against an original's (new `tta.offers.formula`)."""

    outcome: FormulaOutcome
    basis: NutritionBasis | None = None  # of both products; None when it is not the same or not known
    differences: tuple[NutrientDifference, ...] = ()  # every nutrient whose two figures are not equal
    # True: one ingredient list names a vegetable oil or fat and the other does not. None: a list is missing.
    fat_source_differs: bool | None = None
    # True: one product states its figures per 100 g and the other per 100 ml, and they were compared as they
    # stand because both are drinks (our rule, `tta.offers.formula`). `basis` is then None.
    mixed_basis: bool = False
    sentence: str  # for a person: the outcome and the reason, in numbers

    @property
    def keeps_formula(self) -> bool:
        """The data shows the same formula within tolerance. `NOT_KNOWN` is not the same."""
        return self.outcome in (
            FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND, FormulaOutcome.OTHER_BRAND
        )


class ReplaceVerdict(StrEnum):
    """Can one product take another's place in a kitchen? The reading and its word lists are ours."""

    REPLACEABLE = "REPLACEABLE"  # same type, same use, same flavour, same formula within tolerance, no claim lost
    NOT_SHOWN = "NOT_SHOWN"  # nothing the data shows speaks against it, but the formula cannot be compared
    NOT_LIKE_FOR_LIKE = "NOT_LIKE_FOR_LIKE"  # at least one reason against it; `reasons` names each


class ReplaceCheck(Contract):
    """One candidate measured against the product it would replace (`tta.offers.substitutes`).

    Types are keys of `product_types.yaml`; flavours and uses are read from the product names
    (`tta.catalog.kinds`). An empty tuple means the table or the names say nothing, not that nothing is so.
    """

    verdict: ReplaceVerdict
    original_types: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    other_type: bool = False  # the original has a product type and the candidate is not of it
    original_flavours: tuple[str, ...] = ()
    flavours: tuple[str, ...] = ()
    # One of the two is flavoured and the other is not: the candidate leaves the list (a last resort).
    plain_against_flavoured: bool = False
    other_flavour: bool = False  # both are flavoured, with different flavours: said and ranked later, not left out
    original_uses: tuple[str, ...] = ()
    uses: tuple[str, ...] = ()
    other_use: bool = False  # the names say different uses (made for coffee, for whipping, for cooking)
    # The two are of one brand and their names differ in a word no list of ours explains: variants of a product
    # line (`tta.catalog.name_words`). A last resort unless Valio lists the pair.
    name_difference: bool = False
    original_name_words: tuple[str, ...] = ()  # the differing words of the original's name, as written
    name_words: tuple[str, ...] = ()  # the differing words of the candidate's name, as written
    type_not_judged: bool = False  # the original has no product type of ours: only the category was compared
    # The type was not judged and the candidate's name shares no product word with the original's: a last
    # resort unless Valio lists the pair.
    no_shared_word: bool = False
    reasons: tuple[str, ...] = ()  # why it is not like-for-like, each in plain words; empty when replaceable
    sentence: str  # for a person: "Replaceable: ..." or "Not a like-for-like replacement: ..."

    @property
    def leaves_the_list(self) -> bool:
        """Held back while a like-for-like candidate can be ordered: another type (unless Valio lists the
        pair, which the ranking decides), or flavoured against plain."""
        return self.other_type or self.plain_against_flavoured


class Product(Contract):
    """One product of the catalog file. Optional facts stay `None`; nothing is imputed."""

    id: str
    name_en: str | None = None
    name_fi: str | None = None
    brand: str | None = None
    vendor_name: str | None = None
    category: str
    sales_unit: str  # from the product file; the API line's sales unit wins for price and quantity
    base_unit: str
    sales_unit_gtin: str | None = None
    synkka_gtin: str | None = None
    units: tuple[UnitSize, ...] = ()
    unit_conversions: tuple[UnitConversion, ...] = ()
    allowed_lot_size: Number
    variable_weight: bool | None = None  # synkkaData.variableUnit; None when the file does not say
    deposits: tuple[Deposit, ...] = ()
    nutritional_claims: tuple[str, ...] = ()
    allergen_statements: tuple[AllergenStatement, ...] = ()
    has_allergen_groups: bool = False  # False: the file carries no allergen group at all for this product
    listed_substitutes: tuple[str, ...] = ()
    # synkkaData.keyIngredients, English else Finnish; EU labelling writes allergens in capitals
    key_ingredients: str | None = None
    country_of_origin: str | None = None
    countries_of_origin: tuple[str, ...] = ()
    deleted: bool = False
    delivery_reliability: Number | None = None  # share between 0 and 1, from the reliability file
    carbon_kg_co2e_per_kg: Number | None = None  # from the carbon footprint file
    # Certificate labels of packagingMarkedLabel, in file order; its three storage temperatures are not labels
    # (AIMO/docs/SCHEMA-AND-CODES.md section 2.5). Empty: the file states none.
    labels: tuple[str, ...] = ()
    # Nutrients per 100 g or ml; None when the file states none of the six on that basis.
    nutrition: Nutrition | None = None

    @property
    def display_name(self) -> str:
        return self.name_en or self.name_fi or self.id

    @property
    def has_deposits(self) -> bool:
        return bool(self.deposits)

    @property
    def has_allergen_statement(self) -> bool:
        return bool(self.allergen_statements)


class PackSize(Contract):
    """Litres or kilograms per sales unit, and where the figure came from."""

    value: Quantity | None = None
    unit: Unit | None = None  # L or KG
    source: PackSizeSource = PackSizeSource.UNKNOWN
    inner_units: int | None = None  # single items inside one sales unit, when known
    inner_unit_size: Quantity | None = None  # litres or kg of one inner item, when known

    @property
    def is_known(self) -> bool:
        return self.value is not None and self.source is not PackSizeSource.UNKNOWN


class SearchResult(Contract):
    """Candidates for a query, in a deterministic order, with what the search could not match."""

    products: tuple[Product, ...] = ()
    total: int = 0
    categories: tuple[str, ...] = ()  # the categories the result was narrowed to
    unmatched_terms: tuple[str, ...] = ()
    note: str | None = None
