"""Loader of the product file and the two comparison files (SPEC section 3, AIMO/docs/PRODUCT-DATA.md).

The product file is parsed once into the `Product` contract, keeping only what the system uses.
Delivery reliability and carbon footprint are joined by product id; a product with no row keeps
`None`, because a missing value is never imputed (AIMO/FINDINGS.md section 6).

The files are untrusted input: every record is validated and a file that does not fit is rejected
as a whole, naming the product, so that no product is dropped without anyone noticing.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError

from tta.allergens import is_known_code, normalise_code
from tta.catalog.data_errors import data_file_error
from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation
from tta.contracts.product import Product

PRODUCT_ID_COLUMN = "productId"
RELIABILITY_COLUMN = "deliveryReliability"
CARBON_COLUMN = "AVG kg CO2-eq/kg"
MAX_RELIABILITY = Decimal(1)  # a share between 0 and 1 (AIMO/docs/CSV-DATASETS.md section 1)

# Only these units of unitConversions are a real volume or weight; `volume` also carries grams,
# pieces and metres on 88% of its rows (AIMO/docs/PRODUCT-DATA.md section 5, tier 2).
LITRES_PER_VOLUME_UNIT = {"LTR": Decimal(1), "DLT": Decimal("0.1"), "CLT": Decimal("0.01"), "MLT": Decimal("0.001")}
KG_PER_WEIGHT_UNIT = {"KGM": Decimal(1), "GRM": Decimal("0.001")}

# countryOfOrigin values that are not ISO 3166-1 codes (AIMO/docs/PRODUCT-DATA.md section 8, row 18).
ORIGIN_PLACEHOLDERS = frozenset({"zy", "xs", "zz"})

ALLERGEN_GROUP = "allergen"
NON_ALLERGEN_GROUP = "nonAllergen"
CLAIM_GROUP = "nutritionalClaim"
LABEL_GROUP = "packagingMarkedLabel"
# Storage temperatures filed in the label group: not certificates (AIMO/docs/SCHEMA-AND-CODES.md section 2.5).
TEMPERATURE_PSEUDO_LABELS = frozenset({"warmTemperature", "coolTemperature", "freezeTemperature"})
# Every certificate id in the file is UPPER_SNAKE (same section). A label is shown in sentences, so any other
# text rejects the file instead of reaching them.
_LABEL_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,59}")
# keyIngredients is in English on 11,562 products and in Finnish only on 2,427 more (whole catalog). 28
# English values and 53 Finnish ones are a placeholder such as "-" or ".", which is not an ingredient list.
INGREDIENT_LANGUAGES = ("en", "fi")
_LETTER = re.compile(r"[^\W\d_]")
# The six nutrients the formula measure compares (AIMO/docs/SCHEMA-AND-CODES.md section 2.6), by `Nutrition` field.
NUTRIENT_FIELDS = {
    "FAT": "fat", "FASAT": "saturated_fat", "PRO-": "protein", "CHOAVL": "carbohydrate", "SUGAR-": "sugars",
    "SALTEQ": "salt",
}
# A figure is read only when it is stated in grams per 100 g or per 100 ml: 113,093 of the 114,754 nutrient rows
# are per 100, the others per portion or per another quantity (AIMO/docs/PRODUCT-DATA.md section 2.2).
NUTRITION_BASIS_QUANTITY = Decimal(100)
NUTRITION_BASIS_UNITS = {"GRM": "G", "MLT": "ML"}
NUTRIENT_VALUE_UNIT = "GRM"
# The schema documents CONTAINS only; the file also has these two (AIMO/FINDINGS.md section 3).
DECLARED_RELATIONS = frozenset(
    {AllergenRelation.CONTAINS, AllergenRelation.MAY_CONTAIN, AllergenRelation.UNDECLARED}
)

_PRODUCTS = TypeAdapter(tuple[Product, ...])
_RECORD_ERRORS = (KeyError, TypeError, AttributeError, ValueError, InvalidOperation)


def load_products(
    product_file: Path, reliability_file: Path | None = None, carbon_file: Path | None = None
) -> tuple[Product, ...]:
    """Every product of the file, in file order. Raises `SupplierUnavailable` for a file it cannot use."""
    records = _read_records(product_file)
    reliability = load_metric(reliability_file, RELIABILITY_COLUMN, MAX_RELIABILITY) if reliability_file else {}
    carbon = load_metric(carbon_file, CARBON_COLUMN) if carbon_file else {}
    fields = [_fields_of(product_file, index, record, reliability, carbon) for index, record in enumerate(records)]
    try:
        products = _PRODUCTS.validate_python(fields)
    except ValidationError as error:
        first = error.errors(include_url=False, include_input=False)[0]
        product_id = fields[first["loc"][0]]["id"]
        where = ".".join(str(part) for part in first["loc"][1:])
        raise data_file_error(product_file, f"product {product_id!r}, {where}: {first['msg']}") from error
    _reject_duplicates(product_file, products)
    return products


def load_metric(path: Path, value_column: str, maximum: Decimal | None = None) -> dict[str, Decimal]:
    """A two-column CSV of product id and value. Values must be finite, not negative and at most `maximum`."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != [PRODUCT_ID_COLUMN, value_column]:
                raise data_file_error(path, f"the header must be {PRODUCT_ID_COLUMN},{value_column}")
            return _metric_rows(path, reader, value_column, maximum)
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise data_file_error(path, "it cannot be read") from error


def _metric_rows(
    path: Path, reader: csv.DictReader[str], value_column: str, maximum: Decimal | None
) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for line_number, row in enumerate(reader, start=2):
        product_id = (row.get(PRODUCT_ID_COLUMN) or "").strip()
        if not product_id:
            raise data_file_error(path, f"line {line_number} has no product id")
        if product_id in values:
            raise data_file_error(path, f"line {line_number} repeats product {product_id}")
        try:
            value = Decimal((row.get(value_column) or "").strip())
        except InvalidOperation as error:
            raise data_file_error(path, f"line {line_number} has no number for product {product_id}") from error
        if not value.is_finite() or value < 0 or (maximum is not None and value > maximum):
            raise data_file_error(path, f"line {line_number} has a value out of range for product {product_id}")
        values[product_id] = value
    return values


def _read_records(path: Path) -> list[Any]:
    try:
        with path.open(encoding="utf-8-sig") as handle:
            records = json.load(handle)
    except (OSError, UnicodeDecodeError) as error:
        raise data_file_error(path, "it cannot be read") from error
    except ValueError as error:
        raise data_file_error(path, "it is not valid JSON") from error
    if not isinstance(records, list) or not records:
        raise data_file_error(path, "it must be a JSON array with at least one product")
    return records


def _fields_of(
    path: Path, index: int, record: Any, reliability: Mapping[str, Decimal], carbon: Mapping[str, Decimal]
) -> dict[str, Any]:
    product_id = record.get("id") if isinstance(record, dict) else None
    try:
        return _product_fields(record, reliability, carbon)
    except _RECORD_ERRORS as error:
        reason = f"{type(error).__name__}: {error}"
        raise data_file_error(path, f"record {index} (product {product_id!r}) is not valid: {reason}") from error


def _product_fields(
    record: dict[str, Any], reliability: Mapping[str, Decimal], carbon: Mapping[str, Decimal]
) -> dict[str, Any]:
    """One record of the file as `Product` fields. Optional keys are absent, never null: `.get()`."""
    synkka: dict[str, Any] = record["synkkaData"]
    names = {entry["language"]: entry["value"] for entry in synkka.get("names", ())}
    groups = {group["name"]: group.get("values", ()) for group in synkka.get("classifications", ())}
    product_id: str = record["id"]
    return {
        "id": product_id,
        "name_en": names.get("en"),
        "name_fi": names.get("fi"),
        "brand": (synkka.get("brand") or "").strip() or None,
        "vendor_name": record.get("vendorName"),
        "category": record["category"],
        "sales_unit": record["salesUnit"],
        "base_unit": record["baseUnit"],
        "sales_unit_gtin": record.get("salesUnitGtin"),
        "synkka_gtin": synkka.get("gtin"),
        "units": [_unit(unit) for unit in record["units"]],
        "unit_conversions": [_conversion(row) for row in synkka.get("unitConversions", ())],
        "allowed_lot_size": _positive(record["allowedLotSize"], "allowedLotSize"),
        "variable_weight": synkka.get("variableUnit"),  # true, false or absent: absent stays unknown
        "deposits": [_deposit(deposit) for deposit in record.get("deposits", ())],
        "nutritional_claims": tuple(value["id"] for value in groups.get(CLAIM_GROUP, ())),
        "labels": _labels(groups.get(LABEL_GROUP, ())),
        "allergen_statements": _statements(groups),
        "has_allergen_groups": ALLERGEN_GROUP in groups or NON_ALLERGEN_GROUP in groups,
        "listed_substitutes": tuple(pair["substituteProduct"] for pair in record.get("substitutions", ())),
        "key_ingredients": _key_ingredients(synkka.get("keyIngredients", ())),
        "nutrition": _nutrition(synkka.get("nutritionalContent", ())),
        "country_of_origin": _origin(record.get("countryOfOrigin")),
        "countries_of_origin": tuple(synkka.get("countriesOfOrigin", ())),
        "deleted": record["deleted"],
        "delivery_reliability": reliability.get(product_id),
        "carbon_kg_co2e_per_kg": carbon.get(product_id),
    }


def _key_ingredients(entries: Any) -> str | None:
    """The ingredient list in English, else in Finnish; `None` when neither has a letter in it.

    Every entry must carry a language and a text: an entry that does not rejects the file. The list is shown
    in sentences and read by the allergen rule (SPEC section 6), so it stays data and is never interpreted.
    """
    if not isinstance(entries, list | tuple):
        raise TypeError(f"keyIngredients must be a list, got {type(entries).__name__}")
    texts: dict[str, str] = {}
    for entry in entries:
        value = entry["value"]
        if not isinstance(value, str):
            raise TypeError(f"a keyIngredients value must be text, got {type(value).__name__}")
        texts.setdefault(entry["language"], value.strip())
    return next((texts[language] for language in INGREDIENT_LANGUAGES if _LETTER.search(texts.get(language, ""))), None)


def _nutrition(rows: Any) -> dict[str, Any] | None:
    """The six nutrients in grams per 100 g or ml; `None` when the file states none of them on that basis.

    Nothing is imputed: a row per portion, a value that is not in grams and a nutrient stated twice with two
    values are left unknown, and figures on both bases (per 100 g and per 100 ml) are not mixed. A value that
    is not a number from zero up rejects the file.
    """
    stated: dict[str, set[Decimal]] = {}
    bases: set[str] = set()
    for row in rows:
        field = NUTRIENT_FIELDS.get(row["id"])
        basis = NUTRITION_BASIS_UNITS.get(row["basisQuantityUnit"])
        if field is None or basis is None or _decimal(row["basisQuantity"]) != NUTRITION_BASIS_QUANTITY:
            continue
        value = _decimal(row["value"])
        if value < 0:
            raise ValueError(f"the nutrient {row['id']} has a value below zero")
        if row["unit"] != NUTRIENT_VALUE_UNIT:
            continue
        stated.setdefault(field, set()).add(value)
        bases.add(basis)
    if len(bases) != 1:
        return None
    values = {field: next(iter(found)) for field, found in stated.items() if len(found) == 1}
    return {**values, "basis": bases.pop()}


def _labels(values: Any) -> tuple[str, ...]:
    """The certificate labels of the group, each once, in file order; the storage temperatures left out."""
    labels: list[str] = []
    for value in values:
        code = value["id"]
        if not isinstance(code, str):
            raise TypeError(f"a packagingMarkedLabel id must be text, got {type(code).__name__}")
        if code in TEMPERATURE_PSEUDO_LABELS:
            continue
        if not _LABEL_CODE.fullmatch(code):
            raise ValueError(f"the packagingMarkedLabel id {code[:60]!r} is not a label code")
        labels.append(code)
    return tuple(dict.fromkeys(labels))


def _unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": unit["unitId"],
        # Kept as the file gives it: one display-level row (product 476872, unit ZML) says 0.0.
        "size_in_base_units": _decimal(unit["sizeInBaseUnits"]),
        "gtin": unit.get("gtin"),
    }


def _conversion(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "packaging_type": row["synkkaPackagingType"],
        "volume_l": _measure(row.get("volume"), LITRES_PER_VOLUME_UNIT),
        "net_weight_kg": _measure(row.get("netWeight"), KG_PER_WEIGHT_UNIT),
    }


def _measure(entry: dict[str, Any] | None, factors: Mapping[str, Decimal]) -> Decimal | None:
    """The entry in litres or kilograms, or `None` when its unit is not a real volume or weight."""
    if not entry:
        return None
    factor = factors.get(entry.get("unit", ""))
    value = entry.get("value")
    if factor is None or value is None:
        return None
    amount = _decimal(value)
    return amount * factor if amount > 0 else None


def _deposit(deposit: dict[str, Any]) -> dict[str, Any]:
    return {"material": deposit["material"], "unit": deposit["unit"], "quantity": _decimal(deposit["quantity"])}


def _statements(groups: Mapping[str, Any]) -> list[AllergenStatement]:
    """`allergen` carries CONTAINS, MAY_CONTAIN and UNDECLARED; `nonAllergen` is always FREE_FROM."""
    statements: list[AllergenStatement] = []
    for value in groups.get(ALLERGEN_GROUP, ()):
        relation = AllergenRelation(value["unit"])
        if relation not in DECLARED_RELATIONS:
            raise ValueError(f"the allergen group states {relation.value} for {value['id']}")
        statements.append(_statement(_allergen_code(value["id"]), relation))
    for value in groups.get(NON_ALLERGEN_GROUP, ()):
        if value["unit"] != AllergenRelation.FREE_FROM.value:
            raise ValueError(f"the nonAllergen group states {value['unit']} for {value['id']}")
        statements.append(_statement(_allergen_code(value["id"]), AllergenRelation.FREE_FROM))
    return statements


def _allergen_code(raw: Any) -> str:
    """The code as the allergen code table spells it. A code outside the table rejects the file.

    A statement with a misspelt code would match no excluded allergen, and the product would pass
    under DECLARED_ONLY. The file has 45 codes, all in the table (AIMO/docs/SCHEMA-AND-CODES.md
    sections 2.1, 2.3 and 3.3).
    """
    if not isinstance(raw, str):
        raise TypeError(f"expected an allergen code as text, got {type(raw).__name__}")
    code = normalise_code(raw)
    if not is_known_code(code):
        raise ValueError(f"the allergen code {raw!r} is not in the allergen code table")
    return code


@cache
def _statement(code: str, relation: AllergenRelation) -> AllergenStatement:
    """Statements are immutable and there are under 200 distinct ones, so each is built once."""
    return AllergenStatement(code=code, relation=relation)


def _origin(code: str | None) -> str | None:
    """ISO 3166-1 alpha-2 in capitals, or `None` when the file gives no country or a placeholder."""
    if not code or code.lower() in ORIGIN_PLACEHOLDERS:
        return None
    return code.upper()


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"expected a number, got {type(value).__name__}")
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("expected a finite number")
    return number


def _positive(value: Any, field: str) -> Decimal:
    number = _decimal(value)
    if number <= 0:
        raise ValueError(f"{field} must be above zero")
    return number


def _reject_duplicates(path: Path, products: tuple[Product, ...]) -> None:
    seen: set[str] = set()
    for product in products:
        if product.id in seen:
            raise data_file_error(path, f"product {product.id!r} appears more than once")
        seen.add(product.id)
