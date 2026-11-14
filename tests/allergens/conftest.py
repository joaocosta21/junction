"""Helpers for the allergen tests: hand-built statements, no file and no network."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from tta.contracts.allergen import AllergenStatement
from tta.contracts.common import AllergenRelation


def build_statements(*pairs: tuple[str, str]) -> tuple[AllergenStatement, ...]:
    """`build_statements(("AM", "CONTAINS"), ("AW", "FREE_FROM"))` → the statements of one product."""
    return tuple(AllergenStatement(code=code, relation=AllergenRelation(relation)) for code, relation in pairs)


@pytest.fixture
def statements() -> Callable[..., tuple[AllergenStatement, ...]]:
    return build_statements
