"""Who may do what in the order book (SPEC sections 2 and 8). Scores on the 20% "autonomy and controls".

An agent places orders and reads its own buyer's records. An approver decides for its own buyer, and only
for a role it holds and is listed under in the buyer's profile. The supplier does neither: it has the
audit view. An agent on an approval route is rule F-06. A record of another buyer is answered exactly like
a record that does not exist, so nobody learns which ids another buyer holds.
"""

from __future__ import annotations

from tta.contracts.audit import Actor, ActorKind
from tta.contracts.common import ApproverRole, Identity
from tta.contracts.errors import NotAuthorised
from tta.contracts.policy import BuyerProfile
from tta.orders import wording

SUPPLIER_ROLE = "supplier"


def actor_of(identity: Identity) -> Actor:
    """The caller as the audit trail names it: the agent, or a human with the roles of its token."""
    if identity.is_agent:
        return Actor(kind=ActorKind.AGENT, id=identity.id, display_name=identity.display_name)
    role = ", ".join(role.value for role in identity.roles) or SUPPLIER_ROLE
    return Actor(kind=ActorKind.HUMAN, id=identity.id, role=role, display_name=identity.display_name)


def roles_that_count(identity: Identity, profile: BuyerProfile) -> tuple[ApproverRole, ...]:
    """The roles this caller can sign for: held in its token, for this buyer, and listed under its id in the
    profile's `approver_roles`. A token alone is not enough, so the profile setting is real."""
    if not identity.is_approver or identity.profile_id != profile.profile_id:
        return ()
    return tuple(role for role in identity.roles if identity.id in profile.approver_roles.get(role, ()))


def why_not_an_approver(identity: Identity) -> str | None:
    """Why this caller can decide no approval at all; `None` for an approver. An agent here is rule F-06."""
    if identity.is_agent:
        return wording.AGENT_CANNOT_DECIDE
    if not identity.is_approver:
        return wording.ONLY_AN_APPROVER_DECIDES
    return None


def is_of_another_buyer(identity: Identity, profile_id: str) -> bool:
    """Whether a record of this profile belongs to another buyer than the caller's. The supplier has no buyer:
    it is refused by kind (`require_buyer_side`, `why_not_an_approver`), never by this."""
    return identity.profile_id is not None and identity.profile_id != profile_id


def require_buyer_side(identity: Identity) -> None:
    """Orders and approvals are read by the buyer's agent and approvers. Checked before any lookup."""
    if identity.is_supplier:
        raise NotAuthorised(wording.SUPPLIER_READS_THE_AUDIT_VIEW)
