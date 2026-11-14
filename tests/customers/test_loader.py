"""The customer files: four synthetic customers, checked when they load (P1 C2).

Every file is ours and made up for the demonstration (Valio's mentors: "generate the data", BRIEF section 2, V1).
A file that is not marked synthetic, or that names a product it does not list as usual, does not load.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from tta.contracts.common import ApproverRole, Preference, Unit
from tta.contracts.customer import Customer, ProductUse
from tta.customers import CUSTOMERS_DIR, CustomerLoadError, load_customers, shipped_customer, shipped_customers

FOUR_CUSTOMERS = ("allergy-ward", "bakery-cafe", "hotel-kitchen", "school-kitchen")
# The demo clock (runbook, "What is already decided"): no past order may lie after it.
DEMO_CLOCK_DAY = date(2026, 11, 12)
MIN_WEEKS_OF_HISTORY = 8  # P1 section 5.1: 8 weeks fill the drift window of 6 and leave two older weeks
DAYS_PER_WEEK = 7

GOOD_FILE = """
customer_id: test-kitchen
synthetic: true
name: Test Kitchen
kind: Hotel kitchen
contact: {name: Test Person, title: Chef}
people: {purchasing_manager: Test Person}
usual:
  - {product_id: "469363", product_type: milk, unit: L, use: SERVED}
history:
  - {delivered_on: 2026-11-02, quantities: {"469363": 100}}
  - {delivered_on: 2026-11-09, quantities: {"469363": 96}}
"""


def _write(directory: Path, name: str, text: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _problems(directory: Path) -> tuple[str, ...]:
    with pytest.raises(CustomerLoadError) as raised:
        load_customers(directory)
    return raised.value.problems


def test_the_four_shipped_customers_load_and_each_is_marked_synthetic() -> None:
    customers = shipped_customers()

    assert tuple(sorted(customers)) == FOUR_CUSTOMERS
    assert all(customer.synthetic is True for customer in customers.values())
    assert CUSTOMERS_DIR.is_dir()


@pytest.mark.parametrize("customer_id", FOUR_CUSTOMERS)
def test_each_customer_says_who_orders_and_holds_eight_weeks_of_past_orders_before_the_demo_clock(
    customer_id: str,
) -> None:
    customer = shipped_customer(customer_id)

    assert customer is not None
    assert customer.contact.name in customer.people.values()
    assert ApproverRole.PURCHASING_MANAGER in customer.people
    first, last = customer.history[0].delivered_on, customer.history[-1].delivered_on
    assert (last - first).days >= (MIN_WEEKS_OF_HISTORY - 1) * DAYS_PER_WEEK
    assert last < DEMO_CLOCK_DAY


def test_an_unknown_customer_is_none() -> None:
    assert shipped_customer("catering") is None


def test_the_customers_carry_the_names_the_shop_page_shows() -> None:
    names = {customer_id: customer.name for customer_id, customer in shipped_customers().items()}

    assert names == {
        "allergy-ward": "City Hospital, Ward 4",
        "bakery-cafe": "Kallio Bakery",
        "hotel-kitchen": "Harbourside Hotel",
        "school-kitchen": "Kilo School",
    }


def test_the_bakery_owner_holds_two_roles_and_names_no_dietitian() -> None:
    bakery = shipped_customer("bakery-cafe")

    assert bakery is not None
    assert bakery.people == {
        ApproverRole.PURCHASING_MANAGER: "Marko Heikkinen", ApproverRole.FINANCE: "Marko Heikkinen",
    }


def test_a_customer_states_its_usual_products_with_type_unit_and_use() -> None:
    bakery = shipped_customer("bakery-cafe")

    assert bakery is not None
    cream = bakery.usual_product("469346")
    assert cream is not None
    assert (cream.product_type, cream.unit, cream.use) == ("cream", Unit.L, ProductUse.INGREDIENT)
    assert bakery.usual_product("000000") is None
    assert bakery.prefer is Preference.RELIABILITY


def test_a_good_file_loads(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE)

    customers = load_customers(tmp_path)

    customer = customers["test-kitchen"]
    assert customer.history[-1].quantities == {"469363": Decimal(96)}
    assert customer.prefer is Preference.PRICE  # a customer that states no preference keeps the request's default


def test_a_file_that_is_not_marked_synthetic_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE.replace("synthetic: true\n", ""))

    problems = _problems(tmp_path)

    assert any("synthetic" in problem for problem in problems)


def test_a_file_marked_not_synthetic_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE.replace("synthetic: true", "synthetic: false"))

    assert any("synthetic" in problem for problem in _problems(tmp_path))


def test_a_past_order_of_a_product_that_is_not_a_usual_product_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE.replace('{"469363": 96}', '{"469363": 96, "463797": 10}'))

    assert any("463797" in problem for problem in _problems(tmp_path))


def test_past_orders_must_be_oldest_first_one_per_delivery_date(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE.replace("2026-11-09", "2026-11-02"))

    assert any("oldest first" in problem for problem in _problems(tmp_path))


def test_a_price_for_a_product_the_order_did_not_hold_does_not_load(tmp_path: Path) -> None:
    text = GOOD_FILE.replace('{"469363": 96}}', '{"469363": 96}, prices: {"463797": 3.31}}')
    _write(tmp_path, "test-kitchen", text)

    assert any("463797" in problem for problem in _problems(tmp_path))


def test_a_standing_order_of_a_product_that_is_not_usual_does_not_load(tmp_path: Path) -> None:
    text = GOOD_FILE + """
standing_orders:
  - standing_order_id: so_test
    name: Weekly cream
    lines: [{product_id: "463797", quantity: 10}]
"""
    _write(tmp_path, "test-kitchen", text)

    assert any("463797" in problem for problem in _problems(tmp_path))


def test_a_standing_order_id_used_twice_does_not_load(tmp_path: Path) -> None:
    text = GOOD_FILE + """
standing_orders:
  - {standing_order_id: so_test, name: Weekly milk, lines: [{product_id: "469363", quantity: 100}]}
  - {standing_order_id: so_test, name: Other milk, lines: [{product_id: "469363", quantity: 50}]}
"""
    _write(tmp_path, "test-kitchen", text)

    assert any("used twice" in problem for problem in _problems(tmp_path))


def test_a_product_listed_twice_as_usual_does_not_load(tmp_path: Path) -> None:
    text = GOOD_FILE.replace(
        "use: SERVED}\n", 'use: SERVED}\n  - {product_id: "469363", product_type: milk, unit: L, use: SERVED}\n'
    )
    _write(tmp_path, "test-kitchen", text)

    assert any("twice" in problem for problem in _problems(tmp_path))


def test_a_file_whose_name_is_not_its_customer_id_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "another-kitchen", GOOD_FILE)

    assert any("another-kitchen" in problem for problem in _problems(tmp_path))


def test_an_unknown_setting_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE + "max_order_net_eur: 750\n")

    assert any("max_order_net_eur" in problem for problem in _problems(tmp_path))


def test_a_file_that_is_not_yaml_or_not_a_mapping_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "broken", "customer_id: [unclosed\n")
    _write(tmp_path, "a-list", "- one\n- two\n")

    problems = _problems(tmp_path)

    assert any("broken" in problem for problem in problems)
    assert any("a-list" in problem and "mapping" in problem for problem in problems)


def test_an_empty_folder_does_not_load(tmp_path: Path) -> None:
    assert any("no customer file" in problem for problem in _problems(tmp_path))


def test_a_name_with_a_control_character_does_not_load(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE.replace("name: Test Kitchen", 'name: "Test\\u0007Kitchen"'))

    assert _problems(tmp_path)


def test_every_problem_is_listed_at_once(tmp_path: Path) -> None:
    _write(tmp_path, "test-kitchen", GOOD_FILE.replace("synthetic: true\n", ""))
    _write(tmp_path, "another-kitchen", GOOD_FILE)

    assert len(_problems(tmp_path)) >= 2


def test_a_customer_is_immutable() -> None:
    customer = shipped_customer("hotel-kitchen")

    assert isinstance(customer, Customer)
    with pytest.raises(ValueError, match="frozen"):
        customer.name = "Another hotel"  # type: ignore[misc]
