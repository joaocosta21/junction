"""Fixtures for the customer files' tests: the catalog (built once) and tonight's recording in replay.

No test here calls a live service, and nothing reads `.env`.
"""

from __future__ import annotations

from typing import Any

import pytest

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.valio.replay import ReplayGateway


@pytest.fixture(scope="session")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture(scope="session")
def recording(capture_demo: Any) -> ReplayGateway:
    """Tonight's capture `2026-11-14-demo`, as the gateway replays it."""
    return ReplayGateway(capture_demo.path)
