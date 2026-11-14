"""Does a page found on the web name this product? A page for another product is never evidence (task S2, EV).

Evidence is read by the person who signs for an allergen question, and a sibling product (another fat level,
another variant, another pack) can state other allergens. So a page is kept only when nothing in its product name
speaks against it, and a false match is treated as worse than a missing page. `why_not_this_product` returns the
first reason below that holds, in words for that person, or `None`:

1. The brand is in the page's name, its title or the address's host name.
2. What makes a variant is the same on both sides (the product's English and Finnish names together, against the
   page's product name): every percentage ("15%"), each mark of `MARKS` (lactose-free, low-lactose, fat-free,
   whole milk, UHT, organic) and the flavours the catalog's own reader finds (`tta.catalog.kinds.flavours_of`).
   A lactose mark the page's name leaves out is accepted from the page's own free-from list, and from nowhere else.
3. A pack size the page names is one the product names ("1 l", "1L" and "1000 ml" are the same pack). A page
   that names no pack is the page of the product in all its packs.
4. Against the English or the Finnish name, the page adds no word of its own (the brand, pack sizes and "UHT"
   aside): "Barista" on the page of a plain oat drink, "(INT)" on another recipe, another maker's name.
5. And it carries at least `MIN_SHARE_OF_NAME` of that name's words.

Case, punctuation and the "®" and "™" marks are ignored. Words are compared as written and are not translated:
a Finnish page is matched against the Finnish name. Only the marks of step 2 are read in both languages, and they
only ever drop a page. The word lists are ours, written from the recorded pages (fixtures/evidence/).
"""

from __future__ import annotations

import re
from decimal import Decimal
from urllib.parse import urlsplit

from tta.catalog.kinds import flavour_words, flavours_of
from tta.contracts.product import Product
from tta.evidence import wording

MIN_SHARE_OF_NAME = 0.6
# Words that say nothing about which product it is: the units of a pack size, and "UHT", which is compared as a
# mark instead.
NOISE_WORDS = frozenset({"uht", "l", "ml", "cl", "dl", "kg", "g", "x", "pcs", "kpl"})
# Brand word -> the hosts we take to be the brand owner's own site (AP-4). Our list, not Valio Aimo data, and no
# registry was consulted. Each host is here for the reason beside it; a page on any other host is shown as "a
# web page whose owner was not checked".
BRAND_OWNER_HOSTS: dict[str, tuple[str, ...]] = {
    # elovena.fi: the brand's own name, answered by Context.dev on 14 Nov (tests/evidence/conftest.py).
    # raisiofoodsolutions.fi: recording 469512; Valio Aimo's vendor for the product is Raisio ("RAVINTORAISIO OY").
    "elovena": ("elovena.fi", "raisiofoodsolutions.fi"),
    "oddlygood": ("oddlygood.com",),  # recordings 468465, 473609, 474864: the brand's own name
    "fazer": ("fazer.com",),  # recording 475224: the brand's own name
    # valio.fi: recordings 464401 and 469162. valio.com: the same name, in no recording.
    "valio": ("valio.fi", "valio.com"),
    # arla.fi: recordings 462775 and 463047. arlapro.com: Arla's food-service site; recording 463975 is its page
    # "Arla Pro ruoka 15% ..." for the catalog brand "Arla Pro", and the research behind 463047 and 463975 read the
    # same product on arla.fi and on arlapro.com. arla.com: the same name, in no recording.
    "arla": ("arla.fi", "arla.com", "arlapro.com"),
    "alpro": ("alpro.com",),  # recording 465793: the brand's own name
}
# What makes a variant of a product, read in English and in Finnish: label -> pattern. Each must be said by both
# the product's names and the page's name, or by neither.
MARKS: dict[str, re.Pattern[str]] = {
    "lactose-free": re.compile(r"\blaktoosit[oö]n|\blactose[ -]?free\b", re.IGNORECASE),
    "low-lactose": re.compile(r"\bvähälaktoosi|\blow[ -]?lactose\b", re.IGNORECASE),
    "fat-free": re.compile(r"\brasvat[oö]n|\bfat[ -]?free\b|(?<![\w-])skimmed\b", re.IGNORECASE),
    "whole milk": re.compile(r"\btäysmai|\bwhole milk\b", re.IGNORECASE),
    "UHT": re.compile(r"\buht\b", re.IGNORECASE),
    "organic": re.compile(r"\bluomu|\borganic\b", re.IGNORECASE),
}
# The marks a page may also say in its free-from list instead of its product name.
MARKS_READ_FROM_FREE_FROM = frozenset({"lactose-free", "low-lactose"})
# Arla's line "Maitoa Suomesta" (milk from Finland) and its "Suomi" say the origin the catalog's names give as
# "Suomesta" (recordings 462775 and 463047).
_LINE_WORDS = ((re.compile(r"\bmaitoa suomesta\b"), "suomesta"), (re.compile(r"\bsuomi\b"), "suomesta"))
_NUMBER = r"(?<![\w.,])(\d+(?:[.,]\d+)?)"
_PERCENT = re.compile(_NUMBER + r"\s*%")
_PACK = re.compile(_NUMBER + r"\s*(ml|cl|dl|l|kg|g)\b", re.IGNORECASE)
# A pack size in its base unit: litres or kilograms.
_PACK_UNITS: dict[str, tuple[Decimal, str]] = {
    "ml": (Decimal("0.001"), "l"), "cl": (Decimal("0.01"), "l"), "dl": (Decimal("0.1"), "l"),
    "l": (Decimal(1), "l"), "g": (Decimal("0.001"), "kg"), "kg": (Decimal(1), "kg"),
}
_WORD = re.compile(r"\w+")
_HAS_DIGIT = re.compile(r"\d")
Pack = tuple[Decimal, str]


def _words(text: str | None) -> frozenset[str]:
    return frozenset(_WORD.findall((text or "").casefold().replace("_", " ")))


def _number(text: str) -> Decimal:
    return Decimal(text.replace(",", ".")).normalize()


def _percentages(text: str) -> frozenset[Decimal]:
    return frozenset(_number(match.group(1)) for match in _PERCENT.finditer(text))


def _packs(text: str) -> frozenset[Pack]:
    found = set()
    for match in _PACK.finditer(text):
        factor, unit = _PACK_UNITS[match.group(2).casefold()]
        found.add(((_number(match.group(1)) * factor).normalize(), unit))
    return frozenset(found)


def _significant(text: str | None, brand: frozenset[str]) -> frozenset[str]:
    """The words that say which product it is, with each percentage as one word ("15%")."""
    folded = (text or "").casefold()
    for pattern, word in _LINE_WORDS:
        folded = pattern.sub(word, folded)
    words = frozenset(
        word for word in _words(folded) if word not in NOISE_WORDS and word not in brand and not _HAS_DIGIT.search(word)
    )
    return words | {f"{value:f}%" for value in _percentages(folded)}


def _host_words(url: str) -> frozenset[str]:
    host = urlsplit(url).hostname or ""
    return frozenset(word for label in host.split(".") for word in re.split(r"-", label) if word)


def _brand_shown(brand: frozenset[str], page_name: str, page_title: str | None, url: str) -> bool:
    shown = _words(page_name) | _words(page_title) | _host_words(url)
    return brand <= shown


def _listed(values: frozenset[Decimal]) -> str:
    return " and ".join(f"{value:f}%" for value in sorted(values))


def _percentage_differs(ours: str, page_name: str) -> str | None:
    mine, theirs = _percentages(ours), _percentages(page_name)
    if mine == theirs:
        return None
    if not theirs:
        return wording.PERCENT_NOT_ON_PAGE.format(ours=_listed(mine))
    if not mine:
        return wording.PERCENT_NOT_ON_PRODUCT.format(page=_listed(theirs))
    return wording.PERCENT_DIFFERS.format(page=_listed(theirs), ours=_listed(mine))


def _mark_differs(ours: str, page_name: str, free_from: tuple[str, ...]) -> str | None:
    for label, pattern in MARKS.items():
        mine, theirs = bool(pattern.search(ours)), bool(pattern.search(page_name))
        if mine and not theirs and label in MARKS_READ_FROM_FREE_FROM:
            theirs = any(pattern.search(term) for term in free_from)
        if mine and not theirs:
            return wording.MARK_NOT_ON_PAGE.format(mark=label)
        if theirs and not mine:
            return wording.MARK_NOT_ON_PRODUCT.format(mark=label)
    return None


def _flavour_differs(product: Product, page_name: str) -> str | None:
    mine = flavours_of(product)
    theirs = flavours_of(product.model_copy(update={"name_en": page_name, "name_fi": None}))
    if mine == theirs:
        return None
    return wording.FLAVOUR_DIFFERS.format(
        page=flavour_words(theirs) if theirs else wording.NO_FLAVOUR,
        ours=flavour_words(mine) if mine else wording.NO_FLAVOUR,
    )


def _pack_text(packs: frozenset[Pack]) -> str:
    return " or ".join(f"{size:f} {unit}" for size, unit in sorted(packs, key=lambda pack: (pack[1], pack[0])))


def _pack_differs(ours: str, page_name: str) -> str | None:
    mine, theirs = _packs(ours), _packs(page_name)
    if not mine or not theirs or mine & theirs:
        return None
    return wording.PACK_DIFFERS.format(page=_pack_text(theirs), ours=_pack_text(mine))


def _as_written(words: frozenset[str], page_name: str) -> str:
    """The page's own words, in the page's spelling and order."""
    written = [word for word in _WORD.findall(page_name) if word.casefold() in words]
    return ", ".join(f"“{word}”" for word in dict.fromkeys(written)) or ", ".join(f"“{word}”" for word in sorted(words))


def _words_differ(page: frozenset[str], names: tuple[frozenset[str], ...], page_name: str) -> str | None:
    """Why the page's words name another product than each of the product's names; `None` when one name fits."""
    if not page or not names:
        return wording.NOTHING_TO_COMPARE
    if any(page <= ours and len(page) / len(ours) >= MIN_SHARE_OF_NAME for ours in names):
        return None
    if any(page <= ours for ours in names):
        return wording.TOO_LITTLE_OF_NAME
    fewest_added = min((page - ours for ours in names), key=len)
    return wording.WORDS_ADDED.format(words=_as_written(fewest_added, page_name))


def why_not_this_product(
    page_name: str | None, page_title: str | None, url: str, product: Product, free_from: tuple[str, ...] = ()
) -> str | None:
    """Why the page is not kept as evidence for this product, for the person who signs; `None` when it is kept.
    `free_from` is the page's own free-from list (module docstring, step 2)."""
    if not page_name:
        return wording.NOTHING_TO_COMPARE
    brand = _words(product.brand)
    if not _brand_shown(brand, page_name, page_title, url):
        return wording.BRAND_NOT_SHOWN.format(brand=product.brand)
    ours = " | ".join(name for name in (product.name_en, product.name_fi) if name)
    differs = (
        _percentage_differs(ours, page_name)
        or _mark_differs(ours, page_name, free_from)
        or _flavour_differs(product, page_name)
        or _pack_differs(ours, page_name)
    )
    if differs:
        return differs
    names = tuple(_significant(name, brand) for name in (product.name_en, product.name_fi) if name)
    return _words_differ(_significant(page_name, brand), tuple(name for name in names if name), page_name)


def names_match(
    page_name: str | None, page_title: str | None, url: str, product: Product, free_from: tuple[str, ...] = ()
) -> bool:
    """True when the page's product name names this product (module docstring)."""
    return why_not_this_product(page_name, page_title, url, product, free_from) is None


def is_brand_owner_page(url: str, product: Product) -> bool:
    """True when the page's host is one listed for a word of the product's brand, or a subdomain of it."""
    host = (urlsplit(url).hostname or "").casefold()
    listed = (domain for word in _words(product.brand) for domain in BRAND_OWNER_HOSTS.get(word, ()))
    return any(host == domain or host.endswith(f".{domain}") for domain in listed)
