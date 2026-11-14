"""From drafted lines to finished options: totals, coverage, checks, rank and the policy verdict (SPEC section 5)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from tta.availability.wording import format_amount
from tta.contracts.common import AvailabilityState, CheckResult, OptionKind
from tta.contracts.offer import ConstraintCheck, Coverage, OfferLine, OfferOption, SubstituteInfo, Totals
from tta.contracts.policy import BuyerProfile, PolicyContext
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers.candidates import Need
from tta.offers.checks import constraint_checks
from tta.offers.deps import OfferDeps
from tta.offers.lines import coverage_of, lowest_fill_ratio, totals_of, valid_until_of
from tta.offers.wording import counted, eur, line_label, line_words, measured, plain_name

MAX_OPTIONS = 3
# A product asked for comes before a stand-in for it. Only the net total comes after this in the ranking.
KIND_ORDER = {OptionKind.BEST_CONFIRMED: 0, OptionKind.ALTERNATIVE_UNCONFIRMED: 1, OptionKind.SUBSTITUTE: 2}
TITLES = {
    OptionKind.BEST_CONFIRMED: "Best confirmed option",
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


def finish_options(
    drafts: Sequence[Draft],
    request: PurchaseRequest,
    needs: Sequence[Need],
    profile: BuyerProfile,
    deps: OfferDeps,
    now: datetime,
) -> tuple[OfferOption, ...]:
    """At most three options in rank order, each with its totals, checks and the policy verdict."""
    assembled = [_assemble(draft, request, needs, deps) for draft in drafts if draft.lines]
    ranked = sorted(assembled, key=_rank_key)[:MAX_OPTIONS]
    # The day's committed spend must reach the policy, or every option reads APPROVAL for a missing fact.
    context = PolicyContext(now=now, day_committed_net_eur=deps.day_spend(profile.profile_id))
    options = (_option(rank, each) for rank, each in enumerate(ranked, start=1))
    return tuple(
        option.model_copy(update={"decision": deps.policy.evaluate(option, profile, context)}) for option in options
    )


def _assemble(draft: Draft, request: PurchaseRequest, needs: Sequence[Need], deps: OfferDeps) -> _Assembled:
    coverage = coverage_of(request.lines, draft.lines)
    checks = constraint_checks(request, needs, draft.lines, coverage, deps.catalog)
    return _Assembled(
        draft=draft, totals=totals_of(draft.lines), coverage=coverage, checks=checks, asked=tuple(request.lines)
    )


def _rank_key(assembled: _Assembled) -> tuple[bool, int, int, int, Decimal]:
    """Constraint fit, then verification status, then the kind, then the net total (SPEC section 5, step 3).

    An option that holds an unconfirmed quantity is never first: a quantity that is not confirmed is
    never the suggestion (SPEC section 4), so such an option comes after every option that holds none,
    whatever else it fits and however little it costs. The price is the last key and cannot change that.
    """
    unconfirmed = any(line.availability.state is not AvailabilityState.CONFIRMED for line in assembled.draft.lines)
    not_met = sum(check.result is CheckResult.NOT_MET for check in assembled.checks)
    unverified = sum(check.result is CheckResult.UNVERIFIED for check in assembled.checks)
    return unconfirmed, not_met, unverified, KIND_ORDER[assembled.draft.kind], assembled.totals.net


def _option(rank: int, assembled: _Assembled) -> OfferOption:
    draft = assembled.draft
    fill_ratio = lowest_fill_ratio(assembled.coverage)
    return OfferOption(
        option_id=f"opt_{rank}",
        kind=draft.kind,
        rank=rank,
        title=TITLES[draft.kind] + (PARTIAL_SUFFIX if fill_ratio < 1 else ""),
        summary=_summary(assembled),
        lines=draft.lines,
        totals=assembled.totals,
        coverage=assembled.coverage,
        fill_ratio=fill_ratio,
        valid_until=valid_until_of(draft.lines),
        constraint_checks=assembled.checks,
    )


def _summary(assembled: _Assembled) -> str:
    lines, totals = assembled.draft.lines, assembled.totals
    money = f"{eur(totals.net)} before tax"
    covered = _covered_phrase(assembled.coverage)
    if assembled.draft.kind is OptionKind.BEST_CONFIRMED:
        verb = "covers" if len(lines) == 1 else "cover"
        text = f"{counted(len(lines), 'confirmed product')} {verb} {covered}, for {money}."
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
    return text + _per_line(assembled.coverage, assembled.asked) + notes


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
