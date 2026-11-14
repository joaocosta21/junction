"""AP-2: a setting chooses the PostgreSQL schema, so a new build can start a new audit trail and leave the old one
as it is (the database refuses to clean it). Unset, the schema is the environment's, as before. No database is
opened here."""

from __future__ import annotations

import pytest

from tta.config import Settings
from tta.store.postgres import schema_for


def _settings(env: str, schema: str) -> Settings:
    """The real settings: `tta_db_schema` is a field of `tta.config` and is read directly (S18)."""
    return Settings.for_tests(tta_env=env, tta_db_schema=schema)


def test_the_setting_is_a_field_of_the_settings_and_blank_by_default() -> None:
    assert Settings.for_tests().tta_db_schema == ""


@pytest.mark.parametrize(("env", "schema"), [("dev", "tta_dev"), ("demo", "tta"), ("prod", "tta")])
def test_without_the_setting_the_schema_is_the_environments(env: str, schema: str) -> None:
    assert schema_for(Settings.for_tests(tta_env=env)) == schema


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_setting_is_no_setting(blank: str) -> None:
    assert schema_for(_settings("demo", blank)) == "tta"
    assert schema_for(_settings("dev", blank)) == "tta_dev"


def test_the_setting_chooses_the_schema_in_every_environment() -> None:
    assert schema_for(_settings("demo", "tta_nov15")) == "tta_nov15"
    assert schema_for(_settings("dev", " tta_nov15 ")) == "tta_nov15"


@pytest.mark.parametrize("name", ["Tta", "tta-2", "2tta", "tta;drop", "t" * 42, 'tta"'])
def test_a_name_the_stores_pattern_refuses_is_refused_and_not_repeated_in_full(name: str) -> None:
    with pytest.raises(ValueError, match="TTA_DB_SCHEMA") as refused:
        schema_for(_settings("demo", name))
    assert "plain lower-case identifier" in str(refused.value)
