"""`build_offer`: request → candidates → one look-up → options with a verdict each (SPEC section 5).

The builder stores nothing and records no audit event; the gateway service does both.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from tta.allergens.codes import describe
from tta.availability.wording import format_day
from tta.contracts.common import ExclusionReason, Preference
from tta.contracts.offer import Exclusion, Offer, OfferOption
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers.candidates import Candidate, Found, Need, evaluate, exclusion_for, find_products, need_for
from tta.offers.deps import Lookup, OfferDeps, look_up
from tta.offers.options import finish_options
from tta.offers.planning import LineOutcome, plan_options
from tta.offers.preference import KEY_WORDS
from tta.offers.variants import regular_words, variant_claims_for, variant_word
from tta.offers.wording import counted, joined, line_label, line_words, listed, reason_words

OFFER_ID_PREFIX = "off_"
OFFER_ID_HEX_DIGITS = 12
SENTENCE_END = ". "
NO_OPTION_NOTE = "No option can be offered for this request. Each product that dropped out is listed with its reason."


def build_offer(request: PurchaseRequest, profile: BuyerProfile, deps: OfferDeps, *, agent_id: str) -> Offer:
    """Never raises for "nothing fits": the offer then has no options and says why.

    Raises `InvalidRequest` (unknown product type or allergen code, an exclusion with no strictness),
    `UnknownProduct` (a named id the catalog does not hold) and `SupplierUnavailable`.
    """
    needs = tuple(need_for(index, line, request, profile) for index, line in enumerate(request.lines))
    found = tuple(find_products(line, deps.catalog) for line in request.lines)
    lookup = look_up(deps, (product.id for each in found for product in each.products))
    judged = tuple(
        _judge_line(need, asked, each, lookup, deps.catalog)
        for need, asked, each in zip(needs, request.lines, found, strict=True)
    )
    outcomes = tuple(outcome for outcome, _ in judged)
    late = tuple(candidates for _, candidates in judged)
    plan = plan_options(outcomes, lookup.now, deps, request.prefer)
    type_notes = _type_notes(request.lines, deps.catalog)
    options = finish_options(
        plan.drafts, request, needs, profile, deps, lookup.now, headline=_headline(type_notes, len(request.lines))
    )
    return Offer(
        offer_id=OFFER_ID_PREFIX + uuid.uuid4().hex[:OFFER_ID_HEX_DIGITS],
        created_at=deps.clock.now(),
        profile_id=profile.profile_id,
        agent_id=agent_id,
        request=request,
        options=options,
        excluded=tuple(exclusion for outcome in outcomes for exclusion in outcome.excluded),
        candidates_considered=sum(outcome.considered for outcome in outcomes),
        source=lookup.source,
        time_now=lookup.now,
        time_basis=lookup.time_basis,
        notes=(
            *(f"{line_label(index)}: {note}" for index, note in type_notes),
            *_strict_notes(needs), *_variant_notes(request.lines, options, deps.catalog),
            *_search_notes(found), *plan.notes, *_unused_notes(outcomes, options, request.prefer),
            *_empty_notes(outcomes, late, options, lookup.now),
        ),
    )


def _judge_line(
    need: Need, asked: RequestLine, found: Found, lookup: Lookup, catalog: Catalog
) -> tuple[LineOutcome, tuple[Candidate, ...]]:
    """Classify each candidate and run the allergen check; what drops out gets a reason and a sentence.
    Also returns the candidates that dropped out for arriving after the needed-by date."""
    fitting = []
    excluded = []
    late = []
    for product in found.products:
        candidate = evaluate(product, need, lookup, catalog)
        dropped = exclusion_for(candidate, need, lookup.now)
        if dropped is None:
            fitting.append(candidate)
            continue
        reason, sentence = dropped
        if reason is ExclusionReason.LATE_FOR_NEEDED_BY:
            late.append(candidate)
        excluded.append(
            Exclusion(
                product_id=product.id, name=product.display_name, request_line_index=need.index, reason=reason,
                sentence=sentence,
            )
        )
    outcome = LineOutcome(
        need=need, asked=asked, considered=len(found.products), fitting=tuple(fitting), excluded=tuple(excluded)
    )
    return outcome, tuple(late)


def _type_notes(lines: Sequence[RequestLine], catalog: Catalog) -> tuple[tuple[int, str], ...]:
    """What the product type a line asks for leaves out, by request line: a buyer who asks for milk gets no
    milk for coffee, and is told so and how to ask for it (Valio Aimo, 14 Nov 2026: "no be explicit")."""
    notes = []
    for index, line in enumerate(lines):
        note = catalog.product_type_note(line.product_type) if line.product_type is not None else None
        if note:
            notes.append((index, note))
    return tuple(notes)


def _headline(type_notes: Sequence[tuple[int, str]], request_lines: int) -> str:
    """The first sentence of each type note, for the summary of the first option: what was left out. How to
    ask for it stays in `offer.notes`. A request of several lines says which line."""
    sentences = []
    for index, note in type_notes:
        first = note.split(SENTENCE_END, 1)[0].rstrip(".") + "."
        sentences.append(first if request_lines == 1 else f"{line_label(index)}: {first}")
    return " ".join(dict.fromkeys(sentences))


def _strict_notes(needs: Sequence[Need]) -> tuple[str, ...]:
    """An exclusion nobody gave an allergen rule for was read as STRICT (review P4, item M3)."""
    return tuple(
        f"{line_label(need.index)}: no allergen rule was given for "
        f"{joined([describe(code) for code in need.read_as_strict])}, so it was read as strict: a product is offered "
        "as safe only when its data states it is free from it."
        for need in needs if need.read_as_strict
    )


def _variant_notes(
    lines: Sequence[RequestLine], options: Sequence[OfferOption], catalog: Catalog
) -> tuple[str, ...]:
    """A variant nobody asked for is in an option: the rule, and the products it applies to
    (`tta.offers.variants`). Each option that holds one names it in its own summary too."""
    notes = []
    for index, asked in enumerate(lines):
        offered = dict.fromkeys(
            line.product_id for option in options for line in option.lines if line.request_line_index == index
        )
        variants = [
            product_id for product_id in offered
            if (product := catalog.get_product(product_id)) is not None
            and variant_word(asked, product.nutritional_claims) is not None
        ]
        if not variants:
            continue
        kinds = " or ".join(variant_claims_for(asked).values())
        what = line_words(asked)
        notes.append(
            f"{line_label(index)}: a request for {what} is filled with {regular_words(asked)} first. "
            f"{kinds.capitalize()} {what} is offered only as a named alternative: {listed(variants)}."
        )
    return tuple(notes)


def _search_notes(found: Sequence[Found]) -> tuple[str, ...]:
    return tuple(f"{line_label(index)}: {each.note}" for index, each in enumerate(found) if each.note)


def _unused_notes(
    outcomes: Sequence[LineOutcome], options: Sequence[OfferOption], prefer: Preference
) -> tuple[str, ...]:
    """The candidates that fit and are in no option, so every candidate is accounted for: it is in an
    option, in `excluded` with a reason, or named here. A product that fits has not dropped out, and
    `ExclusionReason` has no code for "not needed"."""
    offered = {line.product_id for option in options for line in option.lines}
    taken = "the cheapest products" if prefer is Preference.PRICE else (
        f"the products ranked first by {KEY_WORDS[prefer]}, then price,"
    )
    notes = []
    for outcome in outcomes:
        unused = [each.product.id for each in outcome.fitting if each.product.id not in offered]
        if not unused:
            continue
        fit = "fits the request and is" if len(unused) == 1 else "fit the request and are"
        notes.append(
            f"{line_label(outcome.need.index)}: {counted(len(unused), 'product')} {fit} in no option, because "
            f"the options take {taken} that cover the quantity: {listed(unused)}."
        )
    return tuple(notes)


def _empty_notes(
    outcomes: Sequence[LineOutcome], late: Sequence[tuple[Candidate, ...]], options: Sequence[OfferOption],
    now: datetime,
) -> tuple[str, ...]:
    """Why a request line has no product in any option, the earliest date a late product could make, and that
    there is no option at all."""
    offered = {line.request_line_index for option in options for line in option.lines}
    notes: list[str] = []
    for outcome, arrive_later in zip(outcomes, late, strict=True):
        if outcome.need.index in offered or not outcome.considered:
            continue
        notes.append(_nothing_for(outcome))
        notes.extend(_earliest_date(outcome.need, arrive_later, now))
    if not options:
        notes.append(NO_OPTION_NOTE)
    return tuple(notes)


def _earliest_date(need: Need, arrive_later: Sequence[Candidate], now: datetime) -> tuple[str, ...]:
    """When nothing of a dated line arrives in time: the earliest delivery date among the products that would
    fit on their own date, and which products make it, so the buyer can decide (task FIX-12b).

    A product counts only when it passes every other check with its own date as the needed-by date: one with
    no price, or one that confirmed-only would leave out, is not named.
    """
    if need.needed_by is None:
        return ()
    fits = [
        (day, candidate.product.id)
        for candidate in arrive_later
        if (day := candidate.assessment.available_date) is not None
        and exclusion_for(candidate, replace(need, needed_by=day), now) is None
    ]
    if not fits:
        return ()
    earliest = min(day for day, _ in fits)
    ids = [product_id for day, product_id in fits if day == earliest]
    return (
        f"{line_label(need.index)}: nothing can arrive by {format_day(need.needed_by)}. The earliest delivery date "
        f"in Valio's data for a product that otherwise fits is {format_day(earliest)}, for "
        f"{counted(len(ids), 'product')}: {listed(ids)}.",
    )


def _nothing_for(outcome: LineOutcome) -> str:
    counts = Counter(exclusion.reason for exclusion in outcome.excluded)
    reasons = ", ".join(f"{count} {reason_words(reason)}" for reason, count in counts.most_common())
    checked = counted(outcome.considered, "candidate")
    why = f": {reasons}" if reasons else ""
    return f"{line_label(outcome.need.index)}: no product can be offered. {checked} checked{why}."
