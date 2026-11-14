"""The menu planner: dishes become one offer, and an ingredient that cannot be had in time is replaced by another
product type that does the same job in the dish (task MENU-1).

At most three offers, each through `GatewayService.create_offer` as the caller, so the caller's profile, rate limit
and audit trail apply as to any request:
1. the recipes' own product types;
2. for each line whose top option covers less than the profile's minimum share (nothing deliverable by the date
   is a share of 0): the alternatives of its ingredients, in each role's order;
3. the final offer, with every line: kept, replaced (`stands_in_for` set, so rule F-09 asks a human) or left out
   when nothing can be had in time.
The order is the normal `place_order` on the final offer. Nothing here decides a verdict.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from tta.contracts.common import Identity
from tta.contracts.errors import NotAuthorised
from tta.contracts.menu import MenuPlan, MenuRequest
from tta.contracts.offer import Offer
from tta.contracts.ports import GatewayService
from tta.menus.needs import ZERO, Need, Use, add_to, as_recipe, expand, group, purchase_request
from tta.menus.plan import MAX_PROBE_LINES, Outcome, assemble, fill_of
from tta.menus.recipes import Alternative, Recipe

ONLY_AN_AGENT = "Only a buyer's agent may plan a menu: the plan asks for offers in the buyer's name."


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
        if fill_of(first, index) > ZERO:
            kept.append(remaining)  # a partial fill is still worth ordering; rule P-03 asks a human
        else:
            unsourced.append((index, remaining))
    moved = [use for need in first_needs for use in need.uses if use.use_id in chosen]
    stand_ins = group(moved, lambda use: (chosen[use.use_id], use.ingredient.product_type))
    return _Resolution(needs=(*kept, *stand_ins), chosen=chosen, unsourced=tuple(unsourced))


def _same_lines(left: Sequence[Need], right: Sequence[Need]) -> bool:
    return [(need.key, need.quantity) for need in left] == [(need.key, need.quantity) for need in right]


def plan_menu(
    service: GatewayService, identity: Identity, request: MenuRequest, recipes: Mapping[str, Recipe]
) -> MenuPlan:
    """The menu plan and its final offer. Raises what `create_offer` raises (`InvalidRequest`, `RateLimited`,
    `SupplierUnavailable`, `NotAuthorised`), and `InvalidRequest` for a dish or a stock unit the recipes lack."""
    if not identity.is_agent:
        raise NotAuthorised(ONLY_AN_AGENT)
    uses = expand(request, recipes)
    first_needs = group(uses, as_recipe)
    if not first_needs:
        return assemble(request, uses, Outcome())
    minimum = service.get_authority(identity).profile.min_fill_ratio
    first = service.create_offer(identity, purchase_request(request, first_needs))
    failed = {index for index in range(len(first_needs)) if fill_of(first, index) < minimum}
    if not failed:
        return assemble(request, uses, Outcome(first_needs=first_needs, first=first, final=first,
                                               final_needs=first_needs))
    failed_uses = [use for index in sorted(failed) for use in first_needs[index].uses]
    probe_needs = _probe_needs(failed_uses)
    probe = service.create_offer(identity, purchase_request(request, probe_needs)) if probe_needs else None
    working = {need.key for index, need in enumerate(probe_needs) if fill_of(probe, index) >= minimum}
    resolution = _resolve(first_needs, failed, first, working)
    final: Offer | None = first
    if not _same_lines(resolution.needs, first_needs):
        final = service.create_offer(identity, purchase_request(request, resolution.needs)) if resolution.needs \
            else None
    return assemble(request, uses, Outcome(
        first_needs=first_needs, first=first, probe_needs=probe_needs, probe=probe, final=final,
        final_needs=resolution.needs, chosen=resolution.chosen, unsourced=resolution.unsourced,
    ))
