"""Does a page found on the web name this product? A page for another product is never evidence (task S2).

A page matches when its product name, set against the product's English or its Finnish name:
- adds no word of its own (pack sizes, the brand and "UHT" aside): "Barista" on the page of a plain oat drink,
  or "(INT)" on another recipe, is another product;
- carries at least `MIN_SHARE_OF_NAME` of the product's own words;
- and the brand appears in the page's name, its title or the address's host name.
Case, punctuation and the "®" and "™" marks are ignored. A word with a digit in it is a size and is ignored, so
the same product in another pack size matches (assumption, in the hand-back).
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from tta.contracts.product import Product

MIN_SHARE_OF_NAME = 0.6
# Words that say nothing about which product it is: the packing method and the units of a pack size.
NOISE_WORDS = frozenset({"uht", "l", "ml", "cl", "dl", "kg", "g", "x", "pcs", "kpl"})
_WORD = re.compile(r"\w+")
_HAS_DIGIT = re.compile(r"\d")


def _words(text: str | None) -> frozenset[str]:
    return frozenset(_WORD.findall((text or "").casefold().replace("_", " ")))


def _significant(text: str | None, brand: frozenset[str]) -> frozenset[str]:
    return frozenset(
        word for word in _words(text) if word not in NOISE_WORDS and word not in brand and not _HAS_DIGIT.search(word)
    )


def _host_words(url: str) -> frozenset[str]:
    host = urlsplit(url).hostname or ""
    return frozenset(word for label in host.split(".") for word in re.split(r"-", label) if word)


def _brand_shown(brand: frozenset[str], page_name: str, page_title: str | None, url: str) -> bool:
    shown = _words(page_name) | _words(page_title) | _host_words(url)
    return brand <= shown


def _names_this_product(page: frozenset[str], ours: frozenset[str]) -> bool:
    if not page or not ours or not page <= ours:
        return False
    return len(page) / len(ours) >= MIN_SHARE_OF_NAME


def names_match(page_name: str | None, page_title: str | None, url: str, product: Product) -> bool:
    """True when the page's product name names this product (module docstring)."""
    if not page_name:
        return False
    brand = _words(product.brand)
    if not _brand_shown(brand, page_name, page_title, url):
        return False
    page = _significant(page_name, brand)
    return any(_names_this_product(page, _significant(name, brand)) for name in (product.name_en, product.name_fi))
