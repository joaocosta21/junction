"""What kind of product one is, read from the product file: its product types, its flavour, the use its name
says, and whether it is a drink. A substitute is judged on these (`tta.offers.substitutes`).

**Every word list and threshold here is ours, not Valio's.** The product file has no field for a flavour or
a use, so both are read from the English and the Finnish name. English words are matched whole; Finnish words
are matched at the start of a word, because Finnish joins words ("mansikkajogurtti"). The lists were run over
the whole catalog (17,546 products, 14 Nov 2026); `tests/catalog/test_kinds.py` recounts the figures.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from decimal import Decimal
from functools import lru_cache

from tta.catalog.product_types import ProductType, load_product_types
from tta.catalog.text import names_of, normalise
from tta.contracts.product import Product

# --- Product types -------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _table() -> Mapping[str, ProductType]:
    return load_product_types()


def product_types_of(product: Product, table: Mapping[str, ProductType] | None = None) -> tuple[str, ...]:
    """The keys of `product_types.yaml` the product is of, sorted; empty when the table does not cover it.

    The same four conditions as the search (`tta.catalog.search`): category, name terms, exclude terms, claims.
    """
    names = names_of(product)
    found = []
    for key, entry in (table if table is not None else _table()).items():
        if product.category not in entry.categories:
            continue
        if not frozenset(entry.claims).issubset(product.nutritional_claims):
            continue
        if entry.name_terms and not names.has_any(tuple(normalise(term) for term in entry.name_terms)):
            continue
        if names.has_any(tuple(normalise(term) for term in entry.exclude_terms)):
            continue
        found.append(key)
    return tuple(sorted(found))


def is_same_type(original: tuple[str, ...], other: tuple[str, ...]) -> bool:
    """`other` is of every type the original is of. A chuck steak stands in for beef; beef does not stand in
    for a chuck steak (`beef_chuck` is inside `beef`)."""
    return frozenset(original).issubset(other)


def _listed(words: tuple[str, ...]) -> str:
    """ "a", "a and b", "a, b and c"."""
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}" if words else ""


def type_words(keys: tuple[str, ...]) -> str:
    """Product-type keys as words for a sentence: `coffee_milk` reads "coffee milk"."""
    return _listed(tuple(key.replace("_", " ") for key in keys))


# --- Flavour -------------------------------------------------------------------------------------------

# flavour: (whole English words, starts of Finnish words). A product carries the flavour when either matches
# its English or its Finnish name.
_FLAVOURS: Mapping[str, tuple[str, str]] = {
    "vanilla": (r"vanilla|vanille", r"vanilj"),
    "chocolate": (r"chocolate|choco|cocoa|cacao", r"suklaa|kaakao"),
    "caramel": (r"caramel|toffee|fudge|butterscotch", r"karamelli|kinuski"),
    # Not "espresso" or "latte": in this catalog they name coffee itself, or a mozzarella ("fior di latte").
    "coffee": (r"mocha|mocca|cappuccino|coffee flavou?r(?:ed)?", r"mokka|kahvinmaku"),
    "strawberry": (r"strawberr(?:y|ies)", r"mansik"),
    "raspberry": (r"raspberr(?:y|ies)", r"vadelm"),
    "blueberry": (r"blueberr(?:y|ies)|bilberr(?:y|ies)", r"mustik"),
    "lingonberry": (r"lingonberr(?:y|ies)", r"puoluk"),
    "cranberry": (r"cranberr(?:y|ies)", r"karpalo"),
    "cloudberry": (r"cloudberr(?:y|ies)", r"lakka\b|hilla\b"),
    "currant": (r"(?:black|red)?currants?", r"(?:musta|puna)?heruk"),
    "cherry": (r"cherr(?:y|ies)", r"kirsik"),
    "apple": (r"apples?", r"omena"),
    "pear": (r"pears?", r"päärynä"),
    "banana": (r"bananas?", r"banaani"),
    "orange": (r"oranges?", r"appelsiini"),
    "mandarin": (r"mandarins?|tangerines?|clementines?", r"mandariini|klementiini"),
    "lemon": (r"lemons?|citron", r"sitruuna"),
    "lime": (r"limes?", r"limetti"),
    "mango": (r"mango(?:e?s)?", r"mango"),
    "pineapple": (r"pineapples?", r"ananas"),
    "peach": (r"peach(?:es)?", r"persik"),
    "nectarine": (r"nectarines?", r"nektariini"),
    "apricot": (r"apricots?", r"aprikoosi"),
    "passion fruit": (r"passion ?fruits?|passion", r"passion"),
    "melon": (r"(?:water)?melons?", r"(?:vesi)?meloni"),
    "grapefruit": (r"grapefruits?", r"greippi"),
    "grape": (r"grapes?", r"rypäle"),
    "rhubarb": (r"rhubarb", r"raparperi"),
    "plum": (r"plums?", r"luumu"),
    "pomegranate": (r"pomegranates?", r"granaattiomena"),
    "coconut": (r"coconuts?", r"kookos"),
    "sea buckthorn": (r"sea ?buckthorn", r"tyrni"),
    "hazelnut": (r"hazelnuts?", r"hasselpähkinä"),
    "almond": (r"almonds?", r"manteli"),
    "pistachio": (r"pistachios?", r"pistaasi"),
    "walnut": (r"walnuts?", r"saksanpähkinä"),
    "peanut": (r"peanuts?", r"maapähkinä"),
    "cashew": (r"cashews?", r"cashew"),
    "pecan": (r"pecans?", r"pekaani"),
    "gingerbread": (r"gingerbread", r"piparkakku"),
    "pumpkin spice": (r"pumpkin spice", r"pumpkin spice"),
    "cinnamon": (r"cinnamon", r"kaneli"),
    "cardamom": (r"cardamom", r"kardemumma"),
    "mint": (r"mint|peppermint|spearmint", r"minttu|mintun|piparmint"),
    "liquorice": (r"liquorice|licorice", r"lakrits|salmiak"),
}
_SPICES = frozenset({"gingerbread", "pumpkin spice", "cinnamon", "cardamom", "mint", "liquorice"})
# Words that say a flavour without naming one. Each is dropped when a named flavour of its group is found.
_GENERAL: Mapping[str, tuple[str, str]] = {
    "berry": (r"berr(?:y|ies)|berry ?mix", r"marja"),
    "fruit": (r"fruits?|fruity|tropical", r"hedelm"),
    "nut": (r"nuts?|nutty", r"pähkinä"),
}
_BERRIES = frozenset({"strawberry", "raspberry", "blueberry", "lingonberry", "cranberry", "cloudberry", "currant"})
_NUTS = frozenset({"hazelnut", "almond", "pistachio", "walnut", "peanut", "cashew", "pecan", "coconut"})
_GROUP_OF: Mapping[str, frozenset[str]] = {
    "berry": _BERRIES,
    "nut": _NUTS,
    "fruit": frozenset(_FLAVOURS) - _NUTS - _SPICES - {"vanilla", "chocolate", "caramel", "coffee"},
}
# "flavoured" and "maustettu" (flavoured, seasoned) with no flavour named. "unflavoured" and "maustamaton"
# (plain) do not match: neither holds the word at a word start.
FLAVOURED = "flavoured"
_FLAVOURED = (r"flavou?red", r"maustettu")
# Words that hold a flavour word and are no flavour: a cherry tomato, a plum tomato, an orange capsicum or
# carrot (a colour), lemongrass, fructose ("hedelmäsokeri", fruit sugar), "nut free". They are taken out
# before the reading.
_NOT_A_FLAVOUR = re.compile(
    r"(?:cherry|plum|kirsikka|luumu)[ -]?toma\w*|capsicum orange|orange (?:capsicum|paprika|pepper|carrot)s?"
    r"|toma\w* (?:luumu|kirsikka|plum|cherry)|oranssi\w*|lemon ?grass|sitruunaruoho\w*|hedelmäsokeri\w*"
    r"|nut[ -]?free|pähkinät[öo]n\w*",
    re.IGNORECASE,
)
# The name says the product is coffee: "mokka" is then a roast or a brand (Juhla Mokka), not a flavour.
_IS_COFFEE = re.compile(r"\bcoffee\b(?! flavou?r)|kahvi(?!nmaku)", re.IGNORECASE)


def _pattern(words: tuple[str, str]) -> re.Pattern[str]:
    english, finnish = words
    return re.compile(rf"\b(?:{english})\b|\b(?:{finnish})", re.IGNORECASE)


_FLAVOUR_PATTERNS = {flavour: _pattern(words) for flavour, words in _FLAVOURS.items()}
_GENERAL_PATTERNS = {flavour: _pattern(words) for flavour, words in _GENERAL.items()}
_FLAVOURED_PATTERN = _pattern(_FLAVOURED)


def flavours_of(product: Product) -> tuple[str, ...]:
    """The flavours the product's names say, sorted; empty for a product whose names say none.

    The names are data and are only searched. A general word ("berry", "nut", "flavoured") is kept only when
    no flavour of its group is named, so "nutty vanilla" reads nut and vanilla, and "strawberry" not also berry.
    """
    text = _NOT_A_FLAVOUR.sub(" ", f"{product.name_en or ''} | {product.name_fi or ''}")
    named = {flavour for flavour, pattern in _FLAVOUR_PATTERNS.items() if pattern.search(text)}
    if _IS_COFFEE.search(text):
        named.discard("coffee")
    general = {
        flavour for flavour, pattern in _GENERAL_PATTERNS.items()
        if pattern.search(text) and not named & _GROUP_OF[flavour]
    }
    found = named | general
    if not found and _FLAVOURED_PATTERN.search(text):
        return (FLAVOURED,)
    return tuple(sorted(found))


def flavour_words(flavours: tuple[str, ...]) -> str:
    """Flavours as words for a sentence: "nut and vanilla"."""
    return _listed(flavours)


# --- Use -----------------------------------------------------------------------------------------------

# use: (whole English words, starts of Finnish words), read from the names like a flavour. "coffee" is a
# product made to go into coffee (a barista drink, a coffee milk, a coffee cream), not one that tastes of it.
_USES: Mapping[str, tuple[str, str]] = {
    "coffee": (
        r"barista|for coffee(?! machine)|coffee (?:milk|cream|creamer|whitener)|caf[eèé] (?:milk|cream)|ikaffe",
        r"barista|kahviin|kahvimaito|kahvikerma|caf[eèé] maito",
    ),
    "whipping": (r"whipping|whipped|whip|visp", r"vispi|kuohu"),
    "cooking": (r"cooking|cuisine|imat", r"ruokakerma|ruoka\b|ruoanvalmistu"),
}
_USE_PATTERNS = {use: _pattern(words) for use, words in _USES.items()}
_USE_WORDS = {"coffee": "made for coffee", "whipping": "made for whipping", "cooking": "made for cooking"}


def uses_of(product: Product) -> tuple[str, ...]:
    """The uses the product's names say (coffee, whipping, cooking), sorted; empty when they say none."""
    text = f"{product.name_en or ''} | {product.name_fi or ''}"
    return tuple(sorted(use for use, pattern in _USE_PATTERNS.items() if pattern.search(text)))


def use_words(uses: tuple[str, ...]) -> str:
    """Uses as words for a sentence: "made for coffee"."""
    return _listed(tuple(_USE_WORDS[use] for use in uses))


def is_other_use(original: tuple[str, ...], other: tuple[str, ...]) -> bool:
    """`other` lacks a use the original's name says, or names one where the original names none. A product
    made for cooking and for whipping stands in for one made for whipping."""
    return not frozenset(original).issubset(other) or (bool(other) and not original)


# --- Drink ---------------------------------------------------------------------------------------------

# The product types that are drinks or pour like one. Ours.
DRINK_TYPES = frozenset(
    {"milk", "coffee_milk", "sour_milk", "cream", "vegetable_cream", "plant_drink", "juice", "soft_drink",
     "mineral_water"}
)
# Ours. A product whose file states a volume and a net weight for the base unit is read as a drink when one
# litre weighs between these: milk is 1.03 kg, cream 0.99. Oil (0.92) and a juice concentrate (1.2 and more)
# are outside, and for them a figure per 100 g is not a figure per 100 ml.
DRINK_MIN_KG_PER_L = Decimal("0.97")
DRINK_MAX_KG_PER_L = Decimal("1.06")


def kg_per_litre(product: Product) -> Decimal | None:
    """Net weight over volume of the first packaging level that states both; `None` when none does."""
    for level in product.unit_conversions:
        if level.volume_l and level.net_weight_kg:
            return level.net_weight_kg / level.volume_l
    return None


def drink_evidence(product: Product) -> str | None:
    """Why the product is read as a drink, as words for a sentence; `None` when it is not read as one.

    The stated weight of a litre decides when the file has it; else the product type does. Nothing else
    makes a drink: a sales unit of the file is a piece or a case, never a litre.
    """
    density = kg_per_litre(product)
    if density is not None:
        if DRINK_MIN_KG_PER_L <= density <= DRINK_MAX_KG_PER_L:
            return "one litre weighs about a kilogram in the product data"
        return None
    drink_types = [key for key in product_types_of(product) if key in DRINK_TYPES]
    if drink_types:
        return f"product type {type_words(tuple(drink_types))}"
    return None


def is_drink(product: Product) -> bool:
    return drink_evidence(product) is not None
