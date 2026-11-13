"""Find static Valio Aimo catalog candidates before querying the mock API."""

import argparse
import json
import re
import sys
from pathlib import Path


CATALOG_FILENAME = "valio_aimo_junction26_product_data.json"
VOLUME_TO_LITRES = {"LTR": 1, "DLT": 0.1, "CLT": 0.01, "MLT": 0.001}
NAME_VOLUME = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(ml|cl|dl|l)\b", re.IGNORECASE
)
MULTIPACK_PREFIX = re.compile(r"^\s*(\d+)\s*[x×]", re.IGNORECASE)


def load_catalog(path):
    """Load once and reuse the catalog across searches."""
    with Path(path).open(encoding="utf-8-sig") as catalog_file:
        return json.load(catalog_file)


def sales_unit_size(product, synkka, name):
    """Return litres per sales unit and the source, or an unknown size."""
    sales_unit = product.get("salesUnit")
    base_unit = product.get("baseUnit")
    if sales_unit == base_unit and sales_unit:
        multiplier = 1
    else:
        multiplier = next(
            (
                unit.get("sizeInBaseUnits")
                for unit in product.get("units", [])
                if unit["unitId"] == sales_unit
            ),
            None,
        )

    if not multiplier or multiplier <= 0:
        return None, "unknown"

    # Synkka describes the product identified by its own GTIN. Establish
    # whether that GTIN refers to the sales unit or to the base unit.
    synkka_gtin = synkka.get("gtin")
    base_gtins = {
        unit.get("gtin")
        for unit in product.get("units", [])
        if unit["unitId"] == base_unit
    }
    if synkka_gtin and synkka_gtin == product.get("salesUnitGtin"):
        volume_multiplier = 1
    elif synkka_gtin and synkka_gtin in base_gtins:
        volume_multiplier = multiplier
    else:
        volume_multiplier = None

    for conversion in synkka.get("unitConversions", []):
        if conversion["synkkaPackagingType"] != "BASE_UNIT_OR_EACH":
            continue
        volume = conversion.get("volume", {})
        factor = VOLUME_TO_LITRES.get(volume.get("unit"))
        if volume_multiplier and factor and volume["value"] > 0:
            return round(volume["value"] * factor * volume_multiplier, 6), "catalog_volume"

    matches = NAME_VOLUME.findall(name)
    if len(matches) != 1:
        return None, "unknown"

    # A leading "12 x" describes a multipack. Require it to agree with
    # the unit conversion before using the named volume per item.
    prefix = MULTIPACK_PREFIX.match(name)
    if prefix and int(prefix[1]) != multiplier:
        return None, "unknown"

    amount, unit = matches[0]
    factor = {"l": 1, "dl": 0.1, "cl": 0.01, "ml": 0.001}[unit.lower()]
    litres = float(amount.replace(",", ".")) * factor * multiplier
    return (round(litres, 6), "name_estimate") if litres > 0 else (None, "unknown")


def search_catalog(products, *, category=None, claim=None, query=None):
    """Return candidate records without making network requests."""
    candidates = []
    terms = query.casefold().split() if query else []
    for product in products:
        if product.get("deleted") or (category and product.get("category") != category):
            continue
        synkka = product.get("synkkaData") or {}
        if claim and not any(
            value["id"] == claim
            for group in synkka.get("classifications", [])
            if group["name"] == "nutritionalClaim"
            for value in group.get("values", [])
        ):
            continue

        names = synkka.get("names", [])
        if terms and not any(
            all(term in entry["value"].casefold() for term in terms) for entry in names
        ):
            continue
        names_by_language = {entry["language"]: entry["value"] for entry in names}
        name = names_by_language.get("en") or names_by_language.get("fi")
        if not name and names:
            name = names[0]["value"]
        litres, volume_source = sales_unit_size(product, synkka, name or "")
        candidates.append(
            {
                "id": product["id"],
                "name": name,
                "category": product.get("category"),
                "sales_unit": product.get("salesUnit"),
                "allowed_lot_size": product.get("allowedLotSize"),
                "litres_per_sales_unit": litres,
                "volume_source": volume_source,
            }
        )

    return sorted(candidates, key=lambda candidate: candidate["id"])


def main():
    folder = Path(__file__).resolve().parent
    catalog_path = folder / CATALOG_FILENAME
    if not catalog_path.is_file():
        catalog_path = folder.parent / CATALOG_FILENAME

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=catalog_path)
    parser.add_argument("--category", help="Catalog category code")
    parser.add_argument("--claim", help="Catalog nutritional claim code")
    parser.add_argument("--query", help="Words to match in a catalog product name")
    parser.add_argument("--ids-only", action="store_true", help="Output a JSON list of IDs")
    args = parser.parse_args()

    if not (args.category or args.claim or args.query):
        parser.error("provide at least one of --category, --claim or --query")
    try:
        products = load_catalog(args.catalog)
    except (OSError, ValueError) as error:
        parser.error(f"could not read {args.catalog}: {error}")
    candidates = search_catalog(
        products, category=args.category, claim=args.claim, query=args.query
    )
    output = [candidate["id"] for candidate in candidates] if args.ids_only else candidates
    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
