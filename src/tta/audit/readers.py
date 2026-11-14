"""What the supplier may see (SPEC section 9): never a limit value, an allergen exclusion, an approver's name or note.

Of whoever acted it sees the kind, and for an agent its id ("the agent's identity"): no role and no display name.
The buyer sees everything about its own requests, so the buyer's side needs no rule here.
"""

from __future__ import annotations

from collections.abc import Sequence

from tta.contracts.audit import Actor, ActorKind

# The fixed rules that read only the supplier's own statements or the caller's identity, with the meaning of
# SPEC section 7. Left out on purpose: F-02 and every P- rule, which come from the buyer's exclusions and limits.
SUPPLIER_RULE_MEANINGS = {
    "F-01": "a line's quantity is not confirmed",
    "F-03": "a fact a rule needs is missing",
    "F-04": "the offer expired, a cut-off passed, or price or availability changed",
    "F-05": "a substitute adds an allergen the original does not declare",
    "F-06": "an agent cannot approve an order",
}
AGENT_ON_APPROVAL_ROUTE = "F-06"
REDACTED_HUMAN = Actor(kind=ActorKind.HUMAN, id="buyer-human", display_name="A human at the buyer")


def supplier_rule_ids(rule_ids: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(rule_id for rule_id in rule_ids if rule_id in SUPPLIER_RULE_MEANINGS))


def supplier_actor(actor: Actor) -> Actor:
    """An agent by its id and kind only; a human only as "a human at the buyer"; the gateway as it is."""
    if actor.kind is ActorKind.HUMAN:
        return REDACTED_HUMAN
    if actor.kind is ActorKind.AGENT:
        return Actor(kind=ActorKind.AGENT, id=actor.id)
    return actor
