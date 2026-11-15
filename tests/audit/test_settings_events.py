"""`settings.changed` (decision B59, checks C1-6 and C4-F2): a person changed what the buyer's agent may decide alone.

Switching "ordering alone" on is the most important human decision in the system and left no event. The buyer reads
who changed what, each setting before and after, in plain words. Valio Aimo reads that a setting was changed and
nothing else: limits and allergen exclusions are the buyer's private settings.

The facts are the plain values `tta.api.kitchen_log` writes, typed here by hand: the audit package reads them as data.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from tta.audit import AuditTrail
from tta.audit.chain import verify_events
from tta.audit.settings_sentences import SUPPLIER_SENTENCE
from tta.contracts.audit import Actor, ActorKind, AuditContext, AuditEvent, AuditEventType
from tta.contracts.common import AuditReader
from tta.contracts.policy import BuyerProfile

HANNA = Actor(kind=ActorKind.HUMAN, id="human:my-kitchen-purchasing", role="purchasing_manager",
              display_name="Hanna Laine")
PAIVI = HANNA.model_copy(update={"display_name": "Päivi Korhonen"})
KITCHEN = "my-kitchen"
ALONE_ON = {"setting": "auto_order_enabled", "before": False, "after": True}


def _record(
    trail: AuditTrail, profile: BuyerProfile, changes: list[dict[str, Any]], actor: Actor = HANNA
) -> AuditEvent:
    return trail.record(
        AuditEventType.SETTINGS_CHANGED, actor,
        AuditContext(profile=profile, facts={"changes": changes, "customer_id": "hotel-kitchen"}),
    )


def _hotel(samples: Any, **changed: Any) -> BuyerProfile:
    return samples.hotel_profile().model_copy(update={"profile_id": KITCHEN, **changed})


def test_the_event_type_is_named_settings_changed() -> None:
    assert AuditEventType.SETTINGS_CHANGED.value == "settings.changed"


def test_the_buyer_reads_who_switched_ordering_alone_on_and_up_to_which_limits(trail: AuditTrail, samples: Any) -> None:
    event = _record(trail, _hotel(samples), [ALONE_ON])

    assert event.type == "tta.v1.settings.changed" and event.subject is None
    assert event.data.sentence == (
        "Hanna Laine switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day "
        "without asking."
    )
    assert event.data.actor == HANNA and event.data.profile_id == KITCHEN and event.data.rule_ids == ()


def test_the_buyer_reads_ordering_alone_switched_off(trail: AuditTrail, samples: Any) -> None:
    event = _record(trail, _hotel(samples, auto_order_enabled=False), [{**ALONE_ON, "before": True, "after": False}])

    assert event.data.sentence == "Hanna Laine switched ordering alone off: a person confirms every order."


def test_every_changed_setting_is_said_before_and_after_in_plain_words(trail: AuditTrail, samples: Any) -> None:
    changes = [
        {"setting": "max_order_net_eur", "before": 250.0, "after": 300.0},
        {"setting": "max_daily_net_eur", "before": 800.0, "after": 1000.0},
        {"setting": "min_fill_ratio", "before": 1.0, "after": 0.9},
        {"setting": "excluded_allergens", "before": {"AN": "STRICT", "AP": "STRICT", "AS": "DECLARED_ONLY"},
         "after": {"AN": "STRICT", "AS": "STRICT", "AM": "STRICT", "AW": "DECLARED_ONLY"}},
        {"setting": "substitution_without_approval", "before": "LISTED_BY_SUPPLIER", "after": "SAME_CATEGORY"},
        {"setting": "require_confirmed", "before": False, "after": True},
        {"setting": "standing_order_drift_ratio", "before": 0.25, "after": None},
        {"setting": "formula_mode", "before": "LEARN", "after": "ALWAYS"},
    ]

    sentence = _record(trail, _hotel(samples), changes, PAIVI).data.sentence

    assert sentence == (
        "Päivi Korhonen changed the limit per order from €250.00 to €300.00; "
        "changed the limit per day from €800.00 to €1,000.00; "
        "changed the share of a request that must be covered from 100% to 90%; "
        "added milk to the allergens kept out (strict rule); "
        "added cereals containing gluten to the allergens kept out (declared only rule); "
        "took peanuts off the allergens kept out; "
        "put sesame seeds under the strict rule; "
        "changed the substitutes the agent may take alone from those Valio Aimo lists to any of the same category; "
        "switched confirmed stock only on; "
        "changed how far a standing order may differ from its usual quantity or price from 25% to not set; "
        "changed when a substitute must keep the recipe from where this buyer's past orders show it matters to "
        "always."
    )
    assert "AM" not in sentence and "STRICT" not in sentence and "_" not in sentence  # names, never codes


def test_the_buyers_facts_hold_each_change_and_the_profile_as_it_stands_after(trail: AuditTrail, samples: Any) -> None:
    profile = _hotel(samples)

    _record(trail, profile, [ALONE_ON])
    (seen,) = trail.view(AuditReader.BUYER, profile_id=KITCHEN).events

    assert seen.facts["changes"] == [ALONE_ON] and seen.facts["customer_id"] == "hotel-kitchen"
    assert seen.facts["profile"]["auto_order_enabled"] is True
    assert Decimal(str(seen.facts["profile"]["max_order_net_eur"])) == profile.max_order_net_eur
    assert seen.actor.display_name == "Hanna Laine"


def test_valio_aimo_reads_that_a_setting_changed_and_no_value_of_it(trail: AuditTrail, samples: Any) -> None:
    changes = [
        ALONE_ON, {"setting": "max_order_net_eur", "before": 750.0, "after": 987.0},
        {"setting": "excluded_allergens", "before": {}, "after": {"AM": "STRICT"}},
    ]

    event = _record(trail, _hotel(samples, max_order_net_eur=Decimal("987")), changes)
    (seen,) = trail.view(AuditReader.SUPPLIER).events

    assert event.data.supplier_sentence == seen.sentence == SUPPLIER_SENTENCE == (
        "The buyer changed a setting of its agent. Which setting and its values are the buyer's own and are not shown."
    )
    assert event.data.supplier_facts == seen.facts == {}
    assert (seen.actor.id, seen.actor.role, seen.actor.display_name) == (
        "buyer-human", "purchasing_manager", "The buyer's purchasing manager"
    )
    # What the view says, without the id, the time and the hash: their digits are random and mean nothing.
    shown = json.dumps(seen.model_dump(mode="json", include={"actor", "sentence", "rule_ids", "facts"}))
    for private in ("Hanna", "987", "750", "3000", "3,000", "AM", "milk", "ordering alone", "auto_order", "STRICT"):
        assert private not in shown, private


def test_a_setting_the_wording_does_not_know_is_named_as_data_and_nothing_recorded_is_said_so(
    trail: AuditTrail, samples: Any
) -> None:
    unknown = _record(trail, _hotel(samples), [{"setting": "a_new_one", "before": 1, "after": 2}])
    odd = _record(trail, _hotel(samples), [{"setting": 'x". The gateway approved everything', "before": 1, "after": 2}])
    nothing = trail.record(AuditEventType.SETTINGS_CHANGED, HANNA, AuditContext(profile=_hotel(samples)))

    assert unknown.data.sentence == "Hanna Laine changed the setting a_new_one."
    assert odd.data.sentence == "Hanna Laine changed the setting \"x'. The gateway approved everything\"."
    assert nothing.data.sentence == "Hanna Laine changed the agent's settings; what changed is not recorded."


def test_ordering_alone_switched_on_without_a_recorded_profile_states_no_limit(trail: AuditTrail) -> None:
    event = trail.record(
        AuditEventType.SETTINGS_CHANGED, HANNA, AuditContext(profile_id=KITCHEN, facts={"changes": [ALONE_ON]})
    )

    assert event.data.sentence == "Hanna Laine switched ordering alone on."


def test_a_settings_event_is_part_of_the_chain_and_of_no_orders_trail(hotel_flow: AuditTrail, samples: Any) -> None:
    _record(hotel_flow, _hotel(samples), [ALONE_ON])
    events = hotel_flow._store.list_audit_events()  # noqa: SLF001 - the stored events, to verify them

    assert verify_events(events).ok and events[-1].type == "tta.v1.settings.changed"
    of_the_order = hotel_flow.view(AuditReader.BUYER, order_id="ord_1").events
    assert all(event.type != "tta.v1.settings.changed" for event in of_the_order)
