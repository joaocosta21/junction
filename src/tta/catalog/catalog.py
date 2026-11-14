"""The catalog: the local product file behind the `Catalog` port (SPEC section 3).

Built once and then only read: products, indexes and the product-type table never change afterwards.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal
from functools import cached_property

from tta.catalog import lots, pack
from tta.catalog import search as catalog_search
from tta.catalog.loader import load_products
from tta.catalog.product_types import ProductType, load_product_types
from tta.catalog.qualifiers import Qualifiers, derive_qualifiers, provide_qualifiers
from tta.config import Settings
from tta.contracts.availability import PriceLine
from tta.contracts.common import Unit
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import PackSize, Product, SearchResult
from tta.contracts.request import ProductQuery

CATEGORY_DIGITS = 5  # every category is a 5-digit code (AIMO/FINDINGS.md section 2)


class ProductCatalog:
    """Implements `tta.contracts.ports.Catalog` over the products of the product file."""

    def __init__(self, products: Iterable[Product], product_types: Mapping[str, ProductType]) -> None:
        self._products = tuple(sorted(products, key=lambda product: product.id))
        self._product_types = dict(product_types)
        self._index = catalog_search.build_index(self._products)
        # A deleted product is served by no lookup, the same as by the search (0 of 17,546 today).
        self._by_id = {product.id: product for product in self._index.products}
        self._deleted_ids = frozenset(product.id for product in self._products if product.deleted)
        by_category: defaultdict[str, list[Product]] = defaultdict(list)
        for product in self._index.products:
            by_category[product.category].append(product)
        self._by_category = {category: tuple(members) for category, members in by_category.items()}

    @classmethod
    def from_settings(cls, settings: Settings) -> ProductCatalog:
        """Load the product file, the two comparison files and the product-type table. About a second."""
        products = load_products(settings.tta_product_file, settings.tta_reliability_file, settings.tta_carbon_file)
        catalog = cls(products, load_product_types())
        # The comparison of two ingredient lists reads the qualifiers of the product file. Measured on first
        # use (about 3 seconds for 38,330 statements), not at load, and once per catalog.
        provide_qualifiers(lambda: catalog.qualifiers)
        return catalog

    @cached_property
    def qualifiers(self) -> Qualifiers:
        """The words of origin and farming, measured from this catalog's own ingredient statements."""
        return derive_qualifiers(self._products)

    @property
    def products(self) -> tuple[Product, ...]:
        """Every product of the file, in id order, deleted ones included. The lookups leave those out."""
        return self._products

    def get_product(self, product_id: str) -> Product | None:
        """The product, or `None` for an id that is not in the file or is marked deleted."""
        return self._by_id.get(product_id)

    def search(self, query: ProductQuery) -> SearchResult:
        return catalog_search.search(self._index, self._product_types, query)

    def product_type_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._product_types))

    def product_type_note(self, key: str) -> str | None:
        found = self._product_types.get(key)
        return None if found is None else found.note

    def listed_substitutes(self, product_id: str) -> tuple[str, ...]:
        """The substitutes Valio lists for the product, in file order, as a seed to re-check.

        A product is never its own substitute: `471661` lists itself (AIMO/FINDINGS.md section 5).
        A deleted product has no substitutes and is nobody's substitute.
        """
        product = self._by_id.get(product_id)
        if product is None:
            return ()
        return tuple(
            dict.fromkeys(
                other
                for other in product.listed_substitutes
                if other != product_id and other not in self._deleted_ids
            )
        )

    def same_category(self, product_id: str, digits: int = CATEGORY_DIGITS) -> tuple[Product, ...]:
        """Other products of the same 5-digit category, in id order.

        A category number is opaque: all five digits or nothing. Valio did not confirm that its digits are
        levels (answer V7, 14 Nov 2026), and a shared prefix is a neighbouring shelf, not the same kind of
        product (AIMO/build/replan/P7-categories.md section 2b). `digits` is kept for a caller that still
        passes it, and only 5 is accepted. Deleted products are left out, and a deleted product has no list.
        """
        if digits != CATEGORY_DIGITS:
            raise InvalidRequest(
                f"A category is compared on all {CATEGORY_DIGITS} digits, not {digits}: the digits of a category "
                "number are not levels."
            )
        product = self._by_id.get(product_id)
        if product is None:
            return ()
        return tuple(other for other in self._by_category.get(product.category, ()) if other.id != product_id)

    def pack_size(self, product: Product, price: PriceLine | None, unit: Unit) -> PackSize:
        return pack.pack_size(product, price, unit)

    def is_portion_pack(self, product: Product) -> bool:
        return pack.is_portion_pack(product)

    def round_to_lot(self, product: Product, quantity: Decimal) -> Decimal:
        return lots.round_to_lot(product, quantity)
