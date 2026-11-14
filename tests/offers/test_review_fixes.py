"""Review fixes of 14 Nov 2026 in the offer code: finding S12 and the Python review's items P2 and "low".

Capture of 14 Nov, read offline. Default clock = the recording's instant; demo = Thu 12 Nov 2026 14:15 Helsinki.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from tta.catalog import ProductCatalog
from tta.config import Settings
from tta.contracts.availability import AvailabilityResponse, PriceResponse
from tta.contracts.common import AvailabilityState, DataSource, Identity, OptionKind, Unit
from tta.contracts.offer import SubstituteQuery
from tta.contracts.request import MAX_PRODUCT_IDS
from tta.offers import OfferDeps, OfferService, find_substitutes
from tta.offers.deps import look_up
from tta.valio import ReplayGateway

DEMO_CLOCK = datetime.fromisoformat("2026-11-12T14:15:00+02:00")
LACTOSE_FREE_MILK = "469363"
BARISTA, LISTED_DELIGHT = "473609", "471690"
GONE = "479999"  # an id the product file does not hold


class _ListsAMissingProduct:
    """The real catalog, with one more listed substitute for the barista drink: an id the file does not hold."""

    def __init__(self, inner: ProductCatalog) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def listed_substitutes(self, product_id: str) -> tuple[str, ...]:
        listed = tuple(self._inner.listed_substitutes(product_id))
        return (*listed, GONE) if product_id == BARISTA else listed


def test_a_listed_substitute_that_is_not_in_the_product_file_is_said(
    replay_deps: OfferDeps, catalog: ProductCatalog, policy: Any
) -> None:
    deps = OfferDeps(catalog=_ListsAMissingProduct(catalog), gateway=replay_deps.gateway, policy=policy,
                     clock=replay_deps.clock, day_spend=replay_deps.day_spend)

    result = find_substitutes(BARISTA, policy.get_profile("hotel-kitchen"), deps, SubstituteQuery())

    assert (
        f"1 substitute Valio lists is not in the product file and could not be judged: {GONE}."
    ) in result.notes
    plain = find_substitutes(BARISTA, policy.get_profile("hotel-kitchen"), replay_deps, SubstituteQuery())
    assert not any("could not be judged" in note for note in plain.notes)  # the real file lacks none (249 pairs)


def test_an_option_whose_stand_in_quantity_is_not_confirmed_is_an_alternative_and_says_how_much(
    service: OfferService, make_request: Callable[..., Any], policy: Any
) -> None:
    # The Python review's case: the bakery, 1,000 L of 469363. Before: kind SUBSTITUTE, "With a substitute
    # for a product that cannot be supplied in full", a summary that read as a confirmed full fill.
    bakery = Identity.model_validate({"kind": "AGENT", "id": "agent:bakery-cafe", "display_name": "x",
                                      "profile_id": "bakery-cafe"})
    offer = service.build_offer(
        make_request(quantity=Decimal(1000), unit=Unit.L, product_ids=(LACTOSE_FREE_MILK,)), bakery
    )

    for option in offer.options:
        unconfirmed = [line for line in option.lines if line.availability.state is not AvailabilityState.CONFIRMED]
        if unconfirmed:
            assert option.kind is OptionKind.ALTERNATIVE_UNCONFIRMED
            assert option.title.startswith("Alternative: quantity not confirmed")
            assert "Valio does not confirm the quantity in stock" in option.summary
    mixed = next(
        option for option in offer.options
        if any(line.substitute is not None and line.availability.state is not AvailabilityState.CONFIRMED
               for line in option.lines)
    )
    litres = sum(line.covers for line in mixed.lines if line.availability.state is not AvailabilityState.CONFIRMED)
    assert f"Valio does not confirm the quantity in stock for {litres:,.0f} L of it, so a human must approve" in (
        mixed.summary
    )
    confirmed_only = [
        option.rank for option in offer.options
        if all(line.availability.state is AvailabilityState.CONFIRMED for line in option.lines)
    ]
    assert all(rank < mixed.rank for rank in confirmed_only)


def test_at_the_demo_clock_the_listed_barista_drink_is_still_offered_now_as_an_alternative(
    deps_for: Callable[..., OfferDeps], make_request: Callable[..., Any], agent_hotel: Identity
) -> None:
    deps = deps_for(ReplayGateway(Settings.for_tests().replay_capture_dir, demo_clock=DEMO_CLOCK))

    offer = OfferService(deps).build_offer(
        make_request(quantity=Decimal(100), unit=Unit.UNIT, product_ids=(BARISTA,)), agent_hotel
    )

    stand_in = next(option for option in offer.options if any(line.substitute for line in option.lines))
    assert [line.product_id for line in stand_in.lines] == [LISTED_DELIGHT]
    assert stand_in.kind is OptionKind.ALTERNATIVE_UNCONFIRMED  # its quantity is not confirmed at this clock
    assert stand_in.title == "Alternative: quantity not confirmed"


class _Counting:
    """A gateway that answers nothing and records how many ids each call held."""

    source = DataSource.REPLAY

    def __init__(self, now: datetime) -> None:
        self._now, self.sizes = now, []

    def price(self, product_ids: Sequence[str], *, fresh: bool = False) -> PriceResponse:
        self.sizes.append(len(product_ids))
        return PriceResponse(currency="EUR", lines=(), source=self.source, retrieved_at=self._now)

    def availability(self, product_ids: Sequence[str], *, fresh: bool = False) -> AvailabilityResponse:
        self.sizes.append(len(product_ids))
        return AvailabilityResponse(time_now=self._now, lines=(), source=self.source)


def test_more_ids_than_one_call_holds_are_asked_in_batches_and_none_is_left_out(
    deps_for: Callable[..., OfferDeps], now: datetime
) -> None:
    gateway = _Counting(now)
    ids = [str(100000 + number) for number in range(2 * MAX_PRODUCT_IDS + 5)]

    look_up(deps_for(gateway), ids)

    assert max(gateway.sizes) == MAX_PRODUCT_IDS  # before: one call of 2,005 ids
    assert sum(gateway.sizes) == 2 * len(ids)  # a price call and an availability call for every id


def test_the_claim_note_counts_only_candidates_that_stay_in_the_list(policy: Any, replay_deps: OfferDeps) -> None:
    import re

    checked = 0
    for product_id in ("463047", "469363", "464306", "469346", "473609", "464194"):
        result = find_substitutes(product_id, policy.get_profile("hotel-kitchen"), replay_deps, SubstituteQuery())
        for note in result.notes:
            found = re.search(r"dietary claim of the original .* held back as a last resort: (\d+) that keep", note)
            if found:
                checked += 1
                shown = sum(each.orderable and not each.claims_lost for each in result.candidates)
                # The list shows every listed candidate and at most 10 others, so it can hold fewer than the
                # note counts, never a candidate the note does not count.
                assert int(found.group(1)) >= shown
                assert int(found.group(1)) >= 1
    assert checked >= 1


def test_an_allergen_exclusion_also_carries_the_reason_valios_own_data_gives(
    service: OfferService, make_request: Callable[..., Any], agent_ward: Identity
) -> None:
    # Security review: the ward with tree nuts excluded, at the default clock. The almond drink 474774 is past
    # its closing time and declares tree nuts. The offer records the allergen; Valio's view needs the other reason,
    # or the product goes missing from Valio's own list of products past the closing time.
    from tta.contracts.common import ExclusionReason

    request = make_request(quantity=Decimal(200), unit=Unit.L, product_type="plant_drink",
                           exclude_allergens=("AM", "AW", "AN"))

    offer = service.build_offer(request, agent_ward)

    almond = next(entry for entry in offer.excluded if entry.product_id == "474774")
    assert almond.reason is ExclusionReason.ALLERGEN_DECLARED  # the buyer's view is unchanged
    assert almond.supplier_reason is ExclusionReason.CUTOFF_PASSED
    for entry in offer.excluded:
        if entry.reason not in (ExclusionReason.ALLERGEN_DECLARED, ExclusionReason.ALLERGEN_NOT_STATED,
                                ExclusionReason.CLAIM_CONTRADICTED):
            assert entry.supplier_reason is None
