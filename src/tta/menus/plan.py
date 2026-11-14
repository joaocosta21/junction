"""The menu plan as the buyer reads it: per dish and ingredient, per request line, and what cannot be had in time."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from tta.contracts.menu import DishPlan, IngredientPlan, IngredientStatus, LinePlan, MenuPlan, MenuRequest, Unsourced
from tta.contracts.offer import Exclusion, Offer, OfferOption
from tta.menus.allergens import StandInAllergens
from tta.menus.needs import ZERO, Need, Use, as_recipe, group
from tta.menus.offered import offered_words, total_words
from tta.menus.recipes import Alternative
from tta.menus.wording import (
    amount_words,
    choice_words,
    date_words,
    dish_words,
    found_words,
    joined,
    only_missing_from_recording,
    type_words,
)

ILLUSTRATIVE = "The recipes and their amounts per serving are ours and illustrative, not Valio Aimo's."
NOTHING_TO_ORDER = "The kitchen's stock covers every ingredient: nothing is ordered."
NOT_TRIED = "{choice} was not tried: the second offer asks for at most {limit} lines"
NO_ALTERNATIVE = "the recipe lists no alternative that does the same job"
UNUSED_STOCK = "No dish of this menu uses the stock given for {types}."
# Review A2a, finding M-3: what cannot be sourced stays in the offer, so the offer and the rules both see it.
INCOMPLETE = (
    "{count} cannot be sourced ({types}). {their} in the offer with nothing offered for {them}, so the offer says "
    "what is missing and the rules judge the menu as a whole: an order of the rest goes to a person."
)
IN_THIS_DEMO = "in this demo"
ANOTHER_OPTION_COVERS = (
    " Option 1 ({top}) covers {top_fill:.0%} of that line; option {rank} ({title}) covers {fill:.0%}: the "
    "recipe's own ingredient is kept, and a person chooses the option."
)
UseId = tuple[str, str, tuple[str, ...]]
# The most lines the second offer asks for: the demonstration gateway's limit per request
# (tta.api.service.MAX_DEMO_REQUEST_LINES). Alternatives are taken best first for every ingredient, then second.
MAX_PROBE_LINES = 5


@dataclass(frozen=True)
class Outcome:
    """The offers the planner asked for and what they settled."""

    first_needs: tuple[Need, ...] = ()
    first: Offer | None = None
    probe_needs: tuple[Need, ...] = ()
    probe: Offer | None = None
    final: Offer | None = None
    final_needs: tuple[Need, ...] = ()
    chosen: Mapping[UseId, Alternative] = field(default_factory=dict)
    unsourced: tuple[tuple[int, Need], ...] = ()
    # What each stand-in's products declare about allergens (review A2a, finding M-2), by the use they replace.
    stand_in_allergens: Mapping[UseId, tuple[StandInAllergens, ...]] = field(default_factory=dict)


def fill_of(offer: Offer | None, index: int) -> Decimal:
    """The share of request line `index` that the offer's top option covers; 0 when there is no option."""
    if offer is None or not offer.options:
        return ZERO
    return next((entry.fill_ratio for entry in offer.options[0].coverage if entry.request_line_index == index), ZERO)


def _fill_in(option: OfferOption, index: int) -> Decimal:
    return next((entry.fill_ratio for entry in option.coverage if entry.request_line_index == index), ZERO)


def best_option_for(offer: Offer | None, index: int) -> OfferOption | None:
    """The option that covers the most of request line `index`, the first one on a tie; None with no option.
    A line fails only when no option covers enough of it (review A2a, finding M-4): the top option holds confirmed
    stock only, and the recipe's own ingredient may be in the next one with a quantity that is not confirmed."""
    if offer is None or not offer.options:
        return None
    return max(offer.options, key=lambda option: _fill_in(option, index))


def best_fill_of(offer: Offer | None, index: int) -> Decimal:
    """The largest share of request line `index` that any option of the offer covers; 0 when there is no option."""
    best = best_option_for(offer, index)
    return ZERO if best is None else _fill_in(best, index)


def excluded_of(offer: Offer | None, index: int) -> tuple[Exclusion, ...]:
    return () if offer is None else tuple(item for item in offer.excluded if item.request_line_index == index)


def _index(needs: Sequence[Need], key: tuple[str, tuple[str, ...], str | None]) -> int | None:
    return next((index for index, need in enumerate(needs) if need.key == key), None)


@dataclass(frozen=True)
class _Reader:
    request: MenuRequest
    outcome: Outcome

    def final_index(self, key: tuple[str, tuple[str, ...], str | None]) -> int | None:
        return None if self.outcome.final is None else _index(self.outcome.final_needs, key)

    def offered(self, index: int | None) -> str:
        """What the final offer holds for request line `index`, with what is left over (`tta.menus.offered`)."""
        if index is None or index >= len(self.outcome.final_needs):
            return ""
        need = self.outcome.final_needs[index]
        return offered_words(self.outcome.final, index, need.amount, need.choice.unit)

    def why_not(self, use: Use) -> str:
        """What the first offer found for the recipe's own product type."""
        key = (use.ingredient.product_type, use.ingredient.name_terms, None)
        index = _index(self.outcome.first_needs, key)
        if index is None:
            return ""
        first = self.outcome.first
        fill = best_fill_of(first, index)
        return found_words(use.ingredient, excluded_of(first, index), fill, self.request.needed_by)

    def only_missing_from_recording(self, use: Use) -> bool:
        key = (use.ingredient.product_type, use.ingredient.name_terms, None)
        index = _index(self.outcome.first_needs, key)
        return index is not None and only_missing_from_recording(excluded_of(self.outcome.first, index))

    def tried(self, use: Use) -> list[str]:
        """What the second offer found for each alternative of this use, in the role's order."""
        found = []
        for alternative in use.ingredient.alternatives:
            index = _index(self.outcome.probe_needs, (*alternative.key, use.ingredient.product_type))
            if index is None:
                found.append(NOT_TRIED.format(choice=choice_words(alternative), limit=MAX_PROBE_LINES))
                continue
            probe = self.outcome.probe
            fill = best_fill_of(probe, index)
            found.append(found_words(alternative, excluded_of(probe, index), fill, self.request.needed_by))
        return found or [NO_ALTERNATIVE]


def _ingredient(reader: _Reader, use: Use, unsourced: Mapping[UseId, str]) -> IngredientPlan:
    ingredient, unit = use.ingredient, use.ingredient.unit
    base = {
        "recipe_product_type": ingredient.product_type, "role": ingredient.role, "needed": use.needed,
        "in_stock": use.in_stock, "to_order": use.to_order, "unit": unit,
    }
    if use.to_order <= ZERO:
        sentence = f"In stock: the kitchen holds the {amount_words(use.needed, unit)} of {choice_words(ingredient)}."
        return IngredientPlan(**base, status=IngredientStatus.IN_STOCK, sentence=sentence)
    if use.use_id in unsourced:
        index = reader.final_index((ingredient.product_type, ingredient.name_terms, None))
        return IngredientPlan(
            **base, status=IngredientStatus.CANNOT_BE_SOURCED, request_line_index=index,
            sentence=unsourced[use.use_id],
        )
    alternative = reader.outcome.chosen.get(use.use_id)
    if alternative is not None:
        index = reader.final_index((*alternative.key, ingredient.product_type))
        why_not = reader.why_not(use)
        sentence = (
            f"{choice_words(alternative).capitalize()} stands in for {choice_words(ingredient)}, {ingredient.role}. "
            f"{why_not[:1].upper()}{why_not[1:]}. {alternative.reason}"
        )
        declared = " ".join(found.sentence for found in reader.outcome.stand_in_allergens.get(use.use_id, ()))
        sentence = f"{sentence} {declared} {reader.offered(index)}".strip()
        return IngredientPlan(
            **base, status=IngredientStatus.STANDS_IN, product_type=alternative.product_type,
            alternative_reason=alternative.reason, request_line_index=index, sentence=sentence,
        )
    index = reader.final_index((ingredient.product_type, ingredient.name_terms, None))
    return IngredientPlan(
        **base, status=IngredientStatus.ORDERED_AS_IN_RECIPE, product_type=ingredient.product_type,
        request_line_index=index, sentence=_ordered_sentence(reader, use, index),
    )


def _ordered_sentence(reader: _Reader, use: Use, index: int | None) -> str:
    stock = f"{amount_words(use.in_stock, use.ingredient.unit)} in stock, " if use.in_stock > ZERO else ""
    where = f", on line {index + 1} of the offer" if index is not None else ""
    ordered = f"{amount_words(use.to_order, use.ingredient.unit)} to order as {choice_words(use.ingredient)}"
    text = f"{stock}{ordered}{where}."
    final = reader.outcome.final
    fill = fill_of(final, index) if index is not None else ZERO
    best = best_option_for(final, index) if index is not None else None
    if best is not None and final is not None and _fill_in(best, index) > fill:
        text += ANOTHER_OPTION_COVERS.format(
            top=final.options[0].title, top_fill=fill, rank=best.rank, title=best.title, fill=_fill_in(best, index),
        )
    elif index is not None and fill < 1:
        text += f" The best option covers {fill:.0%} of that line."
    text = f"{text} {reader.offered(index)}".strip()
    return text[0].upper() + text[1:]


def _unsourced(reader: _Reader) -> tuple[tuple[Unsourced, ...], dict[UseId, str]]:
    found: list[Unsourced] = []
    by_use: dict[UseId, str] = {}
    for _, need in reader.outcome.unsourced:
        use = need.uses[0]
        when = IN_THIS_DEMO if reader.only_missing_from_recording(use) else date_words(reader.request.needed_by)
        sentence = f"Cannot be sourced {when}: {reader.why_not(use)}; {'; '.join(reader.tried(use))}."
        tried = tuple(alternative.product_type for alternative in use.ingredient.alternatives)
        found.append(Unsourced(
            product_type=need.choice.product_type, unit=need.choice.unit, quantity=need.quantity,
            dishes=tuple(dict.fromkeys(each.recipe.name for each in need.uses)), tried=tried, sentence=sentence,
        ))
        by_use.update({each.use_id: sentence for each in need.uses})
    return tuple(found), by_use


def _line(need: Need, index: int | None) -> LinePlan:
    stand_in = need.stands_in_for is not None
    return LinePlan(
        product_type=need.choice.product_type, name_terms=need.choice.name_terms, unit=need.choice.unit,
        needed=need.amount if stand_in else sum((use.needed for use in need.uses), ZERO),
        in_stock=ZERO if stand_in else sum((use.in_stock for use in need.uses), ZERO),
        to_order=need.quantity, dishes=tuple(dict.fromkeys(use.recipe.name for use in need.uses)),
        stands_in_for=need.stands_in_for, request_line_index=index,
    )


def _in_stock_lines(uses: Sequence[Use]) -> tuple[LinePlan, ...]:
    covered = [use for use in uses if use.to_order <= ZERO]
    lines = []
    for use_group in _by_ingredient(covered):
        lines.append(LinePlan(
            product_type=use_group[0].ingredient.product_type, name_terms=use_group[0].ingredient.name_terms,
            unit=use_group[0].ingredient.unit, needed=sum((use.needed for use in use_group), ZERO),
            in_stock=sum((use.in_stock for use in use_group), ZERO), to_order=ZERO,
            dishes=tuple(dict.fromkeys(use.recipe.name for use in use_group)),
        ))
    return tuple(lines)


def _by_ingredient(uses: Sequence[Use]) -> list[list[Use]]:
    groups: dict[tuple[str, tuple[str, ...]], list[Use]] = {}
    for use in uses:
        groups.setdefault(use.ingredient.key, []).append(use)
    return list(groups.values())


def _notes(request: MenuRequest, uses: Sequence[Use], outcome: Outcome) -> tuple[str, ...]:
    notes = [ILLUSTRATIVE]
    if not group(uses, as_recipe):
        notes.append(NOTHING_TO_ORDER)
    used = {use.ingredient.product_type for use in uses}
    unused = [entry.product_type for entry in request.stock if entry.product_type not in used]
    if unused:
        notes.append(UNUSED_STOCK.format(types=joined(unused)))
    if outcome.final is not None and outcome.final.options:
        lines = len(outcome.final_needs)
        notes.append(f"The final offer has {lines} line{'s' if lines != 1 else ''} for {dish_words(uses)}.")
    if outcome.unsourced:
        notes.append(_incomplete(outcome))
    if outcome.final is not None:
        notes.extend(total_words(option) for option in outcome.final.options)
    notes.extend(dict.fromkeys(
        found.sentence for group_found in outcome.stand_in_allergens.values() for found in group_found
        if found.added is None or found.added or not found.has_statement
    ))
    return tuple(notes)


def _incomplete(outcome: Outcome) -> str:
    types = list(dict.fromkeys(type_words(need.choice.product_type) for _, need in outcome.unsourced))
    one = len(types) == 1
    return INCOMPLETE.format(
        count="1 ingredient" if one else f"{len(types)} ingredients", types=joined(types),
        their="Its line stays" if one else "Their lines stay", them="it" if one else "them",
    )


def assemble(request: MenuRequest, uses: Sequence[Use], outcome: Outcome) -> MenuPlan:
    reader = _Reader(request, outcome)
    cannot, unsourced = _unsourced(reader)
    dishes = []
    for dish in request.dishes:
        own = [use for use in uses if use.recipe.dish_id == dish.dish_id]
        recipe = own[0].recipe
        dishes.append(DishPlan(
            dish_id=recipe.dish_id, name=recipe.name, servings=dish.servings, left_out=recipe.left_out,
            ingredients=tuple(_ingredient(reader, use, unsourced) for use in own),
        ))
    final_lines = () if outcome.final is None else tuple(
        _line(need, index) for index, need in enumerate(outcome.final_needs)
    )
    asked = (outcome.first, outcome.probe, outcome.final)
    return MenuPlan(
        request=request, dishes=tuple(dishes), lines=(*final_lines, *_in_stock_lines(uses)), cannot_be_sourced=cannot,
        offer_id=outcome.final.offer_id if outcome.final is not None else None,
        offers_asked=tuple(dict.fromkeys(offer.offer_id for offer in asked if offer is not None)),
        notes=_notes(request, uses, outcome),
    )
