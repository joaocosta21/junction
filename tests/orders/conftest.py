"""Fixtures for the order tests: hand-built offers, a clock that can be moved, a fake revalidator, the order book.

The policy engine, the store and the audit trail are the real ones; only the fresh look at price and
availability is faked, so no test calls the mock API. Every line carries all five claims and every option a
`valid_until`, as the offer builder writes them: without them the policy sends the option to a human.
The store is wrapped so that a test can make one of its writes fail.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tta.audit import AuditTrail
from tta.contracts.allergen import AllergenCheck, AllergenFinding, AllergenStatement, SubstituteAllergenCheck
from tta.contracts.audit import EVENT_TYPE_PREFIX, AuditEvent
from tta.contracts.availability import AvailabilityAssessment, ClaimCheck, RevalidationChange, RevalidationResult
from tta.contracts.common import (
    AllergenOutcome,
    AllergenRelation,
    AllergenStrictness,
    ApproverRole,
    AvailabilityState,
    CheckResult,
    ClaimName,
    ClaimStatus,
    ConstraintKind,
    DataSource,
    DecisionKind,
    Identity,
    IdentityKind,
    OptionKind,
    OrderStatus,
    PackSizeSource,
    Unit,
    round_money,
)
from tta.contracts.offer import (
    ConstraintCheck,
    Coverage,
    Offer,
    OfferLine,
    OfferOption,
    SubstituteInfo,
    Totals,
)
from tta.contracts.order import DecisionRequest, Order
from tta.contracts.policy import BuyerProfile, PolicyContext, PolicyDecision
from tta.contracts.product import PackSize, ReplaceCheck, ReplaceVerdict
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.orders import OrderBookService
from tta.policy import RulePolicyEngine
from tta.store import SqliteStore

HELSINKI = timezone(timedelta(hours=2))
# Server time of the demo capture: Saturday 14 Nov 2026, 02:52 (AIMO/build/AGENT-RULES.md).
NOW = datetime(2026, 11, 14, 2, 52, tzinfo=HELSINKI)
ORDER_BY = datetime(2026, 11, 15, 17, 0, tzinfo=HELSINKI)
MONDAY = date(2026, 11, 16)
TAX_RATE = Decimal("14")
HOTEL = "hotel-kitchen"
WARD = "allergy-ward"
_OUTCOMES = {
    AllergenRelation.FREE_FROM: AllergenOutcome.PASS,
    AllergenRelation.CONTAINS: AllergenOutcome.REJECT,
    AllergenRelation.MAY_CONTAIN: AllergenOutcome.TO_HUMAN,
}
_SEVERITY = {AllergenOutcome.PASS: 0, AllergenOutcome.TO_HUMAN: 1, AllergenOutcome.REJECT: 2}


class MovableClock:
    """The data clock of a test: it answers one instant until the test moves it."""

    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def now(self) -> datetime:
        return self.instant

    def advance(self, delta: timedelta) -> None:
        self.instant = self.instant + delta


class FakeRevalidator:
    """The `OfferRevalidator` port for tests. Every call is a fresh look: nothing is remembered between calls."""

    def __init__(self, clock: MovableClock) -> None:
        self._clock = clock
        self.calls: list[OfferOption] = []
        self.result: RevalidationResult | None = None  # None: nothing changed and nothing expired
        self.error: Exception | None = None
        self.delay_seconds: float = 0
        self.during_call: Callable[[], None] | None = None  # for example: time passes while the supplier answers

    def revalidate(self, option: OfferOption) -> RevalidationResult:
        self.calls.append(option)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self.during_call is not None:
            self.during_call()
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return RevalidationResult(ok=True, checked_at=self._clock.now(), source=DataSource.REPLAY)


class RecordingPolicy:
    """The real policy engine, remembering the context of every evaluation. A test can make an evaluation fail."""

    def __init__(self, engine: RulePolicyEngine) -> None:
        self._engine = engine
        self.contexts: list[PolicyContext] = []
        self.error: Exception | None = None

    def evaluate(self, option: OfferOption, profile: BuyerProfile, context: PolicyContext) -> PolicyDecision:
        self.contexts.append(context)
        if self.error is not None:
            raise self.error
        return self._engine.evaluate(option, profile, context)

    def __getattr__(self, name: str) -> object:
        return getattr(self._engine, name)


class WriteFault(Exception):
    """The failure a test injects into one write of the store."""


class FaultyStore:
    """The real store, counting the writes of the order book. A test can make the n-th write from now on fail."""

    WRITES = ("remember_idempotency_key", "save_order", "save_approval", "append_audit_event")

    def __init__(self, store: SqliteStore) -> None:
        self._store = store
        self._until_fault = 0  # 0: no fault is waiting
        self.writes: list[str] = []

    def fail_write(self, number: int) -> None:
        """The `number`-th write from now on raises `WriteFault` instead of writing; the writes after it work."""
        self.writes.clear()
        self._until_fault = number

    def _attempt(self, name: str) -> None:
        self.writes.append(name)
        if not self._until_fault:
            return
        self._until_fault -= 1
        if not self._until_fault:
            raise WriteFault(f"{name} failed")

    def __getattr__(self, name: str) -> object:
        target = getattr(self._store, name)
        if name not in self.WRITES:
            return target

        def write(*args: object) -> object:
            self._attempt(name)
            return target(*args)

        return write


class Samples:
    """Builders for valid contract objects. Every call returns a new frozen object."""

    now = NOW
    order_by = ORDER_BY
    monday = MONDAY

    def allergen_check(self, relations: Mapping[str, AllergenRelation]) -> AllergenCheck:
        """The ward's exclusion rule, STRICT: one finding per excluded code (SPEC section 6)."""
        findings = tuple(
            AllergenFinding(excluded_code=code, relation=relation, outcome=_OUTCOMES[relation],
                            sentence=f"The product states {relation.value} for {code}.")
            for code, relation in relations.items()
        )
        worst = max((finding.outcome for finding in findings), key=_SEVERITY.__getitem__)
        return AllergenCheck(outcome=worst, strictness=AllergenStrictness.STRICT, findings=findings, all_explicit=True)

    def substitute(self, *, adds_allergen: bool = False) -> SubstituteInfo:
        added = (AllergenStatement(code="AM", relation=AllergenRelation.CONTAINS),) if adds_allergen else ()
        return SubstituteInfo(
            original_id="473609", original_name="Oat drink", listed_by_supplier=True, category_distance=0,
            allergen_check=SubstituteAllergenCheck(
                passes=not adds_allergen, added=added,
                sentence="Adds milk (AM)." if adds_allergen else "Adds no allergen.",
            ),
            gives_up="A different brand.",
            # The offer's like-for-like verdict, as every substitute line carries it (rule F-12 reads it).
            replaceable=ReplaceCheck(verdict=ReplaceVerdict.REPLACEABLE, sentence="Replaceable: same type."),
        )

    def line(
        self, product_id: str = "463380", quantity: str = "100", unit_price: str = "2.65", *,
        state: AvailabilityState = AvailabilityState.CONFIRMED, allergens: AllergenCheck | None = None,
        substitute: SubstituteInfo | None = None,
    ) -> OfferLine:
        units = Decimal(quantity)
        net = round_money(units * Decimal(unit_price))
        tax = round_money(net * TAX_RATE / 100)
        confirmed = state is AvailabilityState.CONFIRMED
        statuses = {claim: ClaimStatus.CONFIRMED for claim in ClaimName}
        if not confirmed:
            statuses[ClaimName.QUANTITY] = ClaimStatus.UNKNOWN
        if allergens is not None and allergens.outcome is AllergenOutcome.REJECT:
            statuses[ClaimName.ALLERGENS] = ClaimStatus.RULED_OUT
        if substitute is not None and "original_net" not in substitute.model_fields_set:
            # A substitute at the price of the product asked for, unless the test says what that would have cost:
            # rule P-05 sends a dearer one, and one whose price cannot be compared, to a person (decision B60).
            substitute = substitute.model_copy(update={"original_net": net})
        return OfferLine(
            product_id=product_id, name=f"Product {product_id}", category="10400", request_line_index=0,
            quantity=units, sales_unit="ST",
            pack_size=PackSize(value=Decimal(1), unit=Unit.L, source=PackSizeSource.PRICE_RATIO),
            covers=units, unit_net_price=Decimal(unit_price), tax_rate=TAX_RATE, net=net, tax=tax, gross=net + tax,
            price_valid_to=NOW + timedelta(days=30),
            availability=AvailabilityAssessment(
                product_id=product_id, state=state, usable_amount=Decimal(5000) if confirmed else None,
                sales_unit="ST", available_date=MONDAY, closing_time=ORDER_BY, logistic_model="Stock",
                sentence="Confirmed." if confirmed else "The quantity is not confirmed.",
            ),
            claims=tuple(
                ClaimCheck(claim=claim, status=status, sentence=f"{claim.value}: {status.value}.")
                for claim, status in statuses.items()
            ),
            allergen_check=allergens, variable_weight=False, has_deposits=False, country_of_origin="FI",
            substitute=substitute,
        )

    def option(
        self, option_id: str = "opt_1", lines: Sequence[OfferLine] | None = None, *,
        kind: OptionKind = OptionKind.BEST_CONFIRMED, valid_until: datetime | None = ORDER_BY,
    ) -> OfferOption:
        held = tuple(lines) if lines is not None else (self.line(),)
        net = sum((line.net for line in held), Decimal(0))
        tax = sum((line.tax for line in held), Decimal(0))
        covered = sum((line.covers for line in held), Decimal(0))
        coverage = Coverage(request_line_index=0, requested=covered, covered=covered, unit=Unit.L,
                            fill_ratio=Decimal(1), missing=Decimal(0))
        return OfferOption(
            option_id=option_id, kind=kind, rank=int(option_id.removeprefix("opt_")), title=f"Option {option_id}",
            summary="An option built for an order test.", lines=held,
            totals=Totals(net=net, tax=tax, gross=net + tax), coverage=(coverage,), fill_ratio=Decimal(1),
            valid_until=valid_until,
            constraint_checks=(ConstraintCheck(
                kind=ConstraintKind.NEEDED_BY, subject=MONDAY.isoformat(), result=CheckResult.MET,
                sentence="Every line can be delivered by Monday 16 November 2026.",
            ),),
        )

    def within_authority(self, option_id: str = "opt_1", **overrides: object) -> OfferOption:
        """100 units for EUR 265.00 net, confirmed: no rule of `hotel-kitchen` fires."""
        return self.option(option_id, (self.line("463380", "100", "2.65"),), **overrides)

    def above_order_limit(self, option_id: str = "opt_1", **overrides: object) -> OfferOption:
        """1,000 units for EUR 2,650.00 net, confirmed: above the EUR 750 limit per order (P-01)."""
        return self.option(option_id, (self.line("463380", "1000", "2.65"),), **overrides)

    def above_daily_limit(self, option_id: str = "opt_1") -> OfferOption:
        """1,200 units for EUR 3,180.00 net: above the limit per order (P-01) and per day (P-02)."""
        return self.option(option_id, (self.line("463380", "1200", "2.65"),))

    def unconfirmed(self, option_id: str = "opt_2", **overrides: object) -> OfferOption:
        """1,000 units of the cheapest milk for EUR 1,010.00 net, quantity not confirmed (F-01 and P-01)."""
        lines = (self.line("464306", "1000", "1.01", state=AvailabilityState.QUANTITY_NOT_CONFIRMED),)
        return self.option(option_id, lines, kind=OptionKind.ALTERNATIVE_UNCONFIRMED, **overrides)

    def adds_allergen(self, option_id: str = "opt_3") -> OfferOption:
        """A substitute that adds an allergen the original does not declare (F-05): cannot be ordered."""
        lines = (self.line("471881", "100", "2.00", substitute=self.substitute(adds_allergen=True)),)
        return self.option(option_id, lines, kind=OptionKind.SUBSTITUTE)

    def ward_safe(self, option_id: str = "opt_1") -> OfferOption:
        """200 units of soya drink for EUR 428.00 net, free from milk and gluten: no rule of `allergy-ward` fires."""
        check = self.allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
        return self.option(option_id, (self.line("464056", "200", "2.14", allergens=check),))

    def ward_question(self, option_id: str = "opt_1", quantity: str = "200") -> OfferOption:
        """Soya drink that may contain milk, for a buyer who excludes it: the dietitian decides (P-04). 200 units
        are EUR 428.00 net, within the ward's EUR 500 per order."""
        check = self.allergen_check({"AM": AllergenRelation.MAY_CONTAIN, "AW": AllergenRelation.FREE_FROM})
        return self.option(option_id, (self.line("464056", quantity, "2.14", allergens=check),))

    def ward_question_above_limit(self, option_id: str = "opt_1", quantity: str = "300") -> OfferOption:
        """The same question on EUR 642.00 net, above the ward's EUR 500 per order: two people, the person who
        orders for the limit (P-01) and the dietitian for the allergen (P-04)."""
        return self.ward_question(option_id, quantity)

    def ward_fills_the_day(self, option_id: str = "opt_1") -> OfferOption:
        """520 units of safe soya drink for EUR 1,112.80 net: above the ward's limit per order (P-01) and, with
        EUR 428.00 more, above its EUR 1,500 a day (P-02). Both are decided by the person who orders."""
        check = self.allergen_check({"AM": AllergenRelation.FREE_FROM, "AW": AllergenRelation.FREE_FROM})
        return self.option(option_id, (self.line("464056", "520", "2.14", allergens=check),))

    def ward_declares_milk(self, option_id: str = "opt_1") -> OfferOption:
        """A product that declares milk, for a buyer who excludes it (F-02): cannot be ordered."""
        check = self.allergen_check({"AM": AllergenRelation.CONTAINS, "AW": AllergenRelation.FREE_FROM})
        return self.option(option_id, (self.line("469363", "100", "2.48", allergens=check),))

    def price_changed(self, at: datetime = NOW) -> RevalidationResult:
        change = RevalidationChange(product_id="463380", field="price", before="2.65", after="2.80",
                                    sentence="The price of 463380 changed from €2.65 to €2.80.")
        return RevalidationResult(ok=False, changes=(change,), checked_at=at, source=DataSource.REPLAY)

    def cutoff_passed(self, at: datetime = NOW) -> RevalidationResult:
        return RevalidationResult(ok=False, expired=True, checked_at=at, source=DataSource.REPLAY)

    def approve(self, option_id: str | None = None, note: str | None = None) -> DecisionRequest:
        return DecisionRequest(decision=DecisionKind.APPROVE, option_id=option_id, note=note)

    def reject(self, note: str | None = None) -> DecisionRequest:
        return DecisionRequest(decision=DecisionKind.REJECT, note=note)

    def approver(self, identity_id: str, profile_id: str, *roles: ApproverRole) -> Identity:
        return Identity(kind=IdentityKind.APPROVER, id=identity_id, display_name=f"Approver {identity_id}",
                        profile_id=profile_id, roles=roles)


@dataclass
class Book:
    """The order book of one test with everything around it."""

    service: OrderBookService
    store: FaultyStore
    clock: MovableClock
    revalidator: FakeRevalidator
    policy: RecordingPolicy
    audit: AuditTrail
    _offers: int = field(default=0)

    def offer(self, *options: OfferOption, profile_id: str = HOTEL) -> Offer:
        """Store an offer holding these options, as the offer service does before an order can name it."""
        self._offers += 1
        request = PurchaseRequest(needed_by=MONDAY, lines=(
            RequestLine(text="1,000 litres of lactose-free milk", quantity=Decimal(1000), unit=Unit.L),
        ))
        offer = Offer(
            offer_id=f"off_{self._offers:012x}", created_at=self.clock.now(), profile_id=profile_id,
            agent_id=f"agent:{profile_id}", request=request, options=options, source=DataSource.REPLAY,
            time_now=self.clock.now(),
        )
        self.store.save_offer(offer)
        return offer

    def waiting(self, agent: Identity, *options: OfferOption, profile_id: str = HOTEL) -> Order:
        """An order that waits for a human, placed on the first option of a new offer."""
        offer = self.offer(*options, profile_id=profile_id)
        order = self.service.place_order(offer.offer_id, offer.options[0].option_id, agent, f"key-{offer.offer_id}")
        assert order.status is OrderStatus.PENDING_APPROVAL
        return order

    def events(self, order_id: str | None = None) -> tuple[AuditEvent, ...]:
        return self.store.list_audit_events(order_id=order_id)

    def event_types(self, order_id: str | None = None) -> list[str]:
        return [event.type.removeprefix(EVENT_TYPE_PREFIX) for event in self.events(order_id)]


@pytest.fixture(scope="session")
def samples() -> Samples:
    return Samples()


@pytest.fixture(scope="session")
def engine() -> RulePolicyEngine:
    return RulePolicyEngine.from_files()


@pytest.fixture
def book(engine: RulePolicyEngine) -> Iterator[Book]:
    database = SqliteStore()
    store = FaultyStore(database)
    clock = MovableClock(NOW)
    revalidator = FakeRevalidator(clock)
    policy = RecordingPolicy(engine)
    audit = AuditTrail(store, clock, policy=engine)
    service = OrderBookService(store=store, policy=policy, revalidator=revalidator, audit=audit, clock=clock)
    yield Book(service=service, store=store, clock=clock, revalidator=revalidator, policy=policy, audit=audit)
    database.close()


@pytest.fixture(scope="session")
def write_fault() -> type[Exception]:
    """The error `FaultyStore.fail_write` raises: test modules cannot import it from this file."""
    return WriteFault


@pytest.fixture(scope="session")
def approver_intern(samples: Samples) -> Identity:
    """Holds the role in its token, but the hotel's profile does not list it under any role."""
    return samples.approver("human:hotel-intern", HOTEL, ApproverRole.PURCHASING_MANAGER)


@pytest.fixture(scope="session")
def approver_ward_purchasing(samples: Samples) -> Identity:
    """The ward's person who orders: also decides a spend-limit stop, so there is no separate finance signer
    (decision B54). The ward's second person is the dietitian (`approver_dietitian`)."""
    return Identity(kind=IdentityKind.APPROVER, id="human:ward-purchasing", display_name="Ward purchasing (demo)",
                    profile_id=WARD, roles=(ApproverRole.PURCHASING_MANAGER, ApproverRole.FINANCE))
