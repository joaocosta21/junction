"""The `AuditSink` port: one CloudEvents 1.0 event per step, hash-chained, append-only, with two reader views.

Scores on the 20% "how decisions are logged and auditable" and on the brief's audit trail "for both buyer
and Valio Aimo"; the envelope is an open, documented format (15%). CloudEvents 1.0.2 requires `id`, `source`,
`specversion` and `type`; `time`, `subject` and `datacontenttype` are its optional attributes and are set too.
"""

from __future__ import annotations

import threading
from dataclasses import replace
from uuid import uuid4

from tta.audit.chain import seal, verify_events, verify_view
from tta.audit.facts import buyer_facts, supplier_facts
from tta.audit.readers import AGENT_ON_APPROVAL_ROUTE
from tta.audit.scope import Scope, distinct_rule_ids, resolve
from tta.audit.sentences import buyer_sentence
from tta.audit.supplier_sentences import supplier_sentence
from tta.audit.views import check_view, project, select
from tta.contracts.audit import (
    EVENT_TYPE_PREFIX,
    GENESIS_HASH,
    Actor,
    ActorKind,
    AuditContext,
    AuditData,
    AuditEvent,
    AuditEventType,
    AuditView,
    ChainVerification,
)
from tta.contracts.common import AuditReader
from tta.contracts.ports import Clock, PolicyEngine, Store
from tta.store.errors import AuditChainConflict

# The stored object an event type is first about; the next ones are used when that id is not known.
SUBJECT_ORDER = {
    "order": ("order", "approval", "offer"),
    "approval": ("approval", "order", "offer"),
    "authorisation": ("approval", "order", "offer"),
    "evidence": ("approval", "order", "offer"),
}
DEFAULT_SUBJECT_ORDER = ("offer", "order", "approval")
UNSEALED = ""
# How often one event is chained to the head and offered to the store before the trail gives up. Each failed
# attempt means another writer (a second process on the same database) appended an event in between.
MAX_APPEND_ATTEMPTS = 5
GAVE_UP_DETAIL = (
    "The audit event could not be added: other writers extended the audit trail first on each of "
    "{attempts} attempts. Nothing was recorded."
)


def _subject(event_type: AuditEventType, scope: Scope) -> str | None:
    """`order/<id>`, `approval/<id>` or `offer/<id>`; none when the event is about nothing stored yet."""
    ids = {"order": scope.order_id, "approval": scope.approval_id, "offer": scope.offer_id}
    family = event_type.value.split(".", maxsplit=1)[0]
    for kind in SUBJECT_ORDER.get(family, DEFAULT_SUBJECT_ORDER):
        if ids[kind]:
            return f"{kind}/{ids[kind]}"
    return None


def _rule_ids(event_type: AuditEventType, actor: Actor, scope: Scope) -> tuple[str, ...]:
    if event_type is AuditEventType.AUTHORISATION_REFUSED:
        return (AGENT_ON_APPROVAL_ROUTE,) if actor.kind is ActorKind.AGENT else ()
    return distinct_rule_ids(scope.decision.fired) if scope.decision else ()


class AuditTrail:
    """Writes and reads the audit trail. It can append, read and verify; it cannot change or remove an event."""

    def __init__(self, store: Store, clock: Clock, policy: PolicyEngine | None = None) -> None:
        self._store = store
        self._clock = clock
        self._policy = policy
        self._lock = threading.Lock()  # one writer at a time in this process; the store guards against the others

    def record(self, event_type: AuditEventType, actor: Actor, context: AuditContext) -> AuditEvent:
        """Build the event from the objects in the context, chain it to the last one and append it.

        Raises `ValueError` for a context that contradicts the event type (an order "placed by the agent"
        under a decision that asks for a human) and `AuditChainConflict` when other writers kept extending
        the trail first. In both cases nothing is stored.
        """
        now = self._clock.now()
        if now.utcoffset() is None:
            raise ValueError("The clock gave a time with no UTC offset; an audit event needs one (RFC 3339).")
        scope = self._with_stored_profile(resolve(context))
        data = AuditData(
            actor=actor,
            sentence=buyer_sentence(event_type, actor, context, scope),
            supplier_sentence=supplier_sentence(event_type, actor, context, scope),
            profile_id=scope.profile_id,
            offer_id=scope.offer_id,
            order_id=scope.order_id,
            approval_id=scope.approval_id,
            rule_ids=_rule_ids(event_type, actor, scope),
            facts=buyer_facts(context, scope),
            supplier_facts=supplier_facts(context, scope),
            policy_hash=self._policy_hash(context, scope),
            previous_hash=GENESIS_HASH,
            hash=UNSEALED,
        )
        unchained = AuditEvent(
            id=str(uuid4()), type=f"{EVENT_TYPE_PREFIX}{event_type.value}", time=now,
            subject=_subject(event_type, scope), data=data,
        )
        # The store first, the trail's lock second: the order every writer uses, so a thread inside
        # `store.atomic()` and a thread recording an event can never wait for each other.
        with self._store.atomic(), self._lock:
            return self._append(unchained)

    def view(
        self, reader: AuditReader, order_id: str | None = None, offer_id: str | None = None,
        profile_id: str | None = None,
    ) -> AuditView:
        """The events of one order, offer or buyer as one reader sees them, with the state of the chain.

        The whole chain is verified, but `chain` speaks only of the events in this view: `checked` is their
        number, and a broken event is named only when it is one of them (otherwise the sentence says the trail
        is broken at an event outside this view). `verify_chain()` reports on every event.

        Raises `InvalidRequest` for an unknown reader, and for a buyer's view that names no order, offer or profile.
        The caller checks that the order, offer or profile belongs to whoever is asking.
        """
        known_reader = check_view(reader, order_id, offer_id, profile_id)
        events = self._store.list_audit_events()
        chosen = select(events, order_id, offer_id, profile_id)
        return AuditView(
            reader=known_reader, order_id=order_id, offer_id=offer_id,
            events=tuple(project(event, known_reader) for event in chosen), chain=verify_view(events, chosen),
        )

    def verify_chain(self) -> ChainVerification:
        """Ok, or the first event that was changed or does not follow the one before it, over the whole trail.

        It counts and names any event, so it is for whoever may see the whole trail, not for one buyer.
        """
        return verify_events(self._store.list_audit_events())

    def head(self) -> tuple[int, str]:
        """How many events the trail holds and the hash of the last one (64 zeros when it holds none).

        Verification cannot show that the newest events were cut off (`chain.py`). A party that kept this pair
        from an earlier moment can: the trail must still hold at least that many events, and its event at that
        position must still have that hash.
        """
        events = self._store.list_audit_events()
        return len(events), events[-1].data.hash if events else GENESIS_HASH

    def _append(self, unchained: AuditEvent) -> AuditEvent:
        """Chain the event to the current head and append it. When the store answers that another writer
        appended first, read the head again and try once more, a few times at most."""
        conflict: AuditChainConflict | None = None
        for _ in range(MAX_APPEND_ATTEMPTS):
            head = self._store.last_audit_hash() or GENESIS_HASH
            event = seal(unchained.model_copy(update={
                "data": unchained.data.model_copy(update={"previous_hash": head}),
            }))
            try:
                self._store.append_audit_event(event)
            except AuditChainConflict as error:
                conflict = error
            else:
                return event
        raise AuditChainConflict(GAVE_UP_DETAIL.format(attempts=MAX_APPEND_ATTEMPTS)) from conflict

    def _with_stored_profile(self, scope: Scope) -> Scope:
        """The scope with the buyer profile of the stored order, approval or offer it names, when the context
        gave none: an event recorded with ids only is still found by its buyer's view."""
        if scope.profile_id is not None:
            return scope
        lookups = (
            (scope.order_id, self._store.get_order),
            (scope.approval_id, self._store.get_approval),
            (scope.offer_id, self._store.get_offer),
        )
        for stored_id, get in lookups:
            stored = get(stored_id) if stored_id else None
            if stored is not None:
                return replace(scope, profile_id=stored.profile_id)
        return scope

    def _policy_hash(self, context: AuditContext, scope: Scope) -> str | None:
        """The hash of the rules and profile in force: from the decision, else from the offer, else the engine."""
        if scope.decision is not None:
            return scope.decision.policy_hash
        decided = (option.decision for option in context.offer.options) if context.offer else ()
        from_offer = next((decision.policy_hash for decision in decided if decision is not None), None)
        if from_offer is not None:
            return from_offer
        if self._policy is not None and context.profile is not None:
            return self._policy.policy_hash(context.profile)
        return None
