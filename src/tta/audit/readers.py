"""What Valio Aimo may see of the log (SPEC section 9, as Valio answered on 14 Nov: "all the steps and decisions",
"why it made that decision and the logic behind it and product considered").

Shown: every rule that fired, by its id, its title, whether it is a fixed rule or one the buyer set, its outcome
and the role that must sign; the claims and labels asked for; the products considered and left out.
Masked: limit amounts, allergen codes and the products a rule about an excluded allergen fired on. The role
stands for the approver's name. Notes and the buyer's own words stay out.

Of whoever acted Valio Aimo sees the kind, for an agent its id ("the agent's identity"), and for a human the
approver roles the gateway knows. The buyer sees everything about its own requests, so the buyer's side needs
no rule here. The SQL view `audit_supplier` (`tta/store/sql/003_reader_views.sql`) shows the same;
`tests/audit/test_sql_view.py` fails when the two differ.
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.contracts.audit import Actor, ActorKind
from tta.contracts.common import ApproverRole

# Kept for `tests/store_pg/test_reader_views.py`, which builds its list of rule ids from the keys. Since S4 no
# list filters the supplier's rules: a rule is named by the title it fired with (`tta.audit.supplier_decisions`).
SUPPLIER_RULE_MEANINGS = {
    "F-01": "a line's quantity is not confirmed",
    "F-03": "a fact a rule needs is missing",
    "F-04": "the offer expired, a cut-off passed, or price or availability changed",
    "F-05": "a substitute adds an allergen the original does not declare, or raises one to contains",
    "F-06": "an agent cannot approve an order",
    "F-07": "a price is not confirmed, a delivery date is ruled out, or a needed-by date is not verifiably met",
    "F-08": "a substitute lacks a nutritional claim the original carries",
}
AGENT_ON_APPROVAL_ROUTE = "F-06"
# The rules that fire because of an allergen the buyer excludes. Valio Aimo reads their id, title and outcome;
# never the allergen, and never the product, which together with Valio's own allergen data would give the code.
RULES_ABOUT_AN_EXCLUDED_ALLERGEN = ("F-02", "P-04")
# What a rule read that Valio Aimo is not shown. The sentence says so, so a masked value is not taken for a gap.
MASKED_BY_RULE = {
    "P-01": "the amount is not shown",
    "P-02": "the amounts are not shown",
    "P-03": "the buyer's minimum is not shown",
    "P-08": "the buyer's tolerance is not shown",
    "P-09": "the amount and the buyer's limit are not shown",
    **dict.fromkeys(RULES_ABOUT_AN_EXCLUDED_ALLERGEN, "which allergen and which product are not shown"),
}
KNOWN_ROLES = tuple(role.value for role in ApproverRole)
ROLE_SEPARATOR = ", "  # how `tta.orders.access.actor_of` joins the roles of one token
HUMAN_ID = "buyer-human"
HUMAN_WITHOUT_A_ROLE = "A human at the buyer"
BUYERS_ROLE = "The buyer's {roles}"


def supplier_rule_ids(rule_ids: Sequence[str]) -> tuple[str, ...]:
    """Every rule that fired, each id once, in the order they fired."""
    return tuple(dict.fromkeys(rule_ids))


def supplier_role(role: str | None) -> str | None:
    """The approver roles the gateway knows, of those an actor carries. Any other text is dropped: the field
    is free text in the contract, and only a role may stand for a person."""
    held = [name for name in (role or "").split(ROLE_SEPARATOR) if name in KNOWN_ROLES]
    return ROLE_SEPARATOR.join(held) or None


def supplier_actor(actor: Actor) -> Actor:
    """An agent by its id and kind only; a human by role, never by name or id; the gateway as it is."""
    if actor.kind is ActorKind.AGENT:
        return Actor(kind=ActorKind.AGENT, id=actor.id)
    if actor.kind is not ActorKind.HUMAN:
        return actor
    role = supplier_role(actor.role)
    if role is None:
        return Actor(kind=ActorKind.HUMAN, id=HUMAN_ID, display_name=HUMAN_WITHOUT_A_ROLE)
    return Actor(
        kind=ActorKind.HUMAN, id=HUMAN_ID, role=role, display_name=BUYERS_ROLE.format(roles=role.replace("_", " ")),
    )
