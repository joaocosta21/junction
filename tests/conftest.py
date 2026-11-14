"""Shared test fixtures: recorded captures of the mock API, pinned clocks, the raw product file, identities.

No test calls a live service. Settings built here read no `.env` file and carry no secret.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from tta.config import REPO_ROOT, Settings
from tta.contracts.common import ApproverRole, Identity, IdentityKind

FIXTURES_DIR = REPO_ROOT / "fixtures"
VALIO_FIXTURES_DIR = FIXTURES_DIR / "valio"
CAPTURE_DEMO = "2026-11-14-demo"  # tonight's capture: categories 104xx and 18720, 769 products
CAPTURE_SAMPLE = "2026-11-13-sample"  # Friday's random sample of 1,000 catalog ids plus the made-up 459999
CAPTURE_EXTRAS = "2026-11-13-extras"  # Friday's 37 probe ids


@dataclass(frozen=True)
class Capture:
    """One recorded capture of the mock API: raw bodies as the API returned them."""

    name: str
    path: Path
    manifest: dict[str, Any]

    @property
    def time_now(self) -> datetime:
        return datetime.fromisoformat(self.manifest["time_now"])

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(json.loads((self.path / "ids.json").read_text(encoding="utf-8")))

    def bodies(self, endpoint: str) -> list[dict[str, Any]]:
        """The raw response bodies of `availability` or `price`, one per recorded call."""
        return [
            json.loads((self.path / name).read_text(encoding="utf-8")) for name in self.manifest["files"][endpoint]
        ]

    def lines(self, endpoint: str) -> dict[str, dict[str, Any]]:
        """Raw product entries of every recorded call of an endpoint, by product id."""
        return {entry["productId"]: entry for body in self.bodies(endpoint) for entry in body["products"]}


@dataclass(frozen=True)
class FixedClock:
    """A clock that always answers the same instant. Satisfies the `Clock` port."""

    instant: datetime

    def now(self) -> datetime:
        return self.instant


def read_capture(name: str) -> Capture:
    path = VALIO_FIXTURES_DIR / name
    return Capture(name=name, path=path, manifest=json.loads((path / "manifest.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="session")
def load_capture() -> Callable[[str], Capture]:
    return read_capture


@pytest.fixture(scope="session")
def capture_demo() -> Capture:
    return read_capture(CAPTURE_DEMO)


@pytest.fixture(scope="session")
def capture_sample() -> Capture:
    return read_capture(CAPTURE_SAMPLE)


@pytest.fixture(scope="session")
def capture_extras() -> Capture:
    return read_capture(CAPTURE_EXTRAS)


@pytest.fixture(scope="session")
def demo_clock(capture_demo: Capture) -> FixedClock:
    return FixedClock(capture_demo.time_now)


@pytest.fixture(scope="session")
def sample_clock(capture_sample: Capture) -> FixedClock:
    return FixedClock(capture_sample.time_now)


@pytest.fixture(scope="session")
def raw_products() -> list[dict[str, Any]]:
    """The product file as it is on disk (17,546 records). Loaded once per test session."""
    with (REPO_ROOT / "valio_aimo_junction26_product_data.json").open(encoding="utf-8-sig") as handle:
        return json.load(handle)


@pytest.fixture(scope="session")
def raw_products_by_id(raw_products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(product["id"]): product for product in raw_products}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """Replay settings with a private data directory, no `.env` and no secret."""
    return Settings.for_tests(tta_data_dir=tmp_path / "var", tta_replay_capture=CAPTURE_DEMO)


@pytest.fixture(scope="session")
def agent_hotel() -> Identity:
    return Identity(kind=IdentityKind.AGENT, id="agent:hotel-kitchen", display_name="Hotel kitchen agent",
                    profile_id="hotel-kitchen")


@pytest.fixture(scope="session")
def agent_ward() -> Identity:
    return Identity(kind=IdentityKind.AGENT, id="agent:allergy-ward", display_name="Allergy ward agent",
                    profile_id="allergy-ward")


@pytest.fixture(scope="session")
def approver_purchasing() -> Identity:
    return Identity(kind=IdentityKind.APPROVER, id="human:hotel-purchasing", display_name="Purchasing manager (demo)",
                    profile_id="hotel-kitchen", roles=(ApproverRole.PURCHASING_MANAGER,))


@pytest.fixture(scope="session")
def approver_finance() -> Identity:
    return Identity(kind=IdentityKind.APPROVER, id="human:hotel-finance", display_name="Finance (demo)",
                    profile_id="hotel-kitchen", roles=(ApproverRole.FINANCE,))


@pytest.fixture(scope="session")
def approver_dietitian() -> Identity:
    return Identity(kind=IdentityKind.APPROVER, id="human:ward-dietitian", display_name="Dietitian (demo)",
                    profile_id="allergy-ward", roles=(ApproverRole.DIETITIAN,))


@pytest.fixture(scope="session")
def supplier_reader() -> Identity:
    return Identity(kind=IdentityKind.SUPPLIER, id="supplier:valio-aimo", display_name="Valio Aimo (supplier view)")
