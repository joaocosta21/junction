"""The catalog: the local product file behind the `Catalog` port (SPEC section 3).

Built once and then only read: products, indexes and the product-type table never change afterwards.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from decimal import Decimal

from tta.catalog import lots, pack
from tta.catalog import search as catalog_search
from tta.catalog.loader import load_products
from tta.catalog.product_types import ProductType, load_product_types
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
        return cls(products, load_product_types())

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

    def same_category(self, product_id: str, digits: int) -> tuple[Product, ...]:
        """Other products sharing the first `digits` digits of the category, in id order.

        Deleted products are left out, and a deleted product has no such list.
        """
        if not 1 <= digits <= CATEGORY_DIGITS:
            raise InvalidRequest(f"A category is compared on 1 to {CATEGORY_DIGITS} digits, not {digits}.")
        product = self._by_id.get(product_id)
        if product is None:
            return ()
        prefix = product.category[:digits]
        others = [
            other
            for category, members in self._by_category.items()
            if category.startswith(prefix)
            for other in members
            if other.id != product_id
        ]
        return tuple(sorted(others, key=lambda other: other.id))

    def pack_size(self, product: Product, price: PriceLine | None, unit: Unit) -> PackSize:
        return pack.pack_size(product, price, unit)

    def is_portion_pack(self, product: Product) -> bool:
        return pack.is_portion_pack(product)

    def round_to_lot(self, product: Product, quantity: Decimal) -> Decimal:
        return lots.round_to_lot(product, quantity)
