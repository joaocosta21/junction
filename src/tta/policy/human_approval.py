"""Gateway-wide human approval requirement."""

from tta.contracts.common import ApproverRole, Verdict
from tta.contracts.policy import FiredRule, PolicyDecision

HUMAN_APPROVAL = FiredRule(
    rule_id="F-10",
    title="Every order needs human approval",
    fixed=True,
    verdict=Verdict.APPROVAL,
    approver_role=ApproverRole.PURCHASING_MANAGER,
    sentence="Every order needs human approval before it can be confirmed.",
)


def require_human_approval(decision: PolicyDecision) -> PolicyDecision:
    """Route otherwise autonomous orders to purchasing; preserve specialist approval and blocks."""
    if decision.verdict is Verdict.BLOCK or (
        decision.verdict is Verdict.APPROVAL and decision.required_roles
    ):
        return decision
    return decision.model_copy(update={
        "verdict": Verdict.APPROVAL,
        "required_roles": (ApproverRole.PURCHASING_MANAGER,),
        "fired": (*decision.fired, HUMAN_APPROVAL),
        "sentence": "Every order needs human approval before it can be confirmed (F-10). "
        "It needs the purchasing manager.",
    })
