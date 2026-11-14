"""A variant a buyer did not ask for is a named alternative, never a silent fill (PLAN section 4, decision 6).

A request for plain "milk" is answered with regular milk first. A lactose-free or low-lactose milk answers it only
when regular milk cannot, and the option then names it. The choice is ours: Valio Aimo left it to us on 14 Nov 2026
("what do you think makes the most sense for normal company?"). A line that requires the claim, names a product by
id or names lactose in a name term asked for the variant: nothing here applies to it.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping

from tta.contracts.request import RequestLine

# Product type → nutritional claim → the word a sentence uses for a product that carries it.
VARIANT_CLAIMS: Mapping[str, Mapping[str, str]] = {
    "milk": {"FREE_FROM_LACTOSE": "lactose-free", "LOW_LACTOSE": "low-lactose"},
}
REGULAR_WORDS: Mapping[str, str] = {"milk": "regular milk"}
# A name term that asks for the variant in words, in English or Finnish ("laktoositon").
VARIANT_NAME_STEMS = ("lactos", "laktoos")


def variant_claims_for(asked: RequestLine) -> Mapping[str, str]:
    """The claims that mark a variant for this request line; empty when the line asked for the variant itself."""
    claims = VARIANT_CLAIMS.get(asked.product_type or "", {})
    if not claims or asked.product_ids:
        return {}
    required = {claim.strip().upper() for claim in asked.required_claims}
    if required & claims.keys():
        return {}
    if any(stem in term.lower() for term in asked.name_terms for stem in VARIANT_NAME_STEMS):
        return {}
    return claims


def variant_word(asked: RequestLine, nutritional_claims: Collection[str]) -> str | None:
    """`lactose-free` for a lactose-free milk on a line that asked for plain milk; `None` for a regular product."""
    return next((word for claim, word in variant_claims_for(asked).items() if claim in nutritional_claims), None)


def regular_words(asked: RequestLine) -> str:
    return REGULAR_WORDS.get(asked.product_type or "", "the regular product")
