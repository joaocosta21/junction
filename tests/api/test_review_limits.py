"""Limits for the review hours (A5 #3, A3 F3).

Scores on the 30% "working end-to-end demo". A5 typed six requests in one minute and the sixth was refused: a
visitor had 5 request readings a minute, and every typed request on the shop page is one reading followed by
one offer. A3 F3: one address could take half of each ceiling, so two addresses at their cap locked every other
visitor out. Now a visitor has 15 readings a minute, and it takes four addresses at their cap to fill a ceiling.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tta.api import create_app
from tta.api.limits import ADDRESS_CAPS, GLOBAL_CEILINGS, VISITOR_WINDOWS, CallKind, CallLimits, RateLimit, as_client
from tta.api.wiring import build_parts
from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.agent import Reading, ReadingSource
from tta.contracts.common import DataSource, Identity, Unit
from tta.contracts.errors import RateLimited
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.ui import security

ADDRESSES = tuple(f"93.184.216.{number}" for number in range(40, 46))  # public: RFC 5737 ranges count as private
TYPED_REQUESTS_A5_SENT = 6  # in one minute, before the sixth was refused
ADDRESSES_TO_FILL_A_CEILING = 4
TEXT = "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only"
TYPED = PurchaseRequest(
    needed_by=date(2026, 11, 16), require_confirmed=True,
    lines=(RequestLine(text=TEXT, product_type="plant_drink", quantity=Decimal(200), unit=Unit.L,
                       exclude_allergens=("AM", "AW")),),
)


class FakeTime:
    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


class RuleReader:
    """A reader that answers like the fixed rules do when no model is called."""

    def read(self, text: str, identity: Identity) -> Reading:
        return Reading(
            request=TYPED, source=ReadingSource.RULE_BASED, model="rule-based", sentence="Read by fixed rules."
        )

    def parse_request(self, text: str, identity: Identity) -> PurchaseRequest:
        return TYPED


@pytest.fixture
def demo_client(tmp_path: Path, catalog: ProductCatalog) -> Iterator[TestClient]:
    settings = Settings.for_tests(tta_env="demo", tta_mode=DataSource.REPLAY, tta_data_dir=tmp_path / "var")
    parts = build_parts(settings, catalog=catalog, request_parser=RuleReader())
    with TestClient(create_app(settings, parts=parts)) as client:
        yield client


def _limits() -> CallLimits:
    return CallLimits(RateLimit(), per_visitor=True, monotonic=FakeTime())


# --- A5 #3: a sixth typed request in a minute -----------------------------------------------------------


def test_a_sixth_typed_reading_in_a_minute_from_one_browser_is_served(agent_hotel: Identity) -> None:
    limits = _limits()

    with as_client(ADDRESSES[0], browser=security.new_token()):
        for _ in range(TYPED_REQUESTS_A5_SENT):
            limits.check(agent_hotel, CallKind.MODEL)


def test_a_sixth_typed_request_in_a_minute_over_rest_is_read(demo_client: TestClient) -> None:
    headers = {"Authorization": "Bearer demo-agent-hotel-kitchen"}

    statuses = [
        demo_client.post("/v1/requests/parse", json={"text": TEXT}, headers=headers).status_code
        for _ in range(TYPED_REQUESTS_A5_SENT)
    ]

    assert statuses == [200] * TYPED_REQUESTS_A5_SENT


def test_the_reading_window_holds_fast_typing_and_leaves_room_for_an_examples_own_offer() -> None:
    # Above the reading window an example button still makes its offer from its typed request (test_room_pages).
    assert TYPED_REQUESTS_A5_SENT < VISITOR_WINDOWS[CallKind.MODEL] < VISITOR_WINDOWS[CallKind.LOOKUP]
    assert VISITOR_WINDOWS[CallKind.MODEL] < ADDRESS_CAPS[CallKind.MODEL]


# --- A3 F3: one or two addresses cannot lock everybody out ------------------------------------------------


@pytest.mark.parametrize("kind", list(CallKind))
def test_two_addresses_at_their_cap_leave_every_other_visitor_served(agent_ward: Identity, kind: CallKind) -> None:
    limits = _limits()
    for address in ADDRESSES[:2]:
        for _ in range(ADDRESS_CAPS[kind]):
            with as_client(address, browser=security.new_token()):
                limits.check(agent_ward, kind)

    with as_client(ADDRESSES[2], browser=security.new_token()):
        limits.check(agent_ward, kind)  # a third visitor: served, where it used to get "all callers"


@pytest.mark.parametrize("kind", list(CallKind))
def test_it_takes_four_addresses_at_their_cap_to_fill_a_ceiling(agent_ward: Identity, kind: CallKind) -> None:
    limits = _limits()
    for address in ADDRESSES[:ADDRESSES_TO_FILL_A_CEILING]:
        for _ in range(ADDRESS_CAPS[kind]):
            with as_client(address, browser=security.new_token()):
                limits.check(agent_ward, kind)

    with as_client(ADDRESSES[ADDRESSES_TO_FILL_A_CEILING], browser=security.new_token()), pytest.raises(
        RateLimited
    ) as refused:
        limits.check(agent_ward, kind)

    assert ADDRESS_CAPS[kind] * ADDRESSES_TO_FILL_A_CEILING == GLOBAL_CEILINGS[kind]
    assert "from all callers together" in refused.value.detail
