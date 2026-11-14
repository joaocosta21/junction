"""`build_offer`: request → candidates → one look-up → options with a verdict each (SPEC section 5).

The builder stores nothing and records no audit event; the gateway service does both.
"""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence

from tta.contracts.offer import Exclusion, Offer, OfferOption
from tta.contracts.policy import BuyerProfile
from tta.contracts.ports import Catalog
from tta.contracts.request import PurchaseRequest, RequestLine
from tta.offers.candidates import Found, Need, evaluate, exclusion_for, find_products, need_for
from tta.offers.deps import Lookup, OfferDeps, look_up
from tta.offers.options import finish_options
from tta.offers.planning import LineOutcome, plan_options
from tta.offers.wording import counted, line_label, listed, reason_words

OFFER_ID_PREFIX = "off_"
OFFER_ID_HEX_DIGITS = 12
NO_OPTION_NOTE = "No option can be offered for this request. Each product that dropped out is listed with its reason."


def build_offer(request: PurchaseRequest, profile: BuyerProfile, deps: OfferDeps, *, agent_id: str) -> Offer:
    """Never raises for "nothing fits": the offer then has no options and says why.

    Raises `InvalidRequest` (unknown product type or allergen code, an exclusion with no strictness),
    `UnknownProduct` (a named id the catalog does not hold) and `SupplierUnavailable`.
    """
    needs = tuple(need_for(index, line, request, profile) for index, line in enumerate(request.lines))
    found = tuple(find_products(line, deps.catalog) for line in request.lines)
    lookup = look_up(deps, (product.id for each in found for product in each.products))
    outcomes = tuple(
        _judge_line(need, asked, each, lookup, deps.catalog)
        for need, asked, each in zip(needs, request.lines, found, strict=True)
    )
    plan = plan_options(outcomes, lookup.now, deps)
    options = finish_options(plan.drafts, request, needs, profile, deps, lookup.now)
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
        notes=(
            *_search_notes(found), *plan.notes, *_unused_notes(outcomes, options), *_empty_notes(outcomes, options)
        ),
    )


def _judge_line(need: Need, asked: RequestLine, found: Found, lookup: Lookup, catalog: Catalog) -> LineOutcome:
    """Classify each candidate and run the allergen check; what drops out gets a reason and a sentence."""
    fitting = []
    excluded = []
    for product in found.products:
        candidate = evaluate(product, need, lookup, catalog)
        dropped = exclusion_for(candidate, need, lookup.now)
        if dropped is None:
            fitting.append(candidate)
            continue
        reason, sentence = dropped
        excluded.append(
            Exclusion(
                product_id=product.id, name=product.display_name, request_line_index=need.index, reason=reason,
                sentence=sentence,
            )
        )
    return LineOutcome(
        need=need, asked=asked, considered=len(found.products), fitting=tuple(fitting), excluded=tuple(excluded)
    )


def _search_notes(found: Sequence[Found]) -> tuple[str, ...]:
    return tuple(f"{line_label(index)}: {each.note}" for index, each in enumerate(found) if each.note)


def _unused_notes(outcomes: Sequence[LineOutcome], options: Sequence[OfferOption]) -> tuple[str, ...]:
    """The candidates that fit and are in no option, so every candidate is accounted for: it is in an
    option, in `excluded` with a reason, or named here. A product that fits has not dropped out, and
    `ExclusionReason` has no code for "not needed"."""
    offered = {line.product_id for option in options for line in option.lines}
    notes = []
    for outcome in outcomes:
        unused = [each.product.id for each in outcome.fitting if each.product.id not in offered]
        if not unused:
            continue
        fit = "fits the request and is" if len(unused) == 1 else "fit the request and are"
        notes.append(
            f"{line_label(outcome.need.index)}: {counted(len(unused), 'product')} {fit} in no option, because "
            f"the options take the cheapest products that cover the quantity: {listed(unused)}."
        )
    return tuple(notes)


def _empty_notes(outcomes: Sequence[LineOutcome], options: Sequence[OfferOption]) -> tuple[str, ...]:
    """Why a request line has no product in any option, and that there is no option at all."""
    offered = {line.request_line_index for option in options for line in option.lines}
    notes = [_nothing_for(outcome) for outcome in outcomes if outcome.need.index not in offered and outcome.considered]
    if not options:
        notes.append(NO_OPTION_NOTE)
    return tuple(notes)


def _nothing_for(outcome: LineOutcome) -> str:
    counts = Counter(exclusion.reason for exclusion in outcome.excluded)
    reasons = ", ".join(f"{count} {reason_words(reason)}" for reason, count in counts.most_common())
    checked = counted(outcome.considered, "candidate")
    why = f": {reasons}" if reasons else ""
    return f"{line_label(outcome.need.index)}: no product can be offered. {checked} checked{why}."
