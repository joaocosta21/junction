"""Which suggestions a list shows: at most 3, the buyer's first in the decided order, one per product."""

from __future__ import annotations

from collections.abc import Iterable

from tta.contracts.suggestion import KIND_ORDER, Serves, Suggestion
from tta.suggestions.thresholds import MAX_SUGGESTIONS

_RANK = {kind: rank for rank, kind in enumerate(KIND_ORDER)}


def first_suggestions(suggestions: Iterable[Suggestion], limit: int = MAX_SUGGESTIONS) -> tuple[Suggestion, ...]:
    """The suggestions to show: a supplier's after every buyer's (P15 section 4.2), then by kind (runbook,
    "Suggestions"), then as given; a product already shown is not shown twice."""
    ranked = sorted(enumerate(suggestions),
                    key=lambda item: (item[1].serves is Serves.SUPPLIER, _RANK[item[1].kind], item[0]))
    shown: list[Suggestion] = []
    for _, suggestion in ranked:
        if len(shown) >= limit:
            break
        if all(other.product_id != suggestion.product_id for other in shown):
            shown.append(suggestion)
    return tuple(shown)
