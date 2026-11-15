"""Settings in the log, and the dietitian's exclusions kept (decision B59; checks C1-6 and C4-F2).

Scores on the 20% "autonomy and controls ... how decisions are logged and auditable": switching "ordering alone" on
is the most important human decision in the system, and `PUT /shop/api/kitchen` wrote no event for it. Every change
of a book's settings is one event now, under the name of the customer's person who orders, with each changed
setting before and after. Valio Aimo's view says a setting changed and shows no value.

And a guard that needs no login: at a customer whose profile names a dietitian of its own (the ward, the school),
the settings may add allergen exclusions and raise the strictness, never remove an exclusion or lower it. Before,
a caller emptied the school's exclusions, switched ordering alone on, and the almond drink 465793 ("may contain"
tree nuts) was ordered by the agent alone.

Measured at the recording's own clock (Saturday 14 Nov 2026, 02:52 Helsinki time).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from tta.api.budget import StorageBudget
from tta.api.limits import as_client
from tta.api.sandbox import KITCHEN_AGENT, KITCHEN_APPROVER_NAME, KITCHEN_SETTINGS, Sandbox, file_profile
from tta.api.wiring import Parts, build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.audit import AuditEvent
from tta.contracts.common import ApproverRole, AuditReader, OrderStatus
from tta.contracts.errors import RateLimited
from tta.contracts.request import PurchaseRequest
from tta.policy import PolicyLoadError

HOTEL, SCHOOL, WARD, BAKERY = "hotel-kitchen", "school-kitchen", "allergy-ward", "bakery-cafe"
CHANGED = "tta.v1.settings.changed"
VISITOR = "93.184.216.50"  # a public address: the limits count by it
ALONE_AT_THE_HOTEL = (
    "Hanna Laine switched ordering alone on: the agent may order up to €750.00 an order and €3,000.00 a day "
    "without asking."
)
FOR_VALIO_AIMO = (
    "The buyer changed a setting of its agent. Which setting and its values are the buyer's own and are not shown."
)
ALMOND_DRINK = {
    "needed_by": "2026-11-16",
    "lines": [{"text": "20 litres of almond drink 465793 by Monday", "product_ids": ["465793"], "quantity": 20,
               "unit": "L"}],
}


def _file_settings(customer_id: str, **change: Any) -> dict[str, Any]:
    """The customer's settings as its profile file states them, with some changed: what the page sends."""
    return {**file_profile(customer_id).model_dump(include=set(KITCHEN_SETTINGS)), **change}


def _shop_book(parts: Parts, customer_id: str, key: str = "browser") -> Sandbox:
    """A book of the shop page: it stands for one customer, and the page's first call sends that customer's
    settings (`tta.ui.shop_api`)."""
    book = parts.sandboxes.open(f"{key}.{customer_id}")
    book.customer.name(customer_id)
    book.kitchen.set_up(_file_settings(customer_id))
    return book


def _changes(book: Sandbox) -> list[AuditEvent]:
    return [event for event in book.store.list_audit_events() if event.type == CHANGED]


# --- one event per change ------------------------------------------------------------------------------------


@pytest.mark.parametrize("customer_id", [HOTEL, SCHOOL, WARD, BAKERY])
def test_the_settings_the_page_sends_first_are_the_customers_own_and_write_no_event(
    parts: Parts, customer_id: str
) -> None:
    book = _shop_book(parts, customer_id)
    profile = file_profile(customer_id)
    by_code = {code: profile.strictness_for(code).value for code in profile.excluded_allergens}

    book.kitchen.set_up(_file_settings(customer_id, allergen_strictness_by_code=by_code))  # the page's own shape

    assert book.kitchen.is_set_up and book.store.list_audit_events() == ()


def test_switching_ordering_alone_on_at_the_hotel_is_one_event_under_the_name_of_the_person_who_orders(
    parts: Parts,
) -> None:
    book = _shop_book(parts, HOTEL)

    book.kitchen.set_up(_file_settings(HOTEL, auto_order_enabled=True))

    (event,) = book.store.list_audit_events()
    assert (event.type, event.data.sentence) == (CHANGED, ALONE_AT_THE_HOTEL)
    actor = event.data.actor
    assert (actor.kind.value, actor.display_name, actor.role) == ("human", "Hanna Laine", "purchasing_manager")
    assert event.data.facts["changes"] == [{"setting": "auto_order_enabled", "before": False, "after": True}]
    assert event.data.facts["customer_id"] == HOTEL
    assert event.data.facts["profile"]["auto_order_enabled"] is True
    assert event.data.policy_hash == book.service.get_authority(KITCHEN_AGENT).policy_hash  # the rules now in force


def test_the_buyer_reads_the_change_in_its_log_and_valio_aimo_reads_no_value(parts: Parts) -> None:
    book = _shop_book(parts, HOTEL)
    book.kitchen.set_up(_file_settings(HOTEL, auto_order_enabled=True, max_order_net_eur="987"))

    (for_buyer,) = book.service.get_audit(KITCHEN_AGENT, AuditReader.BUYER).events
    (for_valio,) = book.service.get_audit(KITCHEN_AGENT, AuditReader.SUPPLIER).events

    assert for_buyer.sentence == (
        "Hanna Laine switched ordering alone on: the agent may order up to €987.00 an order and €3,000.00 a day "
        "without asking; changed the limit per order from €750.00 to €987.00."
    )
    assert (for_valio.sentence, for_valio.facts) == (FOR_VALIO_AIMO, {})
    assert for_valio.actor.display_name == "The buyer's purchasing manager"
    # What the view says, without the id, the time and the hash: their digits are random and mean nothing.
    shown = json.dumps(for_valio.model_dump(mode="json", include={"actor", "sentence", "rule_ids", "facts"}))
    assert not any(private in shown for private in ("Hanna", "987", "750", "3000", "3,000", "ordering alone"))


def test_a_form_that_changes_nothing_writes_no_event_and_each_later_change_writes_one(parts: Parts) -> None:
    book = _shop_book(parts, BAKERY)

    book.kitchen.set_up(_file_settings(BAKERY))
    book.kitchen.set_up(_file_settings(BAKERY, max_daily_net_eur="1200"))
    book.kitchen.set_up(_file_settings(BAKERY, max_daily_net_eur="1200"))
    book.kitchen.set_up(_file_settings(BAKERY, max_daily_net_eur=1200, require_confirmed=True))

    assert [event.data.sentence for event in _changes(book)] == [
        "Marko Heikkinen changed the limit per day from €1,000.00 to €1,200.00.",
        "Marko Heikkinen switched confirmed stock only on.",
    ]


def test_a_refused_form_changes_nothing_and_writes_no_event(parts: Parts) -> None:
    book = _shop_book(parts, HOTEL)

    with pytest.raises(PolicyLoadError):
        book.kitchen.set_up(_file_settings(HOTEL, auto_order_enabled=True, min_fill_ratio="1.5"))

    assert book.kitchen.profile.auto_order_enabled is False and book.store.list_audit_events() == ()


def test_each_books_settings_events_are_its_own(parts: Parts) -> None:
    one, other = _shop_book(parts, HOTEL, "one"), _shop_book(parts, HOTEL, "other")

    one.kitchen.set_up(_file_settings(HOTEL, auto_order_enabled=True))

    assert len(_changes(one)) == 1 and _changes(other) == [] and parts.store.list_audit_events() == ()


def test_my_kitchen_of_the_older_page_logs_its_changes_under_its_own_approver(parts: Parts) -> None:
    book = parts.sandboxes.open("the-kitchen-page")  # no customer named: the visitor's own "My kitchen"

    book.kitchen.start_from("hotel-kitchen")  # what it holds already: nothing changes
    book.kitchen.start_from("allergy-ward")
    book.kitchen.set_up({**book.kitchen.settings, "auto_order_enabled": True})

    started, switched = _changes(book)
    assert started.data.actor.display_name == switched.data.actor.display_name == KITCHEN_APPROVER_NAME
    assert started.data.sentence.startswith(f"{KITCHEN_APPROVER_NAME} changed the limit per order from €750.00 to ")
    assert "added milk and cereals containing gluten to the allergens kept out (strict rule)" in started.data.sentence
    assert switched.data.sentence.startswith(f"{KITCHEN_APPROVER_NAME} switched ordering alone on: the agent may ")
    assert "customer_id" not in started.data.facts


# --- the dietitian's exclusions ------------------------------------------------------------------------------


def test_at_the_school_the_dietitians_exclusions_cannot_be_removed_on_the_page(parts: Parts) -> None:
    book = _shop_book(parts, SCHOOL)

    with pytest.raises(PolicyLoadError) as emptied:
        book.kitchen.set_up(_file_settings(SCHOOL, excluded_allergens=[], allergen_strictness=None,
                                           auto_order_enabled=True))
    with pytest.raises(PolicyLoadError) as one_removed:
        book.kitchen.set_up(_file_settings(SCHOOL, excluded_allergens=["AN", "AS"]))

    assert emptied.value.problems == (
        "excluded_allergens: The allergen exclusions of Kilo School are set by its dietitian and cannot be removed "
        "here: tree nuts, peanuts and sesame seeds must stay excluded",
    )
    assert "cannot be removed here: peanuts must stay excluded" in one_removed.value.problems[0]
    profile = book.kitchen.profile
    assert (profile.excluded_allergens, profile.auto_order_enabled) == (("AN", "AP", "AS"), False)
    assert book.store.list_audit_events() == ()


@pytest.mark.parametrize("lowered", [
    {"allergen_strictness": "DECLARED_ONLY"},
    {"allergen_strictness_by_code": {"AM": "DECLARED_ONLY"}},
])
def test_at_the_ward_the_dietitians_strict_rule_cannot_be_relaxed_on_the_page(
    parts: Parts, lowered: dict[str, Any]
) -> None:
    book = _shop_book(parts, WARD)

    with pytest.raises(PolicyLoadError) as refused:
        book.kitchen.set_up(_file_settings(WARD, **lowered))

    assert refused.value.problems[0].startswith(
        "allergen_strictness: The allergen rule of City Hospital, Ward 4 is set by its dietitian and cannot be "
        "relaxed here: milk"
    )
    assert refused.value.problems[0].endswith("must stay under the strict rule")
    assert book.kitchen.profile.strictness_for("AM").value == "STRICT" and book.store.list_audit_events() == ()


def test_at_the_school_an_exclusion_can_be_added_and_taken_back_and_both_are_in_the_log(parts: Parts) -> None:
    book = _shop_book(parts, SCHOOL)
    with_milk = _file_settings(SCHOOL, excluded_allergens=["AN", "AP", "AS", "AM"])

    book.kitchen.set_up(with_milk)
    book.kitchen.set_up(_file_settings(SCHOOL))  # the visitor's own addition goes; the dietitian's three stay

    assert [event.data.sentence for event in _changes(book)] == [
        "Päivi Korhonen added milk to the allergens kept out (strict rule).",
        "Päivi Korhonen took milk off the allergens kept out.",
    ]
    assert book.kitchen.profile.excluded_allergens == ("AN", "AP", "AS")


@pytest.mark.parametrize(("customer_id", "person"), [(HOTEL, "Hanna Laine"), (BAKERY, "Marko Heikkinen")])
def test_the_hotel_and_the_bakery_have_no_dietitian_and_set_their_exclusions_freely(
    parts: Parts, customer_id: str, person: str
) -> None:
    book = _shop_book(parts, customer_id)

    book.kitchen.set_up(_file_settings(customer_id, excluded_allergens=["AM"], allergen_strictness="STRICT"))
    book.kitchen.set_up(_file_settings(customer_id, excluded_allergens=["AM"], allergen_strictness="DECLARED_ONLY"))
    book.kitchen.set_up(_file_settings(customer_id))

    assert [event.data.sentence for event in _changes(book)] == [
        f"{person} added milk to the allergens kept out (strict rule).",
        f"{person} put milk under the declared only rule.",
        f"{person} took milk off the allergens kept out.",
    ]


def test_the_almond_drink_is_no_longer_ordered_alone_at_the_school(parts: Parts) -> None:
    """Checks C1-6 and C4-F2: exclusions emptied and ordering alone on, 20 litres of 465793 were ORDERED by the
    agent. The exclusions now stay, so with ordering alone on the same order waits for the dietitian."""
    book = _shop_book(parts, SCHOOL)
    with pytest.raises(PolicyLoadError):
        book.kitchen.set_up(_file_settings(SCHOOL, excluded_allergens=[], allergen_strictness=None,
                                           auto_order_enabled=True))
    book.kitchen.set_up(_file_settings(SCHOOL, auto_order_enabled=True))

    offer = book.service.create_offer(KITCHEN_AGENT, PurchaseRequest.model_validate(ALMOND_DRINK))
    option = next(option for option in offer.options if [line.product_id for line in option.lines] == ["465793"])
    order = book.service.place_order(KITCHEN_AGENT, offer.offer_id, option.option_id, "k-1")

    assert option.totals.net == Decimal("47.60")
    assert (order.status, order.placed_by) == (OrderStatus.PENDING_APPROVAL, None)
    assert "P-04" in order.decision.rule_ids and ApproverRole.DIETITIAN in order.decision.required_roles
    assert [event.data.sentence for event in _changes(book)] == [
        "Päivi Korhonen switched ordering alone on: the agent may order up to €250.00 an order and €800.00 a day "
        "without asking.",
    ]


# --- a change is a write ----------------------------------------------------------------------------------------


def test_a_change_of_settings_is_refused_once_the_addresss_day_of_stored_bytes_is_spent(
    settings: Settings, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The audit trail is append-only: a settings event is counted like every other write (review H2)."""
    small = StorageBudget(per_address_bytes=1, per_token_bytes=10**9)
    monkeypatch.setattr("tta.api.wiring.StorageBudget", lambda: small)
    parts = build_parts(settings, catalog=catalog)
    try:
        book = _shop_book(parts, HOTEL)
        with as_client(VISITOR):
            book.kitchen.set_up(_file_settings(HOTEL, auto_order_enabled=True))  # stores more than the day's byte
            with pytest.raises(RateLimited) as refused:
                book.kitchen.set_up(_file_settings(HOTEL, auto_order_enabled=False))

        assert "stores at most" in refused.value.detail
        assert book.kitchen.profile.auto_order_enabled is True and len(_changes(book)) == 1
    finally:
        parts.close()
