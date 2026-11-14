"""The `Suggestion` shape (P15 section 4.5) and the order a list shows the kinds in (runbook, "Suggestions")."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from tta.contracts.common import Unit
from tta.contracts.suggestion import (
    KIND_ORDER,
    EvidenceSource,
    Serves,
    Suggestion,
    SuggestionEvidence,
    SuggestionKind,
    suggestion_id_for,
)
from tta.suggestions import first_suggestions
from tta.suggestions.thresholds import MAX_SUGGESTIONS

EVIDENCE = SuggestionEvidence(source=EvidenceSource.SYNTHETIC_HISTORY, synthetic=True, orders_considered=8,
                              orders_matching=7)


def _suggestion(kind: SuggestionKind, product: str, **changes: Any) -> Suggestion:
    fields: dict[str, Any] = {
        "suggestion_id": suggestion_id_for("hotel-kitchen", kind, product), "kind": kind,
        "customer_id": "hotel-kitchen", "product_id": product, "name": f"Product {product}",
        "quantity": Decimal(10), "unit": Unit.L, "sentence": "A sentence with its numbers.", "evidence": EVIDENCE,
    }
    return Suggestion(**{**fields, **changes})


def test_the_kinds_follow_the_decided_order() -> None:
    assert KIND_ORDER[:6] == (
        SuggestionKind.FORGOTTEN_ITEM, SuggestionKind.USUAL_PRODUCT, SuggestionKind.USUAL_QUANTITY,
        SuggestionKind.CHEAPER_SAME_FORMULA, SuggestionKind.LARGER_PACK, SuggestionKind.QUANTITY_TREND,
    )
    assert set(KIND_ORDER) == set(SuggestionKind)


def test_a_suggestion_id_is_stable_for_one_buyer_kind_and_product() -> None:
    first = suggestion_id_for("hotel-kitchen", SuggestionKind.FORGOTTEN_ITEM, "463797")

    assert first == suggestion_id_for("hotel-kitchen", SuggestionKind.FORGOTTEN_ITEM, "463797")
    assert first == "sug_forgotten_item_463797_hotel-kitchen"
    assert first != suggestion_id_for("allergy-ward", SuggestionKind.FORGOTTEN_ITEM, "463797")


def test_a_suggestion_serves_the_buyer_unless_it_says_otherwise_and_is_immutable() -> None:
    found = _suggestion(SuggestionKind.FORGOTTEN_ITEM, "463797")

    assert found.serves is Serves.BUYER
    with pytest.raises(ValidationError):
        found.quantity = Decimal(1)  # type: ignore[misc]


@pytest.mark.parametrize(
    "changes",
    [{"quantity": Decimal(0)}, {"product_id": "46 37"}, {"suggestion_id": "sug with spaces"}, {"surprise": 1}],
)
def test_a_suggestion_that_breaks_its_shape_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _suggestion(SuggestionKind.FORGOTTEN_ITEM, "463797", **changes)


def test_matching_orders_cannot_exceed_the_orders_considered() -> None:
    with pytest.raises(ValidationError):
        SuggestionEvidence(source=EvidenceSource.CATALOG, synthetic=False, orders_considered=2, orders_matching=3)


def test_a_list_shows_at_most_three_buyer_suggestions_first_in_the_decided_order_one_per_product() -> None:
    suggestions = [
        _suggestion(SuggestionKind.QUANTITY_TREND, "470863"),
        _suggestion(SuggestionKind.LARGER_PACK, "473278", serves=Serves.SUPPLIER),
        _suggestion(SuggestionKind.USUAL_PRODUCT, "469363"),
        _suggestion(SuggestionKind.FORGOTTEN_ITEM, "463797"),
        _suggestion(SuggestionKind.USUAL_QUANTITY, "469363"),
    ]

    shown = first_suggestions(suggestions)

    assert MAX_SUGGESTIONS == 3
    assert [(found.kind, found.product_id) for found in shown] == [
        (SuggestionKind.FORGOTTEN_ITEM, "463797"),
        (SuggestionKind.USUAL_PRODUCT, "469363"),
        (SuggestionKind.QUANTITY_TREND, "470863"),
    ]


def test_a_supplier_suggestion_comes_last() -> None:
    shown = first_suggestions([
        _suggestion(SuggestionKind.LARGER_PACK, "473278", serves=Serves.SUPPLIER),
        _suggestion(SuggestionKind.QUANTITY_TREND, "470863"),
    ])

    assert [found.serves for found in shown] == [Serves.BUYER, Serves.SUPPLIER]
    assert first_suggestions([], limit=3) == ()
