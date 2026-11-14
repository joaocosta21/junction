"""The customer's preference applies only when the request states none (P1 C4, "default preference")."""

from __future__ import annotations

from tta.contracts.common import Preference
from tta.contracts.request import PurchaseRequest
from tta.customers import preference_for, shipped_customer

LINE = {"text": "200 litres of soya drink", "product_ids": ["464013"], "quantity": 200, "unit": "L"}


def test_a_request_that_states_no_preference_takes_the_customers() -> None:
    ward = shipped_customer("allergy-ward")
    assert ward is not None
    request = PurchaseRequest.model_validate({"lines": [LINE]})

    assert preference_for(ward, request) is Preference.RELIABILITY


def test_a_request_that_states_a_preference_keeps_it_even_when_it_is_the_default() -> None:
    ward = shipped_customer("allergy-ward")
    assert ward is not None
    request = PurchaseRequest.model_validate({"lines": [LINE], "prefer": "PRICE"})

    assert preference_for(ward, request) is Preference.PRICE


def test_without_a_customer_the_request_decides() -> None:
    request = PurchaseRequest.model_validate({"lines": [LINE]})

    assert preference_for(None, request) is Preference.PRICE
