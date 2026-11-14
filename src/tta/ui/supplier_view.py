"""How the order was decided, as Valio Aimo's view of the audit trail gives it (P9b B13-2).

Scores on the 20% "how decisions are logged and auditable" and on Valio's answer B13 ("all the steps and
decisions"). The supplier's events carry the decision (`facts.decision`: every rule that fired, its title, whether
it is fixed, its outcome and the role that signs) and the products left out for a reason about Valio Aimo's own
data (`facts.offer.left_out`, `excluded_by_reason`). The trail masks the buyer's values (`tta.audit`): no limit
amount, no allergen code, no approver's name, no note. The page reads those facts as data and adds nothing to them.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from tta.audit.readers import MASKED_BY_RULE
from tta.contracts.audit import AuditView
from tta.contracts.common import ApproverRole, ExclusionReason, Verdict

DECISION_FACT = "decision"
OFFER_FACT = "offer"
# Two reasons whose products the supplier's trail never names: they say which allergen the buyer excludes.
ALLERGEN_REASONS = (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.ALLERGEN_NOT_STATED)
PRODUCTS_SHOWN_PER_REASON = 10  # the rest are counted: "and 5 more"

logger = logging.getLogger(__name__)


class _Fact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")


class _Rule(_Fact):
    rule_id: str
    title: str | None = None
    fixed: bool = False
    verdict: Verdict | None = None
    approver_role: ApproverRole | None = None
    product_id: str | None = None


class _Decision(_Fact):
    verdict: Verdict | None = None
    rules: tuple[_Rule, ...] = ()


class _LeftOut(_Fact):
    product_id: str
    name: str | None = None
    reason: ExclusionReason


class _Offer(_Fact):
    excluded_by_reason: dict[ExclusionReason, int] = {}
    left_out: tuple[_LeftOut, ...] = ()


@dataclass(frozen=True)
class RuleRow:
    """One rule that fired, once, with the products it fired on and what the trail masks of it."""

    rule_id: str
    title: str
    fixed: bool
    verdict: Verdict | None
    approver_role: ApproverRole | None
    product_ids: tuple[str, ...]
    masked: str | None


@dataclass(frozen=True)
class ReasonRow:
    """Why products were left out: the count, and the products when the reason is about Valio Aimo's own data."""

    reason: ExclusionReason
    count: int
    products: tuple[tuple[str, str | None], ...]  # (id, name), the first few; empty for the two allergen reasons
    more: int  # products of this reason the trail names and the page does not list
    masked: bool  # an allergen reason: the trail names neither the allergen nor the products


@dataclass(frozen=True)
class SupplierDecision:
    verdict: Verdict | None
    rules: tuple[RuleRow, ...]
    left_out: tuple[ReasonRow, ...]


def _newest(audit: AuditView, fact: str, model: type[_Fact]) -> Any:
    """The newest event's fact of this name, validated; `None` when no event carries one that can be read."""
    for event in reversed(audit.events):
        found = event.facts.get(fact)
        if not isinstance(found, dict):
            continue
        try:
            return model.model_validate(found)
        except ValidationError as error:
            logger.warning("The %s fact of audit event %s cannot be read: %d errors", fact, event.id,
                           error.error_count())
            return None
    return None


def _rows(rules: Iterable[_Rule]) -> tuple[RuleRow, ...]:
    """A rule about a line fires once per line: one row per rule and outcome, with every product it fired on."""
    grouped: dict[tuple[str, Verdict | None, ApproverRole | None], tuple[_Rule, list[str]]] = {}
    for rule in rules:
        _, products = grouped.setdefault((rule.rule_id, rule.verdict, rule.approver_role), (rule, []))
        if rule.product_id is not None and rule.product_id not in products:
            products.append(rule.product_id)
    return tuple(
        RuleRow(rule_id=rule.rule_id, title=rule.title or rule.rule_id, fixed=rule.fixed, verdict=rule.verdict,
                approver_role=rule.approver_role, product_ids=tuple(products), masked=MASKED_BY_RULE.get(rule.rule_id))
        for rule, products in grouped.values()
    )


def _reasons(counts: Mapping[ExclusionReason, int], left_out: Iterable[_LeftOut]) -> tuple[ReasonRow, ...]:
    """Reasons about Valio Aimo's own data first, in the order of the code list; the two allergen reasons last."""
    entries = tuple(left_out)
    ordered = [reason for reason in ExclusionReason if reason not in ALLERGEN_REASONS] + list(ALLERGEN_REASONS)
    rows = []
    for reason in ordered:
        if not counts.get(reason):
            continue
        named = [] if reason in ALLERGEN_REASONS else [
            (entry.product_id, entry.name) for entry in entries if entry.reason is reason
        ]
        shown = tuple(named[:PRODUCTS_SHOWN_PER_REASON])
        rows.append(ReasonRow(reason=reason, count=counts[reason], products=shown, more=len(named) - len(shown),
                              masked=reason in ALLERGEN_REASONS))
    return tuple(rows)


def supplier_decision(audit: AuditView) -> SupplierDecision | None:
    """The decision and the products left out, from the supplier's view of the trail; `None` without a decision."""
    decision: _Decision | None = _newest(audit, DECISION_FACT, _Decision)
    if decision is None:
        return None
    offer: _Offer | None = _newest(audit, OFFER_FACT, _Offer)
    left_out = () if offer is None else _reasons(offer.excluded_by_reason, offer.left_out)
    return SupplierDecision(verdict=decision.verdict, rules=_rows(decision.rules), left_out=left_out)
