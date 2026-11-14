"""The published texts say what the gateway does since B0: ordering alone is a buyer setting, off by default.

Scores on the 20% "what the agent can decide alone, what needs human sign-off" and the 15% "clear visibility of
assumptions". After B0 the OpenAPI description still said every verdict is `APPROVAL` or `BLOCK` and every
order waits for a person; with the setting on, `AUTO` and `ORDERED` come back (`tests/api/test_ordering_alone.py`).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings

UNTRUE_SINCE_B0 = ("(`APPROVAL` or `BLOCK`)", "Every eligible order waits", "for human approval")


@pytest.fixture(scope="module")
def document(catalog: ProductCatalog, tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    settings = Settings.for_tests(tta_data_dir=tmp_path_factory.mktemp("texts") / "var")
    with TestClient(create_app(settings, parts=build_parts(settings, catalog=catalog))) as client:
        yield client.get("/openapi.json").json()


def test_the_description_names_the_three_verdicts_and_the_setting_that_allows_the_first(
    document: dict[str, Any],
) -> None:
    description = " ".join(document["info"]["description"].split())  # the text as read, without line breaks

    for phrase in ("`AUTO`", "`APPROVAL`", "`BLOCK`", "auto_order_enabled", "off by default", "F-10",
                   "every statement", "`placed_by: AGENT`", "`PENDING_APPROVAL`"):
        assert phrase in description, phrase
    for untrue in UNTRUE_SINCE_B0:
        assert untrue not in description, untrue


def test_placing_an_order_says_when_it_is_ordered_alone_and_when_it_waits(document: dict[str, Any]) -> None:
    operation = document["paths"]["/v1/orders"]["post"]
    text = " ".join(f"{operation['summary']} {operation['description']}".split())

    for phrase in ("`AUTO`", "`ORDERED`", "`PENDING_APPROVAL`", "`BLOCK`", "off in every shipped profile"):
        assert phrase in text, phrase
    for untrue in UNTRUE_SINCE_B0:
        assert untrue not in text, untrue
