"""The customer files against the product file and tonight's recording (P1 section 5.3, SPLIT S1 "done when").

Every product id exists in the catalog and is of the product type the file states; its unit converts; every quantity
is a whole number of sales units; every product has a price in the recording, and its state at both clocks is pinned
below so the demo paths are known. Figures are from the recording `2026-11-14-demo` (769 products), not the catalog.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import pytest
import yaml

from tta.catalog import ProductCatalog
from tta.config import REPO_ROOT
from tta.contracts.availability import PriceLine, PriceResponse
from tta.contracts.common import AllergenRelation, AvailabilityState, DataSource, Unit
from tta.contracts.customer import Customer, PastOrder, UsualProduct
from tta.customers import shipped_customer, shipped_customers
from tta.customers.checks import customer_problems, states_at
from tta.valio.replay import ReplayGateway

# The demo clock of the runbook ("What is already decided"), Thursday 12 Nov 2026 14:15 Helsinki time.
DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
PROFILES_DIR = REPO_ROOT / "src" / "tta" / "policy" / "profiles"

# Confirmed amount in sales units of every usual product, the same at the recording's instant (Saturday 14 Nov
# 02:52) and at the demo clock. Counted with `tta.availability.states.classify` over the recording.
CONFIRMED_UNITS = {
    "hotel-kitchen": {"469363": 384, "463797": 114, "464615": 100, "463203": 192, "466988": 109},
    "allergy-ward": {"464013": 478, "473424": 109},
    "school-kitchen": {"462775": 51, "470863": 1414, "464517": 242, "466988": 109, "463254": 4493},
    "bakery-cafe": {"469346": 48, "464727": 37, "463380": 698, "468319": 3003},
}
# The allergens each customer's profile excludes under the strict rule (runbook: the school keeps tree nuts, peanuts
# and sesame out for the whole school, strict; the ward milk and gluten, strict). Under the strict rule only a
# statement "free from" lets a product through.
STRICT_EXCLUSIONS = {"allergy-ward": ("AM", "AW"), "school-kitchen": ("AN", "AP", "AS")}
# The school's usual products whose data states nothing about tree nuts, peanuts or sesame: its strict rule sends
# them to a person, and no suggestion may name them alone. Pinned so that an edit of the data is seen.
SCHOOL_USUALS_WITHOUT_A_STATEMENT = ("462775", "464517")


def _with(customer: Customer, **changes: object) -> Customer:
    return Customer.model_validate({**customer.model_dump(), **changes})


@pytest.mark.parametrize("customer_id", sorted(CONFIRMED_UNITS))
def test_every_usual_product_exists_is_of_its_type_converts_and_is_ordered_in_whole_sales_units(
    customer_id: str, catalog: ProductCatalog, recording: ReplayGateway,
) -> None:
    customer = shipped_customer(customer_id)
    assert customer is not None

    assert customer_problems(customer, catalog, recording) == ()


@pytest.mark.parametrize("clock", ["recording", "demo"])
@pytest.mark.parametrize("customer_id", sorted(CONFIRMED_UNITS))
def test_every_usual_product_has_confirmed_stock_at_both_clocks(
    customer_id: str, clock: str, recording: ReplayGateway,
) -> None:
    customer = shipped_customer(customer_id)
    assert customer is not None
    now = recording.time_now if clock == "recording" else DEMO_CLOCK

    states = states_at(customer, recording, now)

    assert {product_id: state.state for product_id, state in states.items()} == {
        product_id: AvailabilityState.CONFIRMED for product_id in CONFIRMED_UNITS[customer_id]
    }
    assert {product_id: state.usable_amount for product_id, state in states.items()} == {
        product_id: Decimal(units) for product_id, units in CONFIRMED_UNITS[customer_id].items()
    }


@pytest.mark.parametrize("customer_id", sorted(STRICT_EXCLUSIONS))
def test_which_usual_products_rule_out_the_strictly_excluded_allergens(
    customer_id: str, catalog: ProductCatalog,
) -> None:
    customer = shipped_customer(customer_id)
    assert customer is not None
    unstated = []
    for usual in customer.usual:
        product = catalog.get_product(usual.product_id)
        assert product is not None
        relations = {statement.code: statement.relation for statement in product.allergen_statements}
        if not all(relations.get(code) is AllergenRelation.FREE_FROM for code in STRICT_EXCLUSIONS[customer_id]):
            unstated.append(usual.product_id)

    expected = SCHOOL_USUALS_WITHOUT_A_STATEMENT if customer_id == "school-kitchen" else ()
    assert tuple(unstated) == expected


@pytest.mark.parametrize("customer_id", sorted(CONFIRMED_UNITS))
def test_every_role_the_profile_names_has_a_person_in_the_customer_file(customer_id: str) -> None:
    path = PROFILES_DIR / f"{customer_id}.yaml"
    if not path.is_file():
        pytest.skip(f"the profile {customer_id} is written by another lane (P1 C1); not there yet")
    profile = yaml.safe_load(path.read_text(encoding="utf-8"))
    customer = shipped_customer(customer_id)
    assert customer is not None

    named = {str(role) for role in profile.get("approver_roles") or {}}

    assert named <= {role.value for role in customer.people}


def test_a_product_that_is_not_in_the_catalog_is_a_problem(catalog: ProductCatalog, recording: ReplayGateway) -> None:
    hotel = shipped_customer("hotel-kitchen")
    assert hotel is not None
    broken = _with(
        hotel,
        usual=[UsualProduct(product_id="459999", product_type="milk", unit=Unit.L, use="SERVED").model_dump()],
        history=[PastOrder(delivered_on="2026-11-09", quantities={"459999": 10}).model_dump()],
        standing_orders=[],
    )

    problems = customer_problems(broken, catalog, recording)

    assert any("459999" in problem and "catalog" in problem for problem in problems)


def test_a_product_of_another_type_an_unknown_type_and_a_unit_that_does_not_convert_are_problems(
    catalog: ProductCatalog, recording: ReplayGateway,
) -> None:
    hotel = shipped_customer("hotel-kitchen")
    assert hotel is not None
    usual = [
        {"product_id": "469363", "product_type": "cream", "unit": "L", "use": "SERVED"},  # a milk
        {"product_id": "463797", "product_type": "no_such_type", "unit": "L", "use": "INGREDIENT"},
        {"product_id": "466988", "product_type": "beef_chuck", "unit": "L", "use": "INGREDIENT"},  # sold by weight
    ]
    broken = _with(hotel, usual=usual, history=[], standing_orders=[])

    problems = customer_problems(broken, catalog, recording)

    assert any("469363" in problem and "cream" in problem for problem in problems)
    assert any("no_such_type" in problem for problem in problems)
    assert any("466988" in problem and "L" in problem for problem in problems)


def test_a_quantity_that_is_not_a_whole_lot_is_a_problem(catalog: ProductCatalog, recording: ReplayGateway) -> None:
    hotel = shipped_customer("hotel-kitchen")
    assert hotel is not None
    # Beef chuck 466988 is sold by the kilogram in lots of 3 kg: 10 kg is not a whole lot.
    history = [*[order.model_dump() for order in hotel.history],
               PastOrder(delivered_on="2026-11-11", quantities={"466988": 10}).model_dump()]
    broken = _with(hotel, history=history)

    problems = customer_problems(broken, catalog, recording)

    assert problems == ("hotel-kitchen: 10 kg of 466988 on 2026-11-11 is not a whole number of lots",)


class _NoPrices:
    """A price source that holds no price for any product, as a recording without the product would answer."""

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:  # noqa: ARG002
        lines = tuple(PriceLine(product_id=product_id, error=True, not_in_recording=True) for product_id in product_ids)
        return PriceResponse(currency="EUR", lines=lines, source=DataSource.REPLAY)


def test_a_product_with_no_price_in_the_recording_is_a_problem(catalog: ProductCatalog) -> None:
    ward = shipped_customer("allergy-ward")
    assert ward is not None

    problems = customer_problems(ward, catalog, _NoPrices())

    assert problems == (
        "allergy-ward: 464013 has no price in the recording",
        "allergy-ward: 473424 has no price in the recording",
    )


def test_the_shipped_files_name_only_ids_the_recording_holds(recording: ReplayGateway) -> None:
    ids = {usual.product_id for customer in shipped_customers().values() for usual in customer.usual}

    lines = recording.price(sorted(ids)).lines

    assert not [line.product_id for line in lines if line.not_in_recording]
