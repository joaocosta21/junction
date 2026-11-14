"""A catalog product, reduced to what the system uses (SPEC section 3, AIMO/docs/PRODUCT-DATA.md)."""

from __future__ import annotations

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
    country_of_origin: str | None = None
    countries_of_origin: tuple[str, ...] = ()
    deleted: bool = False
    delivery_reliability: Number | None = None  # share between 0 and 1, from the reliability file
    carbon_kg_co2e_per_kg: Number | None = None  # from the carbon footprint file

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
