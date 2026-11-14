"""Rule F-10: the buyer's setting that keeps a person on every order.

Valio Aimo, 14 Nov 2026: "for now deactivate automatic order but you can suggest orders the final submition should
always have the input from the user", and of ordering alone as a setting: "after and if you are 100% sure yes".
So `auto_order_enabled` is a buyer setting that every shipped profile leaves off. While it is off, an order no
other rule sends to a person goes to the purchasing manager under F-10. Switched on, the agent orders alone only
when no rule fires AND every statement of every line is confirmed: price, quantity, delivery date, allergens and
origin (SPEC section 4). One statement that is unknown or missing, and F-10 still sends the order to a person.
The fixed rules hold either way (an unconfirmed quantity, price or date, a missing fact, a substitute that
loses a claim).

F-10 is the one rule that lives here and not in `rules.yaml`: it fires only when nothing else asks for a person,
which a `when` of the rules file cannot say. `rules.yaml` says so where the profile rules start. It is applied in
two places, so no path can forget it: when an option is judged (`tta.policy.engine`) and again when an order is
placed (`tta.orders.checking`). Its texts are part of the policy hash.
"""

from collections.abc import Sequence

from tta.contracts.common import ApproverRole, ClaimName, ClaimStatus, JsonDict, Verdict
from tta.contracts.offer import OfferLine, OfferOption
from tta.contracts.policy import BuyerProfile, FiredRule, PolicyDecision, RuleSummary

SETTING = "auto_order_enabled"  # the profile setting that drives the rule
HUMAN_APPROVAL = FiredRule(
    rule_id="F-10",
    title="Every order needs human approval",
    fixed=False,  # the buyer's setting drives it, so it is not one of the rules that hold whatever is set
    verdict=Verdict.APPROVAL,
    approver_role=ApproverRole.PURCHASING_MANAGER,
    sentence="Every order needs human approval before it can be confirmed.",
)
DECISION_SENTENCE = (
    "Every order needs human approval before it can be confirmed (F-10). It needs the purchasing manager."
)
# With the setting on, when a statement is not confirmed. {what} names each one with its product id.
NOT_CONFIRMED_SENTENCE = (
    "The agent orders alone only when every statement of the offer is confirmed (F-10). Not confirmed: {what}. "
    "It needs the purchasing manager."
)
NOT_CONFIRMED_RULE_SENTENCE = "Not every statement of the offer is confirmed, so a person confirms the order."
STATEMENT_WORDS = {
    ClaimName.PRICE: "the price", ClaimName.QUANTITY: "the quantity", ClaimName.DELIVERY_DATE: "the delivery date",
    ClaimName.ALLERGENS: "the allergen statement", ClaimName.ORIGIN: "the origin",
}
# At decision time, on an order that already waits: the person the approval names is the person F-10 asks for.
NAMED_ROLES_SENTENCE = (
    "Every order needs human approval before it can be confirmed (F-10). The roles this approval already names "
    "sign it."
)
# GET /v1/authority: the rule in plain language, by the value of the setting.
AUTHORITY_OFF = (
    "Every order needs human approval before it can be confirmed: this profile does not let the agent place an "
    "order alone. The purchasing manager approves when no other rule names a role."
)
AUTHORITY_ON = (
    "This profile lets the agent place an order alone, and only when no rule asks for a human and every statement "
    "of the offer is confirmed: price, quantity, delivery date, allergens and origin of every line. Otherwise the "
    "purchasing manager approves."
)


def require_human_approval(decision: PolicyDecision, profile: BuyerProfile, option: OfferOption) -> PolicyDecision:
    """The decision with F-10 applied. Unchanged when the order is blocked, when another rule already names who
    signs, or when the buyer switched ordering alone on and every statement of the option is confirmed."""
    if decision.verdict is Verdict.BLOCK or (decision.verdict is Verdict.APPROVAL and decision.required_roles):
        return decision
    facts: JsonDict = {f"profile.{SETTING}": profile.auto_order_enabled}
    rule, sentence = HUMAN_APPROVAL, DECISION_SENTENCE
    if profile.auto_order_enabled:
        not_confirmed = statements_not_confirmed(option)
        if not not_confirmed:
            return decision
        facts["not_confirmed"] = list(not_confirmed)
        rule = HUMAN_APPROVAL.model_copy(update={"sentence": NOT_CONFIRMED_RULE_SENTENCE})
        sentence = NOT_CONFIRMED_SENTENCE.format(what="; ".join(not_confirmed))
    return decision.model_copy(update={
        "verdict": Verdict.APPROVAL,
        "required_roles": (ApproverRole.PURCHASING_MANAGER,),
        "fired": (*decision.fired, rule.model_copy(update={"facts": facts})),
        "sentence": sentence,
    })


def statements_not_confirmed(option: OfferOption) -> tuple[str, ...]:
    """Every statement of the option that is not confirmed, as "the origin of 463797", in line order. A statement
    a line does not carry counts as not confirmed: no data means unknown, not safe."""
    return tuple(
        f"{STATEMENT_WORDS[name]} of {line.product_id}"
        for line in option.lines for name in ClaimName if not _is_confirmed(line, name)
    )


def _is_confirmed(line: OfferLine, name: ClaimName) -> bool:
    statuses = [check.status for check in line.claims if check.claim is name]
    return bool(statuses) and all(status is ClaimStatus.CONFIRMED for status in statuses)


def let_a_named_role_sign(
    decision: PolicyDecision, named_roles: Sequence[ApproverRole], signer_roles: Sequence[ApproverRole]
) -> PolicyDecision:
    """The decision on an order that already waits for a person, when F-10 is the only rule left.

    An approval asked of finance because of the day's spend may find, when finance decides, that the spend rule
    no longer holds. F-10 then asks for a person, and the role the approval names is one: it completes the
    approval it was asked for. The purchasing manager, F-10's own role, can complete it too.
    Unchanged when another rule fired, when the signer holds a role the decision asks for anyway, or when the
    signer holds none of the roles the approval names."""
    if decision.rule_ids != (HUMAN_APPROVAL.rule_id,) or set(signer_roles) & set(decision.required_roles):
        return decision
    if not set(signer_roles) & set(named_roles):
        return decision
    return decision.model_copy(update={"required_roles": tuple(named_roles), "sentence": NAMED_ROLES_SENTENCE})


def authority_summary(profile: BuyerProfile) -> RuleSummary:
    """F-10 as GET /v1/authority lists it, in this profile's own setting."""
    return RuleSummary(
        rule_id=HUMAN_APPROVAL.rule_id, title=HUMAN_APPROVAL.title, fixed=HUMAN_APPROVAL.fixed,
        verdict=HUMAN_APPROVAL.verdict, approver_role=HUMAN_APPROVAL.approver_role,
        sentence=AUTHORITY_ON if profile.auto_order_enabled else AUTHORITY_OFF,
    )


def canonical() -> JsonDict:
    """What the policy hash covers of F-10: the rule, the setting that drives it and every text it can show."""
    return {
        "rule": HUMAN_APPROVAL.model_dump(mode="json"), "setting": SETTING, "decision_sentence": DECISION_SENTENCE,
        "named_roles_sentence": NAMED_ROLES_SENTENCE, "not_confirmed_sentence": NOT_CONFIRMED_SENTENCE,
        "not_confirmed_rule_sentence": NOT_CONFIRMED_RULE_SENTENCE,
        "statements": {name.value: words for name, words in STATEMENT_WORDS.items()},
        "authority": {"off": AUTHORITY_OFF, "on": AUTHORITY_ON},
    }
