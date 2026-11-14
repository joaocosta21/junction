"""A buyer's own words reach the sentences of the constraint checks as data: a brace in a term cannot break the
sentence it stands in (found by task SUST-1: the NOT_MET sentence was built with `str.format`)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

NAMED_MILK = "469363"  # Arla lactose-free semi-skimmed milk, confirmed in the demo capture


def test_a_name_term_with_braces_on_a_named_product_is_a_failed_check_not_an_error(
    client: TestClient, auth: Any
) -> None:
    request = {
        "needed_by": "2026-11-16",
        "lines": [{"text": "milk {0} {ids}", "product_ids": [NAMED_MILK], "name_terms": ["{0}"], "quantity": 10,
                   "unit": "L"}],
    }

    answer = client.post("/v1/offers", json=request, headers=auth("agent_hotel"))

    assert answer.status_code == 201, answer.text
    checks = [check for option in answer.json()["options"] for check in option["constraint_checks"]]
    failed = [check["sentence"] for check in checks if check["result"] == "NOT_MET" and "{0}" in check["sentence"]]
    assert failed and all(NAMED_MILK in sentence for sentence in failed)
