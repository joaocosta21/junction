"""Buyer profile, the policy decision and the authority summary (SPEC section 7)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field, model_validator

from tta.contracts.availability import RevalidationResult
from tta.contracts.common import (
    AllergenStrictness,
    ApproverRole,
    Contract,
    DepositRule,
    JsonDict,
    Money,
    Ratio,
    SubstitutionScope,
    VariableWeightRule,
    Verdict,
)
from tta.contracts.standing import StandingHistory

MAX_DRIFT_RATIO = 1  # a tolerance of 100%: a quantity or a price may double before a human looks


class BuyerProfile(Contract):
    """What one buyer lets its agent decide alone. The values are illustrative and labelled as ours."""

    profile_id: str
    display_name: str
    description: str | None = None
    illustrative: bool = True
    auto_order_enabled: bool
    max_order_net_eur: Money = Field(ge=0)
    max_daily_net_eur: Money = Field(ge=0)
    min_fill_ratio: Ratio = Field(ge=0, le=1)
    excluded_allergens: tuple[str, ...] = ()
    allergen_strictness: AllergenStrictness | None = Field(
        default=None,
        description="The allergen rule for every excluded allergen that allergen_strictness_by_code does not name",
    )
    allergen_strictness_by_code: dict[str, AllergenStrictness] = Field(
        default_factory=dict,
        description="The allergen rule of one excluded allergen, by its GS1 code: STRICT for an allergy that must be "
        "confirmed, DECLARED_ONLY for one kept out as an ingredient. Each code must also be in excluded_allergens",
    )
    substitution_without_approval: SubstitutionScope
    variable_weight: VariableWeightRule
    deposits: DepositRule
    require_confirmed: bool = False
    standing_order_drift_ratio: Ratio | None = Field(
        default=None, ge=0, le=MAX_DRIFT_RATIO,
        description="How far a renewal of a standing order may differ from the median of its history, on any line's "
        "quantity or unit price, before it goes to a human (P-08). None: not set, so a renewal with enough history "
        "goes to a human for a missing fact (F-03)",
    )
    approver_roles: dict[ApproverRole, tuple[str, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exclusions_need_a_strictness(self) -> BuyerProfile:
        if self.excluded_allergens and self.allergen_strictness is None:
            raise ValueError("a profile that excludes allergens must set allergen_strictness")
        stray = [code for code in self.allergen_strictness_by_code if code not in self.excluded_allergens]
        if stray:
            raise ValueError(
                f"allergen_strictness_by_code names allergens the profile does not exclude: {', '.join(stray)}"
            )
        return self

    def strictness_for(self, code: str) -> AllergenStrictness | None:
        """The allergen rule this profile applies to one excluded allergen."""
        return self.allergen_strictness_by_code.get(code, self.allergen_strictness)

    def codes_under(self, strictness: AllergenStrictness) -> tuple[str, ...]:
        """The excluded allergens this profile checks under one rule, in the profile's order."""
        return tuple(code for code in self.excluded_allergens if self.strictness_for(code) is strictness)


class PolicyContext(Contract):
    """Facts the engine needs that are not on the option. A value left `None` is a missing fact (F-03)."""

    now: datetime
    day_committed_net_eur: Decimal | None = None  # today's ORDERED and PENDING_APPROVAL, this order excluded
    at_order_time: bool = False
    revalidation: RevalidationResult | None = None  # set at order time; None there is a missing fact
    # The standing order the request renews and its past renewals (P-08). None means "not a renewal": it is
    # never a missing fact.
    standing_history: StandingHistory | None = None


class FiredRule(Contract):
    """One rule that fired, with the facts it read and its sentence."""

    rule_id: str
    title: str
    fixed: bool  # True for the F- rules no profile can switch off
    verdict: Verdict
    approver_role: ApproverRole | None = None
    sentence: str
    facts: JsonDict = Field(default_factory=dict)
    product_id: str | None = None  # set when the rule fired on one line


class PolicyDecision(Contract):
    """What the policy says about one option: the verdict, every rule that fired, who must sign."""

    verdict: Verdict
    fired: tuple[FiredRule, ...] = ()
    required_roles: tuple[ApproverRole, ...] = ()
    policy_hash: str  # SHA-256 of the canonical rules plus the profile in force
    profile_id: str
    evaluated_at: datetime
    sentence: str

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.rule_id for rule in self.fired)


class RuleSummary(Contract):
    rule_id: str
    title: str
    fixed: bool
    verdict: Verdict
    approver_role: ApproverRole | None = None
    sentence: str  # plain language, with this profile's values filled in


class Authority(Contract):
    """Answer of GET /v1/authority: what the calling agent may decide alone."""

    profile: BuyerProfile
    rules: tuple[RuleSummary, ...] = ()
    summary: tuple[str, ...] = ()
    policy_hash: str
    note: str  # says that the limit values are illustrative
