"""What Valio Aimo's own suggestion can say a buyer gains, computed from the data in front of it.

The owner's rule (14 Nov 2026): Valio Aimo's own suggestion is shown only when it can state at least one concrete,
checkable benefit over the usual product it relates to; otherwise it stays silent. Four benefits, strongest first:

* `CHEAPER_SAME_FORMULA`: the same formula (`tta.offers.formula`) for at least `CHEAPER_MIN_SAVING` less a litre or
  kilogram (the cheaper kind's own threshold);
* `STOCK_WHERE_YOURS_IS_SHORT`: confirmed stock for the date asked, where the usual product has no confirmed stock
  for its usual quantity;
* `CLAIM_OR_LABEL_YOURS_LACKS`: a dietary claim or a certificate label that Valio Aimo's product data gives the
  candidate and not the usual product, named in words (a code with no words here is not said);
* `FEWER_PACKS`: fewer packs for the usual quantity, holding at most `LARGER_PACK_MAX_OVER` more than it.

The strongest is said; a claim or label is added when it is not the strongest. Each carries the sentence of how it
was computed, with its figures, for a page's "Why?". Nothing here judges allergens or whether the product may be
suggested: the guard does (`tta.suggestions.guard`). The word lists are ours.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from tta.contracts.common import RATIO_PLACES, UNIT_PRICE_PLACES, AvailabilityState, Unit, round_money
from tta.contracts.errors import InvalidRequest
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.product import Product
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.contracts.suggestion import Suggestion, SuggestionEffect
from tta.offers.candidates import Need, evaluate, need_for, price_problem, units_needed
from tta.offers.deps import Lookup
from tta.offers.formula import compare_formula
from tta.offers.substitutes import COVERED_BY
from tta.suggestions.thresholds import CHEAPER_MIN_SAVING, LARGER_PACK_MAX_OVER, named
from tta.suggestions.wording import (
    amount,
    confirmed_words,
    day,
    euros,
    more_or_less,
    number,
    packs,
    per_measure,
    percent,
    sentence,
    short_label,
    short_name,
    stock_amount,
    type_words,
)

MEASURES = (Unit.L, Unit.KG)
_UNIT_PRICE = Decimal(1).scaleb(-UNIT_PRICE_PLACES)
_RATIO = Decimal(1).scaleb(-RATIO_PLACES)
REASON = "Valio Aimo's reason, computed: "
# Certificate labels of the product file (AIMO/docs/SCHEMA-AND-CODES.md section 2.5) as a kitchen says them. Ours.
# OFFICIAL_ECO_LABEL_SUN is left out: the documentation does not say what it certifies.
LABEL_WORDS: Mapping[str, str] = {
    "GOODS_FROM_FINLAND_BLUE_SWAN": "Finnish origin label (blue swan)",
    "MADE_IN_FINLAND_FLAG_WITH_KEY": "Key Flag (made in Finland)",
    "PUHTAASTI_KOTIMAINEN": "Puhtaasti kotimainen label (purely Finnish)",
    "FINNISH_HEART_SYMBOL": "Finnish Heart Symbol",
    "EU_ORGANIC_FARMING": "EU organic label",
    "KRAV_MARK": "KRAV organic label",
    "SOIL_ASSOCIATION_ORGANIC_SYMBOL": "Soil Association organic label",
    "SVANEN": "Nordic Swan ecolabel",
    "EU_ECO_LABEL": "EU Ecolabel",
    "RAINFOREST_ALLIANCE": "Rainforest Alliance label",
    "FAIR_TRADE_MARK": "Fairtrade mark",
    "UTZ_CERTIFIED": "UTZ label",
    "MARINE_STEWARDSHIP_COUNCIL_LABEL": "MSC label",
    "AQUACULTURE_STEWARDSHIP_COUNCIL": "ASC label",
    "DOLPHIN_SAFE": "Dolphin Safe label",
}
# The dietary claims a kitchen orders by. VEGETARIAN is left out: a dairy product that does not declare it is no
# less vegetarian (decision C2 of the run), so its absence says nothing.
CLAIM_WORDS: Mapping[str, str] = {
    "FREE_FROM_LACTOSE": "lactose-free",
    "LOW_LACTOSE": "low-lactose",
    "FREE_FROM_GLUTEN": "gluten-free",
    "FREE_FROM_EGGS": "egg-free",
    "FREE_FROM_SOY": "soy-free",
    "VEGAN": "vegan",
}


class BenefitKind(StrEnum):
    """What Valio Aimo's own suggestion gains over the usual product, strongest first."""

    CHEAPER_SAME_FORMULA = "CHEAPER_SAME_FORMULA"
    STOCK_WHERE_YOURS_IS_SHORT = "STOCK_WHERE_YOURS_IS_SHORT"
    CLAIM_OR_LABEL_YOURS_LACKS = "CLAIM_OR_LABEL_YOURS_LACKS"
    FEWER_PACKS = "FEWER_PACKS"


STRENGTH = tuple(BenefitKind)


@dataclass(frozen=True)
class Benefit:
    """One benefit: the clause the sentence says, the same as a second benefit, how it was computed."""

    kind: BenefitKind
    clause: str  # "with the Finnish origin label (blue swan) yours does not have"
    also: str  # the clause as a second benefit: "it also has the Finnish origin label (blue swan) yours does not have"
    why: str  # "Valio Aimo's reason, computed: ..." with the figures
    values: tuple[Decimal, ...] = ()
    thresholds: Mapping[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class Measured:
    """One product at a quantity, as an offer line reads it: packs, price before tax, confirmed stock."""

    product: Product
    quantity: Decimal
    unit: Unit
    state: AvailabilityState
    units: Decimal | None = None  # packs for the quantity; None: the pack size is not known
    unit_price: Decimal | None = None  # per pack; None: no price an order can rest on
    usable: Decimal | None = None  # packs confirmed
    per_unit: Decimal | None = None  # litres or kg per pack in `unit` (1 for UNIT)
    available_date: date | None = None
    measure: Unit | None = None  # L or KG, for the price a litre or kilogram
    pack_in_measure: Decimal | None = None

    @property
    def label(self) -> str:
        return short_label(self.product.display_name, self.product.id)

    @property
    def sized_label(self) -> str:
        """ "Oatly iKaffe 0.5 L (468319)": with the pack, for two products whose packs differ."""
        if self.per_unit is None or self.unit not in MEASURES:
            return self.label
        return f"{short_name(self.product.display_name)} {amount(self.per_unit, self.unit)} ({self.product.id})"

    @property
    def total(self) -> Decimal | None:
        return None if self.units is None or self.unit_price is None else self.units * self.unit_price

    @property
    def per_measure(self) -> Decimal | None:
        if self.unit_price is None or not self.pack_in_measure:
            return None
        return self.unit_price / self.pack_in_measure

    @property
    def covers(self) -> bool:
        """Confirmed stock covers the quantity."""
        return (self.state is AvailabilityState.CONFIRMED and self.units is not None and self.usable is not None
                and self.usable >= self.units)

    @property
    def stock(self) -> str:
        return stock_amount(self.usable or Decimal(0), self.per_unit, self.unit)


def measured(product: Product, quantity: Decimal, unit: Unit, request: PurchaseRequest, profile: BuyerProfile,
             lookup: Lookup, catalog: Catalog) -> Measured | None:
    """The product at the quantity; None when the buyer's allergen exclusions cannot be read (the guard says so)."""
    try:
        candidate = evaluate(product, _need(product, quantity, unit, request, profile), lookup, catalog)
    except InvalidRequest:
        return None
    assessment = candidate.assessment
    priced = price_problem(candidate.price, lookup.now) is None
    measure, size = _measure(product, request, profile, lookup, catalog, unit, candidate.per_unit)
    return Measured(
        product=product, quantity=quantity, unit=unit, state=assessment.state,
        units=units_needed(candidate, quantity) if candidate.per_unit else None,
        unit_price=candidate.unit_price if priced else None, usable=assessment.usable_amount,
        per_unit=candidate.per_unit, available_date=assessment.available_date, measure=measure, pack_in_measure=size,
    )


def _need(product: Product, quantity: Decimal, unit: Unit, request: PurchaseRequest, profile: BuyerProfile) -> Need:
    line = RequestLine(text=product.display_name, product_ids=(product.id,), quantity=quantity, unit=unit)
    return need_for(len(request.lines), line, request, profile)


def _measure(product: Product, request: PurchaseRequest, profile: BuyerProfile, lookup: Lookup, catalog: Catalog,
             unit: Unit, per_unit: Decimal | None) -> tuple[Unit | None, Decimal | None]:
    """Litres or kilograms in one pack: the line's own measure, else the first the catalog gives."""
    if unit in MEASURES:
        return (unit, per_unit) if per_unit else (None, None)
    for measure in MEASURES:
        size = evaluate(product, _need(product, Decimal(1), measure, request, profile), lookup, catalog).per_unit
        if size:
            return measure, size
    return None, None


def benefits(usual: Measured, candidate: Measured, when: date | None, quantity_words: str) -> tuple[Benefit, ...]:
    """The benefits the candidate can state over the usual product, strongest first; empty: none.
    `quantity_words`: "your usual 10 L" or "your 10 L"."""
    found = (
        _cheaper(usual, candidate),
        _stock(usual, candidate, when),
        _claim_or_label(usual.product, candidate.product),
        _fewer_packs(usual, candidate, quantity_words),
    )
    return tuple(each for each in found if each is not None)


def _cheaper(usual: Measured, candidate: Measured) -> Benefit | None:
    before, after = usual.per_measure, candidate.per_measure
    if before is None or after is None or usual.measure is not candidate.measure or usual.measure is None:
        return None
    saving = 1 - after / before
    if saving < CHEAPER_MIN_SAVING or not compare_formula(usual.product, candidate.product).keeps_formula:
        return None
    measure = usual.measure
    said = f"the same formula, {per_measure(after, measure)} instead of {euros(before)}"
    why = (f"{REASON}the same formula as {usual.label} within our tolerance, and {per_measure(after, measure)} "
           f"against {per_measure(before, measure)}: {percent(saving).lstrip('+')} less (our threshold: "
           f"{percent(CHEAPER_MIN_SAVING).lstrip('+')}).")
    return Benefit(kind=BenefitKind.CHEAPER_SAME_FORMULA, clause=f"with {said}", also=f"it also has {said}",
                   why=why, values=(before, after, saving), thresholds=named(CHEAPER_MIN_SAVING=CHEAPER_MIN_SAVING))


def _stock(usual: Measured, candidate: Measured, when: date | None) -> Benefit | None:
    short = usual.state is not AvailabilityState.CONFIRMED or (
        usual.units is not None and (usual.usable or Decimal(0)) < usual.units)
    if not short or not candidate.covers:
        return None
    on = f" for {day(when)}" if when is not None else ""
    has = usual.usable if usual.state is AvailabilityState.CONFIRMED and usual.usable else None
    where = f"where yours has only {usual.stock}" if has else "where yours has none confirmed"
    said = f"{candidate.stock} confirmed{on} {where}"
    why = (f"{REASON}{amount(candidate.quantity, candidate.unit)} needs {_packs(usual.units)} of {usual.label}, "
           f"which has {_confirmed(usual)}{on}; {candidate.label} has {packs(candidate.usable or Decimal(0))} "
           f"confirmed and needs {_packs(candidate.units)}.")
    values = (usual.usable if has else Decimal(0), candidate.usable or Decimal(0), usual.units or Decimal(0),
              candidate.units or Decimal(0))
    return Benefit(kind=BenefitKind.STOCK_WHERE_YOURS_IS_SHORT, clause=f"with {said}", also=f"it also has {said}",
                   why=why, values=values)


def _packs(count: Decimal | None) -> str:
    return packs(count) if count is not None else "an unknown number of packs"


def _confirmed(usual: Measured) -> str:
    if usual.state is AvailabilityState.CONFIRMED:
        return f"{packs(usual.usable or Decimal(0))} confirmed"
    return f"no confirmed stock (Valio Aimo's state {usual.state.value})"


def _claim_or_label(usual: Product, candidate: Product) -> Benefit | None:
    """A dietary claim first, then a certificate label: the first the candidate carries and the usual does not."""
    held = frozenset(usual.nutritional_claims)
    claims = [claim for claim in candidate.nutritional_claims
              if claim in CLAIM_WORDS and claim not in held and not COVERED_BY.get(claim, frozenset()) & held]
    labels = [label for label in candidate.labels if label in LABEL_WORDS and label not in usual.labels]
    if claims:
        words, code = CLAIM_WORDS[claims[0]], claims[0]
        clause, also = f"marked {words} where yours is not", f"it is also marked {words} where yours is not"
    elif labels:
        words, code = LABEL_WORDS[labels[0]], labels[0]
        clause, also = f"with the {words} yours does not have", f"it also has the {words} yours does not have"
    else:
        return None
    why = (f"{REASON}Valio Aimo's product data gives {candidate.id} the {'claim' if claims else 'label'} {code} "
           f"and does not give it to {usual.id}.")
    return Benefit(kind=BenefitKind.CLAIM_OR_LABEL_YOURS_LACKS, clause=clause, also=also, why=why)


def _fewer_packs(usual: Measured, candidate: Measured, quantity_words: str) -> Benefit | None:
    before, after, size = usual.units, candidate.units, candidate.per_unit
    if usual.unit not in MEASURES or before is None or after is None or size is None:
        return None
    covered = after * size
    if after >= before or covered > candidate.quantity * (1 + LARGER_PACK_MAX_OVER):
        return None
    pack = amount(size, candidate.unit)
    said = f"in {pack} packs: {packs(after)} for {quantity_words} instead of {number(before)}"
    why = (f"{REASON}{amount(candidate.quantity, candidate.unit)} is {packs(after)} of {pack} of "
           f"{candidate.label} against {packs(before)} of {usual.label}, holding {amount(covered, usual.unit)} "
           f"(our limit: {percent(LARGER_PACK_MAX_OVER).lstrip('+')} more than asked).")
    return Benefit(kind=BenefitKind.FEWER_PACKS, clause=said, also=f"it also comes {said}", why=why,
                   values=(before, after, covered), thresholds=named(LARGER_PACK_MAX_OVER=LARGER_PACK_MAX_OVER))


# --- the sentence -------------------------------------------------------------------------------------------------


def strength(found: Sequence[Benefit]) -> tuple[int, Decimal]:
    """How strong the strongest benefit is, strongest first: its rank, then for a lower price the larger saving.
    Past the last for none."""
    if not found:
        return len(STRENGTH), Decimal(0)
    first = found[0]
    saving = first.values[-1] if first.kind is BenefitKind.CHEAPER_SAME_FORMULA else Decimal(0)
    return STRENGTH.index(first.kind), -saving


def stated_benefits(suggestion: Suggestion, anchor_id: str, anchor_type: str, quantity_words: str, *,
                    request: PurchaseRequest, profile: BuyerProfile, lookup: Lookup, catalog: Catalog,
                    closing: str) -> tuple[Suggestion, tuple[Benefit, ...]]:
    """The suggestion worded with its strongest benefit, and every benefit found; the suggestion as it came and
    no benefit when there is none. `closing`: the last sentence, where the suggestion comes from."""
    usual_product, product = catalog.get_product(anchor_id), catalog.get_product(suggestion.product_id)
    if usual_product is None or product is None:
        return suggestion, ()
    usual = measured(usual_product, suggestion.quantity, suggestion.unit, request, profile, lookup, catalog)
    candidate = measured(product, suggestion.quantity, suggestion.unit, request, profile, lookup, catalog)
    if usual is None or candidate is None:
        return suggestion, ()
    when = request.needed_by or candidate.available_date
    found = benefits(usual, candidate, when, quantity_words)
    if not found:
        return suggestion, ()
    return _worded(suggestion, usual, candidate, found, type_words(anchor_type), quantity_words, when,
                   closing), found


def _worded(suggestion: Suggestion, usual: Measured, candidate: Measured, found: Sequence[Benefit], kind: str,
            quantity_words: str, when: date | None, closing: str) -> Suggestion:
    """ "Because you buy Arla Pro Cooking cream 10% (463797), Valio Aimo suggests ...: the same kind of cream, with
    the Finnish origin label (blue swan) yours does not have. For your usual 10 L: €35.00, €1.90 more. 114 L
    confirmed for Monday 16 November. Suggested by Valio Aimo, not from your orders." """
    primary = found[0]
    second = next((each for each in found[1:] if each.kind is BenefitKind.CLAIM_OR_LABEL_YOURS_LACKS), None)
    also = f"; {second.also}" if second is not None else ""
    sized = usual.unit in MEASURES and None not in (usual.per_unit, candidate.per_unit) and (
        usual.per_unit != candidate.per_unit)
    yours, theirs = (usual.sized_label, candidate.sized_label) if sized else (usual.label, candidate.label)
    reason = f"Because you buy {yours}, Valio Aimo suggests {theirs}: the same kind of {kind}, {primary.clause}{also}."
    total, before = _money(candidate.total), _money(usual.total)
    price = "" if total is None else f"For {quantity_words}: {euros(total)}" + (
        f", {more_or_less(total - before)}." if before is not None else ".")
    stock = "" if primary.kind is BenefitKind.STOCK_WHERE_YOURS_IS_SHORT else confirmed_words(candidate.stock, when)
    chosen = (primary, *((second,) if second is not None else ()))
    evidence = suggestion.evidence.model_copy(update={
        "values": (suggestion.quantity, *(value for each in chosen for value in each.values)),
        "thresholds": {name: value for each in chosen for name, value in each.thresholds.items()},
    })
    return suggestion.model_copy(update={
        "sentence": sentence(reason, price, stock, closing), "evidence": evidence,
        "effect": _effect(suggestion, usual, candidate, primary, total, before),
        "checks": (*suggestion.checks, *(each.why for each in chosen)),
    })


def _money(value: Decimal | None) -> Decimal | None:
    return None if value is None else round_money(value)


def _effect(suggestion: Suggestion, usual: Measured, candidate: Measured, primary: Benefit, total: Decimal | None,
            before: Decimal | None) -> SuggestionEffect | None:
    """What accepting changes in the order: the difference when it takes the place of a line of the request, its
    whole cost when it adds one; the two prices a litre or kilogram when both are known."""
    if total is None:
        return None  # the guard then adds the cost it reads
    replaces_a_line = suggestion.request_line_index is not None
    change = total - before if replaces_a_line and before is not None else total
    prices: dict[str, object] = {}
    if usual.per_measure is not None and candidate.per_measure is not None and usual.measure is candidate.measure:
        prices = {"measure": usual.measure, "unit_price_before_eur": _unit_price(usual.per_measure),
                  "unit_price_after_eur": _unit_price(candidate.per_measure)}
        if primary.kind is BenefitKind.CHEAPER_SAME_FORMULA:
            ratio = 1 - candidate.per_measure / usual.per_measure
            prices["saving_ratio"] = ratio.quantize(_RATIO, rounding=ROUND_HALF_UP)
    return SuggestionEffect.model_validate({"net_change_eur": change, **prices})


def _unit_price(value: Decimal) -> Decimal:
    return value.quantize(_UNIT_PRICE, rounding=ROUND_HALF_UP)
