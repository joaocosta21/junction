"""The larger pack: the same product in a larger pack, cheaper per litre or kilogram (P15 R5, LARGER_PACK).

It speaks when all hold: the candidate is the same product in another pack (P10's outcome, judged by the caller
with the formula measure of `tta.offers.formula` and passed in `same_product`); its pack is larger; it is 5% or more
cheaper per litre or kilogram; whole packs cover the quantity with at most 10% more; and confirmed stock covers
those packs. Silent on a line that asks for portion packs. A catalog fact: it needs no order history.
A larger pack that costs more in total, because whole packs hold more than asked, says so first.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from tta.contracts.availability import AvailabilityAssessment
from tta.contracts.common import (
    QUANTITY_PLACES,
    RATIO_PLACES,
    UNIT_PRICE_PLACES,
    AvailabilityState,
    PackPreference,
    Unit,
    round_money,
)
from tta.contracts.errors import InvalidRequest
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.suggestion import (
    EvidenceSource,
    Suggestion,
    SuggestionEffect,
    SuggestionEvidence,
    SuggestionKind,
    suggestion_id_for,
)
from tta.suggestions.requests import with_line_changed
from tta.suggestions.thresholds import LARGER_PACK_MAX_OVER, LARGER_PACK_MIN_SAVING, named
from tta.suggestions.wording import (
    amount,
    confirmed_words,
    euros,
    more_or_less,
    packs,
    per_measure,
    sentence,
    short_label,
    short_name,
    stock_amount,
)

MEASURES = (Unit.L, Unit.KG)
_UNIT_PRICE = Decimal(1).scaleb(-UNIT_PRICE_PLACES)
_RATIO = Decimal(1).scaleb(-RATIO_PLACES)
_QUANTITY = Decimal(1).scaleb(-QUANTITY_PLACES)


@dataclass(frozen=True)
class PackOption:
    """One pack of a product, as the caller read it from the catalog and the supplier's answers."""

    product_id: str
    name: str
    pack_size: Decimal  # litres or kilograms in one sales unit (`Catalog.pack_size`)
    measure: Unit  # L or KG
    unit_net_price_eur: Decimal  # EUR before tax per sales unit
    availability: AvailabilityAssessment | None = None
    lot_step: Decimal = Decimal(1)  # sales units a quantity moves in (`tta.catalog.lots.lot_step`)
    same_product: bool = False  # P10's "same product in another pack" against the original, judged by the caller

    def __post_init__(self) -> None:
        if self.measure not in MEASURES or self.pack_size <= 0 or self.lot_step <= 0 or self.unit_net_price_eur < 0:
            raise InvalidRequest("A pack needs a size and a lot step above zero, a price, and litres or kilograms.",
                                 product_id=self.product_id)

    @property
    def price_per_measure(self) -> Decimal:
        return self.unit_net_price_eur / self.pack_size

    def packs_for(self, needed: Decimal) -> Decimal:
        """The whole packs, in steps of the lot, that hold at least `needed`."""
        steps = (needed / self.pack_size / self.lot_step).to_integral_value(rounding=ROUND_CEILING)
        return steps * self.lot_step


@dataclass(frozen=True)
class _Fit:
    option: PackOption
    packs: Decimal
    saving: Decimal

    @property
    def covered(self) -> Decimal:
        return self.packs * self.option.pack_size


def larger_pack(customer_id: str, request: PurchaseRequest, line_index: int, original: PackOption,
                candidates: Sequence[PackOption]) -> Suggestion | None:
    """The larger pack with the largest saving for one request line, or None."""
    if not 0 <= line_index < len(request.lines):
        raise InvalidRequest(f"The request has no line {line_index + 1}.")
    line = request.lines[line_index]
    needed = needed_in_measure(line, original)
    if line.pack is PackPreference.PORTION or needed is None:
        return None
    fits = [fit for fit in (_fit(candidate, original, needed) for candidate in candidates) if fit is not None]
    if not fits:
        return None
    best = max(fits, key=lambda fit: (fit.saving, fit.option.pack_size, fit.option.product_id))
    return _suggestion(customer_id, request, line_index, original, best, needed)


def needed_in_measure(line: RequestLine, original: PackOption) -> Decimal | None:
    """The line's quantity in the original's measure; None when it is asked in the other measure."""
    if line.unit is original.measure:
        return line.quantity
    if line.unit is Unit.UNIT:
        return (line.quantity * original.pack_size).quantize(_QUANTITY, rounding=ROUND_CEILING)
    return None


def _fit(candidate: PackOption, original: PackOption, needed: Decimal) -> _Fit | None:
    if not candidate.same_product or candidate.measure is not original.measure:
        return None
    if candidate.pack_size <= original.pack_size or original.price_per_measure == 0:
        return None
    saving = 1 - candidate.price_per_measure / original.price_per_measure
    packs = candidate.packs_for(needed)
    if saving < LARGER_PACK_MIN_SAVING or packs * candidate.pack_size > needed * (1 + LARGER_PACK_MAX_OVER):
        return None
    if not confirmed_for(candidate.availability, packs):
        return None
    return _Fit(option=candidate, packs=packs, saving=saving)


def confirmed_for(availability: AvailabilityAssessment | None, packs: Decimal) -> bool:
    return (availability is not None and availability.state is AvailabilityState.CONFIRMED
            and availability.usable_amount is not None and availability.usable_amount >= packs)


def _suggestion(customer_id: str, request: PurchaseRequest, line_index: int, original: PackOption, fit: _Fit,
                needed: Decimal) -> Suggestion:
    option = fit.option
    before = round_money(original.packs_for(needed) * original.unit_net_price_eur)
    after = round_money(fit.packs * option.unit_net_price_eur)
    effect = SuggestionEffect(
        net_change_eur=after - before, measure=original.measure,
        unit_price_before_eur=original.price_per_measure.quantize(_UNIT_PRICE, rounding=ROUND_HALF_UP),
        unit_price_after_eur=option.price_per_measure.quantize(_UNIT_PRICE, rounding=ROUND_HALF_UP),
        saving_ratio=fit.saving.quantize(_RATIO, rounding=ROUND_HALF_UP),
    )
    evidence = SuggestionEvidence(
        source=EvidenceSource.CATALOG, synthetic=False, orders_considered=0, orders_matching=0,
        values=(original.price_per_measure, option.price_per_measure, fit.packs, fit.covered),
        thresholds=named(LARGER_PACK_MIN_SAVING=LARGER_PACK_MIN_SAVING, LARGER_PACK_MAX_OVER=LARGER_PACK_MAX_OVER),
    )
    return Suggestion(
        suggestion_id=suggestion_id_for(customer_id, SuggestionKind.LARGER_PACK, option.product_id),
        kind=SuggestionKind.LARGER_PACK, customer_id=customer_id, request_line_index=line_index,
        product_id=option.product_id, name=option.name, quantity=needed, unit=original.measure,
        replaces_product_id=original.product_id, sentence=_sentence(original, fit, needed, effect),
        evidence=evidence, effect=effect, availability=option.availability, stock_confirmed=True,
        accept_request=with_line_changed(request, line_index, product_ids=[option.product_id], quantity=needed,
                                         unit=original.measure),
    )


def _sentence(original: PackOption, fit: _Fit, needed: Decimal, effect: SuggestionEffect) -> str:
    """ "Because you buy Oatly iKaffe (468319) in 0.5 L packs, we suggest the same product in 1 L packs (464320):
    €1.78 a litre instead of €2.88. 30 packs cover your 30 L for €53.40, €33.00 less." A dearer total says by
    how much more the packs hold than asked."""
    option, unit = fit.option, original.measure
    change = effect.net_change_eur or Decimal(0)
    reason = (f"Because you buy {short_label(original.name, original.product_id)} in {amount(original.pack_size, unit)}"
              f" packs, we suggest the same product in {amount(option.pack_size, unit)} packs ({option.product_id}): "
              f"{per_measure(option.price_per_measure, unit)} instead of {euros(original.price_per_measure)}.")
    over = f", with {amount(fit.covered - needed, unit)} more than you asked" if fit.covered > needed else ""
    total = (f"{packs(fit.packs)} cover your {amount(needed, unit)} for "
             f"{euros(fit.packs * option.unit_net_price_eur)}, {more_or_less(change)}{over}.")
    return sentence(reason, total, stock_words(option))


def pack_label(pack: PackOption) -> str:
    """ "Oatly iKaffe 0.5 L (468319)": the short name, the pack's size and the id."""
    return f"{short_name(pack.name)} {amount(pack.pack_size, pack.measure)} ({pack.product_id})"


def stock_words(pack: PackOption) -> str:
    """ "234 L confirmed for Monday 16 November."; empty when nothing is confirmed."""
    availability = pack.availability
    if availability is None or availability.usable_amount is None:
        return ""
    stock = stock_amount(availability.usable_amount, pack.pack_size, pack.measure)
    return confirmed_words(stock, availability.available_date)
