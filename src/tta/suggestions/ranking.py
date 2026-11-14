"""Which suggestions a list shows (decision B32): at most one per kind and three in all, in the decided order of
kinds, the buyer's before Valio Aimo's own; one per product. Every other one is held back with its reason.

The decided order (runbook, "Suggestions"): the forgotten item, the usual product and quantity, a cheaper product
with the same formula, a larger pack, a trend, a new or related product (Valio Aimo's own). The usual product and
the usual quantity are one kind of that order, so a list holds one of them. Within a kind the strongest wins: the
order each kind's own function gives (strongest first, L5), which the ranking keeps.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

from tta.contracts.common import Contract
from tta.contracts.suggestion import KIND_ORDER, Serves, Suggestion, SuggestionKind
from tta.suggestions.thresholds import MAX_SUGGESTIONS

_RANK = {kind: rank for rank, kind in enumerate(KIND_ORDER)}
# The kinds of the decided order that are one kind there: "the usual product and quantity".
_SLOT = {SuggestionKind.USUAL_QUANTITY: SuggestionKind.USUAL_PRODUCT}
# How a held-back reason names a kind: "another forgotten item ranks higher".
KIND_WORDS = {
    SuggestionKind.FORGOTTEN_ITEM: "forgotten item",
    SuggestionKind.USUAL_PRODUCT: "usual product",
    SuggestionKind.USUAL_QUANTITY: "usual quantity",
    SuggestionKind.CHEAPER_SAME_FORMULA: "cheaper product with the same formula",
    SuggestionKind.LARGER_PACK: "larger pack",
    SuggestionKind.QUANTITY_TREND: "trend",
    SuggestionKind.REORDER_DUE: "reorder reminder",
    SuggestionKind.FROM_SUPPLIER: "Valio Aimo's own suggestion",
}
_SLOT_WORDS = {SuggestionKind.USUAL_PRODUCT: "suggestion of the usual product and quantity",
               SuggestionKind.FROM_SUPPLIER: "of Valio Aimo's own suggestions"}


class HoldReason(StrEnum):
    """Why a suggestion that passed the guard is not shown."""

    KIND_ALREADY_SHOWN = "KIND_ALREADY_SHOWN"  # another suggestion of its kind ranks higher
    PRODUCT_ALREADY_SHOWN = "PRODUCT_ALREADY_SHOWN"  # its product is shown under a kind that ranks higher
    LIST_FULL = "LIST_FULL"  # three suggestions of kinds that rank higher are shown


class HeldBackSuggestion(Contract):
    """A suggestion that passed the guard and is not shown, with the reason in words a page can show."""

    suggestion: Suggestion
    reason: HoldReason
    summary: str  # "another forgotten item ranks higher": lower case, for a list or a log line


class Ranked(Contract):
    shown: tuple[Suggestion, ...] = ()
    held_back: tuple[HeldBackSuggestion, ...] = ()


def ranked(suggestions: Iterable[Suggestion], limit: int = MAX_SUGGESTIONS) -> Ranked:
    """The suggestions to show and those held back, each held back with its reason. Valio Aimo's own after every
    buyer's (P15 section 4.2), then by kind, then as given."""
    ordered = sorted(enumerate(suggestions),
                     key=lambda item: (item[1].serves is Serves.SUPPLIER, _RANK[item[1].kind], item[0]))
    shown: list[Suggestion] = []
    held: list[HeldBackSuggestion] = []
    for _, suggestion in ordered:
        reason = _hold_reason(suggestion, shown, limit)
        if reason is None:
            shown.append(suggestion)
        else:
            held.append(HeldBackSuggestion(suggestion=suggestion, reason=reason[0], summary=reason[1]))
    return Ranked(shown=tuple(shown), held_back=tuple(held))


def first_suggestions(suggestions: Iterable[Suggestion], limit: int = MAX_SUGGESTIONS) -> tuple[Suggestion, ...]:
    """The suggestions to show (`ranked`), without those held back."""
    return ranked(suggestions, limit).shown


def _hold_reason(suggestion: Suggestion, shown: list[Suggestion], limit: int) -> tuple[HoldReason, str] | None:
    """Why the suggestion is not shown beside those already shown; None when it is shown."""
    slot = _slot(suggestion.kind)
    if any(_slot(other.kind) is slot for other in shown):
        words = _SLOT_WORDS.get(slot, KIND_WORDS[slot])
        return HoldReason.KIND_ALREADY_SHOWN, f"another {words} ranks higher"
    same = next((other for other in shown if other.product_id == suggestion.product_id), None)
    if same is not None:
        return HoldReason.PRODUCT_ALREADY_SHOWN, f"the same product is already shown as {the_kind(same.kind)}"
    if len(shown) >= limit:
        return HoldReason.LIST_FULL, f"{len(shown)} suggestions of kinds that rank higher are shown"
    return None


def the_kind(kind: SuggestionKind) -> str:
    """ "the larger pack", "Valio Aimo's own suggestion"."""
    words = KIND_WORDS[kind]
    return words if kind is SuggestionKind.FROM_SUPPLIER else f"the {words}"


def _slot(kind: SuggestionKind) -> SuggestionKind:
    return _SLOT.get(kind, kind)
