"""The gateway's service functions: the one object behind every transport (SPEC section 2).

Scores on the 30% "one continuous flow" and on the 20% "autonomy and controls". REST routes, MCP tools, the
pages and the buyer agent all call this object and nothing else, so no rule can differ between transports.
Each function checks what the caller's identity may do, then hands over to the package that does the work.
It decides no price, quantity, allergen status or verdict.

Who may call what:
    agent      everything of its own buyer, except the approval functions
    approver   reads of its own buyer (authority, catalog, offer, order, audit) and the approval functions
    supplier   the supplier's view of the audit trail, nothing else
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from tta.api.agent_calls import note_offer, note_order, read_with, run_that_stopped, traced
from tta.api.errors import reading_caller_input
from tta.api.limits import CallKind, CallLimits
from tta.contracts.agent import AgentRun, Reading
from tta.contracts.audit import SYSTEM_ACTOR, AuditContext, AuditEventType, AuditView
from tta.contracts.common import ApprovalStatus, AuditReader, Identity, OrderStatus
from tta.contracts.errors import (
    InvalidRequest,
    NotAuthorised,
    NotFound,
    OfferExpired,
    OfferStale,
    SupplierUnavailable,
    TtaError,
    UnknownProduct,
)
from tta.contracts.offer import Exclusion, Offer, SubstituteQuery, SubstituteResult
from tta.contracts.order import Approval, DecisionRequest, Order
from tta.contracts.policy import Authority
from tta.contracts.ports import (
    AgentRunner,
    AuditSink,
    Catalog,
    OfferBuilder,
    OrderService,
    PolicyEngine,
    RequestParser,
    Store,
)
from tta.contracts.product import Product, SearchResult
from tta.contracts.request import MAX_PRODUCT_IDS, ProductQuery, PurchaseRequest
from tta.orders.access import actor_of

MAX_LIST_ITEMS = 100  # the most a list answers: orders, approvals, audit events, products of a search
# In dev and demo, where the tokens are public, one request may hold this many lines (the contract allows 20):
# an offer of 20 lines of 2,000 characters wrote about 700 KB to the database (task FIX-10, finding 10).
MAX_DEMO_REQUEST_LINES = 5

ONLY_AN_AGENT = "Only a buyer's agent may do this."
ONLY_AN_APPROVER = "Only an approver of the buyer reads the approval queue. An agent cannot approve an order (F-06)."
NOT_FOR_THE_SUPPLIER = "The supplier reads its view of the audit trail (GET /v1/audit) and nothing else."
SUPPLIER_VIEW_ONLY = "The supplier reads the supplier's view of the audit trail, not the buyer's."
NO_SUCH_PRODUCT = "No product in the catalog has this id."
NO_SUCH_OFFER = "No offer has this id."
TOO_MANY_PRODUCT_IDS = "A request names at most 1,000 product ids over all its lines; this one names {count:,}."
TOO_MANY_LINES = (
    "In this demonstration a request has at most {limit} lines; this one has {count}. Send the others as "
    "another request."
)
NO_REQUEST_PARSER = (
    "This gateway has no request parser running, so it cannot read free text. "
    "Send the typed request to POST /v1/offers instead."
)
NO_PHOTO_READER = (
    "This gateway's request parser cannot read a photo. Type the request and send it to POST /v1/requests/parse, "
    "or send the typed request to POST /v1/offers instead."
)
A_PHOTO = "A photo of an order list ({media_type}, {size:,} bytes) that could not be read into a typed request."
NO_AGENT_RUNNER = (
    "This gateway has no buyer agent running, so it cannot act on free text. "
    "Send the typed request to POST /v1/offers and the chosen option to POST /v1/orders instead."
)

TEXT_OF_LINES = "; "  # between the words of two request lines, in "request received"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayDeps:
    """The ports the service delegates to. `request_parser` and `agent_runner` are `None` until T10 lands."""

    catalog: Catalog
    policy: PolicyEngine
    store: Store
    audit: AuditSink
    offers: OfferBuilder
    orders: OrderService
    limiter: CallLimits
    request_parser: RequestParser | None = None
    agent_runner: AgentRunner | None = None
    max_request_lines: int | None = None  # `MAX_DEMO_REQUEST_LINES` in dev and demo; the contract's 20 elsewhere


def _require_agent(identity: Identity) -> None:
    if identity.is_supplier:
        raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
    if not identity.is_agent:
        raise NotAuthorised(ONLY_AN_AGENT)


def _require_buyer_side(identity: Identity) -> str:
    """The buyer profile of an agent or an approver. The profile always comes from the identity."""
    if identity.is_supplier or identity.profile_id is None:
        raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
    return identity.profile_id


def _once_per_product(offer: Offer) -> Offer:
    """The offer as the trail records it: a product excluded by several lines of the request is one excluded
    product, with the first line's reason. The stored offer keeps every line's exclusion."""
    first: dict[str, Exclusion] = {}
    for exclusion in offer.excluded:
        first.setdefault(exclusion.product_id, exclusion)
    if len(first) == len(offer.excluded):
        return offer
    return offer.model_copy(update={"excluded": tuple(first.values())})


class Gateway:
    """Implements the `GatewayService` port, plus `list_orders` for the pages."""

    def __init__(self, deps: GatewayDeps) -> None:
        self._deps = deps

    @property
    def has_request_parser(self) -> bool:
        return self._deps.request_parser is not None

    @property
    def has_agent_runner(self) -> bool:
        return self._deps.agent_runner is not None

    # --- Core 3: authority --------------------------------------------------------------------------------

    def get_authority(self, identity: Identity) -> Authority:
        profile = self._deps.policy.get_profile(_require_buyer_side(identity))
        return self._deps.policy.describe_authority(profile)

    # --- Core 1: lookup -----------------------------------------------------------------------------------

    def search_products(self, identity: Identity, query: ProductQuery) -> SearchResult:
        _require_buyer_side(identity)
        return self._deps.catalog.search(query.model_copy(update={"limit": min(query.limit, MAX_LIST_ITEMS)}))

    def get_product(self, identity: Identity, product_id: str) -> Product:
        _require_buyer_side(identity)
        product = self._deps.catalog.get_product(product_id)
        if product is None:
            raise UnknownProduct(NO_SUCH_PRODUCT)
        return product

    def find_substitutes(self, identity: Identity, product_id: str, query: SubstituteQuery) -> SubstituteResult:
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.LOOKUP)
        if self._deps.catalog.get_product(product_id) is None:
            raise UnknownProduct(NO_SUCH_PRODUCT)
        return self._deps.offers.find_substitutes(product_id, identity, query)

    # --- Core 2: offer and order --------------------------------------------------------------------------

    def create_offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        """Build the offer, store it and write its audit events, each with the offer id: the trail of an
        order is found through its offer. The first event is "request received", in the buyer's own words."""
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.LOOKUP)
        limit = self._deps.max_request_lines
        if limit is not None and len(request.lines) > limit:
            raise InvalidRequest(TOO_MANY_LINES.format(limit=limit, count=len(request.lines)))
        named = sum(len(line.product_ids) for line in request.lines)
        if named > MAX_PRODUCT_IDS:
            raise InvalidRequest(TOO_MANY_PRODUCT_IDS.format(count=named))
        return self._offer(identity, request)

    def _offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        offer = self._deps.offers.build_offer(request, identity)
        with self._deps.store.atomic():  # the offer and its events together, or neither
            self._deps.store.save_offer(offer)
            self._record_offer(identity, offer)
        note_offer(offer.offer_id)  # inside a run of the buyer agent: its "request received" is written now
        return offer

    def _record_offer(self, identity: Identity, offer: Offer) -> None:
        record, scope = self._deps.audit.record, {"offer_id": offer.offer_id, "profile_id": offer.profile_id}
        record(AuditEventType.REQUEST_RECEIVED, actor_of(identity), self._received(offer, scope))
        record(AuditEventType.REQUEST_PARSED, actor_of(identity), AuditContext(request=offer.request, **scope))
        looked_up = {
            "products_looked_up": offer.candidates_considered, "source": offer.source.value,
            "time_now": offer.time_now.isoformat(),
        }
        record(AuditEventType.LOOKUP_PERFORMED, SYSTEM_ACTOR, AuditContext(facts=looked_up, **scope))
        record(AuditEventType.OFFER_CREATED, SYSTEM_ACTOR, AuditContext(offer=_once_per_product(offer)))
        for option in offer.options:
            record(AuditEventType.POLICY_EVALUATED, SYSTEM_ACTOR, AuditContext(option=option, **scope))

    @staticmethod
    def _received(offer: Offer, scope: dict[str, str]) -> AuditContext:
        """One "request received" per offer (question T09-1): the buyer's own words, which each request line
        keeps in its `text`. A typed request sent without words is recorded as what it asks for."""
        words = TEXT_OF_LINES.join(line.text.strip() for line in offer.request.lines if line.text.strip())
        if words:
            return AuditContext(facts={"text": words}, **scope)
        return AuditContext(request=offer.request, **scope)

    def get_offer(self, identity: Identity, offer_id: str) -> Offer:
        profile_id = _require_buyer_side(identity)
        offer = self._deps.store.get_offer(offer_id)
        # Another buyer's offer answers as an id nobody issued: the two cannot be told apart.
        if offer is None or offer.profile_id != profile_id:
            raise NotFound(NO_SUCH_OFFER)
        return offer

    def place_order(self, identity: Identity, offer_id: str, option_id: str, idempotency_key: str) -> Order:
        """Raises `OfferStale` or `OfferExpired` with `fresh_offer_id`: a new offer for the same request."""
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.ORDER)
        try:
            order = self._deps.orders.place_order(offer_id, option_id, identity, idempotency_key)
        except (OfferStale, OfferExpired) as error:
            fresh = self._fresh_offer(identity, offer_id)
            if fresh is None:
                raise
            raise type(error)(error.detail, **{**error.extensions, "fresh_offer_id": fresh.offer_id}) from error
        note_order(order.order_id)  # inside a run of the buyer agent: an order the run can never hide
        return order

    def _fresh_offer(self, identity: Identity, offer_id: str) -> Offer | None:
        """A new offer for the request of the offer that can no longer be ordered. `None` when it cannot be
        built: the caller still gets the first error, which is the true answer to its order."""
        stale = self._deps.store.get_offer(offer_id)
        if stale is None:
            return None
        try:
            return self._offer(identity, stale.request)  # part of the same call: not counted by the rate limit again
        except TtaError as error:
            logger.warning("No fresh offer could be built for %s: %s (%s)", offer_id, error.slug, error.detail)
            return None

    def get_order(self, identity: Identity, order_id: str) -> Order:
        return self._deps.orders.get_order(order_id, identity)

    def order_for_offer(self, identity: Identity, offer_id: str) -> Order | None:
        """The newest order placed on this offer of the caller's buyer, or `None`. Read through the store, so
        an offer whose order is older than the newest `MAX_LIST_ITEMS` still finds it; another buyer's offer
        is `not-found`. A waiting order is read through the order book, which expires it when it is late."""
        offer = self.get_offer(identity, offer_id)
        placed = [order for order in self._deps.store.list_orders(profile_id=offer.profile_id)
                  if order.offer_id == offer.offer_id]
        return self._deps.orders.get_order(placed[-1].order_id, identity) if placed else None

    def list_orders(self, identity: Identity) -> tuple[Order, ...]:
        """The orders of the caller's own buyer, newest first, at most `MAX_LIST_ITEMS`."""
        profile_id = _require_buyer_side(identity)
        newest_first = tuple(reversed(self._deps.store.list_orders(profile_id=profile_id)))[:MAX_LIST_ITEMS]
        # Reading a waiting order through the order book expires it when its "order by" time has passed.
        return tuple(
            self._deps.orders.get_order(order.order_id, identity)
            if order.status is OrderStatus.PENDING_APPROVAL else order
            for order in newest_first
        )

    # --- Core 3: approval ---------------------------------------------------------------------------------

    def list_approvals(self, identity: Identity, status: ApprovalStatus | None = None) -> tuple[Approval, ...]:
        """The approvals of the caller's buyer, oldest first; the newest `MAX_LIST_ITEMS` when there are more."""
        if identity.is_supplier:
            raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
        if not identity.is_approver:
            raise NotAuthorised(ONLY_AN_APPROVER)
        return self._deps.orders.list_approvals(identity, status)[-MAX_LIST_ITEMS:]

    def decide_approval(self, identity: Identity, approval_id: str, decision: DecisionRequest) -> Order:
        if identity.is_supplier:
            raise NotAuthorised(NOT_FOR_THE_SUPPLIER)
        self._deps.limiter.check(identity, CallKind.ORDER)
        return self._deps.orders.decide(approval_id, identity, decision)  # an agent is refused there, with an event

    # --- audit trail --------------------------------------------------------------------------------------

    def get_audit(
        self, identity: Identity, reader: AuditReader | None = None, order_id: str | None = None,
        offer_id: str | None = None,
    ) -> AuditView:
        """The trail as one reader sees it; the newest `MAX_LIST_ITEMS` events when there are more.

        The supplier gets the supplier's view. An agent or approver gets the buyer's view of its own buyer's
        events, and may ask for the supplier's view of them to see what the supplier sees.
        """
        if identity.is_supplier:
            if reader not in (None, AuditReader.SUPPLIER):
                raise NotAuthorised(SUPPLIER_VIEW_ONLY)
            view = self._deps.audit.view(AuditReader.SUPPLIER, order_id=order_id, offer_id=offer_id)
        else:
            profile_id = _require_buyer_side(identity)
            if order_id is not None:
                self._deps.orders.get_order(order_id, identity)  # not-found unless it is this buyer's order
            if offer_id is not None:
                self.get_offer(identity, offer_id)
            view = self._deps.audit.view(
                reader or AuditReader.BUYER, order_id=order_id, offer_id=offer_id, profile_id=profile_id
            )
        return view.model_copy(update={"events": view.events[-MAX_LIST_ITEMS:]})

    # --- buyer agent --------------------------------------------------------------------------------------

    def read_request(self, identity: Identity, text: str) -> Reading:
        """The typed request with who read it: the model now, a recording of it, or an answer written by hand.
        Writes no event when the text is read: "request received" is written with the offer that follows
        (`create_offer`). A text that cannot be read has no offer, so it is recorded here."""
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.MODEL)
        parser = self._deps.request_parser
        if parser is None:
            raise SupplierUnavailable(NO_REQUEST_PARSER)
        try:
            with reading_caller_input():  # the parser turns the caller's words into the typed request
                return read_with(parser, identity, text)
        except Exception:
            self._record_received(identity, text)
            raise

    def parse_request(self, identity: Identity, text: str) -> PurchaseRequest:
        return self.read_request(identity, text).request

    def read_image(self, identity: Identity, image: bytes, media_type: str) -> tuple[tuple[str, ...], Reading]:
        """The lines read in a photo of an order list, and the typed request read from them, with who did each
        (task T18). Counted as a model call. The parser checks the image before any model is asked. A photo
        that cannot be read has no offer, so it is recorded here, by its declared type and size: never its
        bytes. Answers `supplier-unavailable` when the parser cannot read a photo."""
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.MODEL)
        read_image = getattr(self._deps.request_parser, "read_image", None)
        if not callable(read_image):
            raise SupplierUnavailable(NO_PHOTO_READER)
        try:
            with reading_caller_input():
                lines, reading = read_image(image, media_type, identity)
        except Exception:
            self._record_received(identity, A_PHOTO.format(media_type=media_type or "no type", size=len(image)))
            raise
        if not isinstance(reading, Reading):
            raise TypeError(f"{type(self._deps.request_parser).__name__}.read_image must return a Reading.")
        return tuple(lines), reading

    def run_agent(self, identity: Identity, text: str) -> AgentRun:
        """The runner gets this object as its tools: whatever the model asks for passes the same checks.
        A run that makes an offer has its "request received" from `create_offer`; one that makes none is
        recorded here, whether it ended with a report or with an error. A runner that breaks after the
        gateway placed an order is answered with that order and a report saying what stopped it."""
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.MODEL)
        runner = self._deps.agent_runner
        if runner is None:
            raise SupplierUnavailable(NO_AGENT_RUNNER)
        with traced() as made:
            try:
                run = runner.run_agent(text, identity, self)
            except Exception as error:
                trace = made()
                if not trace.offer_ids:
                    self._record_received(identity, text)
                if not trace.order_ids:
                    raise
                return run_that_stopped(text, runner, self._deps.orders.get_order(trace.order_ids[-1], identity), error)
            # The run's own word is taken too: a runner may call its tools where the trace does not reach.
            if not made().offer_ids and run.offer_id is None:
                self._record_received(identity, text)
            return run

    def _record_received(self, identity: Identity, text: str) -> None:
        context = AuditContext(profile_id=identity.profile_id, facts={"text": text})
        self._deps.audit.record(AuditEventType.REQUEST_RECEIVED, actor_of(identity), context)
