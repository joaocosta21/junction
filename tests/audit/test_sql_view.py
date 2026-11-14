"""Valio Aimo's view of the log exists twice: `tta.audit.views.project` and the SQL view `audit_supplier`
(`src/tta/store/sql/003_reader_views.sql`, which the supplier's own database login reads). This file checks,
without a database, that the two list the same fields and mask the same things. The comparison row by row runs
against a live PostgreSQL in `tests/store_pg/test_reader_views.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

from tta.audit import readers
from tta.contracts.audit import AuditData, AuditViewEvent
from tta.contracts.common import ApproverRole

SQL_FILE = Path(__file__).resolve().parents[2] / "src" / "tta" / "store" / "sql" / "003_reader_views.sql"
# Columns a view adds to the reader's fields so that the events of one offer, order or approval can be found.
LOOKUP_COLUMNS = ("seq", "offer_id", "order_id", "approval_id")
BUYER_ONLY_COLUMNS = ("profile_id", "subject", "policy_hash", "previous_hash")
STRING_LITERAL = re.compile(r"'((?:[^']|'')*)'")
RULE_ID = re.compile(r"\b[FP]-\d\d\b")


def _statement(view: str) -> str:
    """The SELECT of one view, comments removed."""
    text = "\n".join(line for line in SQL_FILE.read_text(encoding="utf-8").splitlines()
                     if not line.lstrip().startswith("--"))
    found = re.search(rf"CREATE (?:OR REPLACE )?VIEW {view} AS\s+SELECT(.*?);", text, flags=re.DOTALL)
    assert found is not None, f"no view {view} in {SQL_FILE.name}"
    return found.group(1)


def _select_list(statement: str) -> list[str]:
    """The expressions between SELECT and the view's own FROM, split at the commas that are outside every
    parenthesis and every quoted text."""
    depth, start, quoted, parts = 0, 0, False, []
    for position, character in enumerate(statement):
        if character == "'":
            quoted = not quoted
        if quoted:
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(statement[start:position])
            start = position + 1
        elif depth == 0 and statement.startswith("FROM audit_events", position):
            parts.append(statement[start:position])
            return [part.strip() for part in parts]
    raise AssertionError("the view does not read FROM audit_events")


def _columns(view: str) -> dict[str, str]:
    """Column name -> the expression behind it."""
    columns = {}
    for expression in _select_list(_statement(view)):
        alias = re.search(r"\bAS (\w+)\s*$", expression)
        name = alias.group(1) if alias else expression.rsplit(".", maxsplit=1)[-1]
        columns[name] = expression
    return columns


def test_the_sql_view_and_the_supplier_s_reader_list_the_same_fields() -> None:
    columns = _columns("audit_supplier")

    assert sorted(columns) == sorted((*LOOKUP_COLUMNS, *AuditViewEvent.model_fields))


def test_the_buyer_s_sql_view_lists_the_reader_s_fields_and_the_buyer_s_own() -> None:
    columns = _columns("audit_buyer")

    assert sorted(columns) == sorted((*LOOKUP_COLUMNS, *BUYER_ONLY_COLUMNS, *AuditViewEvent.model_fields))


def test_the_supplier_s_sql_view_reads_the_supplier_s_sentence_and_facts_and_nothing_of_the_buyer_s() -> None:
    columns = _columns("audit_supplier")
    statement = _statement("audit_supplier")

    assert "{data,supplier_sentence}" in columns["sentence"]
    assert "{data,supplier_facts}" in columns["facts"]
    assert {"supplier_sentence", "supplier_facts"} <= set(AuditData.model_fields)
    for buyer_only in ("{data,sentence}", "{data,facts}", "profile_id", "policy_hash", "display_name}"):
        assert buyer_only not in statement


def test_the_sql_view_shows_every_rule_that_fired_as_the_reader_does() -> None:
    every_rule = ("P-01", "F-02", "F-01", "P-01", "P-04", "F-09", "F-10")

    assert readers.supplier_rule_ids(every_rule) == ("P-01", "F-02", "F-01", "P-04", "F-09", "F-10")
    assert RULE_ID.findall(_statement("audit_supplier")) == []  # no list of rule ids filters the column
    assert "{data,rule_ids}" in _columns("audit_supplier")["rule_ids"]


def test_the_sql_view_names_a_human_by_the_same_roles_and_words_as_the_reader() -> None:
    literals = {text.replace("''", "'") for text in STRING_LITERAL.findall(_statement("audit_supplier"))}
    reader_s = {
        *(role.value for role in ApproverRole), readers.HUMAN_ID, readers.HUMAN_WITHOUT_A_ROLE,
        readers.ROLE_SEPARATOR, readers.BUYERS_ROLE.format(roles=""),
        readers.SUPPLIER_ROLE, readers.SUPPLIER_READER_ID, readers.SUPPLIER_READER,
        *(text for mask in readers.STORED_SENTENCE_MASKS for text in mask),
        *("{" + ",".join(path) + "}" for path in readers.STORED_COUNT_PATHS),
        "g",  # the flag of regexp_replace: everywhere in the sentence, as `re.sub` does
    }
    # A JSON key, a kind of actor, what `replace` turns a role's "_" into, or a path into the stored event.
    of_the_view = {
        "human", "agent", "kind", "id", "role", "display_name", "_", " ", "{}", "{data,actor,kind}",
        "{data,actor,role}", "{data,actor,id}", "{data,actor}", "{data,supplier_sentence}", "{data,rule_ids}",
        "{data,supplier_facts}",
    }

    assert reader_s <= literals
    assert literals - reader_s - of_the_view == set()  # no other word, so no name of a person and no rule id


def test_the_sql_view_masks_what_an_older_event_holds_exactly_as_the_reader_does() -> None:
    """Review finding M1: the counts of products left out for an allergen, in the sentence and in the facts of
    events stored before the fix. The same patterns, replacements and paths, applied in the same order."""
    columns = _columns("audit_supplier")
    sentence = [text.replace("''", "'") for text in STRING_LITERAL.findall(columns["sentence"])]
    facts = STRING_LITERAL.findall(columns["facts"])

    in_order = [text for mask in readers.STORED_SENTENCE_MASKS for text in (*mask, "g")]
    assert sentence == ["{data,supplier_sentence}", *in_order]
    assert columns["sentence"].count("regexp_replace(") == len(readers.STORED_SENTENCE_MASKS)
    paths = ["{" + ",".join(path) + "}" for path in readers.STORED_COUNT_PATHS]
    assert facts == ["{data,supplier_facts}", "{}", *paths]
    assert columns["facts"].count("#-") == len(readers.STORED_COUNT_PATHS)
    assert ";" not in "".join(in_order)  # the file is one statement per semicolon to whoever reads it by eye


def test_valio_aimo_s_own_token_is_named_by_the_sql_view_as_by_the_reader() -> None:
    actor = _columns("audit_supplier")["actor"]

    assert f"= '{readers.SUPPLIER_ROLE}' THEN" in actor
    assert actor.index(readers.SUPPLIER_READER.replace("'", "''")) < actor.index(readers.HUMAN_WITHOUT_A_ROLE)


def test_the_file_can_run_at_every_start_whatever_view_the_database_already_holds() -> None:
    """`CREATE OR REPLACE VIEW` refuses a changed column, and a refused statement fails the whole start-up
    (AWARDS-PLAN.md, AP-2). The supplier's view is therefore dropped first; `004_supplier_role.sql`, which runs
    next at every start, gives the supplier's role its grant again."""
    text = SQL_FILE.read_text(encoding="utf-8")
    grant = (SQL_FILE.parent / "004_supplier_role.sql").read_text(encoding="utf-8")

    assert text.index("DROP VIEW IF EXISTS audit_supplier;") < text.index("CREATE VIEW audit_supplier AS")
    assert "CREATE OR REPLACE VIEW audit_buyer AS" in text
    assert "CASCADE" not in text
    assert "GRANT SELECT ON %I.audit_supplier" in grant


def test_the_buyer_s_sql_view_keeps_the_columns_the_deployed_database_holds() -> None:
    """Replaced in place, so its columns may only grow at the end: these are the columns of commit 6fab186."""
    assert list(_columns("audit_buyer")) == [
        "seq", "profile_id", "offer_id", "order_id", "approval_id", "id", "type", "time", "subject", "actor",
        "sentence", "rule_ids", "facts", "policy_hash", "previous_hash", "hash",
    ]
