"""Fixtures for the end-to-end scenarios (SPEC section 13): the whole gateway over HTTP, in replay.

The app is built as it runs for the demo: `TTA_ENV=demo`, tonight's capture, the real buyer agent package with
no Gemini key (so it answers from `fixtures/agent/`), the MCP surface and the pages mounted. Each test gets an
empty database: in replay the data clock is pinned, so the day's spend of one database never resets.

Tests check what the gateway decides (products, quantities, totals, verdicts, rules, statuses, audit events),
never the words of a model's reading: the recordings may be replaced by real Gemini answers.
Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.errors import PROBLEM_CONTENT_TYPE, PROBLEM_TYPE_BASE

CAPTURE = "2026-11-14-demo"  # tonight's capture, Saturday 14 Nov 2026 02:52 server time
MONDAY = "2026-11-16"
EVENT_PREFIX = "tta.v1."
# The demonstration tokens of src/tta/api/demo_tokens.yaml. They are public by design.
TOKENS = {
    "hotel": "demo-agent-hotel-kitchen",
    "ward": "demo-agent-allergy-ward",
    "hotel:purchasing_manager": "demo-approver-hotel-purchasing",
    "hotel:finance": "demo-approver-hotel-finance",
    "hotel:dietitian": "demo-approver-hotel-dietitian",
    "ward:purchasing_manager": "demo-approver-ward-purchasing",
    "ward:finance": "demo-approver-ward-finance",
    "ward:dietitian": "demo-approver-ward-dietitian",
    "supplier": "demo-supplier-valio-aimo",
}

# The sentences of the demo. The first two have a recording in fixtures/agent/; the others are sent typed.
SCENARIO_1_TEXT = "1,000 litres of lactose-free milk by Monday"
SCENARIO_2_TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
SCENARIO_3_TEXT = "100 litres of Oddlygood Barista oat drink, product 473609, by Monday"
BACKUP_TEXT = "30 kg beef chuck"


def milk_request(litres: int) -> dict[str, Any]:
    """Scenario 1 as a typed request, for any quantity of lactose-free milk."""
    return {
        "needed_by": MONDAY,
        "lines": [{
            "text": f"{litres:,} litres of lactose-free milk by Monday", "product_type": "milk",
            "required_claims": ["FREE_FROM_LACTOSE"], "quantity": litres, "unit": "L",
        }],
    }


SCENARIO_2_REQUEST = {
    "needed_by": MONDAY,
    "require_confirmed": True,
    "lines": [{
        "text": SCENARIO_2_TEXT, "product_type": "plant_drink", "quantity": 200, "unit": "L",
        "exclude_allergens": ["AM", "AW"],
    }],
}
SCENARIO_3_REQUEST = {
    "needed_by": MONDAY,
    "lines": [{"text": SCENARIO_3_TEXT, "product_ids": ["473609"], "quantity": 100, "unit": "L"}],
}


def beef_request(kilos: int) -> dict[str, Any]:
    """The backup as a typed request: no `needed_by`, as the sentence names no date."""
    line = {"text": f"{kilos} kg beef chuck", "product_type": "beef_chuck", "quantity": kilos, "unit": "KG"}
    return {"lines": [line]}


class Demo:
    """The gateway's REST interface as the demo uses it. Every call asserts its status and returns the JSON."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self._keys = 0

    @staticmethod
    def headers(who: str, key: str | None = None) -> dict[str, str]:
        found = {"Authorization": f"Bearer {TOKENS[who]}"}
        return found if key is None else {**found, "Idempotency-Key": key}

    def _json(self, response: Any, status: int) -> Any:
        assert response.status_code == status, response.text
        return response.json()

    def run_agent(self, who: str, text: str) -> dict[str, Any]:
        return self._json(self.client.post("/v1/agent/run", json={"text": text}, headers=self.headers(who)), 200)

    def parse(self, who: str, text: str) -> dict[str, Any]:
        return self._json(self.client.post("/v1/requests/parse", json={"text": text}, headers=self.headers(who)), 200)

    def offer(self, who: str, request: dict[str, Any]) -> dict[str, Any]:
        return self._json(self.client.post("/v1/offers", json=request, headers=self.headers(who)), 201)

    def get_offer(self, who: str, offer_id: str) -> dict[str, Any]:
        return self._json(self.client.get(f"/v1/offers/{offer_id}", headers=self.headers(who)), 200)

    def next_key(self) -> str:
        self._keys += 1
        return f"e2e-{self._keys}"

    def order(self, who: str, offer: dict[str, Any], option: int = 0, key: str | None = None) -> dict[str, Any]:
        body = {"offer_id": offer["offer_id"], "option_id": offer["options"][option]["option_id"]}
        headers = self.headers(who, key or self.next_key())
        return self._json(self.client.post("/v1/orders", json=body, headers=headers), 201)

    def get_order(self, who: str, order_id: str) -> dict[str, Any]:
        return self._json(self.client.get(f"/v1/orders/{order_id}", headers=self.headers(who)), 200)

    def orders(self, who: str) -> list[dict[str, Any]]:
        return self._json(self.client.get("/v1/orders", headers=self.headers(who)), 200)

    def pending(self, who: str) -> list[dict[str, Any]]:
        return self._json(self.client.get("/v1/approvals?status=pending", headers=self.headers(who)), 200)

    def decide(self, who: str, approval_id: str, decision: str = "APPROVE", note: str | None = None) -> Any:
        body = {"decision": decision, **({} if note is None else {"note": note})}
        return self.client.post(f"/v1/approvals/{approval_id}/decision", json=body, headers=self.headers(who))

    def approval_of(self, buyer: str, order: dict[str, Any]) -> dict[str, Any]:
        """The pending approval of an order, as the buyer's purchasing manager sees it in the queue."""
        queue = self.pending(f"{buyer}:purchasing_manager")
        found = [approval for approval in queue if approval["approval_id"] == order["approval_id"]]
        assert len(found) == 1, queue
        return found[0]

    def approve_all_roles(self, buyer: str, order: dict[str, Any], note: str) -> dict[str, Any]:
        """Each role the order's approval needs approves it, through that role's demo approver."""
        approval = self.approval_of(buyer, order)
        decided: dict[str, Any] = {}
        for role in approval["required_roles"]:
            decided = self._json(self.decide(f"{buyer}:{role}", approval["approval_id"], note=note), 200)
        return decided

    def audit(self, who: str, order_id: str, reader: str | None = None) -> dict[str, Any]:
        query = f"order_id={order_id}" + ("" if reader is None else f"&reader={reader}")
        return self._json(self.client.get(f"/v1/audit?{query}", headers=self.headers(who)), 200)

    def substitutes(self, who: str, product_id: str, query: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(f"/v1/products/{product_id}/substitutes", json=query, headers=self.headers(who))
        return self._json(response, 200)

    def search(self, who: str, query: dict[str, Any]) -> dict[str, Any]:
        return self._json(self.client.post("/v1/products/search", json=query, headers=self.headers(who)), 200)

    def product(self, who: str, product_id: str) -> dict[str, Any]:
        return self._json(self.client.get(f"/v1/products/{product_id}", headers=self.headers(who)), 200)


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    """The real catalog (17,546 products), built once per test session."""
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture
def demo_settings(tmp_path: Path) -> Settings:
    """The demo's settings: replay, `demo` environment, an empty database under `tmp_path`, no key of any kind."""
    settings = Settings.for_tests(tta_data_dir=tmp_path / "var", tta_env="demo", tta_replay_capture=CAPTURE)
    assert not settings.has_gemini_key and not settings.has_valio_key
    return settings


@pytest.fixture
def demo(demo_settings: Settings, catalog: ProductCatalog) -> Iterator[Demo]:
    """The whole gateway as the demo runs it, with the buyer agent package found by the gateway's own hooks."""
    app = create_app(demo_settings, parts=build_parts(demo_settings, catalog=catalog))
    with TestClient(app) as client:
        health = client.get("/healthz").json()
        assert health["agent"] == {"request_parser": True, "agent_runner": True}, health
        assert health["surfaces"] == {"mcp": True, "pages": True}, health
        assert (health["mode"], health["source"]) == ("replay", "replay"), health
        yield Demo(client)


@pytest.fixture(scope="session")
def money() -> Any:
    """A JSON number of the gateway as an exact amount: `money(2580.64) == Decimal("2580.64")`."""
    return lambda value: Decimal(str(value))


@pytest.fixture(scope="session")
def event_types() -> Any:
    """The audit event types of a view, without the CloudEvents prefix, in time order."""
    return lambda view: [event["type"].removeprefix(EVENT_PREFIX) for event in view["events"]]


@pytest.fixture(scope="session")
def fired() -> Any:
    """The rule ids that fired for an option, as a set."""
    return lambda option: {rule["rule_id"] for rule in option["decision"]["fired"]}


@pytest.fixture(scope="session")
def lines_of() -> Any:
    """An option's lines as {product id: quantity in sales units}."""
    return lambda option: {line["product_id"]: Decimal(str(line["quantity"])) for line in option["lines"]}


@pytest.fixture(scope="session")
def assert_problem() -> Any:
    """Check an RFC 9457 problem of one type and status, and hand back its body."""

    def check(response: Any, slug: str, status: int) -> dict[str, Any]:
        assert response.status_code == status, response.text
        assert response.headers["content-type"] == PROBLEM_CONTENT_TYPE
        body = response.json()
        assert body["type"] == PROBLEM_TYPE_BASE + slug
        return body

    return check


@pytest.fixture(scope="session")
def texts() -> Any:
    """The demo's sentences and typed requests, for the test modules."""

    class Texts:
        scenario_1 = SCENARIO_1_TEXT
        scenario_2 = SCENARIO_2_TEXT
        scenario_3 = SCENARIO_3_TEXT
        backup = BACKUP_TEXT
        monday = MONDAY
        scenario_2_request = SCENARIO_2_REQUEST
        scenario_3_request = SCENARIO_3_REQUEST

        @staticmethod
        def milk(litres: int) -> dict[str, Any]:
            return milk_request(litres)

        @staticmethod
        def beef(kilos: int) -> dict[str, Any]:
            return beef_request(kilos)

    return Texts
