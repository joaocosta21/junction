"""The examples of `/openapi.json`: one request and one answer per route, taken from the demo scenarios.

Scores on the 15% "open, documented standards": a reader of the generated interface sees a real request and
the real answer to it. Nothing here is written by hand: the scenarios of SPEC section 13 are run through
the gateway's own service against the replay capture, in a private in-memory store, and each answer is kept
as the contract model serialises it. So an example cannot drift from the code.

Each scenario is run on its own. One that cannot be run is logged and named in `not_built`, and the others
are still built: the document is served without that example and says so. Building never raises.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from tta.api.docs import BuiltExamples
from tta.api.limits import CallKind, CallLimits, RateLimit
from tta.api.service import Gateway
from tta.api.wiring import Parts, wire
from tta.contracts.agent import AgentRun, AgentStep, ParseRequestBody
from tta.contracts.common import (
    ApproverRole,
    AuditReader,
    DecisionKind,
    Identity,
    IdentityKind,
    OrderStatus,
    Unit,
)
from tta.contracts.errors import TtaError
from tta.contracts.offer import Offer, SubstituteQuery
from tta.contracts.order import DecisionRequest, Order, PlaceOrderRequest
from tta.contracts.request import ProductQuery, PurchaseRequest, RequestLine
from tta.store import SqliteStore

# The scenarios of SPEC section 13. The profiles and the product are those of the demonstration.
HOTEL_PROFILE = "hotel-kitchen"
WARD_PROFILE = "allergy-ward"
SCENARIO_1_TEXT = "1,000 litres of lactose-free milk by Monday"
SCENARIO_2_TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
SCENARIO_3_PRODUCT = "473609"
SEARCH_EXAMPLE_LIMIT = 3
EXAMPLE_NOTE = "Checked against the standing order."
EXAMPLE_KEYS = ("scenario-1", "scenario-2")
MONDAY = 0
UNLIMITED_CALLS = 1_000_000  # the examples are built by the gateway itself, in a private store
RECORDED_MODEL = "recorded"

EVERY_EXAMPLE = "every example (the scenarios could not be set up)"
NOTHING_FITS = "{scenario}: the order and what follows it (the recorded capture holds nothing that fits the request)"

Json = Any
Named = dict[str, dict[str, Json]]  # example name -> {"summary": ..., "value": ...}

logger = logging.getLogger(__name__)


def _json(value: BaseModel | Iterable[BaseModel]) -> Json:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return [item.model_dump(mode="json") for item in value]


def _example(summary: str, value: BaseModel | Iterable[BaseModel]) -> dict[str, Json]:
    return {"summary": summary, "value": _json(value)}


def _next_monday(today: date) -> date:
    days = (MONDAY - today.weekday()) % 7 or 7
    return today + timedelta(days=days)


def scenario_requests(today: date) -> tuple[PurchaseRequest, PurchaseRequest]:
    """The typed requests of scenarios 1 and 2, "by Monday" counted from the capture's date."""
    monday = _next_monday(today)
    milk = RequestLine(
        text=SCENARIO_1_TEXT, product_type="milk", required_claims=("FREE_FROM_LACTOSE",), quantity=Decimal(1000),
        unit=Unit.L,
    )
    substitute = RequestLine(
        text=SCENARIO_2_TEXT, product_type="plant_drink", quantity=Decimal(200), unit=Unit.L,
        exclude_allergens=("AM", "AW"),
    )
    return (
        PurchaseRequest(needed_by=monday, lines=(milk,)),
        PurchaseRequest(needed_by=monday, require_confirmed=True, lines=(substitute,)),
    )


def _no_limits() -> CallLimits:
    return CallLimits(
        RateLimit(calls=UNLIMITED_CALLS), per_visitor=False, ceilings=dict.fromkeys(CallKind, UNLIMITED_CALLS)
    )


def _agent(profile_id: str) -> Identity:
    return Identity(
        kind=IdentityKind.AGENT, id=f"agent:{profile_id}", display_name="Example agent", profile_id=profile_id
    )


class _Examples:
    """Runs the scenarios and collects, per operation id, the request sent and the answer given."""

    def __init__(self, parts: Parts, store: SqliteStore) -> None:
        self._parts = parts
        self._service: Gateway = wire(
            catalog=parts.catalog, policy=parts.policy, gateway=parts.replay, clock=parts.replay.clock,
            store=store, limiter=_no_limits(),
        )[0]
        self._ward, self._hotel = _agent(WARD_PROFILE), _agent(HOTEL_PROFILE)
        self._orders: dict[str, Order] = {}  # the order each scenario ended with, for the steps that follow it
        self.requests: dict[str, Named] = {}
        self.answers: dict[str, Named] = {}
        self.not_built: list[str] = []

    def _keep(self, operation: str, name: str, summary: str, answer: Any, request: BaseModel | None = None) -> None:
        self.answers.setdefault(operation, {})[name] = _example(summary, answer)
        if request is not None:
            self.requests.setdefault(operation, {})[name] = _example(summary, request)

    def run(self) -> None:
        """Each step on its own: one that fails is logged and named, and the next one still runs."""
        steps: tuple[tuple[str, Callable[[], None]], ...] = (
            ("the lookups (authority, search, one product)", self._lookups),
            ("scenario 3 (ranked substitutes)", self._substitutes),
            ("scenario 2 (the allergy ward's order and its audit trail)", self._scenario_2),
            ("scenario 1 (the hotel kitchen's order and its approval)", self._scenario_1),
            ("the pasted request and the agent's run", self._pasted),
        )
        for name, step in steps:
            try:
                step()
            except TtaError as error:
                logger.warning("No OpenAPI example for %s: it could not be run (%s).", name, error.slug)
                self.not_built.append(name)
            except Exception:
                # The document is still served: a fault here must not take the published interface down.
                logger.exception("No OpenAPI example for %s: it failed in a way nobody expected.", name)
                self.not_built.append(name)

    def _requests(self) -> tuple[PurchaseRequest, PurchaseRequest]:
        return scenario_requests(self._parts.replay.time_now.date())

    def _lookups(self) -> None:
        service, agent = self._service, self._ward
        self._keep("get_authority", "allergy_ward", "What the allergy ward's agent may decide alone",
                   service.get_authority(agent))
        query = ProductQuery(product_type="plant_drink", limit=SEARCH_EXAMPLE_LIMIT)
        found = service.search_products(agent, query)
        self._keep("search_products", "plant_drinks", "The first three plant drinks of the catalog", found, query)
        if found.products:
            self._keep("get_product", "plant_drink", "One product with its allergen statements and claims",
                       service.get_product(agent, found.products[0].id))

    def _substitutes(self) -> None:
        substitutes = SubstituteQuery()
        self._keep(
            "find_substitutes", "scenario_3", f"Scenario 3: ranked substitutes of product {SCENARIO_3_PRODUCT}",
            self._service.find_substitutes(self._hotel, SCENARIO_3_PRODUCT, substitutes), substitutes,
        )

    def _scenario_2(self) -> None:
        summary = "Scenario 2: the allergy ward's agent"
        order = self._order(self._ward, self._requests()[1], "scenario_2", summary, EXAMPLE_KEYS[1])
        self._audit(self._ward, order)

    def _scenario_1(self) -> None:
        summary = "Scenario 1: the hotel kitchen's agent"
        self._approval(self._order(self._hotel, self._requests()[0], "scenario_1", summary, EXAMPLE_KEYS[0]))

    def _order(self, agent: Identity, request: PurchaseRequest, name: str, summary: str, key: str) -> Order | None:
        offer: Offer = self._service.create_offer(agent, request)
        self._keep("create_offer", name, summary, offer, request)
        self.answers.setdefault("get_offer", {name: _example(summary, offer)})  # one is enough for a read
        if not offer.options:
            self.not_built.append(NOTHING_FITS.format(scenario=name.replace("_", " ")))
            return None
        placed = PlaceOrderRequest(offer_id=offer.offer_id, option_id=offer.options[0].option_id)
        order = self._service.place_order(agent, placed.offer_id, placed.option_id, key)
        self._keep("place_order", name, f"{summary} orders the first option", order, placed)
        self.answers.setdefault("get_order", {name: _example(summary, order)})
        listed = _example("The orders of the caller's buyer, newest first", self._service.list_orders(agent))
        self.answers.setdefault("list_orders", {name: listed})
        self._orders[name] = order
        return order

    def _approver(self, profile_id: str, role: ApproverRole) -> Identity | None:
        listed = self._parts.policy.get_profile(profile_id).approver_roles.get(role, ())
        if not listed:
            return None
        return Identity(
            kind=IdentityKind.APPROVER, id=listed[0], display_name="Example approver", profile_id=profile_id,
            roles=(role,),
        )

    def _approval(self, order: Order | None) -> None:
        """Scenario 1 leaves an order waiting for a human: the queue, then one decision."""
        if order is None or order.status is not OrderStatus.PENDING_APPROVAL or order.approval_id is None:
            return
        roles = order.decision.required_roles
        approver = self._approver(order.profile_id, roles[0]) if roles else None
        if approver is None:
            return
        self._keep("list_approvals", "scenario_1", "Scenario 1: the order waits for a human",
                   self._service.list_approvals(approver))
        decision = DecisionRequest(decision=DecisionKind.APPROVE, note=EXAMPLE_NOTE)
        decided = self._service.decide_approval(approver, order.approval_id, decision)
        self._keep("decide_approval", "scenario_1", "Scenario 1: a human with the role asked for approves", decided,
                   decision)

    def _audit(self, agent: Identity, order: Order | None) -> None:
        if order is None:
            return
        for reader in (AuditReader.BUYER, AuditReader.SUPPLIER):
            view = self._service.get_audit(agent, reader, order_id=order.order_id)
            self._keep("get_audit", reader.value, f"Scenario 2: the trail of the order as the {reader.value} sees it",
                       view)

    def _pasted(self) -> None:
        """The two routes that start from a pasted sentence. The trace is put together from the answers the
        gateway gave in scenario 2: no model is called to build an example."""
        self._keep("parse_request", "scenario_1", "Scenario 1: the pasted sentence as a typed request",
                   self._requests()[0], ParseRequestBody(text=SCENARIO_1_TEXT))
        order = self._orders.get("scenario_2")
        if order is None:
            return
        steps = (
            AgentStep(index=1, tool="get_authority", ok=True, result={"profile_id": order.profile_id}),
            AgentStep(index=2, tool="create_offer", ok=True, result={"offer_id": order.offer_id}),
            AgentStep(
                index=3, tool="place_order", ok=True,
                arguments={"offer_id": order.offer_id, "option_id": order.option_id},
                result={"order_id": order.order_id, "status": order.status.value}, sentence=order.status_sentence,
            ),
        )
        run = AgentRun(
            text=SCENARIO_2_TEXT, model=RECORDED_MODEL, recorded=True, steps=steps, offer_id=order.offer_id,
            order_id=order.order_id, order_status=order.status, report=order.status_sentence,
        )
        self._keep("run_agent", "scenario_2", "Scenario 2: the buyer agent's trace, from recorded data", run,
                   ParseRequestBody(text=SCENARIO_2_TEXT))


def build_examples(parts: Parts) -> BuiltExamples:
    """The examples of every scenario that can be run, and the names of those that cannot (another capture,
    another set of profiles, a fault). Never raises: the published interface is served either way."""
    try:
        store = SqliteStore()  # in memory: nothing of an example reaches the real order book or audit trail
    except Exception:
        logger.exception("No OpenAPI example was built: the private store could not be opened.")
        return BuiltExamples(requests={}, answers={}, not_built=(EVERY_EXAMPLE,))
    try:
        examples = _Examples(parts, store)
        examples.run()
        return BuiltExamples(examples.requests, examples.answers, tuple(examples.not_built))
    except Exception:
        logger.exception("No OpenAPI example was built: the scenarios could not be set up.")
        return BuiltExamples(requests={}, answers={}, not_built=(EVERY_EXAMPLE,))
    finally:
        store.close()
