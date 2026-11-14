"""Sample offers, orders, approvals and audit events for the store tests. Built by hand; no live data."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tta.contracts.audit import GENESIS_HASH, Actor, ActorKind, AuditData, AuditEvent
from tta.contracts.availability import AvailabilityAssessment, ClaimCheck
from tta.contracts.common import (
    ApprovalStatus,
    ApproverRole,
    AvailabilityState,
    ClaimName,
    ClaimStatus,
    DataSource,
    DecisionKind,
    OptionKind,
    OrderStatus,
    PackSizeSource,
    Unit,
    Verdict,
)
from tta.contracts.offer import Coverage, Offer, OfferLine, OfferOption, Totals
from tta.contracts.order import Approval, ApprovalDecision, Order, RelianceStatement
from tta.contracts.policy import FiredRule, PolicyDecision
from tta.contracts.product import PackSize
from tta.contracts.request import PurchaseRequest, RequestLine

HELSINKI = timezone(timedelta(hours=2))
NOW = datetime(2026, 11, 14, 2, 52, tzinfo=HELSINKI)
ORDER_BY = datetime(2026, 11, 15, 17, 0, tzinfo=HELSINKI)
MONDAY = date(2026, 11, 16)


class Samples:
    """Builders for valid contract objects. Every call returns a new frozen object."""

    now = NOW

    def decision(self, profile_id: str = "hotel-kitchen") -> PolicyDecision:
        rule = FiredRule(
            rule_id="P-01", title="Spend limit per order", fixed=False, verdict=Verdict.APPROVAL,
            approver_role=ApproverRole.PURCHASING_MANAGER,
            sentence="The order total of €1,849.70 is above the €750.00 limit for one order.",
            facts={"total_net_eur": "1849.70", "max_order_net_eur": "750.00"},
        )
        return PolicyDecision(
            verdict=Verdict.APPROVAL, fired=(rule,), required_roles=(ApproverRole.PURCHASING_MANAGER,),
            policy_hash="a" * 64, profile_id=profile_id, evaluated_at=NOW, sentence="A human must decide.",
        )

    def option(self, option_id: str = "opt_1", profile_id: str = "hotel-kitchen") -> OfferOption:
        line = OfferLine(
            product_id="463380", name="Lactose free milk 1 l", category="10400", request_line_index=0,
            quantity=Decimal("698"), sales_unit="ST",
            pack_size=PackSize(value=Decimal("1"), unit=Unit.L, source=PackSizeSource.PRICE_RATIO),
            covers=Decimal("698"), unit_net_price=Decimal("2.65"), tax_rate=Decimal("13.5"),
            net=Decimal("1849.70"), tax=Decimal("249.71"), gross=Decimal("2099.41"), price_valid_to=ORDER_BY,
            availability=AvailabilityAssessment(
                product_id="463380", state=AvailabilityState.CONFIRMED, usable_amount=Decimal("698"),
                sales_unit="ST", available_date=MONDAY, closing_time=ORDER_BY, logistic_model="Stock",
                sentence="698 ST are confirmed for Monday 16 November.",
            ),
            claims=(ClaimCheck(claim=ClaimName.QUANTITY, status=ClaimStatus.CONFIRMED, sentence="Confirmed."),),
        )
        return OfferOption(
            option_id=option_id, kind=OptionKind.BEST_CONFIRMED, rank=1, title="Best confirmed option",
            summary="698 of 1,000 litres confirmed.", lines=(line,),
            totals=Totals(net=Decimal("1849.70"), tax=Decimal("249.71"), gross=Decimal("2099.41")),
            coverage=(Coverage(request_line_index=0, requested=Decimal("1000"), covered=Decimal("698"),
                               unit=Unit.L, fill_ratio=Decimal("0.698"), missing=Decimal("302")),),
            fill_ratio=Decimal("0.698"), valid_until=ORDER_BY, decision=self.decision(profile_id),
        )

    def offer(self, offer_id: str = "off_1", profile_id: str = "hotel-kitchen") -> Offer:
        request = PurchaseRequest(
            needed_by=MONDAY,
            lines=(RequestLine(text="1,000 litres of lactose-free milk", product_type="lactose_free_milk",
                               quantity=Decimal("1000"), unit=Unit.L),),
        )
        return Offer(
            offer_id=offer_id, created_at=NOW, profile_id=profile_id, agent_id=f"agent:{profile_id}",
            request=request, options=(self.option(profile_id=profile_id),), candidates_considered=35,
            source=DataSource.REPLAY, time_now=NOW,
        )

    def order(
        self, order_id: str = "ord_1", profile_id: str = "hotel-kitchen",
        status: OrderStatus = OrderStatus.PENDING_APPROVAL, offer_id: str = "off_1",
    ) -> Order:
        reliance = RelianceStatement(
            product_id="463380", unit_net_price=Decimal("2.65"), price_valid_to=ORDER_BY,
            availability_state=AvailabilityState.CONFIRMED, available_amount=Decimal("698"),
            available_date=MONDAY, closing_time=ORDER_BY, time_now=NOW, source=DataSource.REPLAY,
        )
        return Order(
            order_id=order_id, offer_id=offer_id, option_id="opt_1", profile_id=profile_id,
            agent_id=f"agent:{profile_id}", status=status, option=self.option(profile_id=profile_id),
            decision=self.decision(profile_id), approval_id=f"apr_{order_id}", reliance=(reliance,),
            idempotency_key="key-1", created_at=NOW, updated_at=NOW,
            status_sentence="Waiting for the purchasing manager.", source=DataSource.REPLAY,
        )

    def approval(
        self, approval_id: str = "apr_1", profile_id: str = "hotel-kitchen",
        status: ApprovalStatus = ApprovalStatus.PENDING, order_id: str = "ord_1",
    ) -> Approval:
        decided = ApprovalDecision(
            approver_id="human:maija", approver_name="Maija Virtanen", roles=(ApproverRole.PURCHASING_MANAGER,),
            decision=DecisionKind.APPROVE, note="Weekly volume, OK.", decided_at=NOW,
        )
        return Approval(
            approval_id=approval_id, order_id=order_id, offer_id="off_1", option_id="opt_1",
            profile_id=profile_id, status=status, required_roles=(ApproverRole.PURCHASING_MANAGER,),
            reasons=("The order total of €1,849.70 is above the €750.00 limit for one order.",),
            decisions=(decided,) if status is ApprovalStatus.APPROVED else (), created_at=NOW, valid_until=ORDER_BY,
        )

    def event(
        self, event_id: str, previous_hash: str = GENESIS_HASH, event_hash: str = "b" * 64,
        order_id: str | None = "ord_1", offer_id: str | None = "off_1", profile_id: str | None = "hotel-kitchen",
    ) -> AuditEvent:
        data = AuditData(
            actor=Actor(kind=ActorKind.AGENT, id="agent:hotel-kitchen", display_name="Hotel kitchen agent"),
            sentence="The agent sent a request.", supplier_sentence="A buyer's agent sent a request.",
            profile_id=profile_id, offer_id=offer_id, order_id=order_id, rule_ids=("P-01",),
            facts={"products_looked_up": 35}, previous_hash=previous_hash, hash=event_hash,
        )
        return AuditEvent(id=event_id, type="tta.v1.request.received", time=NOW, subject="order/ord_1", data=data)


@pytest.fixture(scope="session")
def samples() -> Samples:
    return Samples()
