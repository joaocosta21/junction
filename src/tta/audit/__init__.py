"""Audit events, hash chain, sentences and the two reader views (SPEC section 9).

Starts from Gabriela's log format (AIMO/policy/LOG-FORMAT.md, branch bio2): one event per step, a sentence
built from a template, every fired rule listed, a hash chain, append-only. What changed: the envelope is
CloudEvents 1.0, there is one chain for the whole trail instead of one per order, each event carries a
sentence for the buyer and one for the supplier instead of a visibility flag, and nothing is reported back
to the supplier as a fault in its data.

    trail = AuditTrail(store, clock)    # one per store and process: it lets one writer in at a time
    trail.record(AuditEventType.APPROVAL_REQUESTED, actor, AuditContext(order=order, approval=approval))

What each event type reads from the context. A missing object only makes the sentence shorter.

    request.received        facts["text"] (the pasted words) or request · profile_id
    request.parsed          request
    lookup.performed        facts["products_looked_up"] and facts["source"], or offer
    offer.created           offer
    policy.evaluated        decision, or option with its decision
    order.placed_by_agent   order
    approval.requested      order · approval
    approval.decided        order · approval · approval_decision · option and decision when another option is chosen
    order.confirmed         order · approval · revalidation
    order.rejected          order · approval or approval_decision
    order.expired           order · approval
    order.blocked           option with its decision, or decision · offer_id
    order.not_placed        option · offer_id · revalidation
    authorisation.refused   approval or approval_id · facts["reason"] when the caller is not an agent
    evidence.attached       approval · evidence

Give `offer_id` on the request and lookup events as well: the trail of an order is found through its offer.
"""

from tta.audit.trail import AuditTrail

__all__ = ["AuditTrail"]
