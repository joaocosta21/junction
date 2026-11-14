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
from tta.api.audit_pages import audit_page
from tta.api.customers import CustomerView, customer_view
from tta.api.errors import reading_caller_input
from tta.api.limits import CallKind, CallLimits
from tta.api.suggesting import (
    OfferSuggestions,
    OfferSuggestionsView,
    acceptance_not_recorded,
    without_acceptance,
)
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
# In dev and demo the buyer's own words of one request, over all its lines (review H2): they are stored once in
# the offer and again in three audit events. The brief's sentence has 133 characters and the longest example of
# the pages 101; the contract allows 2,000 a line.
MAX_DEMO_REQUEST_CHARACTERS = 600
# In dev and demo one catalog search names at most this many name terms (review M3): each is looked for in up to
# 17,546 names. The pages and the recipe table name one; the contract allows 10.
MAX_DEMO_NAME_TERMS = 4

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
TOO_MUCH_TEXT = (
    "In this demonstration the words of a request (`text`, over all its lines) have at most {limit} characters; "
    "these have {count:,}. Shorten them: the typed fields say what is asked, the words are kept for the record."
)
TOO_MANY_NAME_TERMS = (
    "In this demonstration a search names at most {limit} name terms; this one names {count}. Use fewer words, "
    "or a product type."
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
    max_request_characters: int | None = None  # `MAX_DEMO_REQUEST_CHARACTERS` in dev and demo; else the contract's
    max_name_terms: int | None = None  # `MAX_DEMO_NAME_TERMS` in dev and demo; the contract's 10 elsewhere
    suggestions: OfferSuggestions | None = None  # None: offers carry no suggestion (`tta.api.suggesting`)


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

    def get_customer(self, identity: Identity, customer_id: str | None = None) -> CustomerView:
        """The caller's own customer (its file, synthetic, with the profile's name and limits). Another customer's
        id is `not-found`; the supplier is refused (`tta.api.customers`)."""
        return customer_view(identity, self._deps.policy.get_profile, customer_id)

    # --- Core 1: lookup -----------------------------------------------------------------------------------

    def count_read(self, identity: Identity) -> None:
        """Count one read of the catalog or of the audit trail against the caller's lookup window (review M3 and
        H2), or raise `RateLimited`. The REST routes and the MCP tools call it before `search_products`,
        `get_product` and `get_audit`. The gateway's own parts (the menu planner, the pages) read through those
        functions without it: their calls are counted where they begin."""
        self._deps.limiter.check(identity, CallKind.LOOKUP, writes=False)

    def search_products(self, identity: Identity, query: ProductQuery) -> SearchResult:
        _require_buyer_side(identity)
        limit = self._deps.max_name_terms
        if limit is not None and len(query.name_terms) > limit:
            raise InvalidRequest(TOO_MANY_NAME_TERMS.format(limit=limit, count=len(query.name_terms)))
        return self._deps.catalog.search(query.model_copy(update={"limit": min(query.limit, MAX_LIST_ITEMS)}))

    def get_product(self, identity: Identity, product_id: str) -> Product:
        _require_buyer_side(identity)
        product = self._deps.catalog.get_product(product_id)
        if product is None:
            raise UnknownProduct(NO_SUCH_PRODUCT)
        return product

    def find_substitutes(self, identity: Identity, product_id: str, query: SubstituteQuery) -> SubstituteResult:
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.LOOKUP, writes=False)
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
        most, characters = self._deps.max_request_characters, sum(len(line.text) for line in request.lines)
        if most is not None and characters > most:
            raise InvalidRequest(TOO_MUCH_TEXT.format(limit=most, count=characters))
        named = sum(len(line.product_ids) for line in request.lines)
        if named > MAX_PRODUCT_IDS:
            raise InvalidRequest(TOO_MANY_PRODUCT_IDS.format(count=named))
        return self._offer(identity, request)

    def create_menu_offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        """An offer for a menu plan: as `create_offer`, under the contract's 20 lines instead of the demonstration's 5.
        The planner builds each line from the recipe table (a product type and a quantity), so the large free text
        the 5 keeps out cannot arrive this way. Never a route and never a tool: only `tta.menus.planner` calls it."""
        _require_agent(identity)
        self._deps.limiter.check(identity, CallKind.LOOKUP)
        return self._offer(identity, request)

    def _offer(self, identity: Identity, request: PurchaseRequest) -> Offer:
        offer = self._deps.offers.build_offer(request, identity)
        suggesting = self._deps.suggestions
        # Suggestions are computed on the finished offer and change none of its options or totals. A failure
        # there leaves the offer without them, with a note.
        outcome = None
        if suggesting is not None:
            offer, outcome = suggesting.add_to(identity, offer)
        else:
            offer = acceptance_not_recorded(offer)  # suggestions are off: an acceptance is said, not dropped
        with self._deps.store.atomic():  # the offer and its events together, or neither
            self._deps.store.save_offer(offer)
            self._record_offer(identity, offer)
            if suggesting is not None and outcome is not None:
                suggesting.record(identity, offer, outcome)
        budget = self._deps.limiter.storage
        if budget is not None:  # the offer's own row; its events are counted as the trail writes them
            budget.charge(len(offer.model_dump_json().encode("utf-8")))
        note_offer(offer.offer_id)  # inside a run of the buyer agent: its "request received" is written now
        return offer

    def _record_offer(self, identity: Identity, offer: Offer) -> None:
        record, scope = self._deps.audit.record, {"offer_id": offer.offer_id, "profile_id": offer.profile_id}
        record(AuditEventType.REQUEST_RECEIVED, actor_of(identity), self._received(offer, scope))
        record(AuditEventType.REQUEST_PARSED, actor_of(identity), AuditContext(request=offer.request, **scope))
        looked_up = {
            "products_looked_up": offer.candidates_considered, "source": offer.source.value,
            "time_now": offer.time_now.isoformat(),
            # What the clock rests on: the recording, the supplier's answer, or a demo clock that was set.
            **({} if offer.time_basis is None else {"time_basis": offer.time_basis.value}),
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

    def get_offer_suggestions(self, identity: Identity, offer_id: str) -> OfferSuggestionsView:
        """What an offer of the caller's buyer suggested, and what it did not show with the reason: the buyer's
        own view, so the supplier is refused like any read of an offer."""
        offer = self.get_offer(identity, offer_id)
        suggesting = self._deps.suggestions
        if suggesting is None:
            return OfferSuggestionsView(offer_id=offer.offer_id, suggestions=offer.suggestions)
        return suggesting.view(offer)

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
            # Part of the same call: not counted by the rate limit again. A suggestion is accepted once.
            return self._offer(identity, without_acceptance(stale.request))
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
        offer_id: str | None = None, *, limit: int | None = None, before: str | None = None,
    ) -> AuditView:
        """The trail as one reader sees it, a page at a time: the newest events, at most `limit` (default 100,
        at most 200); `before` is the `next_cursor` of an earlier answer and reads the page before it. A trail
        that fits one page is answered whole. The answer says what was verified (`tta.api.audit_pages`).

        The supplier gets the supplier's view. An agent or approver gets the buyer's view of its own buyer's
        events, and may ask for the supplier's view of them to see what the supplier sees.
        """
        if identity.is_supplier:
            if reader not in (None, AuditReader.SUPPLIER):
                raise NotAuthorised(SUPPLIER_VIEW_ONLY)
            return audit_page(
                self._deps.store, AuditReader.SUPPLIER, order_id=order_id, offer_id=offer_id, profile_id=None,
                limit=limit, before=before,
            )
        profile_id = _require_buyer_side(identity)
        if order_id is not None:
            self._deps.orders.get_order(order_id, identity)  # not-found unless it is this buyer's order
        if offer_id is not None:
            self.get_offer(identity, offer_id)
        return audit_page(
            self._deps.store, reader or AuditReader.BUYER, order_id=order_id, offer_id=offer_id,
            profile_id=profile_id, limit=limit, before=before,
        )

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
