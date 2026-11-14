"""The standing-order service: set up, list, read and renew a buyer's recurring orders (task STAND-1).

Scores on the 20% "what the agent can decide alone, what needs human sign-off, and how decisions are logged": a
renewal goes through the normal flow, offer then `place_order` on the top option, so every rule judges it, and rule
P-08 compares it with the history first. The verdict is the policy engine's; nothing here decides. Every step is in
the audit trail: the offer and order events of the gateway, plus "standing order created" and "renewed".

Who may call what, as in `tta.api.service`: an agent sets up and renews its own buyer's standing orders; an agent or
an approver of the buyer reads them; the supplier reads none.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from tta.contracts.audit import AuditContext, AuditEventType
from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, NotAuthorised, NotFound
from tta.contracts.offer import Offer
from tta.contracts.order import Order
from tta.contracts.ports import AuditSink, Clock, GatewayService, Store
from tta.contracts.request import PurchaseRequest
from tta.contracts.standing import (
    DriftReport,
    NewStandingOrder,
    Renewal,
    RenewalLine,
    RenewStandingOrder,
    StandingOrder,
)
from tta.orders.access import actor_of
from tta.policy.drift import assess_drift
from tta.standing.history import standing_history
from tta.standing.models import RenewalOutcome, StandingOrderDetail

ID_RANDOM_BYTES = 6
STANDING_ORDER_ID_PREFIX = "so_"
RENEWAL_ID_PREFIX = "ren_"
KEY_PREFIX = "standing:"  # the Idempotency-Key of a renewal's order: one per offer, so a retry never orders twice
# The most standing orders one buyer holds (review A3, finding F1). Ours and illustrative: a kitchen has a handful.
# Nothing deletes a standing order here, and each set-up writes an audit event that can never be removed, so
# without a ceiling one public token could fill the database and the trail.
MAX_STANDING_ORDERS_PER_BUYER = 20
# The most a list answers, as every other list of the gateway (`tta.api.service.MAX_LIST_ITEMS`).
MAX_LIST_ITEMS = 100

# Counts one set-up for this caller or raises `RateLimited`: the gateway's limit on calls that write to the trail.
CountSetUp = Callable[[Identity], None]

ONLY_AN_AGENT = "Only a buyer's agent sets up or renews a standing order."
NOT_FOR_THE_SUPPLIER = "The supplier reads its view of the audit trail (GET /v1/audit) and nothing else."
NO_SUCH_STANDING_ORDER = "No standing order has this id."
ALREADY_SET_UP = "Standing order {standing_order_id} is already set up; it is not set up twice."
NAMES_A_STANDING_ORDER = (
    "The request of a standing order names no standing order: each renewal sets standing_order_id itself."
)
WRONG_QUANTITIES = (
    "This standing order has {lines}, so a renewal gives {lines_count} quantities, one per line in order; "
    "this one gives {given}."
)
TOO_MANY_STANDING_ORDERS = (
    "This buyer already has {count} standing orders, the most one buyer sets up here. Renew one of them "
    "(POST /v1/standing-orders/{{standing_order_id}}/renew) instead of setting up another."
)
TOO_MANY_LINES = (
    "In this demonstration the request of a standing order has at most {limit} lines; this one has {count}. "
    "Set the others up as another standing order."
)
NO_OPTION = "No order was placed: no option fits the request this time. {notes}"


def _require_agent(identity: Identity) -> str:
    if identity.is_supplier:
        raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
    if not identity.is_agent or identity.profile_id is None:
        raise NotAuthorised(ONLY_AN_AGENT)
    return identity.profile_id


def _require_buyer_side(identity: Identity) -> str:
    if identity.is_supplier or identity.profile_id is None:
        raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
    return identity.profile_id


def _lines(count: int) -> str:
    return "1 request line" if count == 1 else f"{count} request lines"


def renewal_request(standing: StandingOrder, quantities: Sequence[Decimal] | None) -> PurchaseRequest:
    """The stored request, naming the standing order it renews, with this week's quantities when given. Checked
    again as a whole, so a renewal is held to every rule of the request contract."""
    data: dict[str, Any] = standing.request.model_dump()
    if quantities is not None:
        if len(quantities) != len(standing.request.lines):
            count = len(standing.request.lines)
            raise InvalidRequest(WRONG_QUANTITIES.format(lines=_lines(count), lines_count=count, given=len(quantities)))
        pairs = zip(data["lines"], quantities, strict=True)
        data["lines"] = [{**line, "quantity": quantity} for line, quantity in pairs]
    return PurchaseRequest.model_validate({**data, "standing_order_id": standing.standing_order_id})


def renewal_of(standing: StandingOrder, offer: Offer, order: Order) -> Renewal:
    """What the order of this renewal holds, as the history keeps it: per product, the quantity of its request line
    that it covers, in that line's unit, and the net price per sales unit."""
    units = {entry.request_line_index: entry.unit for entry in order.option.coverage}
    lines = tuple(
        RenewalLine(
            request_line_index=line.request_line_index, product_id=line.product_id, quantity=line.covers,
            unit=units.get(line.request_line_index, standing.request.lines[line.request_line_index].unit),
            unit_net_price_eur=line.unit_net_price,
        )
        for line in order.option.lines
    )
    return Renewal(
        renewal_id=f"{RENEWAL_ID_PREFIX}{secrets.token_hex(ID_RANDOM_BYTES)}",
        standing_order_id=standing.standing_order_id, renewed_at=offer.time_now, lines=lines,
        offer_id=offer.offer_id, order_id=order.order_id, synthetic=False,
    )


class StandingOrders:
    """Over the `Store`, the `AuditSink`, the gateway service (`create_offer`, `place_order`, `get_authority`, each
    checking the caller and its rate limits) and the data clock.

    A renewal is limited by the gateway service it goes through. A set-up goes through no offer, so it has its own
    limits: `count_set_up` (the rate limit), `max_request_lines` (the demonstration's limit of lines per request;
    None: the contract's 20) and `MAX_STANDING_ORDERS_PER_BUYER`, which always holds."""

    def __init__(
        self, *, store: Store, audit: AuditSink, gateway: GatewayService, clock: Clock,
        count_set_up: CountSetUp | None = None, max_request_lines: int | None = None,
    ) -> None:
        self._store = store
        self._audit = audit
        self._gateway = gateway
        self._clock = clock
        self._count_set_up = count_set_up
        self._max_request_lines = max_request_lines

    def with_limits(
        self, *, count_set_up: CountSetUp | None = None, max_request_lines: int | None = None
    ) -> StandingOrders:
        """A new service over the same parts with these limits on a set-up; a limit not given stays as it is."""
        return StandingOrders(
            store=self._store, audit=self._audit, gateway=self._gateway, clock=self._clock,
            count_set_up=count_set_up or self._count_set_up,
            max_request_lines=self._max_request_lines if max_request_lines is None else max_request_lines,
        )

    def now(self) -> datetime:
        """The data clock: pinned to the capture in replay."""
        return self._clock.now()

    # --- setting up ---------------------------------------------------------------------------------------

    def create(self, identity: Identity, body: NewStandingOrder) -> StandingOrder:
        """Raises `RateLimited` and `InvalidRequest` (too many lines, or the buyer's 20 are set up) before
        anything is written."""
        profile_id = _require_agent(identity)
        if self._count_set_up is not None:
            self._count_set_up(identity)
        limit, count = self._max_request_lines, len(body.request.lines)
        if limit is not None and count > limit:
            raise InvalidRequest(TOO_MANY_LINES.format(limit=limit, count=count))
        standing = StandingOrder(
            standing_order_id=f"{STANDING_ORDER_ID_PREFIX}{secrets.token_hex(ID_RANDOM_BYTES)}",
            profile_id=profile_id, agent_id=identity.id, name=body.name, request=self._template(body.request),
            cadence_days=body.cadence_days, created_at=self._clock.now(),
        )
        return self.set_up(identity, standing)

    def set_up(self, identity: Identity, standing: StandingOrder, history: tuple[Renewal, ...] = ()) -> StandingOrder:
        """Store a standing order with the past renewals it starts with (the demonstration's synthetic ones) and its
        audit event, all in one unit of work. Raises `InvalidRequest` for an id already set up, and for a buyer
        that already holds `MAX_STANDING_ORDERS_PER_BUYER`: counted inside the unit of work, so two set-ups at the
        same moment cannot both be the twentieth."""
        if _require_agent(identity) != standing.profile_id:
            raise NotAuthorised(ONLY_AN_AGENT)
        if self._store.get_standing_order(standing.standing_order_id) is not None:
            raise InvalidRequest(ALREADY_SET_UP.format(standing_order_id=standing.standing_order_id))
        facts = {
            "standing_order_id": standing.standing_order_id, "standing_order_name": standing.name,
            "cadence_days": standing.cadence_days, "synthetic_renewals": sum(renewal.synthetic for renewal in history),
        }
        with self._store.atomic():
            held = len(self._store.list_standing_orders(standing.profile_id))
            if held >= MAX_STANDING_ORDERS_PER_BUYER:
                raise InvalidRequest(TOO_MANY_STANDING_ORDERS.format(count=held))
            self._store.save_standing_order(standing)
            for renewal in history:
                self._store.save_renewal(renewal)
            self._audit.record(
                AuditEventType.STANDING_ORDER_CREATED, actor_of(identity),
                AuditContext(profile_id=standing.profile_id, request=standing.request, facts=facts),
            )
        return standing

    @staticmethod
    def _template(request: PurchaseRequest) -> PurchaseRequest:
        if request.standing_order_id is not None:
            raise InvalidRequest(NAMES_A_STANDING_ORDER)
        return request

    # --- reading ------------------------------------------------------------------------------------------

    def list(self, identity: Identity) -> tuple[StandingOrder, ...]:
        """The buyer's standing orders in the order they were set up, at most `MAX_LIST_ITEMS`."""
        return self._store.list_standing_orders(_require_buyer_side(identity))[:MAX_LIST_ITEMS]

    def find(self, identity: Identity, standing_order_id: str) -> StandingOrder | None:
        """The caller's own buyer's standing order, or None: another buyer's reads as one nobody set up.
        The caller is checked before anything is looked up, so the supplier's token is refused the same way for
        an id that exists and for one that does not (security review, finding L3)."""
        profile_id = _require_buyer_side(identity)
        standing = self._store.get_standing_order(standing_order_id)
        if standing is None or standing.profile_id != profile_id:
            return None
        return standing

    def get(self, identity: Identity, standing_order_id: str) -> StandingOrderDetail:
        standing = self._own(identity, standing_order_id)
        return StandingOrderDetail(standing_order=standing, renewals=self._store.list_renewals(standing_order_id))

    def _own(self, identity: Identity, standing_order_id: str) -> StandingOrder:
        standing = self.find(identity, standing_order_id)
        if standing is None:
            raise NotFound(NO_SUCH_STANDING_ORDER)
        return standing

    # --- renewing -----------------------------------------------------------------------------------------

    def renew(self, identity: Identity, standing_order_id: str, body: RenewStandingOrder) -> RenewalOutcome:
        """Offer from the stored request, then the top option through `place_order`: the policy decides, P-08
        among its rules. Errors of the order step (`PolicyBlocked`, `OfferStale`, ...) reach the caller as they do
        on POST /v1/orders, after the gateway's own audit events; nothing joins the history then."""
        _require_agent(identity)
        standing = self._own(identity, standing_order_id)
        offer = self._gateway.create_offer(identity, renewal_request(standing, body.quantities))
        if not offer.options:
            self._record(identity, standing, offer, None, None, None)
            notes = " ".join(offer.notes)
            return RenewalOutcome(standing_order=standing, offer=offer, sentence=NO_OPTION.format(notes=notes).strip())
        option = offer.options[0]
        order = self._gateway.place_order(identity, offer.offer_id, option.option_id, f"{KEY_PREFIX}{offer.offer_id}")
        drift = self._drift(identity, standing, offer, order)
        renewal = renewal_of(standing, offer, order)
        self._record(identity, standing, offer, order, drift, renewal)
        return RenewalOutcome(
            standing_order=standing, offer=offer, option_id=option.option_id, order=order, drift=drift,
            renewal=renewal, sentence=f"{drift.sentence} {order.status_sentence}",
        )

    def _drift(self, identity: Identity, standing: StandingOrder, offer: Offer, order: Order) -> DriftReport:
        """The report of the history the policy read for this order, under the profile in force."""
        history = standing_history(
            self._store, standing.profile_id, standing.standing_order_id, excluding_offer_id=offer.offer_id
        )
        profile = self._gateway.get_authority(identity).profile
        return assess_drift(order.option, history, profile.standing_order_drift_ratio)

    def _record(
        self, identity: Identity, standing: StandingOrder, offer: Offer, order: Order | None,
        drift: DriftReport | None, renewal: Renewal | None,
    ) -> None:
        facts: dict[str, Any] = {
            "standing_order_id": standing.standing_order_id, "standing_order_name": standing.name,
        }
        if drift is not None:
            facts.update(drift_sentence=drift.sentence, drift=drift.model_dump(mode="json"))
        if renewal is not None:
            facts["renewal_id"] = renewal.renewal_id
        context = AuditContext(profile_id=standing.profile_id, offer_id=offer.offer_id, order=order, facts=facts)
        with self._store.atomic():
            if renewal is not None:
                self._store.save_renewal(renewal)
            self._audit.record(AuditEventType.STANDING_ORDER_RENEWED, actor_of(identity), context)
