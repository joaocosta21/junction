"""The reader split of SPEC section 9 in SQL: the views `audit_buyer` and `audit_supplier`, and a role that reads
only the supplier's view. Each view must show exactly what `tta.audit` shows that reader.

The flows are the audit package's own (`tests/audit/conftest.py`: the hotel order sent to a human, the ward order
placed by the agent), recorded here through `AuditTrail` on the PostgreSQL store.
"""

from __future__ import annotations

import importlib.util
import json
import secrets
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row

from tta.audit import AuditTrail
from tta.audit.readers import SUPPLIER_RULE_MEANINGS, supplier_rule_ids
from tta.contracts.audit import AuditViewEvent
from tta.contracts.common import AuditReader
from tta.store.postgres import PostgresStore

pytestmark = pytest.mark.live

TESTS_DIR = Path(__file__).resolve().parents[1]
VIEW_EVENT_COLUMNS = "id, type, time, actor, sentence, rule_ids, facts, hash"
TABLES_THE_SUPPLIER_MAY_NOT_READ = ("audit_events", "audit_buyer", "offers", "orders", "approvals", "idempotency_keys")


def _load(relative_path: str) -> ModuleType:
    path = TESTS_DIR / relative_path
    name = "tta_reused_pg_" + relative_path.removesuffix(".py").replace("/", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_audit = _load("audit/conftest.py")
samples, trail, hotel_flow, ward_flow = _audit.samples, _audit.trail, _audit.hotel_flow, _audit.ward_flow
# What the audit package's own test looks for in the supplier's view (tests/audit/test_views.py).
_views = _load("audit/test_views.py")
LIMIT_VALUES, ALLERGEN_EXCLUSIONS, APPROVER_DETAILS = (
    _views.LIMIT_VALUES, _views.ALLERGEN_EXCLUSIONS, _views.APPROVER_DETAILS,
)
store_samples = _load("store/conftest.py").Samples()  # a bare audit event, with any rule ids


@pytest.fixture
def store(pg_store: PostgresStore) -> PostgresStore:
    """The store under the audit package's `trail` fixture."""
    return pg_store


@pytest.fixture
def read_view(admin: psycopg.Connection, pg_schema: str) -> Callable[..., list[dict[str, Any]]]:
    def read(view: str, columns: str = VIEW_EVENT_COLUMNS, where: str = "TRUE", *values: object) -> list[dict]:
        query = sql.SQL("SELECT {columns} FROM {view} WHERE {where} ORDER BY seq").format(
            columns=sql.SQL(columns), view=sql.Identifier(pg_schema, view), where=sql.SQL(where),
        )
        with admin.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(query, values).fetchall()

    return read


def _as_view_events(rows: list[dict[str, Any]]) -> list[AuditViewEvent]:
    return [AuditViewEvent.model_validate(row) for row in rows]


def test_the_supplier_view_shows_exactly_what_tta_audit_shows_the_supplier(
    hotel_flow: AuditTrail, ward_flow: AuditTrail, read_view: Callable[..., list[dict]]
) -> None:
    expected = hotel_flow.view(AuditReader.SUPPLIER).events

    rows = read_view("audit_supplier")

    assert len(rows) == len(expected) == 12
    assert _as_view_events(rows) == list(expected)


def test_the_buyer_view_shows_exactly_what_tta_audit_shows_each_buyer(
    hotel_flow: AuditTrail, ward_flow: AuditTrail, read_view: Callable[..., list[dict]]
) -> None:
    for profile_id, count in (("hotel-kitchen", 8), ("allergy-ward", 4)):
        expected = hotel_flow.view(AuditReader.BUYER, profile_id=profile_id).events

        rows = read_view("audit_buyer", VIEW_EVENT_COLUMNS, "profile_id = %s", profile_id)

        assert len(rows) == len(expected) == count
        assert _as_view_events(rows) == list(expected)


def test_the_supplier_view_has_no_limit_no_allergen_exclusion_no_approver_name_or_note(
    hotel_flow: AuditTrail, ward_flow: AuditTrail, read_view: Callable[..., list[dict]]
) -> None:
    # Every column but the event's id and hash, which are random and may hold any digits.
    rows = read_view(
        "audit_supplier", "seq, offer_id, order_id, approval_id, type, time, actor, sentence, rule_ids, facts"
    )

    shown = json.dumps(rows, ensure_ascii=False, default=str)

    assert [value for value in LIMIT_VALUES if value in shown] == []
    assert ALLERGEN_EXCLUSIONS.search(shown) is None
    assert [value for value in APPROVER_DETAILS if value in shown] == []


def test_the_supplier_view_keeps_only_the_rules_tta_audit_lets_the_supplier_see(
    pg_store: PostgresStore, read_view: Callable[..., list[dict]]
) -> None:
    every_rule = ("P-01", "F-02", *reversed(SUPPLIER_RULE_MEANINGS), "F-01", "P-03", "F-09")
    event = store_samples.event("evt_rules")
    pg_store.append_audit_event(event.model_copy(update={"data": event.data.model_copy(
        update={"rule_ids": every_rule})}))

    (row,) = read_view("audit_supplier", "rule_ids")

    assert row["rule_ids"] == list(supplier_rule_ids(every_rule))


def test_the_supplier_role_can_read_its_view_and_nothing_else(
    hotel_flow: AuditTrail, admin: psycopg.Connection, pg_schema: str,
    connect_as: Callable[[str, str], psycopg.Connection],
) -> None:
    login, password = f"{pg_schema}_login", secrets.token_urlsafe(24)
    admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} IN ROLE {}").format(
        sql.Identifier(login), sql.Literal(password), sql.Identifier(f"{pg_schema}_supplier"),
    ))  # what the supplier's own login is: a member of the role (docs/AIVEN.md)
    supplier = connect_as(login, password)

    (count,) = supplier.execute(
        sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(pg_schema, "audit_supplier"))
    ).fetchone()
    assert count == 8
    for table in TABLES_THE_SUPPLIER_MAY_NOT_READ:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            supplier.execute(sql.SQL("SELECT 1 FROM {}").format(sql.Identifier(pg_schema, table)))
    denied_writes = (
        sql.SQL("DELETE FROM {}").format(sql.Identifier(pg_schema, "audit_events")),
        sql.SQL("CREATE TABLE {} (id int)").format(sql.Identifier(pg_schema, "supplier_table")),
    )
    for write in denied_writes:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            supplier.execute(write)


def test_the_supplier_role_holds_select_on_its_view_alone_and_cannot_log_in(
    pg_store: PostgresStore, admin: psycopg.Connection, pg_schema: str
) -> None:
    role = f"{pg_schema}_supplier"

    grants = admin.execute(
        "SELECT table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee = %s", (role,)
    ).fetchall()
    (can_log_in,) = admin.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (role,)).fetchone()

    assert grants == [("audit_supplier", "SELECT")]
    assert can_log_in is False
