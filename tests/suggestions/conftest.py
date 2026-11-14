"""Fixtures for the suggestions' tests: a factory of small synthetic order histories.

The product ids are real (tonight's recording); the names are short stand-ins so the sentences read in a test.
No test here loads the catalog, calls a live service or reads `.env`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from typing import Any

import pytest

from tta.contracts.customer import Customer
from tta.suggestions import OrderHistory, history_of

FIRST_MONDAY = date(2026, 9, 21)
WEEKLY = 7
# product id: (product type, unit) of the usual products a test history may name
USUAL: dict[str, tuple[str, str]] = {
    "469363": ("milk", "L"),
    "463047": ("milk", "L"),
    "463797": ("cream", "L"),
    "464615": ("yoghurt", "KG"),
    "464013": ("plant_drink", "L"),
    "473424": ("plant_drink", "L"),
    "470863": ("plant_drink", "L"),
    "466988": ("beef_chuck", "KG"),
}
NAMES = {
    "469363": "Arla milk",
    "463047": "Arla whole milk",
    "463797": "Arla cooking cream",
    "464615": "Valio greek yoghurt",
    "464013": "Alpro soya drink",
    "473424": "Alpro rice drink",
    "470863": "Oatly oat drink",
}


def build_customer(orders: Sequence[Mapping[str, Any]], *, start: date = FIRST_MONDAY, every: int = WEEKLY,
                   customer_id: str = "test-kitchen") -> Customer:
    named = sorted({product_id for order in orders for product_id in order})
    usual = [{"product_id": product_id, "product_type": USUAL[product_id][0], "unit": USUAL[product_id][1],
              "use": "SERVED"} for product_id in named or ["469363"]]
    history = [{"delivered_on": start + timedelta(days=every * week), "quantities": dict(order)}
               for week, order in enumerate(orders)]
    return Customer.model_validate({
        "customer_id": customer_id, "synthetic": True, "name": "Test Kitchen", "kind": "Hotel kitchen",
        "contact": {"name": "Test Person", "title": "Chef"}, "people": {"purchasing_manager": "Test Person"},
        "usual": usual, "history": history,
    })


@pytest.fixture
def make_history() -> Callable[..., OrderHistory]:
    """`make_history([{"469363": 100, "463797": 10}, ...])`: one weekly order per mapping, oldest first."""

    def make(orders: Sequence[Mapping[str, Any]], *, names: Mapping[str, str] | None = None,
             **options: Any) -> OrderHistory:
        return history_of(build_customer(orders, **options), NAMES if names is None else names)

    return make


# --- The gateway's parts in replay, for `suggestions_for` and the guard: tonight's recording, no live service -----

from dataclasses import dataclass  # noqa: E402
from datetime import datetime  # noqa: E402
from decimal import Decimal  # noqa: E402

from tta.catalog import ProductCatalog  # noqa: E402
from tta.config import Settings  # noqa: E402
from tta.contracts.common import Identity, IdentityKind  # noqa: E402
from tta.contracts.offer import Offer  # noqa: E402
from tta.contracts.policy import BuyerProfile  # noqa: E402
from tta.contracts.request import PurchaseRequest  # noqa: E402
from tta.contracts.standing import StandingOrder  # noqa: E402
from tta.customers import shipped_customer  # noqa: E402
from tta.offers import OfferDeps, OfferService  # noqa: E402
from tta.policy import RulePolicyEngine  # noqa: E402
from tta.standing.demo import past_renewals, standing_order_of  # noqa: E402
from tta.suggestions import SuggestionList, SuggestionPorts, suggestions_for  # noqa: E402
from tta.valio import ReplayGateway  # noqa: E402

CAPTURE = "2026-11-14-demo"
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")  # the runbook's demo clock
MONDAY = "2026-11-16"


@dataclass(frozen=True)
class World:
    """Everything `suggestions_for` reads, at one clock."""

    catalog: ProductCatalog
    policy: RulePolicyEngine
    replay: ReplayGateway
    offers: OfferService

    @property
    def ports(self) -> SuggestionPorts:
        return SuggestionPorts(catalog=self.catalog, gateway=self.replay, clock=self.replay.clock)

    def profile(self, customer_id: str) -> BuyerProfile:
        return self.policy.get_profile(customer_id)

    def request(self, *lines: Mapping[str, Any], **fields: Any) -> PurchaseRequest:
        return PurchaseRequest.model_validate({"needed_by": MONDAY, "lines": list(lines), **fields})

    def offer(self, customer_id: str, request: PurchaseRequest) -> Offer:
        agent = Identity(kind=IdentityKind.AGENT, id=f"agent:{customer_id}", display_name="Test agent",
                         profile_id=customer_id)
        return self.offers.build_offer(request, agent)

    def standing_orders(self, customer_id: str) -> tuple[StandingOrder, ...]:
        """The customer file's standing orders as the store would hold them (`tta.standing.demo`)."""
        customer, now = shipped_customer(customer_id), self.replay.clock.now()
        assert customer is not None
        found = []
        for entry in customer.standing_orders:
            ids = [line.product_id for line in entry.lines]
            lines = self.replay.price(ids).by_id()
            prices = {product_id: line.catalog_price.value for product_id, line in lines.items()
                      if line.catalog_price is not None}
            renewals = past_renewals(customer, entry, prices, now)
            found.append(standing_order_of(customer, entry, f"agent:{customer_id}", renewals, now))
        return tuple(found)

    def suggest(self, customer_id: str, *lines: Mapping[str, Any], **options: Any) -> SuggestionList:
        """`suggestions_for` for one request of a shipped customer, on the offer built for it."""
        request = self.request(*lines)
        return suggestions_for(shipped_customer(customer_id), request, self.offer(customer_id, request),
                               profile=self.profile(customer_id), ports=self.ports, **options)


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def policy() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


def _world(catalog: ProductCatalog, policy: RulePolicyEngine, clock: datetime | None) -> World:
    replay = ReplayGateway(Settings.for_tests(tta_replay_capture=CAPTURE).replay_capture_dir, demo_clock=clock)
    offers = OfferService(OfferDeps(catalog=catalog, gateway=replay, policy=policy, clock=replay.clock,
                                    day_spend=lambda _profile_id: Decimal(0)))
    return World(catalog=catalog, policy=policy, replay=replay, offers=offers)


@pytest.fixture(scope="session", params=["recording", "demo"])
def world(request: pytest.FixtureRequest, catalog: ProductCatalog, policy: RulePolicyEngine) -> World:
    """The parts at each of the two clocks: the recording's instant and the demo clock."""
    return _world(catalog, policy, None if request.param == "recording" else DEMO_CLOCK)


@pytest.fixture(scope="session")
def world_now(catalog: ProductCatalog, policy: RulePolicyEngine) -> World:
    """The parts at the recording's instant only, for a test that does not depend on the clock."""
    return _world(catalog, policy, None)
