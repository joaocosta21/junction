"""The contracts import, validate, serialise as the spec says and export their schemas."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from tta.contracts import ports
from tta.contracts.common import (
    ApproverRole,
    Identity,
    IdentityKind,
    PackPreference,
    Unit,
    Verdict,
    most_severe,
    round_money,
)
from tta.contracts.errors import ALL_ERRORS, PROBLEM_TYPE_BASE, OfferStale, TtaError
from tta.contracts.offer import Totals
from tta.contracts.policy import BuyerProfile
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.schemas import all_models, all_schemas

SPEC_PROBLEM_TYPES = {
    "offer-expired", "offer-stale", "policy-blocked", "not-authorised", "unknown-product",
    "invalid-request", "supplier-unavailable",
}


def test_every_model_exports_a_json_schema() -> None:
    schemas = all_schemas()

    assert set(schemas) == set(all_models())
    assert len(schemas) >= 55
    json.dumps(schemas)  # serialisable as it stands
    for name in ("PurchaseRequest", "Offer", "Order", "Approval", "AuditEvent", "Authority", "ProblemDetails"):
        assert schemas[name]["type"] == "object", name


def test_every_port_is_a_protocol() -> None:
    names = ("Clock", "ValioGateway", "Catalog", "PolicyEngine", "OfferBuilder", "OfferRevalidator", "Store",
             "AuditSink", "OrderService", "RequestParser", "AgentRunner", "GatewayService")

    for name in names:
        assert getattr(getattr(ports, name), "_is_protocol", False), name


def test_money_is_decimal_inside_and_a_json_number_outside() -> None:
    totals = Totals(net=Decimal("1980.770"), tax=Decimal("267.40395"), gross=Decimal("2248.17"))

    dumped = json.loads(totals.model_dump_json())

    assert isinstance(totals.net, Decimal)
    assert dumped["net"] == 1980.77 and dumped["tax"] == 267.4 and dumped["gross"] == 2248.17
    assert Totals.model_validate_json(totals.model_dump_json()).net == Decimal("1980.77")


def test_round_money_rounds_half_up() -> None:
    assert round_money(Decimal("0.125")) == Decimal("0.13")
    assert round_money(Decimal("2.674999")) == Decimal("2.67")


def test_models_are_frozen_and_reject_unknown_fields() -> None:
    line = RequestLine(text="1,000 litres of lactose-free milk", quantity=Decimal(1000), unit=Unit.L)

    with pytest.raises(ValidationError):
        line.quantity = Decimal(1)  # type: ignore[misc]
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=1, unit="L", profile_id="hotel-kitchen")  # type: ignore[call-arg]


def test_pack_defaults_to_bulk_for_litres_and_kilograms_and_any_for_units() -> None:
    assert RequestLine(text="x", quantity=1, unit="L").pack is PackPreference.BULK
    assert RequestLine(text="x", quantity=1, unit="KG").pack is PackPreference.BULK
    assert RequestLine(text="x", quantity=1, unit="UNIT").pack is PackPreference.ANY
    assert RequestLine(text="x", quantity=1, unit="L", pack="PORTION").pack is PackPreference.PORTION


def test_a_request_needs_a_line_and_a_positive_quantity() -> None:
    with pytest.raises(ValidationError):
        PurchaseRequest(lines=())
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=0, unit="L")


def test_identity_rules() -> None:
    Identity(kind=IdentityKind.AGENT, id="a", display_name="A", profile_id="hotel-kitchen")
    with pytest.raises(ValidationError):
        Identity(kind=IdentityKind.AGENT, id="a", display_name="A")  # an agent must be bound to a profile
    with pytest.raises(ValidationError):
        Identity(kind=IdentityKind.AGENT, id="a", display_name="A", profile_id="p",
                 roles=(ApproverRole.FINANCE,))  # an agent holds no approver role
    with pytest.raises(ValidationError):
        Identity(kind=IdentityKind.APPROVER, id="h", display_name="H", profile_id="p")  # needs a role
    with pytest.raises(ValidationError):
        Identity(kind=IdentityKind.SUPPLIER, id="s", display_name="S", profile_id="p")


def test_a_profile_with_exclusions_must_set_a_strictness() -> None:
    values = dict(profile_id="p", display_name="P", auto_order_enabled=True, max_order_net_eur=500,
                  max_daily_net_eur=1500, min_fill_ratio=1, substitution_without_approval="NONE",
                  variable_weight="APPROVAL", deposits="APPROVAL")

    BuyerProfile(**values)
    BuyerProfile(**values, excluded_allergens=("AM",), allergen_strictness="STRICT")
    with pytest.raises(ValidationError):
        BuyerProfile(**values, excluded_allergens=("AM",))


def test_the_most_severe_verdict_wins() -> None:
    assert most_severe([]) is Verdict.AUTO
    assert most_severe([Verdict.AUTO, Verdict.APPROVAL]) is Verdict.APPROVAL
    assert most_severe([Verdict.APPROVAL, Verdict.BLOCK, Verdict.AUTO]) is Verdict.BLOCK


def test_every_spec_problem_type_has_a_typed_error() -> None:
    slugs = {error.slug for error in ALL_ERRORS}

    assert slugs >= SPEC_PROBLEM_TYPES
    assert all(issubclass(error, TtaError) and 400 <= error.status_code < 600 for error in ALL_ERRORS)


def test_an_error_becomes_a_problem_details_body() -> None:
    problem = OfferStale("The price of 464306 changed.", fresh_offer_id="off_2").to_problem(instance="/v1/orders")

    body = json.loads(problem.model_dump_json())

    assert body["type"] == PROBLEM_TYPE_BASE + "offer-stale"
    assert body["status"] == 409 and body["fresh_offer_id"] == "off_2" and body["instance"] == "/v1/orders"


@pytest.mark.parametrize("quantity", ["1e30", "1e100000", "1000000.001", "0.0001", "NaN", "Infinity"])
def test_a_request_quantity_is_bounded(quantity: str) -> None:
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=quantity, unit="L")


def test_a_request_line_limits_its_lists_and_ids() -> None:
    RequestLine(text="x", quantity="1000000", unit="L", name_terms=("milk",) * 10)
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=1, unit="L", name_terms=("milk",) * 11)
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=1, unit="L", exclude_allergens=("AM",) * 31)
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=1, unit="UNIT", product_ids=("../etc/passwd",))
    with pytest.raises(ValidationError):
        RequestLine(text="x", quantity=1, unit="L", name_terms=("m" * 61,))

