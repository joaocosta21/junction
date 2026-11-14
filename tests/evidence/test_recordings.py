"""The recorded answers in fixtures/evidence/ (Context.dev, 14 Nov 2026): every demo product reads the same way on
every run, and what was sent for each carries its names only."""

from __future__ import annotations

from pathlib import Path

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.evidence.cache import EvidenceCache
from tta.evidence.reading import read_answer, read_page

RECORDINGS = Settings.for_tests().tta_fixtures_dir / "evidence"
DROPPED = (
    "No evidence was found on the web for product {id}: the page found (“{name}”) is not shown to be this product "
    "and was dropped: {why}."
)
NO_BRAND = "the product has no brand in Valio Aimo's data, so a page cannot be shown to be its maker's"
# One entry per recording: the sentence, and above it the judgement it pins (EV, 14 Nov). A change of the matcher
# that keeps a dropped page, or drops a kept one, fails here.
EXPECTED = {
    # --- recorded 14 Nov 08:06 UTC --------------------------------------------------------------------------------
    "469512": "The manufacturer's page “Elovena Kaurajuoma kahviin” on raisiofoodsolutions.fi says: contains “KAURA”; "
              "free from “Gluteeniton”, “Laktoositon”, “Maidoton”, “Kananmunaton”.",
    "468465": "The manufacturer's page “Oddlygood® kaurajuoma 1 l UHT gluteeniton” on oddlygood.com says: contains "
              "“gluteeniton kaura”; free from “gluteeniton”, “ei sisällä maitoa”.",
    "473609": "The manufacturer's page “Oddlygood® Barista kaurajuoma 1 l UHT gluteeniton” on oddlygood.com says: "
              "contains “Gluteeniton kaura”; free from “Gluteeniton”.",
    "475224": "The manufacturer's page “Fazer Aito Professional Barista Oat Drink 1L UHT” on fazer.com names no "
              "allergen in its text.",
    # Another product. The English name says almond drink, the Finnish name soya drink, and the product declares
    # soya (AY); the page is the almond drink ("mantelijuoma"), which is product 474774 in the catalog. The page
    # word is not translated, so it is a word neither name carries.
    "474864": DROPPED.format(
        id="474864", name="Oddlygood® mantelijuoma 1 l no sugars UHT",
        why="the page's product name says “mantelijuoma”, which the product asked for does not",
    ),
    # --- recorded 14 Nov 17:56 to 17:58 UTC -----------------------------------------------------------------------
    # A sibling, as far as the recording shows: same brand, line, lactose-free, fat-free, milk drink, 1 l, but the
    # product is UHT and the page does not say UHT, while arla.fi writes "(UHT)" on the page of 463047.
    "462775": DROPPED.format(
        id="462775", name="Arla Maitoa Suomesta Laktoositon rasvaton maitojuoma Suomi 1 l",
        why="the product asked for is UHT; the page does not say UHT",
    ),
    # The same product: Arla, whole milk, low-lactose, UHT, 1 l, from Finland. "Maitoa Suomesta" is Arla's line.
    "463047": "The manufacturer's page “Arla Maitoa Suomesta Vähälaktoosinen täysmaito (UHT) 1 l” on arla.fi says: "
              "contains “Maito”; free from “Vähälaktoosinen”.",
    # The same product: Arla Pro, Ruoka, 15%, 1 l, lactose-free, UHT, on Arla's food-service site.
    "463975": "The manufacturer's page “Arla Pro ruoka 15% 1L laktoositon (UHT)” on arlapro.com says: contains "
              "“maito”; free from “laktoositon”.",
    # The same product: every word of the Finnish name but the pack size.
    "464401": "The manufacturer's page “Valio Hyvä suomalainen Arki® Eila® rasvaton maitojuoma laktoositon” on "
              "valio.fi says: free from “laktoositon”, “laktoosittomaan ruokavalioon”.",
    # The two products of Valio Aimo's own label "AIMO" carry no brand in the data (S1). This page is on Valio
    # Aimo's own site (valioaimo.fi), the one host an own-label product may be matched on, so the other checks
    # decide: it is a "Valio A+™" yoghurt whose name states no fat percentage, and the product is 2%.
    "464517": DROPPED.format(
        id="464517", name="Valio A+™ luonnonjogurtti maustamaton laktoositon 5 kg",
        why="the product asked for is 2%; the page's product name states no percentage",
    ),
    # A Saare product on saarefood.ee: no maker's site can be shown to be that of a product without a brand.
    # Before S1 it was dropped for the word "Saare".
    "464608": DROPPED.format(id="464608", name="Saare Turkish yogurt 10%, lactose-free", why=NO_BRAND),
    # The same product: the page's name is the Finnish name without the brand and the pack, on alpro.com.
    "465793": "The manufacturer's page “Barista Mantelijuoma” on alpro.com says: contains “manteli”; may contain "
              "“pähkinöistä (ei maapähkinästä)”; free from “laktoositon”, “Maidoton”, “Gluteeniton”.",
    # The same product: Valio, Ruoka, 15%; the page's name leaves out "laktoositon" and its free-from list says it.
    # The page names no pack: it is the product's page for its packs.
    "469162": "The manufacturer's page “Valio Ruoka 15%” on valio.fi says: contains “maito”; free from “laktoositon”.",
}
KEPT = ("463047", "463975", "464401", "465793", "468465", "469162", "469512", "473609", "475224")


def test_nine_recordings_are_kept_and_four_are_dropped(catalog: ProductCatalog) -> None:
    kept = tuple(
        product_id for product_id in sorted(EXPECTED)
        if read_answer(EvidenceCache(RECORDINGS).get(product_id), catalog.get_product(product_id)).found
    )

    assert kept == KEPT


@pytest.mark.parametrize(("product_id", "sentence"), EXPECTED.items())
def test_each_recording_reads_as_recorded(catalog: ProductCatalog, product_id: str, sentence: str) -> None:
    record = EvidenceCache(RECORDINGS).get(product_id)

    evidence = read_answer(record, catalog.get_product(product_id))

    assert evidence.sentence == sentence
    assert evidence.found is not sentence.startswith("No evidence")


def test_every_recording_sent_names_only(catalog: ProductCatalog) -> None:
    files = sorted(Path(RECORDINGS).glob("*.json"))

    assert [path.stem for path in files] == sorted(EXPECTED)
    for path in files:
        record = EvidenceCache(RECORDINGS).get(path.stem)
        assert set(record.request) == {"mode", "task", "json_format", "timeoutOpts"}
        assert path.stem not in record.request["task"]
        brand = catalog.get_product(path.stem).brand  # the two "AIMO" products carry no brand in the catalog
        assert brand is None or brand in record.request["task"]


def test_no_kept_recording_is_of_a_product_without_a_brand_and_none_has_an_unread_entry(
    catalog: ProductCatalog,
) -> None:
    for product_id in KEPT:
        evidence, unread = read_page(EvidenceCache(RECORDINGS).get(product_id), catalog.get_product(product_id))
        assert (catalog.get_product(product_id).brand or "").strip()
        assert (evidence.found, unread) == (True, 0)
