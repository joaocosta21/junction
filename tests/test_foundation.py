"""Settings never reveal a secret, and the recorded captures are complete and hold no key."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tta.config import Settings
from tta.contracts.common import DataSource

SENTINEL = "sentinel-secret-value-0123456789"
SECRET_LOOKING = re.compile(r"x-api-key|authorization|bearer |AIza[0-9A-Za-z_-]{20,}|postgres(ql)?://", re.IGNORECASE)


def test_a_secret_never_appears_in_repr_str_or_describe() -> None:
    settings = Settings.for_tests(valio_aimo_api_key=SENTINEL, gemini_api_key=SENTINEL, database_url=SENTINEL,
                                  context_dev_api_key=SENTINEL, tta_tokens=SENTINEL)

    shown = repr(settings) + str(settings) + repr(settings.describe()) + settings.model_dump_json()

    assert SENTINEL not in shown
    assert settings.has_valio_key and settings.has_gemini_key and settings.has_database_url
    assert settings.valio_aimo_api_key.get_secret_value() == SENTINEL


def test_test_settings_carry_no_secret_and_default_to_replay(settings: Settings) -> None:
    assert settings.tta_mode is DataSource.REPLAY
    assert not (settings.has_valio_key or settings.has_gemini_key or settings.has_database_url)
    assert not settings.has_context_dev_key


def test_an_empty_value_counts_as_not_set() -> None:
    assert not Settings.for_tests(valio_aimo_api_key="  ").has_valio_key


@pytest.mark.parametrize(("name", "count"), [("2026-11-14-demo", 769), ("2026-11-13-sample", 1001),
                                             ("2026-11-13-extras", 37)])
def test_a_capture_has_one_price_and_one_availability_entry_per_id(load_capture, name: str, count: int) -> None:
    capture = load_capture(name)

    assert len(capture.ids) == count == capture.manifest["product_count"]
    assert set(capture.lines("availability")) == set(capture.ids) == set(capture.lines("price"))
    assert capture.time_now.utcoffset() is not None


def test_no_fixture_file_holds_a_key_or_a_request_header(settings: Settings) -> None:
    files = [path for path in Path(settings.tta_fixtures_dir).rglob("*") if path.is_file()]

    assert files
    for path in files:
        # Images (the photo fixtures of the agent) are bytes; their text, where any, is scanned the same way.
        assert not SECRET_LOOKING.search(path.read_bytes().decode("utf-8", errors="ignore")), path.name


def test_demo_capture_holds_the_scenario_products(capture_demo) -> None:
    lines = capture_demo.lines("availability")

    for product_id in ("464306", "463203", "464056", "468319", "473609", "471690", "471881", "464320",
                       "464744", "466988"):
        assert product_id in lines, product_id


def test_an_unset_environment_is_production_and_has_no_demo_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TTA_ENV", raising=False)

    settings = Settings(_env_file=None)

    assert settings.tta_env == "prod"
    assert not settings.is_demo_environment



def test_no_forwarded_header_is_trusted_unless_the_proxy_hops_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError  # noqa: PLC0415  (only this test needs it)

    assert Settings.for_tests().tta_trusted_proxy_hops == 0
    monkeypatch.setenv("TTA_TRUSTED_PROXY_HOPS", "2")
    assert Settings(_env_file=None).tta_trusted_proxy_hops == 2
    with pytest.raises(ValidationError):
        Settings.for_tests(tta_trusted_proxy_hops=-1)
