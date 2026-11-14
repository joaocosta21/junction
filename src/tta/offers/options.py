"""From drafted lines to finished options: totals, coverage, checks, rank and the policy verdict (SPEC section 5)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
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
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers.candidates import Need
from tta.offers.checks import constraint_checks
from tta.offers.comparison import compare, gain
from tta.offers.deps import OfferDeps, standing_history_of
from tta.offers.lines import coverage_of, lowest_fill_ratio, totals_of, valid_until_of
from tta.offers.preference import KEY_WORDS, missing_sentence, title_suffix
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
PARTIAL_SUFFIX = " (partial fill)"
CEILING_NOTE = " The total is a ceiling: a product is sold by weight, so the invoice can be lower, never higher."
DEPOSIT_NOTE = " Deposits are not included in the total."


@dataclass(frozen=True)
class Draft:
    """The lines of one option, before anything is summed or judged."""

    kind: OptionKind
    lines: tuple[OfferLine, ...]


@dataclass(frozen=True)
class _Assembled:
    draft: Draft
    totals: Totals
    coverage: tuple[Coverage, ...]
    checks: tuple[ConstraintCheck, ...]
    asked: tuple[RequestLine, ...]
    comparison: OptionComparison | None = None  # set by `_assemble`; worked out from the lines when not
    extra: str = ""  # sentences of the summary that depend on the other options: the preference's trade-off

    @property
    def compared(self) -> OptionComparison:
        return self.comparison or compare(self.draft.lines)


def finish_options(
    drafts: Sequence[Draft],
    request: PurchaseRequest,
    needs: Sequence[Need],
    profile: BuyerProfile,
    deps: OfferDeps,
    now: datetime,
) -> tuple[OfferOption, ...]:
    """At most three options in rank order (four with the cheapest confirmed one), each with its totals, checks,
    comparison and the policy verdict."""
    assembled = _cheaper_only([_assemble(draft, request, needs, deps) for draft in drafts if draft.lines])
    ranked = _traded_off(sorted(assembled, key=_rank_key)[: _cap(assembled)], request.prefer)
    # The day's committed spend must reach the policy, or every option reads APPROVAL for a missing fact.
    context = PolicyContext(
        now=now, day_committed_net_eur=deps.day_spend(profile.profile_id),
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
    )


def _of_kind(assembled: Sequence[_Assembled], kind: OptionKind) -> _Assembled | None:
    return next((each for each in assembled if each.draft.kind is kind), None)


def _cheaper_only(assembled: list[_Assembled]) -> list[_Assembled]:
    """The cheapest confirmed option stays only when it costs less than the preferred one: otherwise there is no
    trade-off to show."""
    best = _of_kind(assembled, OptionKind.BEST_CONFIRMED)
    ceiling = best.totals.net if best is not None else None
    return [
        each for each in assembled
        if each.draft.kind is not OptionKind.CHEAPEST_CONFIRMED or (ceiling is not None and each.totals.net < ceiling)
    ]


def _cap(assembled: Sequence[_Assembled]) -> int:
    has_cheapest = _of_kind(assembled, OptionKind.CHEAPEST_CONFIRMED) is not None
    return MAX_OPTIONS_WITH_CHEAPEST if has_cheapest else MAX_OPTIONS


def _traded_off(ranked: list[_Assembled], prefer: Preference) -> list[_Assembled]:
    """The preferred option says which lines had no value for the key and what it costs over the cheapest one;
    the cheapest one says how much less it costs."""
    best, cheapest = _of_kind(ranked, OptionKind.BEST_CONFIRMED), _of_kind(ranked, OptionKind.CHEAPEST_CONFIRMED)
    if best is None or prefer is Preference.PRICE:
        return ranked
    extra = {id(best): missing_sentence(best.draft.lines, prefer)}
    if cheapest is not None:
        difference = eur(best.totals.net - cheapest.totals.net)
        what = gain(prefer, best.compared, cheapest.compared) or f"products ranked by {KEY_WORDS[prefer]} first"
        extra[id(best)] += f" {difference} more than the cheapest confirmed option, for {what}."
        extra[id(cheapest)] = f" {difference} less than the option ranked by {KEY_WORDS[prefer]}."
    return [replace(each, extra=extra[id(each)]) if id(each) in extra else each for each in ranked]


def _rank_key(assembled: _Assembled) -> tuple[bool, int, int, int, Decimal]:
    """Constraint fit, then verification status, then the kind, then the net total (SPEC section 5, step 3).

    The buyer's preference ranks the products inside BEST_CONFIRMED, and BEST_CONFIRMED comes before
    CHEAPEST_CONFIRMED by kind: between two options that fit alike the preferred one is first. A preference never
    outranks constraint fit or verification status (`Preference`: "once every constraint is met").

    An option that holds an unconfirmed quantity is never first: a quantity that is not confirmed is
    never the suggestion (SPEC section 4), so such an option comes after every option that holds none,
    whatever else it fits and however little it costs. The price is the last key and cannot change that.
    """
    unconfirmed = any(line.availability.state is not AvailabilityState.CONFIRMED for line in assembled.draft.lines)
    not_met = sum(check.result is CheckResult.NOT_MET for check in assembled.checks)
    unverified = sum(check.result is CheckResult.UNVERIFIED for check in assembled.checks)
    return unconfirmed, not_met, unverified, KIND_ORDER[assembled.draft.kind], assembled.totals.net


def _option(rank: int, assembled: _Assembled, prefer: Preference) -> OfferOption:
    draft = assembled.draft
    fill_ratio = lowest_fill_ratio(assembled.coverage)
    ranked_by = title_suffix(prefer) if draft.kind is OptionKind.BEST_CONFIRMED else ""
    return OfferOption(
        option_id=f"opt_{rank}",
        kind=draft.kind,
        rank=rank,
        title=TITLES[draft.kind] + ranked_by + (PARTIAL_SUFFIX if fill_ratio < 1 else ""),
        summary=_summary(assembled),
        lines=draft.lines,
        totals=assembled.totals,
        coverage=assembled.coverage,
        fill_ratio=fill_ratio,
        valid_until=valid_until_of(draft.lines),
        constraint_checks=assembled.checks,
        comparison=assembled.compared,
    )


def _summary(assembled: _Assembled) -> str:
    lines, totals = assembled.draft.lines, assembled.totals
    money = f"{eur(totals.net)} before tax"
    covered = _covered_phrase(assembled.coverage)
    if assembled.draft.kind in (OptionKind.BEST_CONFIRMED, OptionKind.CHEAPEST_CONFIRMED):
        verb = "covers" if len(lines) == 1 else "cover"
        text = f"{counted(len(lines), 'confirmed product')} {verb} {covered}, for {money}."
        if assembled.draft.kind is OptionKind.CHEAPEST_CONFIRMED:
            text = f"The cheapest confirmed option: {text}"
    elif assembled.draft.kind is OptionKind.ALTERNATIVE_UNCONFIRMED:
        names = _names(line for line in lines if line.availability.state is not AvailabilityState.CONFIRMED)
        text = (
            f"{names} for {covered}, {money}. Valio does not confirm the quantity in stock, "
            "so a human must approve this option."
        )
    else:
        stand_ins = [line for line in lines if line.substitute is not None]
        originals = ", ".join(dict.fromkeys(_original_name(line.substitute) for line in stand_ins if line.substitute))
        kept = len(lines) > len(stand_ins)
        stands_in = "fills what is missing of" if kept else "in place of"
        text = f"{_names(stand_ins)} {stands_in} {originals}: {covered}, for {money}."
    notes = (CEILING_NOTE if totals.is_ceiling else "") + (DEPOSIT_NOTE if totals.excludes_deposits else "")
    return text + assembled.extra + _per_line(assembled.coverage, assembled.asked) + notes


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
