"""Fixtures for the page tests: the whole gateway in replay over tonight's capture, a database under `tmp_path`.

Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
No test here calls a live service or a model, and nothing reads `.env`. The buyer agent (T10) and the MCP
surface (T11) are written while these tests run, so both are switched off here: the pages are tested against
the gateway alone, and against fakes of the parser and the runner.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app, hooks
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import AgentRun, AgentStep
from tta.contracts.common import Identity, Unit
from tta.contracts.errors import InvalidRequest, SupplierUnavailable
from tta.contracts.ports import GatewayService
from tta.contracts.product import Product, SearchResult
from tta.contracts.request import ProductQuery, PurchaseRequest, RequestLine

CSRF_FIELD = re.compile(r'name="csrf" value="([A-Za-z0-9_-]+)"')
RUN_KEY_FIELD = re.compile(r'name="run_key" value="([A-Za-z0-9_-]+)"')
FREE_TEXT = "80 litres of oat drink for the breakfast buffet by Monday"
TYPED_FREE_TEXT = PurchaseRequest(
    needed_by=date(2026, 11, 16),
    lines=(RequestLine(text=FREE_TEXT, product_type="plant_drink", quantity=Decimal(80), unit=Unit.L),),
)
HOSTILE_NAME = ' <script>alert("name")</script>'
RENAMED = ("469363", "464306", "463203", "464013")  # a confirmed line, the alternative, an exclusion, scenario 2

Form = dict[str, str]
Post = Callable[..., Any]


class NoParser:
    """A parser whose model cannot be reached."""

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        raise SupplierUnavailable("The model that reads requests cannot be reached right now.")


class FakeParser:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        self.texts.append(text)
        if "litres" not in text:
            raise InvalidRequest("The request names no quantity.")
        return TYPED_FREE_TEXT


class FakeRunner:
    """Runs the flow the way the buyer agent does: only through the gateway's own functions."""

    def __init__(self) -> None:
        self.runs = 0

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        self.runs += 1
        authority = tools.get_authority(identity)
        offer = tools.create_offer(identity, TYPED_FREE_TEXT)
        order = tools.place_order(identity, offer.offer_id, offer.options[0].option_id, f"fake-agent-{self.runs}")
        steps = (
            AgentStep(index=1, tool="get_authority", ok=True, result={"profile_id": authority.profile.profile_id}),
            AgentStep(index=2, tool="create_offer", ok=True, result={"offer_id": offer.offer_id}),
            AgentStep(index=3, tool="place_order", ok=True, sentence=order.status_sentence,
                      arguments={"note": '<b>from the model</b>'}),
        )
        return AgentRun(
            text=text, model="fake-model-1", recorded=True, steps=steps, offer_id=offer.offer_id,
            order_id=order.order_id, order_status=order.status, report=order.status_sentence,
        )


class StoppedRunner:
    """A buyer agent that looks at its authority and stops without asking for an offer."""

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        authority = tools.get_authority(identity)
        step = AgentStep(index=1, tool="get_authority", ok=True, result={"profile_id": authority.profile.profile_id})
        return AgentRun(
            text=text, model="fake-model-1", recorded=True, steps=(step,), stopped_at_cap=True,
            report="I could not tell which product is meant, so I asked for no offer.",
        )


class DownRunner:
    """A buyer agent whose model cannot be reached."""

    def run_agent(self, text: str, identity: Identity, tools: GatewayService) -> AgentRun:
        raise SupplierUnavailable("The model behind the buyer agent cannot be reached right now.")


class RenamingCatalog:
    """The real catalog, with a hostile product name on a few products: names are untrusted input."""

    def __init__(self, inner: ProductCatalog) -> None:
        self._inner = inner

    def _renamed(self, product: Product) -> Product:
        if product.id not in RENAMED:
            return product
        return product.model_copy(update={"name_en": (product.name_en or "") + HOSTILE_NAME})

    def get_product(self, product_id: str) -> Product | None:
        product = self._inner.get_product(product_id)
        return None if product is None else self._renamed(product)

    def search(self, query: ProductQuery) -> SearchResult:
        result = self._inner.search(query)
        return result.model_copy(update={"products": tuple(self._renamed(product) for product in result.products)})

    def same_category(self, product_id: str, digits: int) -> tuple[Product, ...]:
        return tuple(self._renamed(product) for product in self._inner.same_category(product_id, digits))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@pytest.fixture(scope="session")
def fakes() -> Any:
    """The fakes of this file, for a test module to build a client with (modules cannot import one another)."""
    return SimpleNamespace(
        FakeParser=FakeParser, FakeRunner=FakeRunner, NoParser=NoParser, DownRunner=DownRunner,
        StoppedRunner=StoppedRunner,
        FREE_TEXT=FREE_TEXT, HOSTILE_NAME=HOSTILE_NAME,
    )


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(autouse=True)
def only_the_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    """The agent package and the MCP surface are not loaded, whatever state their own tasks are in."""
    real = hooks.optional_module
    hidden = (hooks.AGENT_MODULE, hooks.MCP_MODULE)
    monkeypatch.setattr(hooks, "optional_module", lambda name: None if name in hidden else real(name))


@pytest.fixture
def make_client(settings: Settings, catalog: ProductCatalog) -> Iterator[Callable[..., TestClient]]:
    """A client over a gateway built with the given replacements (`catalog`, `request_parser`, `agent_runner`)."""
    opened: list[TestClient] = []

    def make(base_url: str = "http://testserver", **replacements: Any) -> TestClient:
        given = {"catalog": catalog, **replacements}
        app = create_app(settings, parts=build_parts(settings, **given))
        client = TestClient(app, base_url=base_url)
        client.__enter__()
        opened.append(client)
        return client

    yield make
    for client in opened:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """The gateway as it is until the agent package lands: no parser, no buyer agent."""
    return make_client()


@pytest.fixture
def parts(client: TestClient) -> Parts:
    return client.app.state.parts  # type: ignore[attr-defined]


@pytest.fixture
def hostile_client(make_client: Callable[..., TestClient], catalog: ProductCatalog) -> TestClient:
    return make_client(catalog=RenamingCatalog(catalog))


@pytest.fixture(scope="session")
def identities() -> Callable[[TestClient], dict[str, Identity]]:
    def by_id(client: TestClient) -> dict[str, Identity]:
        registry = client.app.state.parts.tokens  # type: ignore[attr-defined]
        return {identity.id: identity for identity in registry.identities}

    return by_id


@pytest.fixture(scope="session")
def form_fields() -> Callable[..., Form]:
    """The hidden fields of the first form of a page: the CSRF token and, on the first page, the run key."""

    def read(client: TestClient, path: str = "/") -> Form:
        page = client.get(path)
        assert page.status_code == 200, page.text
        fields = {"csrf": CSRF_FIELD.search(page.text).group(1)}  # type: ignore[union-attr]
        run_key = RUN_KEY_FIELD.search(page.text)
        return fields if run_key is None else {**fields, "run_key": run_key.group(1)}

    return read


@pytest.fixture(scope="session")
def run_example(form_fields: Callable[..., Form]) -> Post:
    """Click one of the examples on the first page and follow the redirect to its result."""

    def post(client: TestClient, example: str) -> Any:
        return client.post("/run", data={**form_fields(client), "example": example})

    return post


@pytest.fixture(scope="session")
def run_text(form_fields: Callable[..., Form]) -> Post:
    """Paste a text, choose who is asking and press Run."""

    def post(client: TestClient, text: str, who: str = "agent:hotel-kitchen") -> Any:
        return client.post("/run", data={**form_fields(client), "text": text, "who": who})

    return post


@pytest.fixture(scope="session")
def act_as(form_fields: Callable[..., Form]) -> Post:
    """Choose the demo approver on the approvals page."""

    def post(client: TestClient, approver_id: str) -> Any:
        fields = form_fields(client, "/approvals")
        return client.post("/approvals/as", data={"csrf": fields["csrf"], "approver": approver_id})

    return post


@pytest.fixture(scope="session")
def decide(form_fields: Callable[..., Form]) -> Post:
    """Approve or reject the one pending approval the chosen approver sees."""

    def post(client: TestClient, approval_id: str, decision: str, **extra: str) -> Any:
        fields = form_fields(client, "/approvals")
        data = {"csrf": fields["csrf"], "decision": decision, **extra}
        return client.post(f"/approvals/{approval_id}/decision", data=data)

    return post


@pytest.fixture(scope="session")
def only_order() -> Callable[..., Any]:
    """The one order of a buyer, read through the service as its agent."""

    def read(client: TestClient, agent_id: str = "agent:hotel-kitchen") -> Any:
        parts = client.app.state.parts  # type: ignore[attr-defined]
        agent = next(identity for identity in parts.tokens.identities if identity.id == agent_id)
        orders = parts.service.list_orders(agent)
        assert len(orders) == 1, orders
        return orders[0]

    return read
