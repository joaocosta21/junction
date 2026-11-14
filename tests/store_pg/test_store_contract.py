"""The contract tests of the SQLite store (`tests/store/`), run on both stores: SQLite in memory, and PostgreSQL.

The tests are not copied. Their modules are loaded from their files, and every test that asks only for `store` and
`samples` is run here again with the `store` fixture below. The ones that also need a file, a second connection or
the SQLite module itself have a PostgreSQL counterpart in `test_postgres_store.py`.
"""

from __future__ import annotations

import importlib.util
import inspect
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tta.contracts.ports import Store
from tta.store import SqliteStore

TESTS_DIR = Path(__file__).resolve().parents[1]
REUSED_MODULES = ("store/test_sqlite_store.py", "store/test_atomic.py")
CONTRACT_FIXTURES = {"store", "samples"}
# The smallest number of tests taken over: a change of `tests/store/` that drops one shows here.
MIN_CONTRACT_TESTS = 30


def _load(relative_path: str) -> ModuleType:
    """A test module or conftest of another folder, loaded from its file under a name of its own."""
    path = TESTS_DIR / relative_path
    name = "tta_reused_" + relative_path.removesuffix(".py").replace("/", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _contract_tests(module: ModuleType) -> dict[str, Callable[..., None]]:
    return {
        name: function for name, function in vars(module).items()
        if name.startswith("test_") and inspect.isfunction(function)
        and set(inspect.signature(function).parameters) <= CONTRACT_FIXTURES
    }


_found = [_contract_tests(_load(path)) for path in REUSED_MODULES]
CONTRACT_TESTS = {name: test for tests in _found for name, test in tests.items()}
assert sum(len(tests) for tests in _found) == len(CONTRACT_TESTS), "two reused tests share a name"
globals().update(CONTRACT_TESTS)  # pytest collects them here, with the fixtures of this module

samples = _load("store/conftest.py").samples  # the same hand-built objects as in tests/store


@pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.live)])
def store(request: pytest.FixtureRequest) -> Iterator[Store]:
    if request.param == "postgres":
        yield request.getfixturevalue("pg_store")  # closed by `open_pg`, before its schema is dropped
        return
    sqlite = SqliteStore()
    yield sqlite
    sqlite.close()


def test_the_contract_tests_were_found() -> None:
    assert len(CONTRACT_TESTS) >= MIN_CONTRACT_TESTS
    assert "test_the_store_offers_no_way_to_change_or_remove_an_audit_event" in CONTRACT_TESTS
    assert "test_an_inner_block_that_fails_takes_back_only_its_own_writes" in CONTRACT_TESTS
