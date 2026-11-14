"""The cheaper product with the same formula (P10 F6, kind CHEAPER_SAME_FORMULA).

For a product an offer chose: another product of the same type that keeps its formula by the measure of
`tta.offers.formula` (judged by the caller and passed in `CheaperOption.formula`), with confirmed stock that covers
the quantity, cheaper per litre or kilogram by `CHEAPER_MIN_SAVING` or more, and cheaper in total for the whole
packs that cover the quantity. At most one per line: the largest saving. The sentence states both prices and that
the formula is kept within our tolerance, with the formula measure's own sentence. A catalog fact: it needs no
order history. The same product in a larger pack is the larger pack's (`tta.suggestions.packs`), not this kind's.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from tta.contracts.common import RATIO_PLACES, UNIT_PRICE_PLACES, PackPreference, round_money
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import FormulaCheck, FormulaOutcome
from tta.contracts.request import PurchaseRequest
from tta.contracts.suggestion import (
    EvidenceSource,
    Suggestion,
    SuggestionEffect,
    SuggestionEvidence,
    SuggestionKind,
    suggestion_id_for,
)
from tta.suggestions.packs import PackOption, confirmed_for, needed_in_measure, pack_label, stock_words
from tta.suggestions.requests import with_line_changed
from tta.suggestions.thresholds import CHEAPER_MIN_SAVING, LARGER_PACK_MAX_OVER, named
from tta.suggestions.wording import amount, euros, more_or_less, per_measure, sentence

_UNIT_PRICE = Decimal(1).scaleb(-UNIT_PRICE_PLACES)
_RATIO = Decimal(1).scaleb(-RATIO_PLACES)
_SAME_BRAND = (FormulaOutcome.SAME_PRODUCT_OTHER_PACK, FormulaOutcome.SAME_BRAND)


@dataclass(frozen=True)
class CheaperOption:
    """One product measured against the offered one: its pack and price, and its formula against the original's."""

    pack: PackOption
    formula: FormulaCheck


@dataclass(frozen=True)
class _Fit:
    option: CheaperOption
    packs: Decimal
    saving: Decimal


def cheaper_same_formula(customer_id: str, request: PurchaseRequest, line_index: int, original: PackOption,
                         candidates: Sequence[CheaperOption], *, same_brand_only: bool = False) -> Suggestion | None:
    """The cheaper product with the largest saving for one request line, or None. `same_brand_only`: where the
    line matters by formula a product of another brand stays silent (P15 section 4.1)."""
    if not 0 <= line_index < len(request.lines):
        raise InvalidRequest(f"The request has no line {line_index + 1}.")
    line = request.lines[line_index]
    needed = needed_in_measure(line, original)
    if line.pack is PackPreference.PORTION or needed is None or original.price_per_measure <= 0:
        return None
    fits = [fit for fit in (_fit(candidate, original, needed, same_brand_only) for candidate in candidates)
            if fit is not None]
    if not fits:
        return None
    best = max(fits, key=lambda fit: (fit.saving, fit.option.pack.product_id))
    return _suggestion(customer_id, request, line_index, original, best, needed)


def _fit(candidate: CheaperOption, original: PackOption, needed: Decimal, same_brand_only: bool) -> _Fit | None:
    pack, formula = candidate.pack, candidate.formula
    if not formula.keeps_formula or pack.measure is not original.measure or pack.product_id == original.product_id:
        return None
    if same_brand_only and formula.outcome not in _SAME_BRAND:
        return None
    if pack.same_product and pack.pack_size > original.pack_size:
        return None  # the same product in a larger pack: the larger pack's suggestion
    saving = 1 - pack.price_per_measure / original.price_per_measure
    packs = pack.packs_for(needed)
    if saving < CHEAPER_MIN_SAVING or packs * pack.pack_size > needed * (1 + LARGER_PACK_MAX_OVER):
        return None
    if packs * pack.unit_net_price_eur >= original.packs_for(needed) * original.unit_net_price_eur:
        return None  # whole packs must not make the order dearer
    if not confirmed_for(pack.availability, packs):
        return None
    return _Fit(option=candidate, packs=packs, saving=saving)


def _suggestion(customer_id: str, request: PurchaseRequest, line_index: int, original: PackOption, fit: _Fit,
                needed: Decimal) -> Suggestion:
    pack, formula = fit.option.pack, fit.option.formula
    before = round_money(original.packs_for(needed) * original.unit_net_price_eur)
    after = round_money(fit.packs * pack.unit_net_price_eur)
    effect = SuggestionEffect(
        net_change_eur=after - before, measure=original.measure,
        unit_price_before_eur=original.price_per_measure.quantize(_UNIT_PRICE, rounding=ROUND_HALF_UP),
        unit_price_after_eur=pack.price_per_measure.quantize(_UNIT_PRICE, rounding=ROUND_HALF_UP),
        saving_ratio=fit.saving.quantize(_RATIO, rounding=ROUND_HALF_UP),
    )
    evidence = SuggestionEvidence(
        source=EvidenceSource.CATALOG, synthetic=False, orders_considered=0, orders_matching=0,
        values=(original.price_per_measure, pack.price_per_measure, fit.packs),
        thresholds=named(CHEAPER_MIN_SAVING=CHEAPER_MIN_SAVING, LARGER_PACK_MAX_OVER=LARGER_PACK_MAX_OVER),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(customer_id, SuggestionKind.CHEAPER_SAME_FORMULA, pack.product_id),
        kind=SuggestionKind.CHEAPER_SAME_FORMULA, customer_id=customer_id, request_line_index=line_index,
        product_id=pack.product_id, name=pack.name, quantity=needed, unit=original.measure,
        replaces_product_id=original.product_id, sentence=_sentence(original, fit, needed, before, after),
        evidence=evidence, effect=effect, availability=pack.availability, stock_confirmed=True,
        checks=(formula.sentence,),
        accept_request=with_line_changed(request, line_index, product_ids=[pack.product_id], quantity=needed,
                                         unit=original.measure),
    )


def _sentence(original: PackOption, fit: _Fit, needed: Decimal, before: Decimal, after: Decimal) -> str:
    """ "Because you buy Oatly iKaffe 0.5 L (468319), we suggest Oatly iKaffe Oat drink 1.5 L (473278): the same
    formula, €1.48 a litre instead of €2.88. For your 30 L: €44.40, €42.00 less. 234 L confirmed for Monday 16
    November." The formula measure's own sentence is in the suggestion's checks."""
    pack, formula, unit = fit.option.pack, fit.option.formula, original.measure
    same = "the same formula" if formula.outcome in _SAME_BRAND else "another brand with the same formula"
    reason = (f"Because you buy {pack_label(original)}, we suggest {pack_label(pack)}: {same}, "
              f"{per_measure(pack.price_per_measure, unit)} instead of {euros(original.price_per_measure)}.")
    total = f"For your {amount(needed, unit)}: {euros(after)}, {more_or_less(after - before)}."
    return sentence(reason, total, stock_words(pack))
