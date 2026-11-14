"""The recorded answers in fixtures/evidence/ (Context.dev, 14 Nov 2026): every demo product reads the same way on
every run, and what was sent for each carries its names only."""

from __future__ import annotations

from pathlib import Path

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.evidence.cache import EvidenceCache
from tta.evidence.reading import read_answer

RECORDINGS = Settings.for_tests().tta_fixtures_dir / "evidence"
EXPECTED = {
    "469512": "The page “Elovena Kaurajuoma kahviin” on raisiofoodsolutions.fi says: contains KAURA; "
              "free from Gluteeniton, Laktoositon, Maidoton, Kananmunaton.",
    "468465": "The page “Oddlygood® kaurajuoma 1 l UHT gluteeniton” on oddlygood.com says: contains gluteeniton "
              "kaura; free from gluteeniton, ei sisällä maitoa.",
    "473609": "The page “Oddlygood® Barista kaurajuoma 1 l UHT gluteeniton” on oddlygood.com says: contains "
              "Gluteeniton kaura; free from Gluteeniton.",
    "475224": "The page “Fazer Aito Professional Barista Oat Drink 1L UHT” on fazer.com names no allergen in its text.",
    # The English name says almond drink, the Finnish name soya drink, and the product declares soya (AY); the page
    # is the almond drink ("mantelijuoma"), which neither name carries, so it is dropped.
    "474864": "No evidence was found on the web for product 474864: the page found is for another product "
              "(“Oddlygood® mantelijuoma 1 l no sugars UHT”), so it was dropped.",
}


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
        assert catalog.get_product(path.stem).brand in record.request["task"]
