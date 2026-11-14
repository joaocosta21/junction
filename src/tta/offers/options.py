"""From drafted lines to finished options: totals, coverage, checks, rank and the policy verdict (SPEC section 5)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from tta.availability.wording import format_amount
from tta.contracts.common import AvailabilityState, CheckResult, OptionKind, Preference
from tta.contracts.offer import (
    ConstraintCheck,
    Coverage,
    OfferLine,
    OfferOption,
    OptionComparison,
    SubstituteInfo,
    Totals,
)
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.ports import Catalog
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers.candidates import Need
from tta.offers.checks import constraint_checks
from tta.offers.comparison import compare, gain
from tta.offers.deps import OfferDeps, spend_parts, standing_history_of
from tta.offers.lines import coverage_of, lowest_fill_ratio, totals_of, valid_until_of
from tta.offers.mixed import mixed_formulas
from tta.offers.preference import (
    KEY_WORDS,
    MAX_PREFERENCE_PREMIUM,
    missing_sentence,
    premium,
    share,
    title_suffix,
)
from tta.offers.safety import has_doubt, open_allergens, who_decides
from tta.offers.variants import regular_words, variant_word
from tta.offers.wording import counted, eur, line_label, line_words, measured, plain_name

MAX_OPTIONS = 3
# Under a preference other than price the cheapest confirmed option is a fourth one, so the trade-off is on the
# table (task SUST-1).
MAX_OPTIONS_WITH_CHEAPEST = 4
# A product asked for comes before a stand-in for it. Only the net total comes after this in the ranking.
KIND_ORDER = {
    OptionKind.BEST_CONFIRMED: 0, OptionKind.CHEAPEST_CONFIRMED: 1, OptionKind.ALTERNATIVE_UNCONFIRMED: 2,
    OptionKind.SUBSTITUTE: 3,
}
TITLES = {
    OptionKind.BEST_CONFIRMED: "Best confirmed option",
    OptionKind.CHEAPEST_CONFIRMED: "Cheapest confirmed option",
    OptionKind.ALTERNATIVE_UNCONFIRMED: "Alternative: quantity not confirmed",
    OptionKind.SUBSTITUTE: "With a substitute for a product that cannot be supplied in full",
}
# An alternative says what is not confirmed about it: the quantity, the allergen statement, or both (review P4,
# item M1). Both carry the kind ALTERNATIVE_UNCONFIRMED: `OptionKind` has no kind of its own for the second.
ALTERNATIVE = "Alternative: "
QUANTITY_NOT_CONFIRMED = "quantity not confirmed"
ALLERGEN_NOT_RULED_OUT = "allergen not ruled out"
# A substitute that does not keep the formula on a line where the formula matters: the request says so (P10
# item F5) or the buyer profile does (decision B35). `said` is `Need.formula_said`.
FORMULA_NOT_KEPT = "a substitute that does not keep the formula"
FORMULA_NOTE = (
    " {said}, and no substitute that keeps it can be ordered: this one does not keep it, so a person decides."
)
# The option ranked by a preference, when its premium put it after the cheapest one (review A2b, finding H2).
DEMOTED_TITLE = "Confirmed option"
PARTIAL_SUFFIX = " (partial fill)"
# Valio Aimo, 14 Nov 2026 (answer Q16): "what is actually delivered. like in a normal store". The weight
# delivered can be under or over the weight ordered, so the total is an estimate and never a ceiling.
ESTIMATE_NOTE = " The total is an estimate: a product is sold by weight, and Valio Aimo invoices the weight delivered."
ABOUT = "about "
DEPOSIT_NOTE = " Deposits are not included in the total."


@dataclass(frozen=True)
class Draft:
    """The lines of one option, before anything is summed or judged."""

    kind: OptionKind
    lines: tuple[OfferLine, ...]
    said: str = ""  # a sentence for the summary that only the planning knows: what the stand-in search found


@dataclass(frozen=True)
class _Assembled:
    draft: Draft
    totals: Totals
    coverage: tuple[Coverage, ...]
    checks: tuple[ConstraintCheck, ...]
    asked: tuple[RequestLine, ...]
    comparison: OptionComparison | None = None  # set by `_assemble`; worked out from the lines when not
    extra: str = ""  # sentences of the summary that depend on the other options: the preference's trade-off
    named: str = ""  # sentences that name a variant nobody asked for (`tta.offers.variants`)
    net_above_cheapest: Decimal | None = None  # on the preferred option, when a cheaper confirmed one is offered
    demoted: bool = False  # the preferred option costs too much over the cheapest one to come first
    promoted: bool = False  # the cheapest confirmed option, when the preferred one is demoted
    # Per request line where the formula matters, who says so (`Need.formula_said`).
    formula_said: Mapping[int, str] = field(default_factory=dict)

    @property
    def compared(self) -> OptionComparison:
        return self.comparison or compare(self.draft.lines)

    @property
    def quantity_unconfirmed(self) -> bool:
        return any(line.availability.state is not AvailabilityState.CONFIRMED for line in self.draft.lines)

    @property
    def allergen_doubt(self) -> bool:
        return any(has_doubt(line) for line in self.draft.lines)

    @property
    def formula_changed(self) -> bool:
        """A line where the formula matters holds a substitute that does not keep it, or one that cannot be
        compared: not known is never read as the same formula."""
        return bool(self.formula_changed_said)

    @property
    def formula_changed_said(self) -> str:
        """Who says the formula matters on the first line whose substitute does not keep it; empty when none."""
        return next(
            (
                self.formula_said[line.request_line_index] for line in self.draft.lines
                if line.request_line_index in self.formula_said and _changes_formula(line)
            ),
            "",
        )


def finish_options(
    drafts: Sequence[Draft],
    request: PurchaseRequest,
    needs: Sequence[Need],
    profile: BuyerProfile,
    deps: OfferDeps,
    now: datetime,
    *,
    headline: str = "",
) -> tuple[OfferOption, ...]:
    """At most three options in rank order (four with the cheapest confirmed one), each with its totals, checks,
    comparison and the policy verdict. `headline` is added to the summary of the first option: what the
    request's product type left out."""
    assembled = _cheaper_only([_assemble(draft, request, needs, deps) for draft in drafts if draft.lines])
    priced = _traded_off(assembled, request.prefer)
    ranked = _safe_first(sorted(priced, key=_rank_key)[: _cap(priced)])
    if ranked and headline:
        ranked = [replace(ranked[0], named=f"{ranked[0].named} {headline}"), *ranked[1:]]
    # The day's committed spend must reach the policy, or every option reads APPROVAL for a missing fact.
    committed, waiting = spend_parts(deps.day_spend(profile.profile_id))
    context = PolicyContext(
        now=now, day_committed_net_eur=committed, day_waiting_net_eur=waiting,
        standing_history=standing_history_of(deps, profile.profile_id, request.standing_order_id),  # P-08
    )
    options = (_option(rank, each, request.prefer) for rank, each in enumerate(ranked, start=1))
    return tuple(
        option.model_copy(update={"decision": deps.policy.evaluate(option, profile, context)}) for option in options
    )


def _assemble(draft: Draft, request: PurchaseRequest, needs: Sequence[Need], deps: OfferDeps) -> _Assembled:
    coverage = coverage_of(request.lines, draft.lines)
    checks = constraint_checks(request, needs, draft.lines, coverage, deps.catalog)
    return _Assembled(
        draft=draft, totals=totals_of(draft.lines), coverage=coverage, checks=checks, asked=tuple(request.lines),
        comparison=compare(draft.lines),
        named=_variants_named(draft.lines, request.lines, coverage, deps.catalog)
        + mixed_formulas(draft.lines, deps.catalog),
        extra=draft.said,
        formula_said={need.index: need.formula_said for need in needs if need.formula_matters},
    )


def _changes_formula(line: OfferLine) -> bool:
    """A substitute that does not keep the formula, or carries no comparison. Asked only where it matters."""
    if line.substitute is None:
        return False
    return line.substitute.formula is None or not line.substitute.formula.keeps_formula


def _variants_named(
    lines: Sequence[OfferLine], asked: Sequence[RequestLine], coverage: Sequence[Coverage], catalog: Catalog
) -> str:
    """` X (id) is lactose-free milk, offered as a named alternative to regular milk: regular milk covers 200 L
    of the 300 L asked for in this option.` One sentence per request line that a variant nobody asked for
    fills; nothing when there is none (`tta.offers.variants`)."""
    sentences = []
    for entry in coverage:
        request_line = asked[entry.request_line_index]
        own = [line for line in lines if line.request_line_index == entry.request_line_index]
        words = {line.product_id: _variant_of(line, request_line, catalog) for line in own}
        variants = [line for line in own if words[line.product_id]]
        if not variants:
            continue
        regular = sum((line.covers for line in own if not words[line.product_id]), Decimal(0))
        kinds = " or ".join(dict.fromkeys(words[line.product_id] or "" for line in variants))
        verb = "is" if len(variants) == 1 else "are"
        plain = regular_words(request_line)
        sentences.append(
            f" {_names(variants)} {verb} {kinds} {line_words(request_line)}, offered as a named alternative to "
            f"{plain}: {plain} covers {measured(regular, entry.unit)} of the {measured(entry.requested, entry.unit)} "
            "asked for in this option."
        )
    return "".join(sentences)


def _variant_of(line: OfferLine, asked: RequestLine, catalog: Catalog) -> str | None:
    product = catalog.get_product(line.product_id)
    return variant_word(asked, product.nutritional_claims) if product is not None else None


def _of_kind(assembled: Sequence[_Assembled], kind: OptionKind) -> _Assembled | None:
    return next((each for each in assembled if each.draft.kind is kind), None)


def _cheaper_only(assembled: list[_Assembled]) -> list[_Assembled]:
    """The cheapest confirmed option stays only when it costs less than the preferred one: otherwise there is no
    trade-off to show."""
    best = _of_kind(assembled, OptionKind.BEST_CONFIRMED)
    preferred = best.totals.net if best is not None else None
    return [
        each for each in assembled
        if each.draft.kind is not OptionKind.CHEAPEST_CONFIRMED
        or (preferred is not None and each.totals.net < preferred)
    ]


def _cap(assembled: Sequence[_Assembled]) -> int:
    has_cheapest = _of_kind(assembled, OptionKind.CHEAPEST_CONFIRMED) is not None
    return MAX_OPTIONS_WITH_CHEAPEST if has_cheapest else MAX_OPTIONS


def _traded_off(assembled: list[_Assembled], prefer: Preference) -> list[_Assembled]:
    """The preferred option says which lines had no value for the key and what it costs over the cheapest one,
    as an amount and as a share; the cheapest one says how much less it costs.

    A preference has a price (review A2b, finding H2): above `MAX_PREFERENCE_PREMIUM` the preferred option is
    demoted, so the cheapest confirmed option is the suggestion and the preferred one comes right after it.
    """
    best, cheapest = (
        _of_kind(assembled, OptionKind.BEST_CONFIRMED), _of_kind(assembled, OptionKind.CHEAPEST_CONFIRMED)
    )
    if best is None or prefer is Preference.PRICE:
        return assembled
    if cheapest is None:
        changed = {id(best): replace(best, extra=missing_sentence(best.draft.lines, prefer))}
        return [changed.get(id(each), each) for each in assembled]
    more = best.totals.net - cheapest.totals.net
    ratio = premium(best.totals.net, cheapest.totals.net)
    by_share = f", a premium of {share(ratio)}" if ratio is not None else ""
    demoted = ratio is not None and ratio > MAX_PREFERENCE_PREMIUM
    what = gain(prefer, best.compared, cheapest.compared) or f"products ranked by {KEY_WORDS[prefer]} first"
    key = KEY_WORDS[prefer]
    paid = f" {eur(more)} more than the cheapest confirmed option, for {what}{by_share}."
    saved = f" {eur(more)} less than the option ranked by {key}."
    if demoted:
        saved = (
            f" Suggested first: the option ranked by {key} costs {eur(more)} more{by_share}, above the "
            f"{share(MAX_PREFERENCE_PREMIUM)} a preference may add before the cheapest option comes first (our "
            "threshold)."
        )
    changed = {
        id(best): replace(
            best, extra=missing_sentence(best.draft.lines, prefer) + paid, net_above_cheapest=more, demoted=demoted
        ),
        id(cheapest): replace(cheapest, extra=saved, promoted=demoted),
    }
    return [changed.get(id(each), each) for each in assembled]


def _safe_first(ranked: list[_Assembled]) -> list[_Assembled]:
    """The first option says that its products rule out every excluded allergen, and what that costs over the
    alternative whose data does not (review P4, item M1)."""
    doubtful = next((each for each in ranked if each.allergen_doubt and not each.quantity_unconfirmed), None)
    if not ranked or doubtful is None or ranked[0].allergen_doubt:
        return ranked
    first = ranked[0]
    saving = first.totals.net - doubtful.totals.net
    other = f"costs {eur(saving)} less" if saving > 0 else "is listed after it"
    said = f" Its data rules out every excluded allergen; the alternative whose data does not {other}."
    return [replace(first, extra=first.extra + said), *ranked[1:]]


def _rank_key(assembled: _Assembled) -> tuple[bool, bool, bool, int, int, int, Decimal]:
    """Allergen safety, then constraint fit, then verification status, then the kind, then the net total (SPEC
    section 5, step 3).

    An option that holds a product whose data does not rule out an excluded allergen comes after every option
    that holds none: the safe product wins, whatever it costs (review P4, item M1).

    The buyer's preference ranks the products inside BEST_CONFIRMED, and BEST_CONFIRMED comes before
    CHEAPEST_CONFIRMED by kind: between two options that fit alike the preferred one is first. A preference never
    outranks constraint fit or verification status (`Preference`: "once every constraint is met").

    An option that holds an unconfirmed quantity is never first: a quantity that is not confirmed is
    never the suggestion (SPEC section 4), so such an option comes after every option that holds none,
    whatever else it fits and however little it costs. The price is the last key and cannot change that.

    Where the formula matters (the request line or the buyer profile says so), an option whose substitute does
    not keep it comes after every
    option that changes no formula (P10 item F5): it is a labelled alternative, never the suggestion while
    another option exists. This is the one case where an option with an unconfirmed quantity can come first:
    the product asked for, quantity not confirmed, before a confirmed stand-in of another formula. Both go to a
    person (rules F-01 and F-11).
    """
    not_met = sum(check.result is CheckResult.NOT_MET for check in assembled.checks)
    unverified = sum(check.result is CheckResult.UNVERIFIED for check in assembled.checks)
    return (
        assembled.allergen_doubt, assembled.formula_changed, assembled.quantity_unconfirmed, not_met, unverified,
        _kind_order(assembled), assembled.totals.net,
    )


def _kind_order(assembled: _Assembled) -> int:
    """The place of the option's kind. A demoted preferred option comes right after the cheapest confirmed one."""
    if assembled.demoted:
        return KIND_ORDER[OptionKind.CHEAPEST_CONFIRMED]
    if assembled.promoted:
        return KIND_ORDER[OptionKind.BEST_CONFIRMED]
    return KIND_ORDER[assembled.draft.kind]


def _title(assembled: _Assembled, prefer: Preference, fill_ratio: Decimal) -> str:
    kind = assembled.draft.kind
    title = TITLES[kind]
    if kind is OptionKind.BEST_CONFIRMED:
        ranked_by = title_suffix(prefer)
        title = DEMOTED_TITLE + ranked_by.replace(",", "", 1) if assembled.demoted else title + ranked_by
    elif kind is OptionKind.ALTERNATIVE_UNCONFIRMED:
        doubts = [
            *([QUANTITY_NOT_CONFIRMED] if assembled.quantity_unconfirmed else []),
            *([ALLERGEN_NOT_RULED_OUT] if assembled.allergen_doubt else []),
            *([FORMULA_NOT_KEPT] if assembled.formula_changed else []),
        ]
        title = ALTERNATIVE + ", ".join(doubts or [QUANTITY_NOT_CONFIRMED])
    elif assembled.formula_changed:
        title = ALTERNATIVE + FORMULA_NOT_KEPT
    return title + (PARTIAL_SUFFIX if fill_ratio < 1 else "")


def _option(rank: int, assembled: _Assembled, prefer: Preference) -> OfferOption:
    draft = assembled.draft
    fill_ratio = lowest_fill_ratio(assembled.coverage)
    return OfferOption(
        option_id=f"opt_{rank}",
        kind=draft.kind,
        rank=rank,
        title=_title(assembled, prefer, fill_ratio),
        summary=_summary(assembled),
        lines=draft.lines,
        totals=assembled.totals,
        coverage=assembled.coverage,
        fill_ratio=fill_ratio,
        valid_until=valid_until_of(draft.lines),
        constraint_checks=assembled.checks,
        comparison=assembled.compared,
        net_above_cheapest=assembled.net_above_cheapest,
    )


def _summary(assembled: _Assembled) -> str:
    lines, totals = assembled.draft.lines, assembled.totals
    money = f"{ABOUT if totals.is_ceiling else ''}{eur(totals.net)} before tax"
    covered = _covered_phrase(assembled.coverage)
    if assembled.draft.kind in (OptionKind.BEST_CONFIRMED, OptionKind.CHEAPEST_CONFIRMED):
        verb = "covers" if len(lines) == 1 else "cover"
        text = f"{counted(len(lines), 'confirmed product')} {verb} {covered}, for {money}."
        if assembled.draft.kind is OptionKind.CHEAPEST_CONFIRMED:
            text = f"The cheapest confirmed option: {text}"
    elif assembled.draft.kind is OptionKind.ALTERNATIVE_UNCONFIRMED:
        text = _alternative_summary(assembled, covered, money)
    else:
        stand_ins = [line for line in lines if line.substitute is not None]
        originals = ", ".join(dict.fromkeys(_original_name(line.substitute) for line in stand_ins if line.substitute))
        kept = len(lines) > len(stand_ins)
        stands_in = "fills what is missing of" if kept else "in place of"
        text = f"{_names(stand_ins)} {stands_in} {originals}: {covered}, for {money}."
    if assembled.formula_changed:
        said = assembled.formula_changed_said
        text += FORMULA_NOTE.format(said=said[0].upper() + said[1:])
    notes = (ESTIMATE_NOTE if totals.is_ceiling else "") + (DEPOSIT_NOTE if totals.excludes_deposits else "")
    return text + assembled.extra + _per_line(assembled.coverage, assembled.asked) + notes + assembled.named


def _alternative_summary(assembled: _Assembled, covered: str, money: str) -> str:
    """What is not confirmed about the alternative, and who decides: the quantity, the allergen statement, or
    both."""
    lines = assembled.draft.lines
    open_lines = [
        line for line in lines if line.availability.state is not AvailabilityState.CONFIRMED or has_doubt(line)
    ]
    stand_ins = [line.substitute for line in open_lines if line.substitute is not None]
    originals = ", ".join(dict.fromkeys(_original_name(each) for each in stand_ins))
    in_place = f", a substitute for {originals}," if stand_ins else ""
    text = f"{_names(open_lines)}{in_place} for {covered}, {money}."
    if assembled.quantity_unconfirmed or not assembled.allergen_doubt:
        text += " Valio does not confirm the quantity in stock, so a human must approve this option."
    if assembled.allergen_doubt:
        allergens = open_allergens(line.allergen_check for line in lines)
        decides = who_decides(line.allergen_check for line in lines)
        text += f" The product data does not rule out {allergens}, so {decides}."
    return text


def _covered_phrase(coverage: Sequence[Coverage]) -> str:
    if len(coverage) == 1:
        only = coverage[0]
        asked = f"the {measured(only.requested, only.unit)} asked for"
        if only.missing <= 0:
            return asked
        return f"{measured(only.covered, only.unit)} of {asked} ({measured(only.missing, only.unit)} missing)"
    full = sum(entry.missing <= 0 for entry in coverage)
    if full == len(coverage):
        return f"all {len(coverage)} request lines in full"
    return f"{full or 'none'} of the {len(coverage)} request lines in full"


def _per_line(coverage: Sequence[Coverage], asked: Sequence[RequestLine]) -> str:
    """What each request line gets, the least covered first, when an option of several lines falls short on
    one. Rule P-03 compares the lowest line's ratio and names the lines the same way (`tta.policy.coverage`)."""
    if len(coverage) <= 1 or all(entry.missing <= 0 for entry in coverage):
        return ""
    least_first = sorted(coverage, key=lambda entry: (entry.fill_ratio, entry.request_line_index))
    return f" Covered: {'; '.join(_line_covered(entry, asked[entry.request_line_index]) for entry in least_first)}."


def _line_covered(entry: Coverage, asked: RequestLine) -> str:
    """`0 of 10 kg of butter, request line 2`."""
    words = line_words(asked)
    named = f" of {words}" if words else ""
    label = line_label(entry.request_line_index).lower()
    return f"{format_amount(entry.covered)} of {measured(entry.requested, entry.unit)}{named}, {label}"


def _names(lines: Iterable[OfferLine]) -> str:
    return ", ".join(dict.fromkeys(f"{plain_name(line.name)} ({line.product_id})" for line in lines))


def _original_name(substitute: SubstituteInfo) -> str:
    if not substitute.original_name:
        return substitute.original_id
    return f"{plain_name(substitute.original_name)} ({substitute.original_id})"
