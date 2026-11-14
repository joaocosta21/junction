"""Fixtures for the web-evidence tests (task S2): Context.dev answers as recorded, fakes of the service, and the
gateway in replay with an evidence finder wired into its order book.

No test here calls Context.dev or the Valio mock, and nothing reads `.env`: the answers below are the bodies
Context.dev returned on 14 Nov 2026 (request ids kept), and the supplier side answers from tonight's capture.
Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tta.api.limits import call_limits
from tta.api.service import Gateway, GatewayDeps
from tta.audit import AuditTrail
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.common import AllergenStrictness, ApproverRole, Identity, IdentityKind, Unit
from tta.contracts.product import Product
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.evidence.answers import AnswerRecord, EvidenceUnavailable
from tta.evidence.cache import EvidenceCache
from tta.evidence.finder import EvidenceFinder
from tta.offers import OfferDeps, OfferService
from tta.orders import OrderBookService, day_committed_net_eur
from tta.policy import RulePolicyEngine
from tta.store import SqliteStore
from tta.valio import ReplayGateway

CAPTURE = "2026-11-14-demo"
MONDAY = date(2026, 11, 16)
RETRIEVED_AT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
ELOVENA = "469512"  # Elovena 1l oat drink barista: confirmed tonight, no statement about milk (AM)
ODDLYGOOD_OAT = "468465"  # Oddlygood oat drink 1 l: quantity not confirmed, no statement about milk
ODDLYGOOD_ALMOND = "474864"  # no page of this product was found
ELOVENA_URL = "https://elovena.fi/tuotteet/elovena-kaurajuoma-kahviin/"

# What Context.dev's Answers endpoint returned for Elovena 1l oat drink barista (request 10 of this task).
ELOVENA_BODY: dict[str, Any] = {
    "json_content": {
        "page_found": True,
        "source_url": ELOVENA_URL,
        "page_title": "Elovena Kaurajuoma kahviin",
        "product_name_on_page": "Elovena Kaurajuoma kahviin",
        "contains": ["KAURA"],
        "may_contain": [],
        "free_from": ["Gluteeniton", "Laktoositon", "Maidoton", "Kananmunaton"],
    },
    "sources": [ELOVENA_URL],
    "key_metadata": {"credits_consumed": 100, "credits_remaining": 50185},
    "request_id": "d11bafe0-bca1-4ee4-b724-c98352fcc8c0",
}
# Asked for Oddlygood oat drink 1 l (468465), Context.dev returned the page of the Barista drink (473609).
WRONG_PRODUCT_BODY: dict[str, Any] = {
    "json_content": {
        "page_found": True,
        "source_url": "https://www.oddlygood.com/uk/tuotteet/oddlygood-barista-oat-drink-1-l-uht-gluten-free/",
        "page_title": "Oddlygood® Barista oat drink 1 l UHT gluten free",
        "product_name_on_page": "Oddlygood® Barista oat drink 1 l UHT gluten free",
        "contains": ["Gluten-free oats"],
        "may_contain": [],
        "free_from": [],
    },
    "sources": ["https://www.oddlygood.com/uk/tuotteet/oddlygood-barista-oat-drink-1-l-uht-gluten-free/"],
    "key_metadata": {"credits_consumed": 100, "credits_remaining": 50685},
    "request_id": "cf5c649a-3fca-4a1f-8bd6-2388c09d9a90",
}
NOT_FOUND_BODY: dict[str, Any] = {
    "json_content": {
        "page_found": False, "source_url": None, "page_title": None, "product_name_on_page": None,
        "contains": [], "may_contain": [], "free_from": [],
    },
    "sources": ["https://www.oddlygood.com/uk/our-products/", "https://www.oddlygood.com/our-products/"],
    "key_metadata": {"credits_consumed": 100, "credits_remaining": 50385},
    "request_id": "85d4bf56-ce4a-40d9-941b-c0391eb937d7",
}
HOSTILE_TEXT = '<script>alert("page")</script>'


def elovena_request() -> PurchaseRequest:
    """The demo moment: the hotel kitchen asks for 100 L of the Elovena barista oat drink, without milk."""
    text = "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk"
    return PurchaseRequest(needed_by=MONDAY, lines=(RequestLine(
        text=text, product_ids=(ELOVENA,), quantity=Decimal(100), unit=Unit.L, exclude_allergens=("AM",),
        allergen_strictness=AllergenStrictness.STRICT,
    ),))


class FakeAnswers:
    """Stands in for the Context.dev client: answers one body for every product, or raises what it is given."""

    def __init__(self, body: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.body = body
        self.error = error
        self.asked: list[str] = []

    def ask(self, product: Product) -> AnswerRecord:
        self.asked.append(product.id)
        if self.error is not None:
            raise self.error
        assert self.body is not None
        return AnswerRecord(product_id=product.id, retrieved_at=RETRIEVED_AT, request={"task": "test"}, body=self.body)


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def bodies() -> SimpleNamespace:
    return SimpleNamespace(
        elovena=ELOVENA_BODY, wrong_product=WRONG_PRODUCT_BODY, not_found=NOT_FOUND_BODY, hostile=HOSTILE_TEXT,
        elovena_url=ELOVENA_URL, retrieved_at=RETRIEVED_AT,
    )


@pytest.fixture(scope="session")
def ids() -> SimpleNamespace:
    return SimpleNamespace(elovena=ELOVENA, oddlygood_oat=ODDLYGOOD_OAT, oddlygood_almond=ODDLYGOOD_ALMOND)


@pytest.fixture(scope="session")
def record() -> Callable[..., AnswerRecord]:
    """An answer as the client hands it on: the product, when it was read, what was sent and what came back."""

    def build(product_id: str, body: dict[str, Any]) -> AnswerRecord:
        return AnswerRecord(product_id=product_id, retrieved_at=RETRIEVED_AT, request={"task": "test"}, body=body)

    return build


@pytest.fixture(scope="session")
def fake_answers() -> Callable[..., FakeAnswers]:
    return FakeAnswers


@pytest.fixture(scope="session")
def unavailable() -> Callable[[str], EvidenceUnavailable]:
    return EvidenceUnavailable


@pytest.fixture
def empty_cache(tmp_path: Path) -> EvidenceCache:
    """A cache with nothing in it and no recordings behind it."""
    return EvidenceCache(tmp_path / "evidence")


@pytest.fixture(scope="session")
def hotel_dietitian() -> Identity:
    """Who decides a dietitian's question at the hotel. One person confirms (decision SIMP): the hotel names no
    dietitian of its own, and the person who orders holds that role with the two others."""
    return Identity(kind=IdentityKind.APPROVER, id="human:hotel-purchasing", display_name="Demo approver Hanna",
                    profile_id="hotel-kitchen", roles=tuple(ApproverRole))


@pytest.fixture(scope="session")
def requests() -> SimpleNamespace:
    return SimpleNamespace(elovena=elovena_request)


@pytest.fixture
def make_stack(settings: Settings, catalog: ProductCatalog) -> Callable[..., SimpleNamespace]:
    """The gateway over an empty in-memory store, in replay, as `tta.api.wiring.wire` builds it, with the given
    evidence finder (or none) handed to the order book."""

    def build(finder: EvidenceFinder | None) -> SimpleNamespace:
        policy = RulePolicyEngine.from_files()
        replay = ReplayGateway(settings.replay_capture_dir)
        clock = replay.clock
        store = SqliteStore()
        audit = AuditTrail(store, clock, policy=policy)
        offers = OfferService(OfferDeps(
            catalog=catalog, gateway=replay, policy=policy, clock=clock,
            day_spend=lambda profile_id: day_committed_net_eur(store, clock, profile_id),
        ))
        orders = OrderBookService(
            store=store, policy=policy, revalidator=offers, audit=audit, clock=clock, evidence=finder,
        )
        service = Gateway(GatewayDeps(
            catalog=catalog, policy=policy, store=store, audit=audit, offers=offers, orders=orders,
            limiter=call_limits(False),
        ))
        return SimpleNamespace(service=service, store=store, audit=audit, orders=orders)

    return build


@pytest.fixture
def make_finder(catalog: ProductCatalog, empty_cache: EvidenceCache) -> Callable[..., EvidenceFinder]:
    """A finder over the real catalog and an empty cache, asking the given fake (or nothing: no key)."""

    def build(answers: FakeAnswers | None, cache: EvidenceCache | None = None) -> EvidenceFinder:
        return EvidenceFinder(catalog=catalog, cache=cache or empty_cache, answers=answers)

    return build
