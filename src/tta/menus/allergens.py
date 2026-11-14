"""What a recipe stand-in declares about allergens, next to the recipe's own product type (review A2a, finding M-2).

A product substitute may never add an allergen (`tta.allergens.substitution`, Valio Aimo's answer B6). A recipe
stand-in is another product type, chosen by its job in the dish, so the same comparison is made here and said in
the plan: a person approves a stand-in (rule F-09) and must read what it brings into the dish. Nothing here blocks
or decides.

Compared code by code, as the substitution rule does. "The recipe's type declares a code" means every product of
that type does: a guest safe with the dish as written is then safe with that code. When the catalog search does
not return every product of the type, nothing is compared and every declared code is named.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tta.allergens.codes import GENERAL_STATEMENT_CODE, describe
from tta.contracts.common import AllergenRelation, Identity
from tta.contracts.offer import Offer
from tta.contracts.ports import GatewayService
from tta.contracts.product import Product
from tta.contracts.request import ProductQuery
from tta.menus.recipes import Choice
from tta.menus.wording import choice_words, joined

# X99 is GS1's "does not contain declaration obligatory allergens": it names no allergen (AIMO/docs, allergens).
DECLARING = (AllergenRelation.CONTAINS, AllergenRelation.MAY_CONTAIN)
NO_STATEMENT = (
    "Allergens: {product} makes no allergen statement in Valio Aimo's data, which is unknown, not safe: check "
    "the dish against the guests' allergies."
)
DECLARES = "Allergens: {product} declares {codes}"
ADDS = " The recipe's {recipe} does not declare {them}: check the dish against the guests' allergies."
SAME = ", as the recipe's {recipe} does."
NOT_COMPARED = (
    ". They were not compared with the recipe's {recipe}: check the dish against the guests' allergies."
)
DECLARES_NOTHING = "Allergens: {product} declares no allergen."


@dataclass(frozen=True)
class StandInAllergens:
    """One stand-in product: what it declares, and which of it the recipe's own type does not."""

    product_id: str
    name: str
    declared: tuple[str, ...]  # GS1 codes with CONTAINS or MAY_CONTAIN, in code order
    added: tuple[str, ...] | None  # the declared codes the recipe's type does not declare; None: not compared
    has_statement: bool
    sentence: str


def declared_codes(product: Product) -> frozenset[str]:
    return frozenset(
        statement.code for statement in product.allergen_statements
        if statement.relation in DECLARING and statement.code != GENERAL_STATEMENT_CODE
    )


def _recipe_declares(service: GatewayService, identity: Identity, recipe: Choice) -> frozenset[str] | None:
    """The codes every product of the recipe's type declares; None when the search does not return them all."""
    found = service.search_products(
        identity, ProductQuery(product_type=recipe.product_type, name_terms=recipe.name_terms)
    )
    if not found.products or found.total > len(found.products):
        return None
    return frozenset.intersection(*(declared_codes(product) for product in found.products))


def _sentence(
    label: str, product: Product, declared: Sequence[str], added: Sequence[str] | None, recipe: Choice
) -> str:
    if not product.has_allergen_statement:
        return NO_STATEMENT.format(product=label)
    if not declared:
        return DECLARES_NOTHING.format(product=label)
    start = DECLARES.format(product=label, codes=joined([describe(code) for code in declared]))
    words = choice_words(recipe)
    if added is None:
        return start + NOT_COMPARED.format(recipe=words)
    if not added:
        return start + SAME.format(recipe=words)
    if len(added) == len(declared):
        return f"{start}.{ADDS.format(recipe=words, them='them' if len(added) > 1 else 'it')}"
    return f"{start}.{ADDS.format(recipe=words, them=joined([describe(code) for code in added]))}"


def stand_in_allergens(
    service: GatewayService, identity: Identity, final: Offer, line_index: int, recipe: Choice
) -> tuple[StandInAllergens, ...]:
    """For each product the final offer's top option holds on this line. Raises what `get_product` and
    `search_products` raise."""
    if not final.options:
        return ()
    names = {
        line.product_id: line.name for line in final.options[0].lines if line.request_line_index == line_index
    }
    if not names:
        return ()
    usual = _recipe_declares(service, identity, recipe)
    found = []
    for product_id, name in names.items():
        product = service.get_product(identity, product_id)
        declared = tuple(sorted(declared_codes(product)))
        added = None if usual is None else tuple(code for code in declared if code not in usual)
        found.append(StandInAllergens(
            product_id=product_id, name=name, declared=declared, added=added,
            has_statement=product.has_allergen_statement,
            sentence=_sentence(f"{name} ({product_id})", product, declared, added, recipe),
        ))
    return tuple(found)
