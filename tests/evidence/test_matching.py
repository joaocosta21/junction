"""A page counts as evidence only when it names this product: the brand, and no word of its own that the product's
English or Finnish name does not carry (pack sizes aside)."""

from __future__ import annotations

import pytest

from tta.catalog import ProductCatalog
from tta.evidence.matching import BRAND_OWNER_HOSTS, is_brand_owner_page, names_match, why_not_this_product

FAZER_PROFESSIONAL = "475224"
ODDLYGOOD_BARISTA = "473609"


@pytest.mark.parametrize(
    ("product_id", "page_name", "url"),
    [
        ("469512", "Elovena Kaurajuoma kahviin", "https://elovena.fi/tuotteet/elovena-kaurajuoma-kahviin/"),
        ("468465", "Oddlygood® kaurajuoma 1 l UHT gluteeniton", "https://www.oddlygood.com/fi/tuotteet/x/"),
        (ODDLYGOOD_BARISTA, "Oddlygood® Barista oat drink 1 l UHT gluten free", "https://www.oddlygood.com/uk/x/"),
        (FAZER_PROFESSIONAL, "Fazer Aito Professional Barista Oat Drink 1L UHT", "https://www.fazer.com/en/x/"),
        (FAZER_PROFESSIONAL, "Fazer Aito Professional Barista Kaurajuoma 1L UHT", "https://www.fazer.fi/x/"),
        # The brand is in the address, not in the page's name.
        ("469512", "Oat drink barista", "https://elovena.nl/producten/oat-drink-barista/"),
    ],
)
def test_a_page_that_names_the_product_matches(
    catalog: ProductCatalog, product_id: str, page_name: str, url: str
) -> None:
    assert names_match(page_name, None, url, catalog.get_product(product_id))


@pytest.mark.parametrize(
    ("product_id", "page_name", "url"),
    [
        # Asked for the plain oat drink, the answer was the Barista drink: a word the product does not carry.
        ("468465", "Oddlygood® Barista oat drink 1 l UHT gluten free", "https://www.oddlygood.com/uk/x/"),
        # The international recipe of another Fazer barista drink.
        (FAZER_PROFESSIONAL, "Fazer Aito Oat Drink Barista 1L UHT (INT)", "https://www.fazeraito.com/x/"),
        # Too little of the product's name.
        (ODDLYGOOD_BARISTA, "Oddlygood® oat", "https://www.oddlygood.com/x/"),
        # Another brand.
        ("469512", "Oatly Kaurajuoma kahviin", "https://www.oatly.com/x/"),
        # Nothing to compare.
        ("469512", "", "https://elovena.fi/x/"),
        ("469512", "® 1 l", "https://elovena.fi/x/"),
    ],
)
def test_a_page_for_another_product_does_not_match(
    catalog: ProductCatalog, product_id: str, page_name: str, url: str
) -> None:
    assert not names_match(page_name, None, url, catalog.get_product(product_id))


def test_the_page_title_can_carry_the_brand(catalog: ProductCatalog) -> None:
    product = catalog.get_product("469512")

    assert names_match("Kaurajuoma kahviin", "Elovena Kaurajuoma kahviin", "https://example.org/x", product)
    assert not names_match("Kaurajuoma kahviin", "Kaurajuoma kahviin", "https://example.org/x", product)


# --- near misses: a sibling is never evidence (EV) ---------------------------------------------------------------

ARLA_PRO_RUOKA_15 = "463975"  # Arla Pro Ruoka 1 L 15% laktoositon kasvirasvasekoite Uht
ARLA_LOW_LACTOSE_WHOLE = "463047"  # Arla Täysmaito 1 L Suomesta vähälaktoosinen Uht
ARLA_LACTOSE_FREE_FAT_FREE = "462775"  # Arla Maitojuoma 1L laktoositon rasvaton UHT Suomesta
VALIO_RUOKA_15 = "469162"  # Valio Ruoka 15 % 1 l laktoositon
VALIO_EILA_FAT_FREE = "464401"  # Valio Hyvä suomalainen Arki® Eila® rasvaton maitojuoma 1 l laktoositon
ODDLYGOOD_OAT = "468465"  # Oddlygood® kaurajuoma 1 l UHT gluteeniton
ODDLYGOOD_BARISTA_VANILLA = "472303"  # Oddlygood® Barista kaurajuoma 1 l vanilja UHT gluteeniton
AIMO_NATURAL_YOGURT = "464517"  # AIMO NATURAL YOGURT 5KG 2% LACTOSE FREE, no brand in the catalog
ARLA_FI, ARLAPRO = "https://www.arla.fi/x/", "https://www.arlapro.com/fi/x/"
VALIO_FI, ODDLYGOOD = "https://www.valio.fi/x/", "https://www.oddlygood.com/fi/x/"


@pytest.mark.parametrize(
    ("product_id", "page_name", "url", "why"),
    [
        # Same brand and line, another fat percentage.
        (ARLA_PRO_RUOKA_15, "Arla Pro ruoka 7% 1L laktoositon (UHT)", ARLAPRO,
         "the page is for the 7% product; the product asked for is 15%"),
        (VALIO_RUOKA_15, "Valio Ruoka 4% laktoositon", VALIO_FI,
         "the page is for the 4% product; the product asked for is 15%"),
        (VALIO_RUOKA_15, "Valio Ruoka laktoositon", VALIO_FI,
         "the product asked for is 15%; the page's product name states no percentage"),
        (VALIO_EILA_FAT_FREE, "Valio Hyvä suomalainen Arki® Eila® maitojuoma 1,5% laktoositon", VALIO_FI,
         "the page is for a 1.5% product; the product asked for states no percentage"),
        # Lactose-free against low-lactose, both ways, and against a page that says neither.
        (ARLA_LOW_LACTOSE_WHOLE, "Arla Maitoa Suomesta Laktoositon täysmaito (UHT) 1 l", ARLA_FI,
         "the page says lactose-free; the product asked for does not say lactose-free"),
        (ARLA_LACTOSE_FREE_FAT_FREE, "Arla Maitoa Suomesta Vähälaktoosinen rasvaton maitojuoma UHT Suomi 1 l", ARLA_FI,
         "the product asked for is lactose-free; the page does not say lactose-free"),
        (ARLA_LOW_LACTOSE_WHOLE, "Arla Maitoa Suomesta täysmaito (UHT) 1 l", ARLA_FI,
         "the product asked for is low-lactose; the page does not say low-lactose"),
        # Fat-free against a page that does not say so, and whole milk against fat-free.
        (VALIO_EILA_FAT_FREE, "Valio Hyvä suomalainen Arki® Eila® maitojuoma laktoositon", VALIO_FI,
         "the product asked for is fat-free; the page does not say fat-free"),
        (ARLA_LOW_LACTOSE_WHOLE, "Arla Maitoa Suomesta Vähälaktoosinen rasvaton maito (UHT) 1 l", ARLA_FI,
         "the page says fat-free; the product asked for does not say fat-free"),
        # UHT against a page that does not say UHT, and the reverse: the chilled and the long-life product.
        (ARLA_LOW_LACTOSE_WHOLE, "Arla Maitoa Suomesta Vähälaktoosinen täysmaito 1 l", ARLA_FI,
         "the product asked for is UHT; the page does not say UHT"),
        (VALIO_EILA_FAT_FREE, "Valio Hyvä suomalainen Arki® Eila® rasvaton maitojuoma UHT laktoositon", VALIO_FI,
         "the page says UHT; the product asked for does not say UHT"),
        # Organic against the usual product.
        (VALIO_EILA_FAT_FREE, "Valio Luomu™ Eila® rasvaton maitojuoma laktoositon", VALIO_FI,
         "the page says organic; the product asked for does not say organic"),
        # Another pack, where the page names one.
        (VALIO_RUOKA_15, "Valio Ruoka 15% 10 l laktoositon", VALIO_FI,
         "the page is for the 10 l pack; the product asked for is 1 l"),
        (ARLA_PRO_RUOKA_15, "Arla Pro ruoka 15% 5 kg laktoositon (UHT)", ARLAPRO,
         "the page is for the 5 kg pack; the product asked for is 1 l"),
        # Flavoured against plain, both ways.
        (ODDLYGOOD_OAT, "Oddlygood® kaurajuoma vanilja 1 l UHT gluteeniton", ODDLYGOOD,
         "the page's product name says vanilla; the product asked for says no flavour"),
        (ODDLYGOOD_BARISTA_VANILLA, "Oddlygood® Barista kaurajuoma 1 l UHT gluteeniton", ODDLYGOOD,
         "the page's product name says no flavour; the product asked for says vanilla"),
        # Another maker's or another line's name.
        (AIMO_NATURAL_YOGURT, "Valio A+™ natural yogurt 2% lactose free 5 kg", "https://www.valioaimo.fi/x/",
         "the page's product name says “Valio”, “A”, which the product asked for does not"),
        # Another brand, too little of the name, nothing to compare.
        ("469512", "Oatly Kaurajuoma kahviin", "https://www.oatly.com/x/",
         "the page does not show the brand “Elovena”"),
        (ODDLYGOOD_BARISTA, "Oddlygood® oat UHT", ODDLYGOOD,
         "the page's product name carries too little of the name of the product asked for"),
        ("469512", "® 1 l", "https://elovena.fi/x/", "the page's product name names no product"),
    ],
)
def test_a_sibling_is_dropped_and_the_reason_says_what_did_not_match(
    catalog: ProductCatalog, product_id: str, page_name: str, url: str, why: str
) -> None:
    assert why_not_this_product(page_name, None, url, catalog.get_product(product_id)) == why


@pytest.mark.parametrize(
    ("product_id", "page_name", "url"),
    [
        # The pack written another way is the same pack.
        (ARLA_PRO_RUOKA_15, "Arla Pro ruoka 15 % 1 l laktoositon UHT", ARLAPRO),
        (ARLA_PRO_RUOKA_15, "Arla Pro ruoka 15% 1000 ml laktoositon (UHT)", ARLAPRO),
        (VALIO_RUOKA_15, "Valio Ruoka 15 % 1L laktoositon", VALIO_FI),
        # "™" and "®", case and punctuation say nothing.
        (VALIO_EILA_FAT_FREE, "VALIO hyvä suomalainen Arki Eila, rasvaton maitojuoma - laktoositon", VALIO_FI),
        # Arla's line "Maitoa Suomesta" and "Suomi" are the catalog's "Suomesta".
        (ARLA_LOW_LACTOSE_WHOLE, "Arla Maitoa Suomesta Vähälaktoosinen täysmaito (UHT) 1 l", ARLA_FI),
        (ARLA_LACTOSE_FREE_FAT_FREE, "Arla Maitoa Suomesta Laktoositon rasvaton maitojuoma UHT Suomi 1 l", ARLA_FI),
    ],
)
def test_the_same_product_written_another_way_matches(
    catalog: ProductCatalog, product_id: str, page_name: str, url: str
) -> None:
    assert why_not_this_product(page_name, None, url, catalog.get_product(product_id)) is None


def test_a_lactose_mark_missing_from_the_pages_name_is_read_from_its_free_from_list_and_from_nowhere_else(
    catalog: ProductCatalog,
) -> None:
    ruoka, eila = catalog.get_product(VALIO_RUOKA_15), catalog.get_product(VALIO_EILA_FAT_FREE)

    assert names_match("Valio Ruoka 15%", None, VALIO_FI, ruoka, ("laktoositon",))
    assert why_not_this_product("Valio Ruoka 15%", None, VALIO_FI, ruoka, ("gluteeniton",)) == (
        "the product asked for is lactose-free; the page does not say lactose-free"
    )
    # A low-lactose page is not a lactose-free page, and "fat-free" is never read from the free-from list.
    assert not names_match("Valio Ruoka 15%", None, VALIO_FI, ruoka, ("vähälaktoosinen",))
    assert not names_match(
        "Valio Hyvä suomalainen Arki® Eila® maitojuoma laktoositon", None, VALIO_FI, eila, ("rasvaton",)
    )


def test_a_free_from_list_never_turns_a_page_against_a_product_that_does_not_carry_the_mark(
    catalog: ProductCatalog,
) -> None:
    alpro = catalog.get_product("465793")  # its names do not say lactose-free; its page's free-from list does

    assert names_match("Barista Mantelijuoma", None, "https://www.alpro.com/fi/x", alpro, ("laktoositon",))


# --- whose page it is ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("product_id", "url", "is_owner"),
    [
        ("463975", "https://www.arlapro.com/fi/tuotteet/arla-ruoka-15-laktoositon-1l-uht/", True),  # Arla Pro
        ("463047", "https://www.arlapro.com/fi/tuotteet/arla-taysmaito-1-l-vahalakt-uht-suomi/", True),  # Arla
        ("463047", "https://www.arla.fi/tuotteet/maito/vahalaktoosinen-taysmaito-uht-1l-695747/", True),
        ("464401", "https://www.valio.fi/tuotteet/x/", True),
        ("465793", "https://www.alpro.com/fi/tuotteemme/juomat/barista-mantelijuoma", True),
        ("463975", "https://arlapro.com.example.org/x", False),  # a look-alike host
        ("464401", "https://www.arlapro.com/fi/x/", False),  # another brand's site
        # The wholesaler's own site and an Estonian maker's: no brand in the catalog, so nobody's page is "the
        # manufacturer's".
        ("464517", "https://www.valioaimo.fi/ammattilaistuotteet/valio-a-luonnonjogurtti-sanko/", False),
        ("464608", "https://saarefood.ee/product/horeca/saare-turkish-yogurt-10-lactose-free", False),
    ],
)
def test_the_brand_owners_hosts(catalog: ProductCatalog, product_id: str, url: str, is_owner: bool) -> None:
    assert is_brand_owner_page(url, catalog.get_product(product_id)) is is_owner


def test_the_list_of_brand_owner_hosts_is_pinned() -> None:
    assert BRAND_OWNER_HOSTS == {
        "elovena": ("elovena.fi", "raisiofoodsolutions.fi"),
        "oddlygood": ("oddlygood.com",),
        "fazer": ("fazer.com",),
        "valio": ("valio.fi", "valio.com"),
        "arla": ("arla.fi", "arla.com", "arlapro.com"),
        "alpro": ("alpro.com",),
    }


# --- S1: a product with no brand in Valio Aimo's data ---------------------------------------------------------------

AIMO_YOGURT = "464517"  # "AIMO NATURAL YOGURT 5KG 2% LACTOSE FREE": Valio Aimo's own label, no brand in the data
AIMO_PAGE = "AIMO Natural Yogurt 5kg 2% lactose free"
NO_BRAND = "the product has no brand in Valio Aimo's data, so a page cannot be shown to be its maker's"


def test_the_product_of_the_reproduction_has_no_brand(catalog: ProductCatalog) -> None:
    assert catalog.get_product(AIMO_YOGURT).brand is None


@pytest.mark.parametrize("url", [
    "https://random-shop.example/aimo-natural-yogurt",
    "https://valioaimo.fi.random-shop.example/x",  # the supplier's host as a label of another host
    "https://notvalioaimo.fi/x",
])
def test_with_no_brand_a_page_on_any_other_host_is_never_evidence(catalog: ProductCatalog, url: str) -> None:
    product = catalog.get_product(AIMO_YOGURT)

    assert why_not_this_product(AIMO_PAGE, AIMO_PAGE, url, product) == NO_BRAND
    assert not names_match(AIMO_PAGE, AIMO_PAGE, url, product)


@pytest.mark.parametrize("brand", [None, "", "   ", "®"])
def test_a_blank_brand_is_no_brand(catalog: ProductCatalog, brand: str | None) -> None:
    product = catalog.get_product("469512").model_copy(update={"brand": brand})

    assert why_not_this_product("Elovena Kaurajuoma kahviin", None, "https://elovena.fi/x/", product) == NO_BRAND


def test_an_own_label_product_on_valio_aimos_own_site_is_kept_when_everything_else_agrees(
    catalog: ProductCatalog,
) -> None:
    product = catalog.get_product(AIMO_YOGURT)

    assert names_match(AIMO_PAGE, None, "https://www.valioaimo.fi/tuotteet/x", product)
    # The other checks still hold on that host: another percentage, and a product that is not own label.
    assert why_not_this_product("AIMO Natural Yogurt 5kg 10% lactose free", None, "https://valioaimo.fi/x", product) \
        == "the page is for the 10% product; the product asked for is 2%"
    other = catalog.get_product("469512").model_copy(update={"brand": None})
    assert why_not_this_product("Elovena Kaurajuoma kahviin", None, "https://valioaimo.fi/x", other) == NO_BRAND
