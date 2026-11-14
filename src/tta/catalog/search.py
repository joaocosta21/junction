"""Catalog search (SPEC section 3, steps 1 to 4). It returns candidates; others judge them.

Every filter given must hold: product type, explicit ids, category prefix, claims, name terms.
A product type is its categories, its claims, its name terms and its exclude terms: a product whose
name has an exclude term is not of the type ("milk" leaves out sour milk).
A name term may be in the English or in the Finnish name (`tta.catalog.text`). With name terms and
nothing that fixes the categories, the result keeps the categories that hold most of the matches.
Order: products whose English name has every term first, then those found through the Finnish
name; by id within each.

Why not "Finnish only when English finds nothing": English names keep Finnish words here and there,
so "maito" (milk) starts a word in 2 English names, both chocolate bars, and is in 233 Finnish names.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from tta.catalog.product_types import ProductType
from tta.catalog.text import ProductNames, names_of, normalise
from tta.contracts.errors import InvalidRequest
from tta.contracts.product import Product, SearchResult
from tta.contracts.request import ProductQuery

# Fallback of SPEC section 3, step 3: a category is kept when it holds at least this share of the
# matches of the largest category. Our threshold.
NARROW_SHARE_OF_LARGEST = Decimal("0.5")


@dataclass(frozen=True, slots=True)
class SearchIndex:
    """What a search reads: the products that are not deleted, in id order, and their names for matching."""

    products: tuple[Product, ...]
    names: Mapping[str, ProductNames]
    claim_codes: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Term:
    text: str  # as the caller wrote it
    key: str  # normalised for matching


def build_index(products: Iterable[Product]) -> SearchIndex:
    active = tuple(sorted((product for product in products if not product.deleted), key=lambda p: p.id))
    return SearchIndex(
        products=active,
        names={product.id: names_of(product) for product in active},
        claim_codes=frozenset(claim for product in active for claim in product.nutritional_claims),
    )


def search(index: SearchIndex, product_types: Mapping[str, ProductType], query: ProductQuery) -> SearchResult:
    terms = _terms(query.name_terms)
    claims = _unique(claim.strip().upper() for claim in query.required_claims)
    prefix = (query.category_prefix or "").strip()
    product_type = _product_type(product_types, query.product_type)
    if not (product_type or query.product_ids or prefix or claims or terms):
        raise InvalidRequest(
            "A search needs at least one of product_type, product_ids, name_terms, required_claims or category_prefix."
        )
    notes = [*_unknown_id_notes(index, query.product_ids), *_unknown_claim_notes(index, claims)]
    scope = _scope(index, product_type, query.product_ids, prefix, claims)
    if not scope or not terms:
        return _result(scope, query.limit, notes)
    unmatched = tuple(term.text for term in terms if not any(index.names[p.id].has(term.key) for p in scope))
    if unmatched:
        return _unmatched_result(unmatched, len(scope), len(index.products), notes)
    matches = [product for product in scope if all(index.names[product.id].has(term.key) for term in terms)]
    if not matches:
        together = ", ".join(f"'{term.text}'" for term in terms)
        not_together = f"Each term is in some name, but no name has them together: {together}."
        return _result(matches, query.limit, [not_together, *notes])
    if product_type is None and not query.product_ids and not prefix:
        matches, narrowing_note = _narrow_to_main_categories(matches)
        notes = [*narrowing_note, *notes]
    return _result(_english_matches_first(index, matches, terms), query.limit, notes)


def _product_type(product_types: Mapping[str, ProductType], key: str | None) -> ProductType | None:
    if key is None or not key.strip():
        return None
    product_type = product_types.get(key.strip())
    if product_type is None:
        known = ", ".join(sorted(product_types))
        raise InvalidRequest(f"Unknown product type '{key}'. The product types are: {known}.", product_type=key)
    return product_type


def _terms(raw_terms: Iterable[str]) -> tuple[_Term, ...]:
    """Blank terms are dropped; a term given twice counts once."""
    first_text_by_key: dict[str, str] = {}
    for text in raw_terms:
        first_text_by_key.setdefault(normalise(text), text.strip())
    return tuple(_Term(text=text, key=key) for key, text in first_text_by_key.items() if key)


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _scope(
    index: SearchIndex, product_type: ProductType | None, product_ids: Sequence[str], prefix: str,
    claims: Sequence[str],
) -> list[Product]:
    """The products that pass every filter except the name terms of the query."""
    wanted_ids = frozenset(product_ids)
    type_claims = product_type.claims if product_type else ()
    type_terms = tuple(normalise(term) for term in product_type.name_terms) if product_type else ()
    type_excluded = tuple(normalise(term) for term in product_type.exclude_terms) if product_type else ()
    required = frozenset((*claims, *type_claims))
    return [
        product
        for product in index.products
        if (not wanted_ids or product.id in wanted_ids)
        and (product_type is None or product.category in product_type.categories)
        and product.category.startswith(prefix)
        and required.issubset(product.nutritional_claims)
        and (not type_terms or index.names[product.id].has_any(type_terms))
        and not index.names[product.id].has_any(type_excluded)
    ]


def _english_matches_first(index: SearchIndex, matches: Sequence[Product], terms: Sequence[_Term]) -> list[Product]:
    """English first, then Finnish. `matches` is in id order and both groups keep it."""
    in_english = [p for p in matches if all(index.names[p.id].english_word_starts_with(term.key) for term in terms)]
    in_english_ids = {product.id for product in in_english}
    return [*in_english, *(product for product in matches if product.id not in in_english_ids)]


def _narrow_to_main_categories(matches: Sequence[Product]) -> tuple[list[Product], list[str]]:
    """Keep the largest category and every category with at least half as many matches."""
    counts = Counter(product.category for product in matches)
    largest = max(counts.values())
    kept = [category for category, count in _by_count(counts) if count >= largest * NARROW_SHARE_OF_LARGEST]
    if len(kept) == len(counts):
        return list(matches), []
    narrowed = [product for product in matches if product.category in kept]
    others = len(counts) - len(kept)
    note = (
        f"No product type or category was given, so the search kept {_categories_phrase(kept)}, "
        f"which {'holds' if len(kept) == 1 else 'hold'} {len(narrowed)} of the {len(matches)} products whose name "
        f"matches; {len(matches) - len(narrowed)} in {others} other {'category' if others == 1 else 'categories'} "
        "were left out."
    )
    return narrowed, [note]


def _by_count(counts: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _categories_phrase(categories: Sequence[str]) -> str:
    return f"category {categories[0]}" if len(categories) == 1 else f"categories {', '.join(categories)}"


def _unknown_id_notes(index: SearchIndex, product_ids: Sequence[str]) -> list[str]:
    unknown = [product_id for product_id in _unique(product_ids) if product_id not in index.names]
    return [f"Not in the catalog: {', '.join(unknown)}."] if unknown else []


def _unknown_claim_notes(index: SearchIndex, claims: Sequence[str]) -> list[str]:
    unknown = [claim for claim in claims if claim not in index.claim_codes]
    if not unknown:
        return []
    return [
        f"No product carries the claim {', '.join(unknown)}. "
        f"The claim codes in the catalog are: {', '.join(sorted(index.claim_codes))}."
    ]


def _unmatched_result(unmatched: tuple[str, ...], in_scope: int, in_catalog: int, notes: Sequence[str]) -> SearchResult:
    quoted = ", ".join(f"'{term}'" for term in unmatched)
    where = "in the catalog" if in_scope == in_catalog else f"among the {in_scope} products that pass the other filters"
    sentence = f"No product matches: no product name {where} contains {quoted}."
    return SearchResult(unmatched_terms=unmatched, note=" ".join([sentence, *notes]))


def _result(matches: Sequence[Product], limit: int, notes: Sequence[str]) -> SearchResult:
    total = len(matches)
    if total == 0:
        count = "No product matches."
    elif total > limit:
        count = f"Showing the first {limit} of {total} products that match."
    else:
        count = "1 product matches." if total == 1 else f"{total} products match."
    categories = tuple(category for category, _ in _by_count(Counter(product.category for product in matches)))
    return SearchResult(
        products=tuple(matches[:limit]), total=total, categories=categories, note=" ".join([count, *notes])
    )
