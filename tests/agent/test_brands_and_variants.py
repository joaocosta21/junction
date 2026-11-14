"""A brand in a request is kept, and a use narrows the product type (decisions B39 and B40; lane L1-3).

Scores on the 20% "how precisely the agent matches what the buyer actually asked for": "Arla lactose-free whipping
cream" used to come back as any brand's, and "cream for whipping" as plain cream, whose first pick may be a
cooking cream. No model is called: the reader is the fixed rules, the brands are read from the product file.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tta.agent import build_request_parser
from tta.agent.brands import MIN_BRAND_LETTERS, NO_BRANDS, Brands
from tta.agent.parser import ModelRequestParser
from tta.agent.rules_model import RuleModel
from tta.agent.unread import NotReadByRules
from tta.agent.variants import variant_for
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import Identity
from tta.contracts.ports import Clock
from tta.contracts.request import ProductQuery, RequestLine

READ_BY_RULES = "Read by fixed rules, not by a model."
ARLA_CREAM = "24 litres of Arla lactose-free whipping cream by Wednesday"


@pytest.fixture
def rules(
    product_type_keys: tuple[str, ...], demo_clock: Clock, brands: Brands
) -> ModelRequestParser:
    return ModelRequestParser(
        model=RuleModel.for_keys(product_type_keys, brands), clock=demo_clock, product_type_keys=product_type_keys,
        profile_strictness=lambda _profile: None, brands=brands,
    )


def _line(parser: Any, text: str, identity: Identity) -> tuple[RequestLine, str]:
    reading = parser.read(text, identity)
    assert len(reading.request.lines) == 1
    return reading.request.lines[0], reading.sentence.removeprefix(READ_BY_RULES).strip()


# --- the brand list ---------------------------------------------------------------------------------------


def test_the_list_holds_the_brands_a_kitchen_names_by_the_catalogs_spelling(brands: Brands) -> None:
    named = {"arla": "Arla", "arla pro": "Arla Pro", "valio": "Valio", "oatly": "Oatly", "alpro": "Alpro",
             "oddlygood": "Oddlygood®", "fazer": "Fazer", "elovena": "Elovena"}

    assert {words: brands.spelling.get(tuple(words.split())) for words in named} == named
    assert len(brands) == 531  # of the 1,466 brands of the product file (17,546 products); 172 are two words


@pytest.mark.parametrize(
    "words",
    [
        "fresh", "classic", "pizza", "royal", "pro", "super",  # everyday words of other brands' product names
        "true", "always", "look",  # everyday words of a request
        "rama professional", "nordic sugar",  # words the reader already reads as a product type
        "hk", "rf",  # under three letters
        "valio eila",  # a product line in the names, not a brand of the catalog: "Valio" is the brand
    ],
)
def test_a_brand_that_is_an_everyday_word_or_a_word_the_reader_reads_is_not_in_the_list(
    brands: Brands, words: str
) -> None:
    assert tuple(words.split()) not in brands.spelling


def test_every_brand_is_one_or_two_whole_words_of_letters(brands: Brands) -> None:
    assert all(1 <= len(phrase) <= 2 and all(word.isalpha() for word in phrase) for phrase in brands.spelling)
    assert all(len("".join(phrase)) >= MIN_BRAND_LETTERS for phrase in brands.spelling)


def test_a_brand_is_found_as_whole_words_and_the_longer_brand_wins(brands: Brands) -> None:
    assert brands.found(("arla", "pro", "whipping", "cream")) == {0: "Arla Pro", 1: "Arla Pro"}
    assert brands.found(("arla", "whipping", "cream")) == {0: "Arla"}
    assert brands.found(("arlas", "valiolainen", "cream")) == {}
    assert brands.found(("arla", "cream"), skipping={0}) == {}


def test_a_brand_term_returns_that_brands_products_and_no_other_brands(catalog: ProductCatalog) -> None:
    """The typed request has no brand field: the brand is a name term. Measured on the product file."""
    lactose_free_cream = {"product_type": "cream", "required_claims": ("FREE_FROM_LACTOSE",)}

    any_brand = catalog.search(ProductQuery(**lactose_free_cream, name_terms=("whipping",)))
    arla = catalog.search(ProductQuery(**lactose_free_cream, name_terms=("Arla", "whipping")))
    all_arla = catalog.search(ProductQuery(**lactose_free_cream, name_terms=("Arla",)))

    assert (any_brand.total, arla.total, all_arla.total) == (12, 3, 9)
    assert sorted(product.brand or "" for product in arla.products) == ["Arla", "Arla", "Arla Pro"]
    assert {product.brand for product in all_arla.products} == {"Arla", "Arla Pro", "Arla Lempi"}
    assert all(product.name_en.startswith(("Arla", "14 x Arla")) for product in arla.products)


# --- B39: a brand in the request --------------------------------------------------------------------------


def test_the_one_sentence_that_was_read_wrong_keeps_its_brand(rules: ModelRequestParser, agent_hotel: Identity) -> None:
    line, says = _line(rules, ARLA_CREAM, agent_hotel)

    assert (line.product_type, line.name_terms, line.required_claims) == (
        "cream", ("Arla", "whipping"), ("FREE_FROM_LACTOSE",)
    )
    assert says == 'The brand "Arla" is required.'


@pytest.mark.parametrize(
    ("text", "product_type", "terms", "brand"),
    [
        ("24 litres of Arla Pro whipping cream", "cream", ("Arla Pro", "whipping"), "Arla Pro"),
        ("24 litres of ARLA cream", "cream", ("Arla",), "Arla"),
        ("24 litres of cream from Arla by Monday", "cream", ("Arla",), "Arla"),
        ("24 litres of whipping Arla cream", "cream", ("Arla", "whipping"), "Arla"),
        ("100 litres of Oatly oat drink by Monday", "plant_drink", ("Oatly", "oat"), "Oatly"),
        ("100 litres of Oddlygood oat drink", "plant_drink", ("Oddlygood®", "oat"), "Oddlygood®"),
        ("100 litres of Valio Eila milk", "milk", ("Valio", "eila"), "Valio"),
        ("10 kg of Fazer bread", "bread", ("Fazer",), "Fazer"),
    ],
)
def test_a_brand_of_the_catalog_is_a_term_the_product_must_carry_and_the_sentence_says_so(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, product_type: str, terms: tuple[str, ...], brand: str
) -> None:
    line, says = _line(rules, text, agent_hotel)

    assert (line.product_type, line.name_terms) == (product_type, terms)
    assert says == f'The brand "{brand}" is required.'


def test_each_line_keeps_its_own_brand(rules: ModelRequestParser, agent_hotel: Identity) -> None:
    reading = rules.read("20 litres of Arla cream and 100 litres of Valio milk by Monday", agent_hotel)

    assert [line.name_terms for line in reading.request.lines] == [("Arla",), ("Valio",)]
    assert reading.sentence == f'{READ_BY_RULES} The brands "Arla" and "Valio" are required.'


@pytest.mark.parametrize(
    ("text", "terms"),
    [
        ("200 litres of fresh milk by Monday", ("fresh",)),  # the one word before the type, as before
        ("200 litres of lovely fresh milk", ("fresh",)),  # any other unknown word: left as it was, not asked about
        ("200 litres of milk by Monday", ()),
        ("20 kg of royal cheese", ("royal",)),
    ],
)
def test_a_word_that_is_no_brand_of_the_list_is_read_as_before(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, terms: tuple[str, ...]
) -> None:
    line, says = _line(rules, text, agent_hotel)

    assert line.name_terms == terms and says == ""


def test_a_line_that_names_its_product_by_number_gets_no_brand_term(
    rules: ModelRequestParser, agent_hotel: Identity
) -> None:
    line, says = _line(rules, "100 litres of Oddlygood Barista oat drink, product 473609, by Monday", agent_hotel)

    assert (line.product_ids, line.name_terms, says) == (("473609",), (), "")


def test_without_the_brand_list_the_brand_word_is_read_as_any_other_word(
    make_parser: Callable[..., ModelRequestParser], product_type_keys: tuple[str, ...], demo_clock: Clock,
    agent_hotel: Identity,
) -> None:
    line, says = _line(make_parser(RuleModel.for_keys(product_type_keys, NO_BRANDS), demo_clock), ARLA_CREAM,
                       agent_hotel)

    assert (line.name_terms, says) == (("whipping",), "")


def test_the_gateways_own_parser_reads_the_brand(
    settings: Settings, demo_clock: Clock, product_type_keys: tuple[str, ...], agent_hotel: Identity
) -> None:
    parser = build_request_parser(settings=settings, clock=demo_clock, product_type_keys=product_type_keys)

    reading = parser.read(ARLA_CREAM, agent_hotel)

    assert reading.request.lines[0].name_terms == ("Arla", "whipping")
    assert reading.sentence.endswith('The brand "Arla" is required.')


# --- B40: the use narrows the type ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "terms", "keep_formula", "says"),
    [
        ("20 litres of cream for whipping", ("whipping",), True,
         'Cream "for whipping" is read as whipping cream. Formula matters: the request says "for whipping".'),
        ("20 litres of cream by Monday, for whipping", ("whipping",), True,
         'Cream "for whipping" is read as whipping cream. Formula matters: the request says "for whipping".'),
        ("20 litres of cream to whip", ("whipping",), True,
         'Cream "to whip" is read as whipping cream. Formula matters: the request says "to whip".'),
        ("20 litres of lactose-free cream for whipping", ("whipping",), True,
         'Cream "for whipping" is read as whipping cream. Formula matters: the request says "for whipping".'),
        ("20 litres of Arla cream for whipping", ("Arla", "whipping"), True,
         'The brand "Arla" is required. Cream "for whipping" is read as whipping cream. Formula matters: the '
         'request says "for whipping".'),
        ("20 litres of cream for cooking", ("cooking",), None, 'Cream "for cooking" is read as cooking cream.'),
        ("20 litres of whipping cream", ("whipping",), None, ""),  # the product's own name, as before
        ("20 litres of whipping cream for cooking", ("whipping",), None, ""),  # the name already says the variant
        ("20 litres of cream for whipping and for cooking", (), True,
         'Formula matters: the request says "for whipping".'),  # two variants: none is chosen
        ("20 litres of cream not for whipping", (), None, ""),
        ("20 litres of cream for the sauce", (), True, 'Formula matters: the request says "for the sauce".'),
        ("10 kg of butter for baking", (), True, 'Formula matters: the request says "for baking".'),
        ("10 kg of butter for cooking", (), None, ""),  # no variant of butter is known
        ("100 litres of milk for whipping", (), True, 'Formula matters: the request says "for whipping".'),
    ],
)
def test_a_use_that_names_a_variant_of_the_type_is_read_as_that_variant(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, terms: tuple[str, ...], keep_formula: bool | None,
    says: str,
) -> None:
    line, said = _line(rules, text, agent_hotel)

    assert (line.name_terms, line.keep_formula, said) == (terms, keep_formula, says)


def test_the_use_narrows_only_the_line_it_is_said_on(rules: ModelRequestParser, agent_hotel: Identity) -> None:
    reading = rules.read("20 litres of cream for whipping and 10 litres of cream by Monday", agent_hotel)

    assert [(line.name_terms, line.keep_formula) for line in reading.request.lines] == [(("whipping",), True),
                                                                                         ((), None)]


def test_cream_for_whipping_finds_whipping_creams_only(catalog: ProductCatalog) -> None:
    """Measured on the product file: the 42 creams, 15 with "whipping" in the name, 17 with "cooking"."""
    cream = catalog.search(ProductQuery(product_type="cream"))
    whipping = catalog.search(ProductQuery(product_type="cream", name_terms=("whipping",)))
    cooking = catalog.search(ProductQuery(product_type="cream", name_terms=("cooking",)))

    assert (cream.total, whipping.total, cooking.total) == (42, 15, 17)
    assert all("whipping" in product.name_en.casefold() for product in whipping.products)
    assert all("cooking" in product.name_en.casefold() for product in cooking.products)


def test_a_variant_is_known_for_cream_only() -> None:
    assert variant_for("cream", "20 litres of cream for whipping") is not None
    assert variant_for("butter", "10 kg of butter for whipping") is None
    assert variant_for(None, "20 litres for whipping") is None


# --- a place or a recipient is not a use ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "keep_formula"),
    [
        ("10 litres of cream to the dessert kitchen", None),
        ("10 litres of cream for the dessert kitchen", None),
        ("10 litres of cream for the pastry chef", None),
        ("10 litres of cream for desserts", True),
        ("10 litres of cream for a dessert", True),
        ("10 litres of cream for the dessert recipe", True),
        ("10 litres of cream to make desserts", True),
    ],
)
def test_where_the_goods_go_is_not_what_they_are_for(
    rules: ModelRequestParser, agent_hotel: Identity, text: str, keep_formula: bool | None
) -> None:
    line, says = _line(rules, text, agent_hotel)

    assert line.keep_formula is keep_formula and line.name_terms == ()
    assert says.startswith("Formula matters") is bool(keep_formula)


def test_a_place_said_in_a_part_of_its_own_is_asked_about(rules: ModelRequestParser, agent_hotel: Identity) -> None:
    """Nothing is half-read (review finding S3): the request has no field for where in the house the goods go."""
    with pytest.raises(NotReadByRules) as asked:
        rules.read("10 litres of cream by Monday, to the dessert kitchen", agent_hotel)

    assert asked.value.why == 'it also says "dessert kitchen", which the rules did not read'
