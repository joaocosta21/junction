"""Hand-built contract objects for the audit tests: the hotel flow (limits, approval) and the ward flow (allergens).

The figures are those of SPEC section 9's example: 749 of 1,000 litres for EUR 1,980.77 net.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tta.audit import AuditTrail
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEventType
from tta.contracts.availability import AvailabilityAssessment, ClaimCheck, RevalidationChange, RevalidationResult
from tta.contracts.common import (
    AllergenStrictness,
    ApprovalStatus,
    ApproverRole,
    AvailabilityState,
    ClaimName,
    ClaimStatus,
    DataSource,
    DecisionKind,
    DepositRule,
    ExclusionReason,
    OptionKind,
    OrderStatus,
    PackSizeSource,
    PlacedBy,
    SubstitutionScope,
    Unit,
    VariableWeightRule,
    Verdict,
    most_severe,
    round_money,
)
from tta.contracts.offer import Coverage, Exclusion, Offer, OfferLine, OfferOption, Totals
from tta.contracts.order import Approval, ApprovalDecision, Evidence, Order, RelianceStatement
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyDecision
from tta.contracts.product import PackSize
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.store import SqliteStore

HELSINKI = timezone(timedelta(hours=2))
NOW = datetime(2026, 11, 14, 2, 52, tzinfo=HELSINKI)
ORDER_BY = datetime(2026, 11, 15, 17, 0, tzinfo=HELSINKI)
MONDAY = date(2026, 11, 16)
TAX_RATE = Decimal("13.5")
HOTEL = "hotel-kitchen"
WARD = "allergy-ward"
POLICY_HASH = "c" * 64
PASTED_TEXT = "1,000 litres of lactose-free milk by Monday"
# Decision sentences in the form the policy engine writes them (src/tta/policy/rules.yaml, decision_sentences).
PARTIAL_DECISION = (
    "The agent cannot place this order alone: the total of €1,980.77 before tax is above the €750 limit per order "
    "(P-01) and only 74.9% of the requested quantity is covered (P-03). It needs the purchasing manager."
)
WARD_DECISION = (
    "The agent may place this order alone: the total of €428.00 before tax is within the €500 limit per order "
    "and no rule asks for a human"
)

AGENT_HOTEL = Actor(kind=ActorKind.AGENT, id="agent:hotel-kitchen", display_name="Hotel kitchen agent")
AGENT_WARD = Actor(kind=ActorKind.AGENT, id="agent:allergy-ward", display_name="Allergy ward agent")
MAIJA = Actor(kind=ActorKind.HUMAN, id="human:maija", role="purchasing_manager", display_name="Maija Virtanen")
GATEWAY = Actor(kind=ActorKind.SYSTEM, id="gateway", display_name="The gateway")


class Samples:
    """Builders for valid contract objects. Every call returns a new frozen object."""

    now = NOW
    order_by = ORDER_BY
    policy_hash = POLICY_HASH
    agent_hotel = AGENT_HOTEL
    agent_ward = AGENT_WARD
    maija = MAIJA
    gateway = GATEWAY

    def line(
        self, product_id: str, quantity: str, unit_price: str,
        state: AvailabilityState = AvailabilityState.CONFIRMED,
    ) -> OfferLine:
        units = Decimal(quantity)
        net = round_money(units * Decimal(unit_price))
        tax = round_money(net * TAX_RATE / 100)
        confirmed = state is AvailabilityState.CONFIRMED
        return OfferLine(
            product_id=product_id, name=f"Product {product_id}", category="10400", request_line_index=0,
            quantity=units, sales_unit="ST",
            pack_size=PackSize(value=Decimal("1"), unit=Unit.L, source=PackSizeSource.PRICE_RATIO),
            covers=units, unit_net_price=Decimal(unit_price), tax_rate=TAX_RATE, net=net, tax=tax, gross=net + tax,
            price_valid_to=ORDER_BY,
            availability=AvailabilityAssessment(
                product_id=product_id, state=state, usable_amount=units if confirmed else None, sales_unit="ST",
                available_date=MONDAY, closing_time=ORDER_BY, logistic_model="Stock",
                sentence="Confirmed." if confirmed else "The quantity is not confirmed.",
            ),
            claims=(ClaimCheck(
                claim=ClaimName.QUANTITY, status=ClaimStatus.CONFIRMED if confirmed else ClaimStatus.UNKNOWN,
                sentence="Confirmed." if confirmed else "Not confirmed.",
            ),),
        )

    def rule(
        self, rule_id: str, sentence: str, verdict: Verdict = Verdict.APPROVAL,
        role: ApproverRole | None = ApproverRole.PURCHASING_MANAGER, facts: dict | None = None,
        product_id: str | None = None,
    ) -> FiredRule:
        return FiredRule(
            rule_id=rule_id, title=f"Rule {rule_id}", fixed=rule_id.startswith("F-"), verdict=verdict,
            approver_role=role, sentence=sentence, facts=facts or {}, product_id=product_id,
        )

    def decision(self, *rules: FiredRule, profile_id: str = HOTEL, sentence: str | None = None) -> PolicyDecision:
        roles = tuple(dict.fromkeys(rule.approver_role for rule in rules if rule.approver_role is not None))
        verdict = most_severe([rule.verdict for rule in rules])
        return PolicyDecision(
            verdict=verdict, fired=rules, required_roles=roles, policy_hash=POLICY_HASH, profile_id=profile_id,
            evaluated_at=NOW, sentence=sentence or f"The verdict is {verdict.value}.",
        )

    def option(
        self, option_id: str, lines: tuple[OfferLine, ...], decision: PolicyDecision, requested: str = "1000",
        kind: OptionKind = OptionKind.BEST_CONFIRMED, rank: int = 1,
    ) -> OfferOption:
        net = sum((line.net for line in lines), Decimal(0))
        tax = sum((line.tax for line in lines), Decimal(0))
        covered = sum((line.covers for line in lines), Decimal(0))
        ratio = covered / Decimal(requested)
        coverage = Coverage(request_line_index=0, requested=Decimal(requested), covered=covered, unit=Unit.L,
                            fill_ratio=ratio, missing=Decimal(requested) - covered)
        return OfferOption(
            option_id=option_id, kind=kind, rank=rank, title=f"Option {rank}", summary="A summary.", lines=lines,
            totals=Totals(net=net, tax=tax, gross=net + tax), coverage=(coverage,), fill_ratio=ratio,
            valid_until=ORDER_BY, decision=decision,
        )

    def partial_option(self) -> OfferOption:
        """749 of 1,000 litres, confirmed, EUR 1,980.77 net: crosses the spend limit and the fill ratio."""
        decision = self.decision(
            self.rule("P-01", "The order total of €1,980.77 is above the €750.00 limit for one order.",
                      facts={"total_net_eur": "1980.77", "max_order_net_eur": "750.00"}),
            self.rule("P-03", "Only 74.9% of the requested quantity is covered; the profile asks for at least 90%",
                      facts={"fill_ratio": "0.749", "min_fill_ratio": "0.9"}),
            sentence=PARTIAL_DECISION,
        )
        lines = (self.line("463380", "698", "2.65"), self.line("462775", "51", "2.57"))
        return self.option("opt_1", lines, decision)

    def unconfirmed_option(self) -> OfferOption:
        """1,000 litres of the cheapest milk, quantity not confirmed, EUR 1,010.00 net."""
        decision = self.decision(
            self.rule("F-01", "The quantity of 464306 is not confirmed by Valio Aimo's data.", product_id="464306"),
            self.rule("P-01", "The order total of €1,010.00 is above the €750.00 limit for one order.",
                      facts={"total_net_eur": "1010.00", "max_order_net_eur": "750.00"}),
        )
        lines = (self.line("464306", "1000", "1.01", AvailabilityState.QUANTITY_NOT_CONFIRMED),)
        return self.option("opt_2", lines, decision, kind=OptionKind.ALTERNATIVE_UNCONFIRMED, rank=2)

    def ward_option(self) -> OfferOption:
        """200 litres of soya drink, confirmed, EUR 428.00 net: no rule fires."""
        decision = self.decision(profile_id=WARD, sentence=WARD_DECISION)
        return self.option("opt_1", (self.line("464056", "200", "2.14"),), decision, "200")

    def hotel_profile(self) -> BuyerProfile:
        return BuyerProfile(
            profile_id=HOTEL, display_name="Hotel kitchen", auto_order_enabled=True,
            max_order_net_eur=Decimal("750"), max_daily_net_eur=Decimal("3000"), min_fill_ratio=Decimal("0.9"),
            substitution_without_approval=SubstitutionScope.SAME_CATEGORY,
            variable_weight=VariableWeightRule.APPROVAL, deposits=DepositRule.APPROVAL,
            approver_roles={ApproverRole.PURCHASING_MANAGER: ("human:maija",)},
        )

    def hotel_request(self) -> PurchaseRequest:
        line = RequestLine(text="1,000 litres of lactose-free milk", product_type="lactose_free_milk",
                           required_claims=("FREE_FROM_LACTOSE",), quantity=Decimal("1000"), unit=Unit.L)
        return PurchaseRequest(needed_by=MONDAY, lines=(line,))

    def ward_request(self) -> PurchaseRequest:
        line = RequestLine(
            text="200 litres of a milk substitute; no milk, no gluten", product_type="milk_substitute",
            quantity=Decimal("200"), unit=Unit.L, exclude_allergens=("AM", "AW"),
            allergen_strictness=AllergenStrictness.STRICT,
        )
        return PurchaseRequest(needed_by=MONDAY, require_confirmed=True, lines=(line,))

    def hotel_offer(self) -> Offer:
        excluded = (
            Exclusion(product_id="463203", name="Portion milk", request_line_index=0,
                      reason=ExclusionReason.PORTION_PACK, sentence="A portion pack."),
            Exclusion(product_id="471690", name="Oat drink", request_line_index=0,
                      reason=ExclusionReason.CUTOFF_PASSED, sentence="The cut-off has passed."),
        )
        return Offer(
            offer_id="off_1", created_at=NOW, profile_id=HOTEL, agent_id=AGENT_HOTEL.id,
            request=self.hotel_request(), options=(self.partial_option(), self.unconfirmed_option()),
            excluded=excluded, candidates_considered=35, source=DataSource.REPLAY, time_now=NOW,
        )

    def ward_offer(self) -> Offer:
        excluded = (
            Exclusion(product_id="469363", name="Lactose free milk", request_line_index=0,
                      reason=ExclusionReason.ALLERGEN_DECLARED, sentence="Declares milk (AM)."),
            Exclusion(product_id="468319", name="Oat drink", request_line_index=0,
                      reason=ExclusionReason.ALLERGEN_DECLARED, sentence="Declares gluten (AW)."),
        )
        return Offer(
            offer_id="off_2", created_at=NOW, profile_id=WARD, agent_id=AGENT_WARD.id, request=self.ward_request(),
            options=(self.ward_option(),), excluded=excluded, candidates_considered=12, source=DataSource.REPLAY,
            time_now=NOW, notes=("Every product declaring AM or AW was left out.",),
        )

    def order(
        self, option: OfferOption, status: OrderStatus, order_id: str = "ord_1", profile_id: str = HOTEL,
        offer_id: str = "off_1", placed_by: PlacedBy | None = None, approval_id: str | None = "apr_1",
    ) -> Order:
        reliance = tuple(
            RelianceStatement(
                product_id=line.product_id, unit_net_price=line.unit_net_price, price_valid_to=ORDER_BY,
                availability_state=line.availability.state, available_amount=line.availability.usable_amount,
                available_date=MONDAY, closing_time=ORDER_BY, time_now=NOW, source=DataSource.REPLAY,
            )
            for line in option.lines
        )
        return Order(
            order_id=order_id, offer_id=offer_id, option_id=option.option_id, profile_id=profile_id,
            agent_id=f"agent:{profile_id}", status=status, placed_by=placed_by, option=option,
            decision=option.decision, approval_id=approval_id, reliance=reliance, created_at=NOW, updated_at=NOW,
            status_sentence="The total is above the €750.00 limit.", source=DataSource.REPLAY,
        )

    def approve(self, option_id: str | None = None, note: str | None = None) -> ApprovalDecision:
        return ApprovalDecision(
            approver_id=MAIJA.id, approver_name="Maija Virtanen", roles=(ApproverRole.PURCHASING_MANAGER,),
            decision=DecisionKind.APPROVE, option_id=option_id, note=note, decided_at=NOW,
        )

    def reject(self, note: str | None = None) -> ApprovalDecision:
        return ApprovalDecision(
            approver_id=MAIJA.id, approver_name="Maija Virtanen", roles=(ApproverRole.PURCHASING_MANAGER,),
            decision=DecisionKind.REJECT, note=note, decided_at=NOW,
        )

    def approval(
        self, status: ApprovalStatus = ApprovalStatus.PENDING, decisions: tuple[ApprovalDecision, ...] = (),
        option_id: str = "opt_1", roles: tuple[ApproverRole, ...] = (ApproverRole.PURCHASING_MANAGER,),
    ) -> Approval:
        return Approval(
            approval_id="apr_1", order_id="ord_1", offer_id="off_1", option_id=option_id, profile_id=HOTEL,
            status=status, required_roles=roles, reasons=("The total is above the €750.00 limit.",),
            decisions=decisions, created_at=NOW, valid_until=ORDER_BY,
        )

    def revalidation(self, changed: bool = False, expired: bool = False) -> RevalidationResult:
        change = RevalidationChange(
            product_id="463380", field="price", before="2.65", after="2.80",
            sentence="The price of 463380 changed from €2.65 to €2.80.",
        )
        return RevalidationResult(
            ok=not (changed or expired), expired=expired, changes=(change,) if changed else (), checked_at=NOW,
            source=DataSource.REPLAY,
        )

    def evidence(self) -> Evidence:
        return Evidence(product_id="473609", found=True, source_url="https://example.org/oat-drink",
                        sentence="The manufacturer's page lists oats and no milk.")


@pytest.fixture(scope="session")
def samples() -> Samples:
    return Samples()


@pytest.fixture
def store() -> Iterator[SqliteStore]:
    store = SqliteStore()
    yield store
    store.close()


@pytest.fixture
def trail(store: SqliteStore, demo_clock) -> AuditTrail:
    return AuditTrail(store, demo_clock)


@pytest.fixture
def hotel_flow(trail: AuditTrail, samples: Samples) -> AuditTrail:
    """Scenario 1 from request to order: sent to a human, who picks the unconfirmed alternative."""
    offer = samples.hotel_offer()
    first, chosen = offer.options
    pending = samples.order(first, OrderStatus.PENDING_APPROVAL)
    approved_by = samples.approve(option_id="opt_2", note="Weekly volume, OK.")
    approved = samples.approval(ApprovalStatus.APPROVED, (approved_by,), option_id="opt_2")
    ordered = samples.order(chosen, OrderStatus.ORDERED, placed_by=PlacedBy.HUMAN_APPROVAL)
    steps = (
        (AuditEventType.REQUEST_RECEIVED, AGENT_HOTEL,
         AuditContext(profile_id=HOTEL, offer_id="off_1", facts={"text": PASTED_TEXT})),
        (AuditEventType.REQUEST_PARSED, GATEWAY,
         AuditContext(profile_id=HOTEL, offer_id="off_1", request=offer.request)),
        (AuditEventType.LOOKUP_PERFORMED, GATEWAY,
         AuditContext(profile_id=HOTEL, offer_id="off_1", facts={"products_looked_up": 35, "source": "replay"})),
        (AuditEventType.OFFER_CREATED, GATEWAY, AuditContext(offer=offer, profile=samples.hotel_profile())),
        (AuditEventType.POLICY_EVALUATED, GATEWAY,
         AuditContext(offer_id="off_1", option=first, decision=first.decision, profile=samples.hotel_profile())),
        (AuditEventType.APPROVAL_REQUESTED, AGENT_HOTEL, AuditContext(order=pending, approval=samples.approval())),
        (AuditEventType.APPROVAL_DECIDED, MAIJA,
         AuditContext(order=pending, approval=approved, approval_decision=approved_by, option=chosen,
                      decision=chosen.decision)),
        (AuditEventType.ORDER_CONFIRMED, GATEWAY,
         AuditContext(order=ordered, approval=approved, revalidation=samples.revalidation())),
    )
    for event_type, actor, context in steps:
        trail.record(event_type, actor, context)
    return trail


@pytest.fixture
def ward_flow(trail: AuditTrail, samples: Samples) -> AuditTrail:
    """Scenario 2 from request to order: the agent places the order alone."""
    offer = samples.ward_offer()
    option = offer.options[0]
    ordered = samples.order(option, OrderStatus.ORDERED, order_id="ord_2", profile_id=WARD, offer_id="off_2",
                            placed_by=PlacedBy.AGENT, approval_id=None)
    steps = (
        (AuditEventType.REQUEST_PARSED, GATEWAY,
         AuditContext(profile_id=WARD, offer_id="off_2", request=offer.request)),
        (AuditEventType.OFFER_CREATED, GATEWAY, AuditContext(offer=offer)),
        (AuditEventType.POLICY_EVALUATED, GATEWAY, AuditContext(offer_id="off_2", option=option)),
        (AuditEventType.ORDER_PLACED_BY_AGENT, AGENT_WARD, AuditContext(order=ordered)),
    )
    for event_type, actor, context in steps:
        trail.record(event_type, actor, context)
    return trail
