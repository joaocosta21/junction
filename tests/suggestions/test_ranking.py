"""Which suggestions a list shows (decision B32): one per kind, three in all, in the decided order of kinds; the
strongest of a kind wins; every other one is held back with a reason a page can show.

Hand-built suggestions: no catalog, no recording.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from tta.contracts.common import Unit
from tta.contracts.suggestion import (
    EvidenceSource,
    Serves,
    Suggestion,
    SuggestionEvidence,
    SuggestionKind,
    suggestion_id_for,
)
from tta.suggestions.ranking import HoldReason, ranked

EVIDENCE = SuggestionEvidence(source=EvidenceSource.SYNTHETIC_HISTORY, synthetic=True, orders_considered=8,
                              orders_matching=7)
K = SuggestionKind


def _suggestion(kind: SuggestionKind, product: str, **changes: Any) -> Suggestion:
    fields: dict[str, Any] = {
        "suggestion_id": suggestion_id_for("bakery-cafe", kind, product), "kind": kind,
        "customer_id": "bakery-cafe", "product_id": product, "name": f"Product {product}",
        "quantity": Decimal(10), "unit": Unit.L, "sentence": "A sentence with its numbers.", "evidence": EVIDENCE,
    }
    return Suggestion(**{**fields, **changes})


def _shown(found: Any) -> list[tuple[SuggestionKind, str]]:
    return [(each.kind, each.product_id) for each in found.shown]


def _held(found: Any) -> list[tuple[SuggestionKind, str, HoldReason]]:
    return [(each.suggestion.kind, each.suggestion.product_id, each.reason) for each in found.held_back]


def test_three_forgotten_items_no_longer_hide_the_cheaper_line() -> None:
    """The bakery asking for 30 L of 468319 (L4-2a's figures): three forgotten items, then the cheaper line, the
    larger pack and Valio Aimo's own. One forgotten item, the cheaper line and the larger pack are shown."""
    suggestions = [
        _suggestion(K.FORGOTTEN_ITEM, "463380"), _suggestion(K.FORGOTTEN_ITEM, "469346"),
        _suggestion(K.FORGOTTEN_ITEM, "464727"), _suggestion(K.CHEAPER_SAME_FORMULA, "473278"),
        _suggestion(K.LARGER_PACK, "464320"), _suggestion(K.FROM_SUPPLIER, "464320", serves=Serves.SUPPLIER),
    ]

    found = ranked(suggestions)

    assert _shown(found) == [(K.FORGOTTEN_ITEM, "463380"), (K.CHEAPER_SAME_FORMULA, "473278"),
                             (K.LARGER_PACK, "464320")]
    assert _held(found) == [
        (K.FORGOTTEN_ITEM, "469346", HoldReason.KIND_ALREADY_SHOWN),
        (K.FORGOTTEN_ITEM, "464727", HoldReason.KIND_ALREADY_SHOWN),
        (K.FROM_SUPPLIER, "464320", HoldReason.PRODUCT_ALREADY_SHOWN),
    ]


def test_each_held_back_suggestion_says_why_in_words_a_page_can_show() -> None:
    suggestions = [
        _suggestion(K.FORGOTTEN_ITEM, "463380"), _suggestion(K.FORGOTTEN_ITEM, "469346"),
        _suggestion(K.CHEAPER_SAME_FORMULA, "473278"), _suggestion(K.LARGER_PACK, "473278"),
        _suggestion(K.QUANTITY_TREND, "470863"), _suggestion(K.FROM_SUPPLIER, "462775", serves=Serves.SUPPLIER),
    ]

    found = ranked(suggestions)

    said = {each.suggestion.product_id + each.suggestion.kind.value: each.summary for each in found.held_back}
    assert said == {
        "469346FORGOTTEN_ITEM": "another forgotten item ranks higher",
        "473278LARGER_PACK": "the same product is already shown as the cheaper product with the same formula",
        "462775FROM_SUPPLIER": "3 suggestions of kinds that rank higher are shown",
    }
    assert _shown(found) == [(K.FORGOTTEN_ITEM, "463380"), (K.CHEAPER_SAME_FORMULA, "473278"),
                             (K.QUANTITY_TREND, "470863")]
    assert next(each for each in found.held_back if each.suggestion.kind is K.FROM_SUPPLIER).reason is (
        HoldReason.LIST_FULL
    )


def test_within_a_kind_the_strongest_wins_and_a_product_already_shown_makes_way_for_the_next() -> None:
    """Strongest first is the order each kind's own function gives (L5): the ranking keeps it. A product shown
    under a higher kind does not take the slot of its own kind: the next of that kind is shown."""
    suggestions = [
        _suggestion(K.FORGOTTEN_ITEM, "463797"), _suggestion(K.FORGOTTEN_ITEM, "473424"),
        _suggestion(K.LARGER_PACK, "463797"), _suggestion(K.LARGER_PACK, "464320"),
    ]

    found = ranked(suggestions)

    assert _shown(found) == [(K.FORGOTTEN_ITEM, "463797"), (K.LARGER_PACK, "464320")]
    assert _held(found) == [(K.FORGOTTEN_ITEM, "473424", HoldReason.KIND_ALREADY_SHOWN),
                            (K.LARGER_PACK, "463797", HoldReason.PRODUCT_ALREADY_SHOWN)]


def test_the_usual_product_and_the_usual_quantity_are_one_kind_of_the_decided_order() -> None:
    suggestions = [_suggestion(K.USUAL_QUANTITY, "469363"), _suggestion(K.USUAL_PRODUCT, "463047"),
                   _suggestion(K.CHEAPER_SAME_FORMULA, "473278")]

    found = ranked(suggestions)

    assert _shown(found) == [(K.USUAL_PRODUCT, "463047"), (K.CHEAPER_SAME_FORMULA, "473278")]
    held = found.held_back[0]
    assert (held.suggestion.kind, held.reason) == (K.USUAL_QUANTITY, HoldReason.KIND_ALREADY_SHOWN)
    assert held.summary == "another suggestion of the usual product and quantity ranks higher"


def test_valio_aimos_own_suggestion_is_shown_last_even_when_given_first() -> None:
    found = ranked([_suggestion(K.FROM_SUPPLIER, "462775", serves=Serves.SUPPLIER),
                    _suggestion(K.FORGOTTEN_ITEM, "463797")])

    assert _shown(found) == [(K.FORGOTTEN_ITEM, "463797"), (K.FROM_SUPPLIER, "462775")]
    assert found.held_back == ()


def test_nothing_to_rank_shows_and_holds_back_nothing() -> None:
    found = ranked([])

    assert (found.shown, found.held_back) == ((), ())
