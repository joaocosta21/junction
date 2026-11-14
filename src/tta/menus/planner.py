"""The menu planner: dishes become one offer, and an ingredient that cannot be had in time is replaced by another
product type that does the same job in the dish (task MENU-1).

At most three offers, each through the gateway service as the caller, so the caller's profile, rate limit and audit
trail apply as to any request:
1. the recipes' own product types;
2. for each line that no option covers to the profile's minimum share (nothing deliverable by the date is a share
   of 0): the alternatives of its ingredients, in each role's order;
3. the final offer, with every line: kept, replaced (`stands_in_for` set, so rule F-09 asks a human), or kept with
   nothing offered for it when neither the recipe's type nor an alternative can be had. Such a line stays so that
   the offer shows what is missing and the rules judge the menu as a whole (review A2a, finding M-3): the fill is
   below any minimum (P-03) and a needed-by date is not met for it (F-07, a fixed rule).
The order is the normal `place_order` on the final offer. Nothing here decides a verdict.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from tta.contracts.common import Identity
from tta.contracts.errors import InvalidRequest, NotAuthorised
from tta.contracts.menu import MenuPlan, MenuRequest
from tta.contracts.offer import Offer
from tta.contracts.ports import GatewayService
from tta.contracts.request import MAX_REQUEST_LINES, PurchaseRequest
from tta.menus.allergens import StandInAllergens, stand_in_allergens
from tta.menus.needs import ZERO, Need, Use, add_to, as_recipe, expand, group, purchase_request
from tta.menus.plan import MAX_PROBE_LINES, Outcome, UseId, assemble, best_fill_of
from tta.menus.recipes import Alternative, Recipe

ONLY_AN_AGENT = "Only a buyer's agent may plan a menu: the plan asks for offers in the buyer's name."
TOO_MANY_LINES = (
    "This menu needs {count} request lines; one offer holds at most {limit}. Plan fewer dishes at once."
)
# Review A2a, finding M-1. A gateway service that has this method builds a plan's offers under the contract's
# limit of lines instead of the demonstration's 5 (`tta.api.service.MAX_DEMO_REQUEST_LINES`). The 5 keeps large
# free text out of the database; a plan's lines are built here from the recipe table, a product type and a
# quantity each. A service without the method is asked through `create_offer`, under its own limit.
MENU_OFFER = "create_menu_offer"
MakeOffer = Callable[[Identity, PurchaseRequest], Offer]


def _offer_maker(service: GatewayService) -> MakeOffer:
    return getattr(service, MENU_OFFER, None) or service.create_offer


def _request(request: MenuRequest, needs: Sequence[Need], recipes: Mapping[str, Recipe]) -> PurchaseRequest:
    """Raises `InvalidRequest` for more lines than one offer holds, in plain words."""
    if len(needs) > MAX_REQUEST_LINES:
        raise InvalidRequest(TOO_MANY_LINES.format(count=len(needs), limit=MAX_REQUEST_LINES))
    return purchase_request(request, needs, recipes)


def alternative_key(use: Use, alternative: Alternative) -> tuple[str, tuple[str, ...], str]:
    return alternative.product_type, alternative.name_terms, use.ingredient.product_type


def _probe_needs(failed: Sequence[Use]) -> tuple[Need, ...]:
    """The alternatives of the failed uses, best first for every use, then second, at most MAX_PROBE_LINES lines."""
    needs: dict[tuple[str, tuple[str, ...], str], Need] = {}
    depth = max((len(use.ingredient.alternatives) for use in failed), default=0)
    for rank in range(depth):
        for use in failed:
            if rank >= len(use.ingredient.alternatives):
                continue
            alternative = use.ingredient.alternatives[rank]
            key = alternative_key(use, alternative)
            if key in needs or len(needs) < MAX_PROBE_LINES:
                needs[key] = add_to(needs.get(key), use, alternative, use.ingredient.product_type)
    return tuple(needs.values())


@dataclass(frozen=True)
class _Resolution:
    """What the second offer settled: the lines of the final offer and what stands in for what."""

    needs: tuple[Need, ...]
    chosen: Mapping[tuple[str, str, tuple[str, ...]], Alternative] = field(default_factory=dict)
    unsourced: tuple[tuple[int, Need], ...] = ()  # (index in the first offer, the uses nothing can supply)


def _first_working(use: Use, working: set[tuple[str, tuple[str, ...], str]]) -> Alternative | None:
    return next((each for each in use.ingredient.alternatives if alternative_key(use, each) in working), None)


def _resolve(first_needs: Sequence[Need], failed: set[int], first: Offer, working: set[tuple]) -> _Resolution:
    kept: list[Need] = []
    chosen: dict[tuple[str, str, tuple[str, ...]], Alternative] = {}
    unsourced: list[tuple[int, Need]] = []
    for index, need in enumerate(first_needs):
        if index not in failed:
            kept.append(need)
            continue
        stay = [use for use in need.uses if _first_working(use, working) is None]
        chosen.update({use.use_id: alt for use in need.uses if (alt := _first_working(use, working)) is not None})
        if not stay:
            continue
        remaining = group(stay, as_recipe)[0]
        kept.append(remaining)  # a partial fill is still worth ordering; rule P-03 asks a human
        if best_fill_of(first, index) <= ZERO:
            unsourced.append((index, remaining))  # nothing is offered for it: it stays, and the rules see it
    moved = [use for need in first_needs for use in need.uses if use.use_id in chosen]
    stand_ins = group(moved, lambda use: (chosen[use.use_id], use.ingredient.product_type))
    return _Resolution(needs=(*kept, *stand_ins), chosen=chosen, unsourced=tuple(unsourced))


def _same_lines(left: Sequence[Need], right: Sequence[Need]) -> bool:
    return [(need.key, need.quantity) for need in left] == [(need.key, need.quantity) for need in right]


def plan_menu(
    service: GatewayService, identity: Identity, request: MenuRequest, recipes: Mapping[str, Recipe]
) -> MenuPlan:
    """The menu plan and its final offer. Raises what `create_offer` raises (`InvalidRequest`, `RateLimited`,
    `SupplierUnavailable`, `NotAuthorised`), and `InvalidRequest` for a dish or a stock unit the recipes lack and
    for a menu of more lines than one offer holds."""
    if not identity.is_agent:
        raise NotAuthorised(ONLY_AN_AGENT)
    uses = expand(request, recipes)
    first_needs = group(uses, as_recipe)
    if not first_needs:
        return assemble(request, uses, Outcome())
    offer_for = _offer_maker(service)
    minimum = service.get_authority(identity).profile.min_fill_ratio
    first = offer_for(identity, _request(request, first_needs, recipes))
    # A line fails only when no option covers enough of it (finding M-4): the recipe's own ingredient is kept
    # when an option holds it, also one whose quantity is not confirmed.
    failed = {index for index in range(len(first_needs)) if best_fill_of(first, index) < minimum}
    if not failed:
        return assemble(request, uses, Outcome(first_needs=first_needs, first=first, final=first,
                                               final_needs=first_needs))
    failed_uses = [use for index in sorted(failed) for use in first_needs[index].uses]
    probe_needs = _probe_needs(failed_uses)
    probe = offer_for(identity, _request(request, probe_needs, recipes)) if probe_needs else None
    working = {need.key for index, need in enumerate(probe_needs) if best_fill_of(probe, index) >= minimum}
    resolution = _resolve(first_needs, failed, first, working)
    final = first
    if not _same_lines(resolution.needs, first_needs):
        final = offer_for(identity, _request(request, resolution.needs, recipes))
    return assemble(request, uses, Outcome(
        first_needs=first_needs, first=first, probe_needs=probe_needs, probe=probe, final=final,
        final_needs=resolution.needs, chosen=resolution.chosen, unsourced=resolution.unsourced,
        stand_in_allergens=_stand_in_allergens(service, identity, uses, resolution, final),
    ))


def _stand_in_allergens(
    service: GatewayService, identity: Identity, uses: Sequence[Use], resolution: _Resolution, final: Offer
) -> dict[UseId, tuple[StandInAllergens, ...]]:
    """What the products that stand in declare, per use they replace (finding M-2). One catalog search per recipe
    ingredient replaced and one product read per stand-in product; neither reaches the supplier."""
    keys = [need.key for need in resolution.needs]
    found: dict[UseId, tuple[StandInAllergens, ...]] = {}
    for use in uses:
        alternative = resolution.chosen.get(use.use_id)
        if alternative is None:
            continue
        index = keys.index((*alternative.key, use.ingredient.product_type))
        found[use.use_id] = stand_in_allergens(service, identity, final, index, use.ingredient)
    return found
