"""AP-4: evidence on every kind of allergen doubt, from recorded pages only; the heading says "manufacturer's page"
only for a host listed for the brand; the count of requests survives a restart. No lookup is made here."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import AllergenRelation, Identity, OrderStatus, Unit
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.evidence import build_evidence_finder, wording
from tta.evidence.answers import COUNT_KEY, AnswersClient, EvidenceUnavailable
from tta.evidence.finder import COUNT_FILE
from tta.evidence.matching import is_brand_owner_page
from tta.evidence.reading import read_answer

Make = Callable[..., Any]
ALMOND_DRINK = "465793"  # Alpro Barista almond drink: declares "free from tree nuts", its ingredients name ALMOND
NOT_RECORDED = "464013"  # no page of this product is in fixtures/evidence/
NOT_RULED_OUT = "Alternative: allergen not ruled out"
KEY = "ctx-test-key-not-real"


def _almond_request() -> PurchaseRequest:
    text = "10 litres of Alpro Barista almond drink, product 465793, by Monday; no tree nuts"
    return PurchaseRequest(needed_by=date(2026, 11, 16), lines=(RequestLine(
        text=text, product_ids=(ALMOND_DRINK,), quantity=Decimal(10), unit=Unit.L, exclude_allergens=("AN",),
    ),))


def test_a_contradiction_gets_the_recorded_page_with_an_answer_for_the_excluded_allergen(
    make_stack: Make, catalog: ProductCatalog, agent_hotel: Identity, hotel_dietitian: Identity, tmp_path: Path,
) -> None:
    """P13 section 2.4: this product had 0 evidence entries, because its finding is "may contain". Its page was
    recorded on 14 Nov (fixtures/evidence/465793.json): Alpro's own page names almond and other nuts, so the
    person who signs reads that the page names the excluded allergen. Nothing here makes the product safe."""
    finder = build_evidence_finder(Settings.for_tests(), tmp_path, catalog)  # no key: recorded pages only
    stack = make_stack(finder)
    offer = stack.service.create_offer(agent_hotel, _almond_request())
    option = next(
        option for option in offer.options
        if option.title == NOT_RULED_OUT and [line.product_id for line in option.lines] == [ALMOND_DRINK]
    )
    (finding,) = option.lines[0].allergen_check.findings
    assert finding.relation is AllergenRelation.MAY_CONTAIN  # a doubt of another kind than "no statement"

    order = stack.service.place_order(agent_hotel, offer.offer_id, option.option_id, "ap4-almond")
    approval = stack.orders.get_approval(order.approval_id, hotel_dietitian)

    (evidence,) = approval.evidence
    assert (evidence.product_id, evidence.found) == (ALMOND_DRINK, True)
    assert evidence.sentence == (
        "The manufacturer's page “Barista Mantelijuoma” on alpro.com says: contains “manteli”; may contain "
        "“pähkinöistä (ei maapähkinästä)”; free from “laktoositon”, “Maidoton”, “Gluteeniton”. "
        "Asked about tree nuts (AN): Valio Aimo's data does not rule it out; the page says it contains it, in its "
        "words “manteli”. "
        "The page names tree nuts (AN), which this order excludes: check the product before approving. "
        "What a page says can add a doubt and never removes one."
    )
    assert order.status is OrderStatus.PENDING_APPROVAL  # the page changed no status: a person still decides
    assert not list(tmp_path.rglob("*.json"))  # nothing was asked, counted or stored


def test_a_product_with_no_recorded_page_says_so(catalog: ProductCatalog, tmp_path: Path) -> None:
    finder = build_evidence_finder(Settings.for_tests(), tmp_path, catalog)  # no key: recorded pages only

    evidence = finder.find_evidence(catalog.get_product(NOT_RECORDED))

    assert not evidence.found
    assert evidence.sentence == (
        f"No evidence was found on the web for product {NOT_RECORDED}: no recorded page of this product is stored "
        "and no lookup is made on this link (no Context.dev key is set)."
    )
    assert not list(tmp_path.rglob("*.json"))


def test_the_recorded_elovena_page_is_attached_to_the_option_whose_allergen_is_not_ruled_out(
    make_stack: Make, catalog: ProductCatalog, agent_hotel: Identity, hotel_dietitian: Identity,
    requests: SimpleNamespace, tmp_path: Path,
) -> None:
    stack = make_stack(build_evidence_finder(Settings.for_tests(), tmp_path, catalog))
    offer = stack.service.create_offer(agent_hotel, requests.elovena())
    option = next(option for option in offer.options if option.title == NOT_RULED_OUT)

    order = stack.service.place_order(agent_hotel, offer.offer_id, option.option_id, "ap4-elovena")
    (evidence,) = stack.orders.get_approval(order.approval_id, hotel_dietitian).evidence

    assert evidence.found and evidence.source_url.startswith("https://www.raisiofoodsolutions.fi/")
    assert evidence.sentence.startswith(
        "The manufacturer's page “Elovena Kaurajuoma kahviin” on raisiofoodsolutions.fi"
    )


# --- the heading ------------------------------------------------------------------------------------------------


def test_the_heading_says_manufacturers_page_only_for_a_host_listed_for_the_brand(
    catalog: ProductCatalog, ids: SimpleNamespace
) -> None:
    elovena = catalog.get_product(ids.elovena)

    assert is_brand_owner_page("https://www.raisiofoodsolutions.fi/tuotteet/x", elovena)
    assert is_brand_owner_page("https://elovena.fi/tuotteet/x", elovena)
    assert not is_brand_owner_page("https://elovena.fi.example.com/x", elovena)  # a look-alike host
    assert not is_brand_owner_page("https://www.oddlygood.com/x", elovena)  # another brand's site
    assert not is_brand_owner_page("https://shop.example/elovena", elovena)
    # The sentence is the one place that says whose page it is: no separate heading text exists to disagree with it.
    assert not hasattr(wording, "heading") and not hasattr(wording, "HEADING_UNCHECKED")
    assert (wording.PAGE_OWNER, wording.PAGE_UNCHECKED) == (
        "The manufacturer's page", "A web page whose owner was not checked,",
    )


def test_a_page_on_a_host_that_is_not_listed_is_not_called_the_manufacturers(
    catalog: ProductCatalog, record: Make, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    url = "https://elovena.shop.example/tuotteet/elovena-kaurajuoma-kahviin/"
    body = {**bodies.elovena, "sources": [url], "json_content": {**bodies.elovena["json_content"], "source_url": url}}

    evidence = read_answer(record(ids.elovena, body), catalog.get_product(ids.elovena))

    assert evidence.found
    assert evidence.sentence.startswith(
        "A web page whose owner was not checked, “Elovena Kaurajuoma kahviin” on elovena.shop.example says: "
    )
    assert "manufacturer" not in evidence.sentence


# --- the count of requests, kept on disk --------------------------------------------------------------------------


def _client(tmp_path: Path, bodies: SimpleNamespace, sent: list[str], **options: Any) -> AnswersClient:
    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(str(request.url))
        return httpx.Response(200, json=bodies.elovena)

    settings = Settings.for_tests(context_dev_api_key=KEY)
    return AnswersClient(settings, transport=httpx.MockTransport(answer), **options)


def test_a_second_client_on_the_same_folder_continues_the_first_ones_count(
    tmp_path: Path, catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    counter, sent, product = tmp_path / "evidence" / COUNT_FILE, [], catalog.get_product(ids.elovena)
    first = _client(tmp_path, bodies, sent, max_calls=3, counter=counter)
    first.ask(product)
    first.ask(product)
    first.close()

    restarted = _client(tmp_path, bodies, sent, max_calls=3, counter=counter)
    assert restarted.calls_made == 2
    restarted.ask(product)
    with pytest.raises(EvidenceUnavailable, match="limit of 3 web lookups is spent"):
        restarted.ask(product)

    assert len(sent) == 3
    assert json.loads(counter.read_text(encoding="utf-8")) == {COUNT_KEY: 3}
    assert KEY not in counter.read_text(encoding="utf-8")


def test_without_a_counter_file_the_count_is_per_process_as_before(
    tmp_path: Path, catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace
) -> None:
    sent: list[str] = []
    _client(tmp_path, bodies, sent, max_calls=1).ask(catalog.get_product(ids.elovena))
    _client(tmp_path, bodies, sent, max_calls=1).ask(catalog.get_product(ids.elovena))

    assert len(sent) == 2 and not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "text", ["{", "[]", '{"requests_sent": "3"}', '{"requests_sent": -1}', '{"requests_sent": true}']
)
def test_a_count_that_cannot_be_read_sends_nothing(
    tmp_path: Path, catalog: ProductCatalog, bodies: SimpleNamespace, ids: SimpleNamespace, text: str
) -> None:
    counter, sent = tmp_path / COUNT_FILE, []
    counter.write_text(text, encoding="utf-8")

    with pytest.raises(EvidenceUnavailable) as refused:
        _client(tmp_path, bodies, sent, counter=counter).ask(catalog.get_product(ids.elovena))

    assert refused.value.reason == "the count of web lookups already made could not be read, so none was made"
    assert sent == []


def test_the_gateways_finder_keeps_its_count_beside_the_stored_answers_and_the_cache_never_reads_it(
    tmp_path: Path, catalog: ProductCatalog, ids: SimpleNamespace
) -> None:
    finder = build_evidence_finder(Settings.for_tests(context_dev_api_key=KEY), tmp_path, catalog)

    assert finder._answers._counter == tmp_path / "evidence" / COUNT_FILE
    (tmp_path / "evidence").mkdir()
    (tmp_path / "evidence" / COUNT_FILE).write_text('{"requests_sent": 40}', encoding="utf-8")
    # The recorded demo product is still answered, and the spent budget is said for a product with no page.
    assert finder.find_evidence(catalog.get_product(ids.elovena)).found
    spent = finder.find_evidence(catalog.get_product(NOT_RECORDED))
    assert spent.sentence.endswith(": this gateway's limit of 40 web lookups is spent.")
    finder.close()
