"""The approval card shows the evidence first, under its own heading, with the link, and escapes every word of it."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, hooks
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import ApprovalStatus, Identity
from tta.contracts.order import Evidence
from tta.evidence.answers import AnswerRecord
from tta.evidence.reading import read_answer

CSRF_FIELD = re.compile(r'name="csrf" value="([A-Za-z0-9_-]+)"')
BOOK_COOKIES = ("tta_book", "__Host-tta_book")
HEADING = "Found on the manufacturer's page — not Valio data"
DIETITIAN = "human:hotel-purchasing"  # one person confirms: the hotel's buyer holds the dietitian's role


@pytest.fixture(autouse=True)
def only_the_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agent package and the MCP surface are not loaded: other tasks are writing them."""
    real = hooks.optional_module
    hidden = (hooks.AGENT_MODULE, hooks.MCP_MODULE)
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in hidden else real(name))


@pytest.fixture
def client(settings: Settings, catalog: ProductCatalog) -> Iterator[TestClient]:
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))
    with TestClient(app) as opened:
        yield opened


def _waiting_card(client: TestClient, requests: SimpleNamespace, evidence: tuple[Evidence, ...]) -> str:
    """Place the demo order in this browser's own book, attach the evidence to its approval, and read the card
    as the hotel's dietitian."""
    client.get("/")
    key = next(client.cookies.get(name) for name in BOOK_COOKIES if client.cookies.get(name))
    parts = client.app.state.parts  # type: ignore[attr-defined]
    book = parts.sandboxes.open(key)
    agent = next(identity for identity in parts.tokens.identities if identity.id == "agent:hotel-kitchen")
    dietitian: Identity = next(identity for identity in parts.tokens.identities if identity.id == DIETITIAN)
    offer = book.service.create_offer(agent, requests.elovena())
    book.service.place_order(agent, offer.offer_id, offer.options[0].option_id, "card-1")
    (approval,) = book.service.list_approvals(dietitian, ApprovalStatus.PENDING)
    book.store.save_approval(approval.model_copy(update={"evidence": evidence}))
    csrf = CSRF_FIELD.search(client.get("/approvals").text).group(1)  # type: ignore[union-attr]
    client.post("/approvals/as", data={"csrf": csrf, "approver": DIETITIAN})
    page = client.get("/approvals")
    assert page.status_code == 200, page.text
    return page.text


def _evidence(catalog: ProductCatalog, record: Callable[..., AnswerRecord], body: dict[str, Any]) -> Evidence:
    return read_answer(record("469512", body), catalog.get_product("469512"))


def test_the_card_shows_the_evidence_first_with_its_label_and_link(
    client: TestClient, catalog: ProductCatalog, record: Callable[..., AnswerRecord], bodies: SimpleNamespace,
    requests: SimpleNamespace,
) -> None:
    page = _waiting_card(client, requests, (_evidence(catalog, record, bodies.elovena),))

    assert HEADING in page
    assert page.index(HEADING) < page.index("Why a human is needed")
    assert f'href="{bodies.elovena_url}"' in page
    assert 'rel="noopener noreferrer nofollow"' in page
    assert "Maidoton" in page and "KAURA" in page
    assert "Elovena Kaurajuoma kahviin" in page
    assert "changes no status and no verdict" in page
    assert page.count(HEADING) == 1  # the evidence is shown once, however the approval came to carry it


def test_page_text_containing_a_script_is_rendered_escaped(
    client: TestClient, catalog: ProductCatalog, record: Callable[..., AnswerRecord], bodies: SimpleNamespace,
    requests: SimpleNamespace,
) -> None:
    content = {**bodies.elovena["json_content"], "contains": [bodies.hostile], "page_title": bodies.hostile}
    hostile = _evidence(catalog, record, {**bodies.elovena, "json_content": content})

    page = _waiting_card(client, requests, (hostile,))

    assert hostile.found
    assert bodies.hostile not in page
    # Escaped by the page, and its double quotation marks made single by the reader (security review L2).
    assert "&lt;script&gt;alert(&#39;page&#39;)&lt;/script&gt;" in page


def test_a_card_without_evidence_found_says_so_and_links_nothing(
    client: TestClient, catalog: ProductCatalog, record: Callable[..., AnswerRecord], bodies: SimpleNamespace,
    requests: SimpleNamespace,
) -> None:
    dropped = _evidence(catalog, record, bodies.wrong_product)

    page = _waiting_card(client, requests, (dropped,))

    assert HEADING in page
    assert "No evidence was found on the web for product 469512" in page
    assert 'href="https://www.oddlygood.com' not in page


def test_a_card_with_no_evidence_has_no_evidence_section(client: TestClient, requests: SimpleNamespace) -> None:
    page = _waiting_card(client, requests, ())

    assert HEADING not in page
