"""Fixtures for the end-to-end scenarios (SPEC section 13): the whole gateway over HTTP, in replay.

The app is built as it runs for the demo: `TTA_ENV=demo`, tonight's capture, the real buyer agent package with
no Gemini key (so it answers from `fixtures/agent/`), the MCP surface and the pages mounted. Each test gets an
empty database: in replay the data clock is pinned, so the day's spend of one database never resets.

Tests check what the gateway decides (products, quantities, totals, verdicts, rules, statuses, audit events),
never the words of a model's reading: the recordings may be replaced by real Gemini answers.
Every helper is a fixture, because test modules cannot import from one another (`--import-mode=importlib`).

Two apps: `demo` is the gateway at the recording's own clock (Saturday 14 Nov 2026 02:52 Helsinki time), with
`Settings.for_tests()` as it stands; `both` is the gateway as it is shipped for the demo (the customers' standing
orders loaded at start), once at the recording's clock and once at the demo clock (Thursday 12 Nov 2026 14:15,
`TTA_DEMO_CLOCK`), so a scenario of docs/DEMO.md is checked at the two clocks.
"""

from __future__ import annotations

import re
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
# The demonstration tokens of src/tta/api/demo_tokens.yaml. They are public by design. One person confirms
# (decision B54): the hotel's and the bakery's person who orders holds every role; at the ward and the school that
# person also holds finance's role, and the dietitian is the only second person.
DEMO_CLOCK = "2026-11-12T14:15:00+02:00"  # Thursday 12 Nov 2026 14:15 Helsinki time: the clock the demo is shown at
RECORDING, THURSDAY = "recording", "demo"  # the two clocks of the `both` fixture
TOKENS = {
    "hotel": "demo-agent-hotel-kitchen",
    "ward": "demo-agent-allergy-ward",
    "school": "demo-agent-school-kitchen",
    "bakery": "demo-agent-bakery-cafe",
    "school:purchasing_manager": "demo-approver-school-purchasing",
    "school:finance": "demo-approver-school-purchasing",
    "school:dietitian": "demo-approver-school-dietitian",
    "bakery:purchasing_manager": "demo-approver-bakery-owner",  # the owner holds every role of the bakery (B27)
    "bakery:finance": "demo-approver-bakery-owner",
    "bakery:dietitian": "demo-approver-bakery-owner",
    "hotel:purchasing_manager": "demo-approver-hotel-purchasing",
    "hotel:finance": "demo-approver-hotel-purchasing",
    "hotel:dietitian": "demo-approver-hotel-purchasing",
    "ward:purchasing_manager": "demo-approver-ward-purchasing",
    "ward:finance": "demo-approver-ward-purchasing",
    "ward:dietitian": "demo-approver-ward-dietitian",
    "supplier": "demo-supplier-valio-aimo",
}

# The people of src/tta/api/demo_tokens.yaml, as the buyer's view of the log names them.
APPROVERS = {
    "hotel:purchasing_manager": "Demo approver Hanna", "hotel:finance": "Demo approver Hanna",
    "hotel:dietitian": "Demo approver Hanna", "ward:purchasing_manager": "Demo approver Jussi",
    "ward:finance": "Demo approver Jussi", "ward:dietitian": "Demo approver Sari",
    "school:purchasing_manager": "Demo approver Päivi", "school:finance": "Demo approver Päivi",
    "school:dietitian": "Demo approver Riikka", "bakery:purchasing_manager": "Demo approver Marko",
    "bakery:finance": "Demo approver Marko", "bakery:dietitian": "Demo approver Marko",
}
# What Valio Aimo's view of a buyer's log never shows: a limit amount of any profile (src/tta/policy/profiles/),
# a customer's or a person's name, a profile id. A limit is printed without cents ("€750"), a total with them.
LIMIT_AMOUNTS = ("€750", "€3,000", "€500", "€1,500", "€250", "€800", "€300", "€1,000")
NAMES = (
    "Harbourside", "City Hospital", "Kilo School", "Kallio", "hotel-kitchen", "allergy-ward", "school-kitchen",
    "bakery-cafe", "Hanna", "Jussi", "Sari", "Päivi", "Riikka", "Marko",
)
# A GS1 allergen code as a word of its own, or an allergen named with its code as the buyer's view writes it.
ALLERGEN_CODE = re.compile(r"\b(AM|AW|AN|AP|AS|SA)\b|tree nuts|peanuts|sesame|excluding allergen")

# The sentences of the demo. The first two have a recording in fixtures/agent/; the others are sent typed.
SCENARIO_1_TEXT = "1,000 litres of lactose-free milk by Monday"
SCENARIO_2_TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
SCENARIO_3_TEXT = "100 litres of Oddlygood Barista oat drink, product 473609, by Monday"
BACKUP_TEXT = "30 kg beef chuck"
# The brief's own sentence (AIMO/CHALLENGE.md). The fixed-rules reader reads it as scenario 1's typed request.
BRIEF_TEXT = (
    "I need 1,000 litres of lactose-free milk by Monday. Find an option that meets our requirements based on "
    "price and availability."
)
# The other sentences of docs/DEMO.md, as the first page offers them (src/tta/ui/examples.py).
DIETITIAN_TEXT = "100 litres of Elovena barista oat drink, product 469512, by Monday; no milk, strict rule"
ALMOND_TEXT = "20 litres of almond drink by Monday"
PATTERN_TEXT = "100 litres of lactose-free milk by Monday"
FORMULA_CHANGED_TEXT = "40 kg of Valio crème fraîche, product 477055, by Monday, for baking"
FORMULA_KEPT_TEXT = "100 litres of whipping cream by Monday, for cakes"


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
    "lines": [{
        "text": SCENARIO_3_TEXT, "product_type": "plant_drink", "product_ids": ["473609"], "quantity": 100,
        "unit": "L",
    }],
}
DIETITIAN_REQUEST = {
    "needed_by": MONDAY,
    "lines": [{
        "text": DIETITIAN_TEXT, "product_type": "plant_drink", "product_ids": ["469512"], "quantity": 100,
        "unit": "L", "exclude_allergens": ["AM"], "allergen_strictness": "STRICT",
    }],
}
# The school's profile excludes tree nuts, peanuts and sesame under the strict rule: the request names none.
ALMOND_REQUEST = {
    "needed_by": MONDAY,
    "lines": [{
        "text": ALMOND_TEXT, "product_type": "plant_drink", "name_terms": ["almond"], "quantity": 20, "unit": "L",
    }],
}
FORMULA_CHANGED_REQUEST = {
    "needed_by": MONDAY,
    "lines": [{
        "text": FORMULA_CHANGED_TEXT, "product_ids": ["477055"], "quantity": 40, "unit": "KG", "keep_formula": True,
    }],
}
FORMULA_KEPT_REQUEST = {
    "needed_by": MONDAY,
    "lines": [{
        "text": FORMULA_KEPT_TEXT, "product_type": "cream", "name_terms": ["whipping"], "quantity": 100,
        "unit": "L", "keep_formula": True,
    }],
}


def beef_request(kilos: int) -> dict[str, Any]:
    """The backup as a typed request: no `needed_by`, as the sentence names no date."""
    line = {"text": f"{kilos} kg beef chuck", "product_type": "beef_chuck", "quantity": kilos, "unit": "KG"}
    return {"lines": [line]}


class Demo:
    """The gateway's REST interface as the demo uses it. Every call asserts its status and returns the JSON."""

    def __init__(self, client: TestClient, clock: str = RECORDING) -> None:
        self.client = client
        self.clock = clock  # RECORDING or THURSDAY: which of the two clocks this gateway judges deadlines against
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
        """Each person the order's approval needs approves it once, through that person's demo token: one
        person who holds several of the roles decides once for all of them."""
        approval = self.approval_of(buyer, order)
        decided: dict[str, Any] = {}
        for who in self.people(buyer, approval["required_roles"]):
            decided = self._json(self.decide(who, approval["approval_id"], note=note), 200)
        return decided

    @staticmethod
    def people(buyer: str, roles: list[str]) -> list[str]:
        """One "buyer:role" per person who holds any of these roles, in the roles' order."""
        first_role_of: dict[str, str] = {}
        for role in roles:
            first_role_of.setdefault(TOKENS[f"{buyer}:{role}"], f"{buyer}:{role}")
        return list(first_role_of.values())

    def approval_for(self, approver: str, order: dict[str, Any]) -> dict[str, Any]:
        """The pending approval of an order as one approver ("hotel:dietitian") finds it in the queue."""
        found = [approval for approval in self.pending(approver) if approval["approval_id"] == order["approval_id"]]
        assert len(found) == 1, self.pending(approver)
        return found[0]

    def confirm(self, buyer: str, order: dict[str, Any], note: str, option_id: str | None = None) -> dict[str, Any]:
        """Each person the order asks for approves it once, with a note; `option_id` takes another option of the
        offer."""
        decided: dict[str, Any] = {}
        for who in self.people(buyer, order["decision"]["required_roles"]):
            body = {"decision": "APPROVE", "note": note, **({} if option_id is None else {"option_id": option_id})}
            answer = self.client.post(
                f"/v1/approvals/{order['approval_id']}/decision", json=body, headers=self.headers(who)
            )
            decided = self._json(answer, 200)
        return decided

    def offer_audit(self, who: str, offer_id: str) -> dict[str, Any]:
        return self._json(self.client.get(f"/v1/audit?offer_id={offer_id}", headers=self.headers(who)), 200)

    def shop(self, kitchen: str, method: str, path: str, status: int = 200, **kwargs: Any) -> Any:
        """One call of the shop page (`/shop/api`), on this client's own demo book for that customer."""
        headers = {"X-Shop-Request": "1", "X-Shop-Kitchen": kitchen}
        return self._json(self.client.request(method, "/shop/api" + path, headers=headers, **kwargs), status)

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


@pytest.fixture(params=[RECORDING, THURSDAY])
def both(request: pytest.FixtureRequest, tmp_path: Path, catalog: ProductCatalog) -> Iterator[Demo]:
    """The gateway as it is shipped for the demo, at each of the two clocks in turn, on its own empty database.

    The customers' standing orders are loaded at start, as in the shipped settings (`Settings.for_tests()` leaves
    them out). `both.clock` says which clock is in force; a test pins a figure per clock only where they differ.
    """
    clock = {} if request.param == RECORDING else {"tta_demo_clock": DEMO_CLOCK}
    settings = Settings.for_tests(
        tta_data_dir=tmp_path / "var", tta_env="demo", tta_replay_capture=CAPTURE,
        tta_customer_standing_orders=True, **clock,
    )
    assert not settings.has_gemini_key and not settings.has_valio_key
    app = create_app(settings, parts=build_parts(settings, catalog=catalog))
    with TestClient(app) as client:
        health = client.get("/healthz").json()
        assert (health["mode"], health["source"]) == ("replay", "replay"), health
        assert health["clock"]["demo_clock_set"] is (request.param == THURSDAY), health
        yield Demo(client, request.param)


@pytest.fixture(scope="session")
def two_views() -> Any:
    """Check the log of a decided order as the buyer and as Valio Aimo read it, and hand both back.

    The trail verifies for both readers and holds the same events; the buyer's view names the person who decided
    and carries the note; Valio Aimo's view shows every rule that fired and never a limit amount, an excluded
    allergen, a name or the note.
    """

    def check(demo: Demo, buyer: str, order: dict[str, Any], *, decided_by: str, note: str) -> tuple[Any, Any]:
        own = demo.audit(buyer, order["order_id"])
        valio = demo.audit("supplier", order["order_id"])
        assert (own["reader"], valio["reader"]) == ("buyer", "supplier")
        assert own["chain"]["ok"] is True and valio["chain"]["ok"] is True
        kinds = [event["type"] for event in own["events"]]
        assert kinds == [event["type"] for event in valio["events"]]
        assert all(event["sentence"].strip() for view in (own, valio) for event in view["events"])

        read = " ".join(event["sentence"] for event in own["events"])
        assert APPROVERS[decided_by] in own["events"][-1]["sentence"], own["events"][-1]["sentence"]
        assert note in read

        shown = " ".join(event["sentence"] for event in valio["events"])
        for rule in order["decision"]["fired"]:
            assert rule["rule_id"] in shown, rule["rule_id"]
        for amount in LIMIT_AMOUNTS:
            assert not re.search(re.escape(amount) + r"(?![\d,]|\.\d)", shown), amount
        for private in (*NAMES, note):
            assert private not in shown, private
        assert not ALLERGEN_CODE.search(shown), ALLERGEN_CODE.search(shown)
        return own, valio

    return check


@pytest.fixture(scope="session")
def option_of() -> Any:
    """The one option of an offer that holds a product, whatever its place."""

    def find(offer: dict[str, Any], product_id: str) -> dict[str, Any]:
        found = [option for option in offer["options"]
                 if any(line["product_id"] == product_id for line in option["lines"])]
        assert len(found) == 1, [[line["product_id"] for line in option["lines"]] for option in offer["options"]]
        return found[0]

    return find


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
        brief = BRIEF_TEXT
        dietitian = DIETITIAN_TEXT
        almond = ALMOND_TEXT
        pattern = PATTERN_TEXT
        formula_changed = FORMULA_CHANGED_TEXT
        formula_kept = FORMULA_KEPT_TEXT
        scenario_2_request = SCENARIO_2_REQUEST
        scenario_3_request = SCENARIO_3_REQUEST
        dietitian_request = DIETITIAN_REQUEST
        almond_request = ALMOND_REQUEST
        formula_changed_request = FORMULA_CHANGED_REQUEST
        formula_kept_request = FORMULA_KEPT_REQUEST

        @staticmethod
        def milk(litres: int) -> dict[str, Any]:
            return milk_request(litres)

        @staticmethod
        def beef(kilos: int) -> dict[str, Any]:
            return beef_request(kilos)

    return Texts
