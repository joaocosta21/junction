"""Which roles an approver can sign for: held in the token, for this buyer, and listed in the buyer's profile."""

from __future__ import annotations

from tta.contracts.common import ApproverRole, Identity
from tta.orders.access import actor_of, roles_that_count

PURCHASING = ApproverRole.PURCHASING_MANAGER
FINANCE = ApproverRole.FINANCE
DIETITIAN = ApproverRole.DIETITIAN


def test_an_approver_listed_under_its_role_counts_for_it(engine, approver_purchasing: Identity) -> None:
    assert roles_that_count(approver_purchasing, engine.get_profile("hotel-kitchen")) == (PURCHASING,)


def test_a_role_in_the_token_that_the_profile_does_not_list_for_this_id_does_not_count(engine, samples) -> None:
    # The ward lists its dietitian's role under another person: a token cannot take it.
    both_in_token = samples.approver("human:ward-purchasing", "allergy-ward", PURCHASING, DIETITIAN)

    assert roles_that_count(both_in_token, engine.get_profile("allergy-ward")) == (PURCHASING,)


def test_the_person_who_orders_counts_for_every_role_at_the_hotel_and_for_all_but_the_dietitians_at_the_ward(
    engine, approver_hotel_buyer: Identity, approver_ward_purchasing: Identity, approver_dietitian: Identity
) -> None:
    """One person confirms (decision B54): no customer has a separate finance signer; the ward's second person
    is its dietitian."""
    ward = engine.get_profile("allergy-ward")

    assert roles_that_count(approver_hotel_buyer, engine.get_profile("hotel-kitchen")) == (
        PURCHASING, FINANCE, DIETITIAN,
    )
    assert roles_that_count(approver_ward_purchasing, ward) == (PURCHASING, FINANCE)
    assert roles_that_count(approver_dietitian, ward) == (DIETITIAN,)


def test_nobody_counts_for_another_buyer_and_an_agent_counts_for_no_role(
    engine, approver_purchasing: Identity, agent_hotel: Identity, supplier_reader: Identity
) -> None:
    assert roles_that_count(approver_purchasing, engine.get_profile("allergy-ward")) == ()
    assert roles_that_count(agent_hotel, engine.get_profile("hotel-kitchen")) == ()
    assert roles_that_count(supplier_reader, engine.get_profile("hotel-kitchen")) == ()


def test_the_audit_trail_names_the_caller_by_kind_id_and_roles(
    samples, agent_hotel: Identity, supplier_reader: Identity
) -> None:
    human = actor_of(samples.approver("human:hotel-purchasing", "hotel-kitchen", PURCHASING, FINANCE))

    assert (actor_of(agent_hotel).kind, actor_of(agent_hotel).role) == ("agent", None)
    assert (human.kind, human.role, human.id) == ("human", "purchasing_manager, finance", "human:hotel-purchasing")
    assert (actor_of(supplier_reader).kind, actor_of(supplier_reader).role) == ("human", "supplier")
