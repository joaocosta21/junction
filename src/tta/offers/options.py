"""From drafted lines to finished options: totals, coverage, checks, rank and the policy verdict (SPEC section 5)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal

from tta.availability.wording import format_amount, format_day
from tta.contracts.common import AvailabilityState, CheckResult, OptionKind, Preference, Unit, Verdict
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
from tta.offers.safe_swap import SAFE_SWAP_TITLE, safe_swap_said
from tta.offers.safety import has_doubt, open_allergens, who_decides
from tta.offers.variants import regular_words, variant_word
from tta.offers.wording import UNIT_WORDS, counted, eur, joined, line_names, line_words, measured, plain_name

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
LAST_RESORT_SUBSTITUTE = "a substitute a person must judge"
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
# The confirmed fill of a request by type or by words, completed from confirmed stock of the nearest kind
# (`tta.offers.completing`, decision B56). Each completing line is a substitute and is judged as one.
COMPLETED = "confirmed stock, completed with a substitute"
# A dated request that nothing meets, offered for the earliest date it can be met (`tta.offers.later`, decision
# B67). Rule F-07 sends every such option to a person: the date asked for is not met.
ACCEPT_LATER = " A person must accept the later date."


@dataclass(frozen=True)
class Draft:
    """The lines of one option, before anything is summed or judged."""

    kind: OptionKind
    lines: tuple[OfferLine, ...]
    said: str = ""  # a sentence for the summary that only the planning knows: what the stand-in search found
    # The confirmed fill with what completes it (`tta.offers.completing`): listed after every other option.
    completed: bool = False


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
    safe_swap: str = ""  # the substitute was chosen for an excluded allergen, said (`tta.offers.safe_swap`)
    # Per request line where the formula matters, who says so (`Need.formula_said`).
    formula_said: Mapping[int, str] = field(default_factory=dict)
    needed_by: date | None = None  # the date the request asks for

    @property
    def compared(self) -> OptionComparison:
        return self.comparison or compare(self.draft.lines)

    @property
    def delivered_later(self) -> tuple[date, ...]:
        """The delivery dates of the lines that arrive after the date asked for, the earliest first; empty when
        every line arrives in time or no date was asked. Only an option built for a later date holds such a
        line (`tta.offers.later`): a product that is late for the date asked has dropped out of every other."""
        if self.needed_by is None:
            return ()
        days = {line.availability.available_date for line in self.draft.lines}
        return tuple(sorted(day for day in days if day is not None and day > self.needed_by))

    @property
    def quantity_unconfirmed(self) -> bool:
        return any(line.availability.state is not AvailabilityState.CONFIRMED for line in self.draft.lines)

    @property
    def last_resort(self) -> bool:
        """A line holds a substitute that is a last resort (`SubstituteInfo.last_resort`; rule F-12)."""
        return any(line.substitute is not None and line.substitute.last_resort for line in self.draft.lines)

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
    comparison and the policy verdict; then the completed option, when the planning drafted one (`Draft.completed`).
    `headline` is added to the summary of the first option: what the request's product type left out."""
    assembled = _cheaper_only([_assemble(draft, request, needs, deps) for draft in drafts if draft.lines])
    priced = _traded_off([each for each in assembled if not each.draft.completed], request.prefer)
    ranked = _safe_swaps(_safe_first(sorted(priced, key=_rank_key)[: _cap(priced)]))
    if ranked and headline:
        ranked = [replace(ranked[0], named=f"{ranked[0].named} {headline}"), *ranked[1:]]
    # The completed option is one more, after the others: it takes no place of theirs and changes none of them.
    ranked = [*ranked, *(each for each in assembled if each.draft.completed)]
    # The day's committed spend must reach the policy, or every option reads APPROVAL for a missing fact.
    committed, waiting = spend_parts(deps.day_spend(profile.profile_id))
    context = PolicyContext(
        now=now, day_committed_net_eur=committed, day_waiting_net_eur=waiting,
        standing_history=standing_history_of(deps, profile.profile_id, request.standing_order_id),  # P-08
    )
    options = (_option(rank, each, request.prefer) for rank, each in enumerate(ranked, start=1))
    judged = (
        option.model_copy(update={"decision": deps.policy.evaluate(option, profile, context)}) for option in options
    )
    # A completed option that a rule blocks is not offered: it is last, so leaving it out moves no other option.
    return tuple(
        option for option, each in zip(judged, ranked, strict=True)
        if not (each.draft.completed and option.decision is not None and option.decision.verdict is Verdict.BLOCK)
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
        needed_by=request.needed_by,
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


def _safe_swaps(ranked: list[_Assembled]) -> list[_Assembled]:
    """A SUBSTITUTE option whose stand-ins were chosen because the product asked for leaves a doubt about an
    excluded allergen says that, not that the product cannot be supplied."""
    return [
        replace(each, safe_swap=safe_swap_said(
            each.draft.lines, [other.draft.lines for other in ranked if other is not each]
        )) if each.draft.kind is OptionKind.SUBSTITUTE else each
        for each in ranked
    ]


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

    An option whose substitute is marked `last_resort` (it loses a dietary claim, it is not shown to be the same
    kind of product, or it is a variant the data does not explain) is ranked the same way and for the same
    reason: it is never the suggestion while another option exists, and it goes to a person (rule F-12).
    """
    not_met = sum(check.result is CheckResult.NOT_MET for check in assembled.checks)
    unverified = sum(check.result is CheckResult.UNVERIFIED for check in assembled.checks)
    return (
        assembled.allergen_doubt, assembled.formula_changed or assembled.last_resort,
        assembled.quantity_unconfirmed, not_met, unverified,
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
    if assembled.delivered_later:
        doubts = [
            _later_words(assembled),
            *([QUANTITY_NOT_CONFIRMED] if assembled.quantity_unconfirmed else []),
            *([ALLERGEN_NOT_RULED_OUT] if assembled.allergen_doubt else []),
        ]
        title = ALTERNATIVE + ", ".join(doubts)
    elif assembled.draft.completed:
        title = ALTERNATIVE + COMPLETED
    elif kind is OptionKind.BEST_CONFIRMED:
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
    elif assembled.last_resort:
        title = ALTERNATIVE + LAST_RESORT_SUBSTITUTE
    elif assembled.safe_swap:
        title = SAFE_SWAP_TITLE
    return title + (PARTIAL_SUFFIX if fill_ratio < 1 else "")


def _option(rank: int, assembled: _Assembled, prefer: Preference) -> OfferOption:
    draft = assembled.draft
    fill_ratio = lowest_fill_ratio(assembled.coverage)
    return OfferOption(
        option_id=f"opt_{rank}",
        # An option for a later date than asked is an alternative, whatever it holds: never "best confirmed".
        kind=OptionKind.ALTERNATIVE_UNCONFIRMED if assembled.delivered_later else draft.kind,
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
    if assembled.draft.completed:
        text = _completed_summary(assembled, money)
    elif assembled.draft.kind in (OptionKind.BEST_CONFIRMED, OptionKind.CHEAPEST_CONFIRMED):
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
        text = f"{_names(stand_ins)} {stands_in} {originals}: {covered}, for {money}.{assembled.safe_swap}"
    if assembled.formula_changed:
        said = assembled.formula_changed_said
        text += FORMULA_NOTE.format(said=said[0].upper() + said[1:])
    notes = (ESTIMATE_NOTE if totals.is_ceiling else "") + (DEPOSIT_NOTE if totals.excludes_deposits else "")
    if assembled.delivered_later and assembled.needed_by is not None:
        later = _later_words(assembled)
        text = (
            f"Nothing can arrive by {format_day(assembled.needed_by)}. {later[0].upper()}{later[1:]}: {text}"
            f"{ACCEPT_LATER}"
        )
    return text + assembled.extra + _per_line(assembled.coverage, assembled.asked, lines) + notes + assembled.named


def _later_words(assembled: _Assembled) -> str:
    """`delivered Monday 16 Nov, 3 days later than asked`; with lines on several dates, the last of them:
    `delivered by Tuesday 17 Nov, 4 days later than asked`."""
    days = assembled.delivered_later
    if not days or assembled.needed_by is None:
        return ""
    by = "" if len(days) == 1 else "by "
    return (
        f"delivered {by}{format_day(days[-1])}, {counted((days[-1] - assembled.needed_by).days, 'day')} later "
        "than asked"
    )


def _completed_summary(assembled: _Assembled, money: str) -> str:
    """`All 1,000 L from confirmed stock, if 565 L may be X (id) at €2.65 per L: €2,580.64 before tax.` Then, for
    each completing product, whether it replaces like for like and what differs, in the substitute check's own
    sentence, and the product it was measured against."""
    stand_ins = [line for line in assembled.draft.lines if line.substitute is not None]
    units = {entry.request_line_index: entry.unit for entry in assembled.coverage}
    may_be = joined([
        f"{measured(line.covers, units[line.request_line_index])} may be {_names([line])} at "
        f"{_price_per_measure(line, units[line.request_line_index])}"
        for line in stand_ins
    ])
    text = f"{_from_confirmed_stock(assembled.coverage)}, if {may_be}: {money}."
    several = len(stand_ins) > 1
    for line in stand_ins:
        info = line.substitute
        if info is None:
            continue
        judged = info.replaceable.sentence if info.replaceable is not None else ""
        subject = f"{_names([line])}: " if several else ""
        said = " ".join(part for part in (judged, f"It was compared with {_original_name(info)}.") if part)
        text += f" {subject}{said}"
    return text


def _from_confirmed_stock(coverage: Sequence[Coverage]) -> str:
    """`All 1,000 L from confirmed stock`, or what of it when the completed option still falls short."""
    if len(coverage) == 1 and coverage[0].missing <= 0:
        return f"All {measured(coverage[0].requested, coverage[0].unit)} from confirmed stock"
    phrase = _covered_phrase(coverage)
    return f"{phrase[0].upper()}{phrase[1:]} from confirmed stock"


def _price_per_measure(line: OfferLine, unit: Unit) -> str:
    """`€2.65 per L`: the price of one litre or kilogram where the pack size is known in the request's unit,
    else the price of one sales unit."""
    pack = line.pack_size
    if unit is not Unit.UNIT and pack.is_known and pack.unit is unit and pack.value:
        return f"{eur(line.unit_net_price / pack.value)} per {UNIT_WORDS[unit]}"
    return f"{eur(line.unit_net_price)} per sales unit"


def _alternative_summary(assembled: _Assembled, covered: str, money: str) -> str:
    """What is not confirmed about the alternative, and who decides: the quantity, the allergen statement, or
    both."""
    lines = assembled.draft.lines
    open_lines = [
        line for line in lines if line.availability.state is not AvailabilityState.CONFIRMED or has_doubt(line)
    ]
    if len(assembled.coverage) == 1:
        text = f"{_named_with_originals(open_lines)} for {covered}, {money}."
    else:
        text = f"{_by_item(assembled, open_lines)}: {covered}, {money}."
    if assembled.quantity_unconfirmed or not assembled.allergen_doubt:
        part = _unconfirmed_part(assembled)
        text += f" Valio does not confirm the quantity in stock{part}, so a human must approve this option."
    if assembled.allergen_doubt:
        allergens = open_allergens(line.allergen_check for line in lines)
        decides = who_decides(line.allergen_check for line in lines)
        text += f" The product data does not rule out {allergens}, so {decides}."
    return text


def _named_with_originals(lines: Sequence[OfferLine]) -> str:
    """`X (id)`, and what it stands in for when it is a substitute: `X (id), a substitute for Y (id),`."""
    stand_ins = [line.substitute for line in lines if line.substitute is not None]
    originals = ", ".join(dict.fromkeys(_original_name(each) for each in stand_ins))
    return f"{_names(lines)}, a substitute for {originals}," if stand_ins else _names(lines)


def _by_item(assembled: _Assembled, open_lines: Sequence[OfferLine]) -> str:
    """`X (id) for the 100 L of milk, and from confirmed stock the 10 L of Y (id)`: an alternative to a request
    of several lines says which products fill which item. The products that make it an alternative come first
    (quantity not confirmed, or an allergen not ruled out); what the option also holds from confirmed stock
    follows. Before, the first products alone were said to be `for all 2 items asked for in full`."""
    names = line_names(assembled.asked)
    entries = {entry.request_line_index: entry for entry in assembled.coverage}
    still_open = {id(line) for line in open_lines}
    confirmed = [line for line in assembled.draft.lines if id(line) not in still_open]

    def said(lines: Sequence[OfferLine]) -> str:
        parts = []
        for index in dict.fromkeys(line.request_line_index for line in lines):
            own = [line for line in lines if line.request_line_index == index]
            parts.append(_for_item(own, entries[index], assembled.asked[index], names[index]))
        return joined(parts)

    text = said(open_lines)
    if confirmed:
        text += f", and from confirmed stock {said(confirmed)}"
    return text


def _for_item(lines: Sequence[OfferLine], entry: Coverage, asked: RequestLine, name: str) -> str:
    """`X (id) for the 100 L of milk`, `X (id) for 40 L of the 100 L of milk`; a line that asked for the product
    itself by its id reads `the 10 L of Y (id)`, as the item has no other words than the product's."""
    covers = sum((line.covers for line in lines), Decimal(0))
    whole = f"the {measured(entry.requested, entry.unit)}"
    amount = whole if covers >= entry.requested else f"{measured(covers, entry.unit)} of {whole}"
    by_id_only = not (asked.product_type or asked.name_terms)
    if by_id_only and all(line.substitute is None for line in lines):
        return f"{amount} of {_names(lines)}"
    return f"{_named_with_originals(lines)} for {amount} of {line_words(asked) if by_id_only else name}"


def _unconfirmed_part(assembled: _Assembled) -> str:
    """` for 616 L of it`: how much of a one-line request the unconfirmed products cover, when the option also
    holds confirmed stock. ` of 464306`: which products, when a request of several lines also gets confirmed
    stock. Empty when all of the option is unconfirmed."""
    lines, coverage = assembled.draft.lines, assembled.coverage
    unconfirmed = [line for line in lines if line.availability.state is not AvailabilityState.CONFIRMED]
    if not unconfirmed or len(unconfirmed) == len(lines):
        return ""
    if len(coverage) != 1:
        return f" of {joined(tuple(dict.fromkeys(line.product_id for line in unconfirmed)))}"
    return f" for {measured(sum((line.covers for line in unconfirmed), Decimal(0)), coverage[0].unit)} of it"


def _covered_phrase(coverage: Sequence[Coverage]) -> str:
    if len(coverage) == 1:
        only = coverage[0]
        asked = f"the {measured(only.requested, only.unit)} asked for"
        if only.missing <= 0:
            return asked
        return f"{measured(only.covered, only.unit)} of {asked} ({measured(only.missing, only.unit)} missing)"
    full = sum(entry.missing <= 0 for entry in coverage)
    if full == len(coverage):
        return f"all {len(coverage)} items asked for in full"
    return f"{full or 'none'} of the {len(coverage)} items asked for in full"


def _per_line(coverage: Sequence[Coverage], asked: Sequence[RequestLine], lines: Sequence[OfferLine]) -> str:
    """` Nothing with confirmed stock for sugar, eggs and butter. Covered in part: 60 of 100 L of milk.` Only the
    request lines an option of several lines falls short on, each by its own words: one that is covered in
    full is not listed, and one that is covered in part keeps its amounts, the least covered first. Rule P-03
    still says what every line gets, with the line numbers (`tta.policy.coverage`)."""
    if len(coverage) <= 1 or all(entry.missing <= 0 for entry in coverage):
        return ""
    names = line_names(asked)
    nothing = [names[entry.request_line_index] for entry in coverage if entry.covered <= 0]
    in_part = sorted(
        (entry for entry in coverage if entry.covered > 0 and entry.missing > 0),
        key=lambda entry: (entry.fill_ratio, entry.request_line_index),
    )
    confirmed_only = all(line.availability.state is AvailabilityState.CONFIRMED for line in lines)
    said = ""
    if nothing:
        what = "Nothing with confirmed stock for" if confirmed_only else "Nothing is offered for"
        said += f" {what} {joined(nothing)}."
    if in_part:
        amounts = "; ".join(_line_covered(entry, names[entry.request_line_index]) for entry in in_part)
        said += f" Covered in part: {amounts}."
    return said


def _line_covered(entry: Coverage, name: str) -> str:
    """`6 of 10 kg of butter`."""
    return f"{format_amount(entry.covered)} of {measured(entry.requested, entry.unit)} of {name}"


def _names(lines: Iterable[OfferLine]) -> str:
    return ", ".join(dict.fromkeys(f"{plain_name(line.name)} ({line.product_id})" for line in lines))


def _original_name(substitute: SubstituteInfo) -> str:
    if not substitute.original_name:
        return substitute.original_id
    return f"{plain_name(substitute.original_name)} ({substitute.original_id})"
