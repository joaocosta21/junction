"""The page "Your kitchen": the buyer sets what its agent may decide alone (task FEAT-1).

Scores on the 20% "autonomy and controls" (the guardrails are a setting the buyer reads and changes, with the
fixed rules shown as what no setting can switch off) and on the 30% demo: set €3,000 per order, run scenario 1
as "My kitchen agent", and the agent orders alone; set €750, and the same request goes to the purchasing manager.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api.sandbox import KITCHEN_AGENT as KITCHEN_IDENTITY
from tta.contracts.common import OrderStatus, PlacedBy

KITCHEN = "/kitchen"
KITCHEN_AGENT = "agent:my-kitchen"
KITCHEN_PURCHASING = "human:my-kitchen-purchasing"
SCENARIO_1 = "1,000 litres of lactose-free milk by Monday"
SETTINGS_SHOWN = ("F-10", "P-01", "P-02", "P-03", "P-04", "P-05", "P-06", "P-07", "P-08", "P-09")
FIXED_SHOWN = ("F-01", "F-02", "F-03", "F-04", "F-05", "F-06", "F-07", "F-08", "F-09", "F-11")
HASH = re.compile(r"sha256:[0-9a-f]{64}")
PROBLEM = re.compile(r'id="problem">(.*?)</div>', re.DOTALL)

Form = dict[str, Any]


def _kitchen_form(client: TestClient, form_fields: Callable[..., Form], **change: Any) -> Form:
    """The hotel kitchen's settings as the form sends them, with some changed."""
    form = {
        **form_fields(client, KITCHEN),
        "display_name": "My kitchen", "max_order_net_eur": "750",
        "max_daily_net_eur": "3000", "min_fill_ratio": "90", "allergen_strictness": "",
        "substitution_without_approval": "SAME_CATEGORY", "variable_weight": "APPROVAL", "deposits": "APPROVAL",
    }
    return {key: value for key, value in {**form, **change}.items() if value is not None}


def _problem(page: str) -> str:
    """The refusal shown above the form, and nothing else of the page: every field's name is on the page."""
    found = PROBLEM.search(page)
    assert found is not None, "the page shows no refusal"
    return found.group(1)


def _kitchen_orders(book: Callable[[TestClient], Any], client: TestClient) -> tuple[Any, ...]:
    """My kitchen's orders in this browser's book, newest first."""
    return book(client).service.list_orders(KITCHEN_IDENTITY)


def _save(client: TestClient, form_fields: Callable[..., Form], **change: Any) -> Any:
    return client.post(KITCHEN, data=_kitchen_form(client, form_fields, **change), follow_redirects=False)


def test_the_page_shows_each_setting_with_its_rule_and_the_fixed_rules_below(client: TestClient) -> None:
    page = client.get(KITCHEN)

    assert page.status_code == 200
    for rule_id in (*SETTINGS_SHOWN, *FIXED_SHOWN):
        assert rule_id in page.text
    # The buyer's own setting is on the page again, and starts unticked: no order without a person by default.
    assert 'name="auto_order_enabled" value="yes">' in page.text
    assert 'name="auto_order_enabled" value="yes" checked' not in page.text
    always = page.text.split('id="fixed-title"')[1]
    assert "F-10" not in always  # the setting drives it, so it is not one of the rules that hold whatever is set
    assert "whatever you set" in page.text.lower()
    assert 'value="AM"' in page.text and "Milk and its derivatives" in page.text  # GS1 codes with their names
    assert HASH.search(page.text)
    assert "€750" in page.text  # the copy of the hotel kitchen, with its values in the rule sentences


def test_the_form_round_trips_and_the_agent_selector_offers_my_kitchen(
    client: TestClient, form_fields: Callable[..., Form]
) -> None:
    before = HASH.search(client.get(KITCHEN).text).group(0)  # type: ignore[union-attr]

    saved = _save(client, form_fields, display_name="Ravintola Aalto", max_order_net_eur="3000",
                  excluded_allergens=["AM", "AW"], allergen_strictness="STRICT", require_confirmed="yes")
    page = client.get(KITCHEN)

    assert saved.status_code == 303
    assert "Ravintola Aalto" in page.text and 'value="3000"' in page.text
    assert HASH.search(page.text).group(0) != before  # type: ignore[union-attr]
    first = client.get("/").text
    assert KITCHEN_AGENT in first and "My kitchen agent" in first and "Ravintola Aalto" in first


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"max_order_net_eur": "100001"}, "max_order_net_eur"),
        ({"max_daily_net_eur": "a lot"}, "max_daily_net_eur"),
        ({"min_fill_ratio": "150"}, "min_fill_ratio"),
        ({"min_fill_ratio": "most"}, "min_fill_ratio"),
        ({"excluded_allergens": ["AM"]}, "allergen_strictness"),
        ({"excluded_allergens": ["AM", "milk"], "allergen_strictness": "STRICT"}, "excluded_allergens"),
        ({"display_name": ""}, "display_name"),
        ({"deposits": "IGNORE"}, "deposits"),
        ({"max_order_net_eur": ["750", "3000"]}, "max_order_net_eur"),
    ],
)
def test_every_refusal_names_its_field_and_changes_nothing(
    client: TestClient, form_fields: Callable[..., Form], change: Form, named: str
) -> None:
    refused = _save(client, form_fields, **change)

    assert refused.status_code == 422
    assert named in _problem(refused.text)
    assert "€750" in client.get(KITCHEN).text


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"F-01": "off"}, "fixed rule F-01"),
        ({"variable_weight": "F-07"}, "fixed rule F-07"),
        ({"approver_roles": "agent:my-kitchen"}, "approver_roles"),
        ({"profile_id": "hotel-kitchen"}, "profile_id"),
        ({"max_unit_price_eur": "1"}, "unknown setting max_unit_price_eur"),
    ],
)
def test_a_crafted_post_that_sets_a_fixed_rule_or_an_unknown_setting_is_refused(
    client: TestClient, form_fields: Callable[..., Form], change: Form, named: str
) -> None:
    refused = _save(client, form_fields, **change)

    assert refused.status_code == 422 and named in _problem(refused.text)


def test_a_form_without_its_token_is_refused(client: TestClient, form_fields: Callable[..., Form]) -> None:
    form = _kitchen_form(client, form_fields, max_order_net_eur="3000")

    refused = client.post(KITCHEN, data={**form, "csrf": "x" * 43})
    copied = client.post(f"{KITCHEN}/start-from", data={"profile": "allergy-ward"})

    assert refused.status_code == 403 and copied.status_code == 403
    assert "€750" in client.get(KITCHEN).text


def test_the_name_is_escaped(client: TestClient, form_fields: Callable[..., Form], fakes: Any) -> None:
    _save(client, form_fields, display_name=fakes.HOSTILE_NAME.strip())

    for path in (KITCHEN, "/"):
        page = client.get(path).text
        assert "<script>" not in page and "&lt;script&gt;" in page


def test_a_kitchen_starts_from_a_copy_of_the_allergy_ward(client: TestClient, form_fields: Callable[..., Form]) -> None:
    fields = form_fields(client, KITCHEN)

    copied = client.post(f"{KITCHEN}/start-from", data={"csrf": fields["csrf"], "profile": "allergy-ward"},
                         follow_redirects=False)
    unknown = client.post(f"{KITCHEN}/start-from", data={"csrf": fields["csrf"], "profile": "my-kitchen"})
    page = client.get(KITCHEN).text

    assert copied.status_code == 303 and unknown.status_code == 422
    assert "€500" in page and re.search(r'value="AM"[^>]*checked', page)


def test_scenario_1_as_my_kitchen_needs_approval_at_both_spend_limits(
    client: TestClient, form_fields: Callable[..., Form], run_text: Any, book: Any, only_order: Any,
) -> None:
    _save(client, form_fields, max_order_net_eur="3000")
    within_limit = run_text(client, SCENARIO_1, who=KITCHEN_AGENT)
    _save(client, form_fields, max_order_net_eur="750", max_daily_net_eur="10000")
    to_a_human = run_text(client, SCENARIO_1, who=KITCHEN_AGENT)
    hotel = run_text(client, SCENARIO_1)  # the hotel's own agent, in the same browser

    newest, first = _kitchen_orders(book, client)
    assert within_limit.status_code == to_a_human.status_code == 200
    assert (first.status, first.decision.rule_ids, first.profile_id) == (
        OrderStatus.PENDING_APPROVAL, ("P-03",), "my-kitchen",
    )
    assert (newest.status, newest.decision.rule_ids) == (OrderStatus.PENDING_APPROVAL, ("P-01", "P-03"))
    assert only_order(client).decision.rule_ids == ("P-01", "P-03") and hotel.status_code == 200
    record = client.get(f"/orders/{first.order_id}").text
    assert first.decision.policy_hash in record and "my-kitchen" in record


def test_ordering_alone_is_the_visitors_own_choice_and_starts_switched_off(
    client: TestClient, form_fields: Callable[..., Form], run_text: Any, book: Any,
) -> None:
    """The one place a buyer can switch the setting on. Ticked: an order inside every limit, with every statement
    confirmed, is placed by the agent. Unticked, as the page starts: the same order waits for a person (F-10).
    The order is scenario 1's confirmed option, 435 L for €1,083.39, in a kitchen that accepts a 40% fill."""
    limits = {"max_order_net_eur": "3000", "min_fill_ratio": "40"}
    _save(client, form_fields, **limits)
    waiting_page = run_text(client, SCENARIO_1, who=KITCHEN_AGENT)
    saved = _save(client, form_fields, auto_order_enabled="yes", **limits)
    ticked = client.get(KITCHEN).text
    alone_page = run_text(client, SCENARIO_1, who=KITCHEN_AGENT)

    newest, first = _kitchen_orders(book, client)
    assert saved.status_code == 303 and 'name="auto_order_enabled" value="yes" checked' in ticked
    assert (first.status, first.placed_by, first.decision.rule_ids) == (OrderStatus.PENDING_APPROVAL, None, ("F-10",))
    # Only F-10 holds it back: the agent prepared it, one confirmation places it (P8 F1)
    assert "Prepared: confirm to order" in waiting_page.text and "Ordered by the agent" not in waiting_page.text
    assert (newest.status, newest.placed_by, newest.decision.fired) == (OrderStatus.ORDERED, PlacedBy.AGENT, ())
    assert "Ordered by the agent" in alone_page.text
    assert newest.option.totals.net == first.option.totals.net == Decimal("1083.39")  # the same option both times


def test_the_kitchens_approvals_are_decided_by_its_own_approvers(
    client: TestClient, run_text: Any, act_as: Any, decide: Any, book: Any
) -> None:
    run_text(client, SCENARIO_1, who=KITCHEN_AGENT)
    (waiting,) = _kitchen_orders(book, client)

    act_as(client, KITCHEN_PURCHASING)
    decided = decide(client, waiting.approval_id, "APPROVE", option=waiting.option_id)

    assert decided.status_code == 200
    assert _kitchen_orders(book, client)[0].status is OrderStatus.ORDERED


def test_two_browsers_never_see_each_others_kitchen(
    client: TestClient, form_fields: Callable[..., Form], run_text: Any, book: Any
) -> None:
    one, other = client, TestClient(client.app, base_url=str(client.base_url))
    _save(one, form_fields, max_order_net_eur="3000", display_name="Visitor one")

    run_text(other, SCENARIO_1, who=KITCHEN_AGENT)

    assert "Visitor one" not in other.get(KITCHEN).text
    assert _kitchen_orders(book, other)[0].status is OrderStatus.PENDING_APPROVAL


def test_starting_again_clears_the_kitchen(client: TestClient, form_fields: Callable[..., Form]) -> None:
    _save(client, form_fields, max_order_net_eur="3000", display_name="Before")

    client.post("/start-again", data={"csrf": form_fields(client, KITCHEN)["csrf"]})

    page = client.get(KITCHEN).text
    assert "Before" not in page and "€750" in page


# --- the drift tolerance of standing orders (task STAND-1, rule P-08) -------------------------------------


def test_the_drift_tolerance_is_a_percentage_with_its_rule_and_can_be_left_unset(
    client: TestClient, form_fields: Callable[..., Form], book: Callable[[TestClient], Any]
) -> None:
    assert _save(client, form_fields, standing_order_drift_ratio="10").status_code == 303
    page = client.get(KITCHEN).text

    assert book(client).kitchen.profile.standing_order_drift_ratio == Decimal("0.1")
    assert 'name="standing_order_drift_ratio" value="10"' in page
    assert "differs by more than 10% from the median" in page

    assert _save(client, form_fields, standing_order_drift_ratio="").status_code == 303
    assert book(client).kitchen.profile.standing_order_drift_ratio is None
    assert "sets no drift tolerance" in client.get(KITCHEN).text


def test_a_drift_tolerance_above_100_percent_is_refused_by_name(
    client: TestClient, form_fields: Callable[..., Form]
) -> None:
    refused = _save(client, form_fields, standing_order_drift_ratio="150")

    assert refused.status_code == 422
    assert "standing_order_drift_ratio: write a share from 0 to 100 percent" in _problem(refused.text)


# --- the formula (rule F-11) and what a preference may cost (rule P-09), L3-2's two settings ----------------------


def test_the_formula_and_a_preferences_premium_are_set_on_the_page_with_their_rules(
    client: TestClient, form_fields: Callable[..., Form], book: Callable[[TestClient], Any]
) -> None:
    page = client.get(KITCHEN).text
    assert 'name="formula_matters" value="yes">' in page  # unticked: only where a request says the formula matters
    assert 'name="max_preference_premium_ratio" value=""' in page  # the hotel's copy sets no limit of its own

    assert _save(client, form_fields, formula_matters="yes", max_preference_premium_ratio="10").status_code == 303
    page = client.get(KITCHEN).text

    profile = book(client).kitchen.profile
    assert (profile.formula_matters, profile.max_preference_premium_ratio) == (True, Decimal("0.1"))
    assert 'name="formula_matters" value="yes" checked' in page
    assert 'name="max_preference_premium_ratio" value="10"' in page
    assert "uses its products as ingredients, so the formula matters on every line" in page  # F-11, this kitchen
    assert "more than 10% above the cheapest confirmed option" in page  # P-09 with this kitchen's value

    assert _save(client, form_fields, max_preference_premium_ratio="").status_code == 303
    profile = book(client).kitchen.profile
    assert (profile.formula_matters, profile.max_preference_premium_ratio) == (False, None)


def test_a_preferences_premium_above_the_offers_own_25_percent_is_refused_by_name(
    client: TestClient, form_fields: Callable[..., Form]
) -> None:
    refused = _save(client, form_fields, max_preference_premium_ratio="30")

    assert refused.status_code == 422
    assert "max_preference_premium_ratio" in _problem(refused.text)
