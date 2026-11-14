"""Audit events, hash chain, sentences and the two reader views (SPEC section 9).

Starts from Gabriela's log format (AIMO/policy/LOG-FORMAT.md, branch bio2): one event per step, a sentence
built from a template, every fired rule listed, a hash chain, append-only. What changed: the envelope is
CloudEvents 1.0, there is one chain for the whole trail instead of one per order, each event carries a
sentence for the buyer and one for the supplier instead of a visibility flag, and nothing is reported back
to the supplier as a fault in its data.

    trail = AuditTrail(store, clock)
    trail.record(AuditEventType.APPROVAL_REQUESTED, actor, AuditContext(order=order, approval=approval))
    trail.head()                        # (number of events, hash of the last one): for another party to keep

Several trails, in one process or in several, can write to one database: the store accepts an event only when
it follows the last one, and a trail that was overtaken reads the head again (`trail.py`). What the chain
shows and what it does not is in `chain.py`.

What each event type reads from the context. A sentence states only what its context holds: a missing object
leaves its clause out, and where that would mislead the sentence says what is not recorded.

    request.received        facts["text"] (the pasted words) or request · profile_id
    request.parsed          request
    lookup.performed        facts["products_looked_up"] and facts["source"], or offer
    offer.created           offer
    policy.evaluated        decision, or option with its decision
    order.placed_by_agent   order (its decision must have the verdict AUTO; any other is a `ValueError`)
    approval.requested      order · approval
    approval.decided        order · approval · approval_decision · option and decision when another option is chosen
    order.confirmed         order · approval · revalidation
    order.rejected          order · approval or approval_decision
    order.expired           order · approval
    order.blocked           option with its decision, or decision · offer_id
    order.not_placed        option · offer_id · revalidation
    authorisation.refused   approval or approval_id · facts["reason"] when the caller is not an agent
    evidence.attached       approval · evidence
    suggestions.shown       offer_id · facts["suggestions"] and facts["supplier_view"]["suggestions"]
    suggestion.accepted     offer_id · facts["suggestion"] and facts["supplier_view"]["suggestion"]
                            (both written by `tta.suggestions.events`; the supplier's view reaches only Valio Aimo)

Give `offer_id` on the request and lookup events as well: the trail of an order is found through its offer.
An event given ids only takes its buyer profile from the stored order, approval or offer, so the buyer's view
finds it; when the id names nothing stored, the event has no profile and no view by buyer profile shows it.
"""

from tta.audit.trail import AuditTrail

__all__ = ["AuditTrail"]
